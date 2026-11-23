"""Reproducible full-copy migration acceptance (SQLite by default).

Credentials are read from process environment only. No app services start and
the supplied data copy remains read-only. MySQL reset requires explicit flags
and a verified backup outside the source directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from business_storage import StoragePolicy
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore
from storage_migration import build_plan, import_documents, verify_documents, export_documents


def inventory(root):
    digest, count, size = hashlib.sha256(), 0, 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Source copy must not contain symlinks')
        if not path.is_file():
            continue
        before = path.stat()
        with path.open('rb') as handle:
            checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Source changed during inventory')
        item = [path.relative_to(root).as_posix(), before.st_size, before.st_mtime_ns, checksum]
        digest.update(json.dumps(item, ensure_ascii=False).encode('utf-8'))
        count += 1
        size += before.st_size
    return {'files': count, 'bytes': size, 'manifest_sha256': digest.hexdigest()}


def mysql_factory(settings, environ):
    import pymysql
    pin = environ.get('MYSQL_SSL_CERT_SHA256', '').lower().replace(':', '')
    if pin:
        if len(pin) != 64 or any(char not in '0123456789abcdef' for char in pin):
            raise ValueError('Invalid MYSQL_SSL_CERT_SHA256')
        class PinnedContext(ssl.SSLContext):
            def wrap_socket(self, *args, **kwargs):
                sock = super().wrap_socket(*args, **kwargs)
                if hashlib.sha256(sock.getpeercert(binary_form=True)).hexdigest() != pin:
                    sock.close()
                    raise ssl.SSLError('MySQL TLS certificate fingerprint mismatch')
                return sock
        context = PinnedContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = ssl.create_default_context(cafile=settings.ssl_ca)
    def connect():
        return pymysql.connect(host=settings.host, port=settings.port, user=settings.user,
            password=settings.password, database=settings.database, charset='utf8mb4',
            connect_timeout=settings.connect_timeout, read_timeout=settings.read_timeout,
            write_timeout=settings.write_timeout, ssl=context)
    return connect


def run_test(source, settings, *, reset=False, backup_dir=None, connection_factory=None):
    source = Path(source).resolve(strict=True)
    if settings.backend == 'sqlite':
        target = Path(settings.sqlite_path).resolve()
        if target == source or source in target.parents:
            raise ValueError('SQLite target must be outside the read-only source copy')
    from persistence.schema import make_schema
    make_schema(settings.table_prefix)
    before = inventory(source)
    policy = StoragePolicy(source)
    plan = build_plan(policy)
    report = {'format': 1, 'backend': settings.backend, 'schema_version': 2,
        'started_at': datetime.now(timezone.utc).isoformat(), 'source_before': before,
        'documents': len(plan.entries), 'bytes': plan.total_bytes,
        'by_namespace': dict(Counter(entry.namespace for entry in plan.entries))}
    if reset:
        if settings.backend != 'mysql' or not connection_factory or not backup_dir:
            raise ValueError('Reset requires MySQL, connection factory and backup directory')
        backup_dir = Path(backup_dir).resolve()
        if backup_dir == source or source in backup_dir.parents:
            raise ValueError('Backup must be outside the read-only source copy')
        # Full relational/uniqueness/semantic acceptance must precede any
        # destructive operation. SQLite also catches source defects that a
        # syntax-only scan cannot detect.
        with TemporaryDirectory(prefix='storage-preflight-') as folder:
            preflight = RelationalStore(DatabaseSettings(root=Path(folder), table_prefix=settings.table_prefix))
            try:
                preflight.init_schema()
                checked = import_documents(policy, preflight)
                if not checked.verification.ok or not checked.verification.expected:
                    raise ValueError('Empty or invalid source; reset refused')
            finally:
                preflight.database.dispose()
        if before != inventory(source):
            raise ValueError('Source changed after preflight; reset refused')
        from persistence.mysql_backup import backup_database, reset_database
        connection = connection_factory()
        try:
            backup = backup_database(connection, backup_dir, settings.database)
            report['backup'] = str(backup)
            report['reset'] = reset_database(connection, backup, settings.database)
        finally:
            connection.close()
    store = RelationalStore(settings, connection_factory)
    try:
        store.init_schema()
        result = import_documents(policy, store)
        report['import'] = asdict(result)
        report['idempotent'] = asdict(import_documents(policy, store))
        report['verification'] = asdict(verify_documents(policy, store))
        if not report['verification']['expected'] or not result.verification.ok:
            raise ValueError('Migration verification failed or source was empty')
        from sqlalchemy import func, select
        with store.database.connection() as connection:
            report['entity_counts'] = {name: connection.execute(select(func.count()).select_from(table)).scalar_one()
                for name, table in store.entities.items()}
        with TemporaryDirectory(prefix='storage-roundtrip-') as folder:
            folder = Path(folder)
            exported = folder / 'export'
            report['export'] = asdict(export_documents(policy, store, exported))
            roundtrip = RelationalStore(DatabaseSettings(root=folder / 'roundtrip'))
            try:
                roundtrip.init_schema()
                report['roundtrip'] = asdict(import_documents(StoragePolicy(exported), roundtrip))
            finally:
                roundtrip.database.dispose()
        report['ready'] = store.check_ready()
    finally:
        store.database.dispose()
    after = inventory(source)
    report['source_after'] = after
    if before != after:
        raise ValueError('Source copy changed during migration test')
    report['source_unchanged'] = True
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--backend', choices=('sqlite', 'mysql'), default='sqlite')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--reset-target', action='store_true')
    parser.add_argument('--stopped', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args(argv)
    if args.reset_target and not args.stopped:
        parser.error('--reset-target requires --stopped')
    report_path = args.report.resolve()
    source = args.source_root.resolve()
    if report_path.exists() or report_path == source or source in report_path.parents:
        parser.error('Report must be a new path outside the source copy')
    environment = dict(os.environ, APP_STORAGE_BACKEND=args.backend)
    try:
        with TemporaryDirectory(prefix='storage-acceptance-') as folder:
            settings = DatabaseSettings.from_env(environment, root=Path(folder))
            factory = mysql_factory(settings, environment) if args.backend == 'mysql' else None
            report = run_test(source, settings, reset=args.reset_target, backup_dir=args.backup_dir, connection_factory=factory)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open('x', encoding='utf-8') as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps({'ok': True, 'documents': report['documents'], 'source_unchanged': True, 'ready': report['ready']}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__, 'message': 'Migration test failed; source is read-only; inspect locally without publishing credentials.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
