"""Explicit offline migration from approved files and legacy databases.

This module never imports main or installs filesystem hooks. Sources remain
read-only unless verified business-file removal or old-table removal is explicitly
selected. Log files are always retained.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath


class MigrationError(RuntimeError):
    """A migration cannot safely continue. Messages never contain record bodies."""


class VerificationError(MigrationError):
    pass


_CORRUPT_SOURCE_ERRORS = (ValueError, KeyError, TypeError, IndexError, AttributeError,
                          UnicodeError, configparser.Error, MigrationError)


@dataclass(frozen=True)
class SourceEntry:
    namespace: str
    key: str
    path: Path
    content: bytes
    mtime_ns: int
    digest: str


@dataclass(frozen=True)
class MigrationPlan:
    entries: tuple[SourceEntry, ...]
    skipped_empty: tuple[tuple[str, str], ...] = ()
    skipped_corrupt: tuple[tuple[str, str], ...] = ()

    @property
    def total_bytes(self):
        return sum(len(entry.content) for entry in self.entries)


@dataclass(frozen=True)
class VerificationReport:
    expected: int
    actual: int
    missing: tuple[tuple[str, str], ...] = ()
    different: tuple[tuple[str, str], ...] = ()
    extra: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self):
        return not (self.missing or self.different or self.extra)


@dataclass(frozen=True)
class ImportResult:
    imported: int
    unchanged: int
    skipped_conflict: int
    skipped_empty: int
    verification: VerificationReport
    issues: tuple = ()


@dataclass(frozen=True)
class ExportResult:
    exported: int
    total_bytes: int


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _reject_json_constant(_value):
    raise ValueError("nonfinite JSON number")


def _validate_content(key, content):
    try:
        text = content.decode("utf-8-sig")
        if key.lower().endswith(".json"):
            json.loads(text, parse_constant=_reject_json_constant)
        elif key.lower().endswith(".ini"):
            parser = configparser.RawConfigParser(strict=False)
            parser.read_string(text)
            if not parser.sections():
                raise ValueError("INI without sections")
    except (UnicodeError, ValueError, configparser.Error) as exc:
        raise MigrationError(f"源文件格式无效：{key}（{type(exc).__name__}）") from None


def build_plan(policy, *, skip_empty=False):
    """Validate the entire allowlisted source before opening a database."""
    entries, skipped, seen = [], [], set()
    for original_path in policy.iter_files():
        path = Path(original_path)
        identity = policy.identify(path)
        if identity is None:
            raise MigrationError("存储策略返回了范围外的源文件")
        namespace, key = identity
        if identity in seen:
            raise MigrationError(f"源文件标识重复：{namespace}/{key}")
        seen.add(identity)
        if path.is_symlink():
            raise MigrationError(f"拒绝迁移符号链接：{namespace}/{key}")
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise MigrationError(f"读取过程中源文件发生变化：{namespace}/{key}；请先停止应用")
        if not content.strip() and path.suffix.lower() != '.txt':
            if skip_empty:
                skipped.append(identity)
                continue
            raise MigrationError(f"源文件为空：{namespace}/{key}；修复源文件或显式使用 --skip-empty")
        _validate_content(key, content)
        entries.append(SourceEntry(namespace, key, path, content, after.st_mtime_ns, _digest(content)))
    sms_path = _legacy_sms_path(policy)
    if sms_path.is_file():
        from sms_history import iter_legacy_sms_records
        if sms_path.is_symlink():
            raise MigrationError('拒绝迁移符号链接短信历史')
        before = sms_path.stat()
        try:
            for key, content, mtime_ns in iter_legacy_sms_records(sms_path):
                identity = 'sms_records', key
                if identity in seen:
                    raise MigrationError('短信历史记录标识重复')
                seen.add(identity)
                entries.append(SourceEntry(*identity, sms_path, content, mtime_ns, _digest(content)))
        except (ValueError, UnicodeError) as exc:
            raise MigrationError(f'短信历史格式无效（{type(exc).__name__}）；请修复原日志后重试') from None
        after = sms_path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise MigrationError('读取过程中短信历史发生变化；请先停止应用')
    return MigrationPlan(tuple(sorted(entries, key=lambda item: (item.namespace, item.key))), tuple(sorted(skipped)))


def _legacy_sms_path(policy):
    """Locate the append-only log without importing the application runtime."""
    configured_path = getattr(policy, 'sms_history_path', None)
    if configured_path is not None:
        return Path(configured_path).absolute()
    root = Path(policy.root).resolve()
    log_dir = 'logs'
    configs = getattr(policy, 'roots', {}).get('configs')
    config_path = Path(configs) / 'config.json' if configs is not None else None
    if config_path is not None and config_path.is_file():
        try:
            config = json.loads(config_path.read_bytes().decode('utf-8-sig'))
            logging_config = config.get('Logging', {})
            if isinstance(logging_config, dict):
                log_dir = logging_config.get('log_dir', log_dir)
        except (ValueError, UnicodeError, AttributeError, TypeError):
            raise MigrationError('源目录配置无效，无法确定短信日志位置') from None
    return (root / str(log_dir) / 'sms_history.jsonl').absolute()


def _database_documents(store):
    records = {}
    for namespace in store.namespaces():
        for document in store.list(namespace):
            identity = (document.namespace, document.key)
            if identity in records:
                raise MigrationError("数据库返回了重复文档标识")
            records[identity] = document
    return records


def _equivalent(entry, document, store):
    if _digest(document.content) != document.digest:
        return False
    if not getattr(store, 'normalized', False):
        return _digest(document.content) == entry.digest
    from persistence.store import parse_content
    expected = parse_content(entry.key, entry.content)
    actual = parse_content(document.key, document.content)
    # Canonical serialization distinguishes true/1, null/missing and strings.
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return (canonical(expected) == canonical(actual)
            and document.source_sha256 == entry.digest)


def _verify_plan(plan, store):
    expected = {(entry.namespace, entry.key): entry for entry in plan.entries}
    actual = _database_documents(store)
    missing = tuple(sorted(expected.keys() - actual.keys()))
    extra = tuple(sorted(actual.keys() - expected.keys()))
    different = tuple(sorted(
        identity for identity in expected.keys() & actual.keys()
        if not _equivalent(expected[identity], actual[identity], store)
    ))
    return VerificationReport(len(expected), len(actual), missing, different, extra)


def verify_documents(policy, store, *, skip_empty=False):
    """Compare every managed source with every stored document by SHA256."""
    return _verify_plan(build_plan(policy, skip_empty=skip_empty), store)


def import_documents(policy, store, *, conflict="error", batch_size=100, skip_empty=False, remove_source=False):
    """Import in verified batches; optional removal never includes log files."""
    plan = build_plan(policy, skip_empty=skip_empty)
    result = _import_with_aliases(plan, store, lambda: build_plan(policy, skip_empty=skip_empty),
                                  conflict=conflict, batch_size=batch_size)
    if remove_source:
        remove_source_files(policy, store, plan, skip_empty=skip_empty)
    return result


def _same_plan(original, fresh):
    signature = lambda plan: {(item.namespace, item.key): (item.digest, item.mtime_ns)
                              for item in plan.entries}
    return (signature(original) == signature(fresh)
            and original.skipped_empty == fresh.skipped_empty
            and original.skipped_corrupt == fresh.skipped_corrupt)


def remove_source_files(policy, store, plan=None, *, skip_empty=False):
    """Delete only verified in-root business files, without creating backups."""
    store.check_ready()
    plan = build_plan(policy, skip_empty=skip_empty) if plan is None else plan
    root = Path(policy.root).resolve()
    prepared = []
    for entry in plan.entries:
        # SMS history is an immutable migration input that remains a log file.
        if entry.namespace == 'sms_records' and Path(entry.path).absolute() == _legacy_sms_path(policy):
            continue
        path = Path(entry.path).absolute()
        try:
            path.resolve().relative_to(root)
        except (ValueError, OSError, RuntimeError):
            raise MigrationError('拒绝清理 root 之外的源文件') from None
        if path == root or any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
            raise MigrationError('拒绝清理符号链接源文件或目录')
        if policy.identify(path) != (entry.namespace, entry.key):
            raise MigrationError('源文件已不属于受管业务范围，拒绝清理')
        prepared.append((path, entry))
    fresh = build_plan(policy, skip_empty=skip_empty)
    if not _same_plan(plan, fresh):
        raise VerificationError('清理前源文件发生变化；没有删除源文件')
    if not _verify_plan(fresh, store).ok:
        raise VerificationError('清理前完整数据库校验失败；没有删除源文件')
    # Validate the entire deletion set before removing its first member.
    for path, entry in prepared:
        if path.is_symlink() or path.stat().st_mtime_ns != entry.mtime_ns or _digest(path.read_bytes()) != entry.digest:
            raise VerificationError('清理前源文件发生变化；没有删除源文件')
    for path, _entry in prepared:
        path.unlink()
    return len(prepared)


def _import_with_aliases(plan, store, reload_source, **options):
    if not getattr(store, 'normalized', False):
        return _import_plan(plan, store, reload_source, **options)
    from persistence.validation import build_owner_aliases
    previous = getattr(store, 'migration_owner_aliases', {})
    store.migration_owner_aliases = build_owner_aliases(plan.entries)
    try:
        return _import_plan(plan, store, reload_source, **options)
    finally:
        store.migration_owner_aliases = previous


def _import_plan(plan, store, reload_source, *, conflict='error', batch_size=100):
    if conflict not in {"error", "skip", "overwrite"}:
        raise MigrationError("未知冲突策略")
    if not isinstance(batch_size, int) or batch_size < 1:
        raise MigrationError("batch_size 必须为正整数")
    issues = ()
    if getattr(store, 'normalized', False):
        # Encode all records before the first destination mutation. Malformed
        # historical values must not create a half-converted domain model.
        for entry in plan.entries:
            try:
                store._encode(entry.namespace, entry.key, store._identity(entry.namespace, entry.key), entry.content)
            except Exception as exc:
                raise MigrationError(f'Domain preflight failed: {entry.namespace}/{entry.key} ({type(exc).__name__})') from None
        from persistence.validation import validate_entries
        issues = tuple(validate_entries(plan.entries))
        if any(issue['severity'] == 'error' for issue in issues):
            raise MigrationError('Source identity validation failed; inspect the read-only preflight report')
    pending, unchanged, skipped = [], 0, 0
    current_documents = _database_documents(store)
    for entry in plan.entries:
        existing = current_documents.get((entry.namespace, entry.key))
        if existing is not None and _equivalent(entry, existing, store):
            unchanged += 1
            continue
        if existing is not None and conflict == "error":
            raise MigrationError(f"目标文档内容冲突：{entry.namespace}/{entry.key}；未开始本轮写入")
        if existing is not None and conflict == "skip":
            skipped += 1
            continue
        pending.append((entry, existing.revision if existing is not None else None))
    store.mark_pending()
    imported = 0
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        with store.transaction():
            if hasattr(store, 'create_many') and all(revision is None for _, revision in batch):
                store.create_many([entry for entry, _ in batch])
            else:
                for entry, revision in batch:
                    options = {"mtime_ns": entry.mtime_ns}
                    if getattr(store, 'normalized', False):
                        options['source_sha256'] = entry.digest
                    if revision is None:
                        options["create_only"] = True
                    else:
                        options["expected_revision"] = revision
                    store.put(entry.namespace, entry.key, entry.content, **options)
        imported += len(batch)
    fresh_plan = reload_source()
    if not _same_plan(plan, fresh_plan):
        raise VerificationError("迁移过程中源数据发生变化；未标记就绪，请停止应用后重试")
    with store.transaction():
        verification = _verify_plan(fresh_plan, store)
        if not verification.ok:
            raise VerificationError(
                f"导入后校验失败：缺失 {len(verification.missing)}，不同 {len(verification.different)}，多余 {len(verification.extra)}；未标记就绪"
            )
        store.mark_ready()
    return ImportResult(imported, unchanged, skipped, len(plan.skipped_empty), verification, issues)


def _legacy_plan(source):
    source.check_ready()
    entries = []
    for document in _database_documents(source).values():
        if document.digest != _digest(document.content):
            raise VerificationError('Legacy source checksum mismatch')
        _validate_content(document.key, document.content)
        entries.append(SourceEntry(document.namespace, document.key,
            Path(document.namespace) / document.key, document.content, document.mtime_ns, document.digest))
    return MigrationPlan(tuple(sorted(entries, key=lambda entry: (entry.namespace, entry.key))))


def import_legacy_store(source, target, *, conflict='error', batch_size=100):
    """Read schema-v1 documents without updating or marking the source store."""
    plan = _legacy_plan(source)
    return _import_with_aliases(plan, target, lambda: _legacy_plan(source), conflict=conflict, batch_size=batch_size)


def verify_legacy_store(source, target):
    return _verify_plan(_legacy_plan(source), target)


def _relational_plan(source, *, skip_corrupt_sessions=False):
    """Read current typed v2 values; its last-write digest is not authority."""
    from sqlalchemy import select
    from persistence.codec import decode_tree
    from persistence.store import parse_content, render_content

    def ordered(value):
        if isinstance(value, dict):
            return {key: ordered(value[key]) for key in sorted(value)}
        if isinstance(value, list):
            return [ordered(item) for item in value]
        return value

    source.check_ready()
    entries, skipped = [], []
    def append_document(namespace, key, document, content):
        entries.append(SourceEntry(namespace, key, Path(namespace) / key,
            content, document.mtime_ns, _digest(content)))

    # Lightweight test doubles and v1 adapters do not expose the relational
    # connection/schema; retain their document API. Real v2 stores use the
    # single-connection branch below so a skipped decode error cannot poison a
    # transaction.
    if not hasattr(source, 'database'):
        for namespace in source.namespaces():
            for key in source.keys(namespace):
                try:
                    document = source.get(namespace, key)
                    if document is None:
                        raise MigrationError('旧版记录在读取过程中消失')
                    _validate_content(key, document.content)
                    format, value = parse_content(key, document.content)
                    append_document(namespace, key, document, render_content(format, ordered(value)))
                except _CORRUPT_SOURCE_ERRORS as exc:
                    if skip_corrupt_sessions and namespace == 'sessions' and PurePosixPath(key).name != '_index.json':
                        skipped.append((namespace, key))
                        continue
                    raise MigrationError(f'旧版记录无法读取：{namespace}/{key}（{type(exc).__name__}）') from None
    else:
        with source.transaction():
            # Read and decode through one connection. Calling source.get() from
            # a nested store transaction marks it rollback-only when a corrupt
            # record raises, even if this loop deliberately skips that session.
            with source.database.connection() as connection:
                records = list(connection.execute(select(source.registry).order_by(
                    source.registry.c.namespace, source.registry.c.record_key)).mappings())
                document_ids = [row['document_id'] for row in records]
                entity_tables = sorted({name for row in records for name in row['entity_tables']})
                grouped = {document_id: {} for document_id in document_ids}
                for name in entity_tables:
                    table = source.entities.get(name)
                    if table is None:
                        raise MigrationError('旧版文档引用了未知实体表')
                    for offset in range(0, len(document_ids), 400):
                        batch = document_ids[offset:offset + 400]
                        if not batch:
                            continue
                        for entity in connection.execute(select(table).where(
                                table.c.document_id.in_(batch))).mappings():
                            grouped[entity['document_id']].setdefault(name, []).append(dict(entity))

                for row in records:
                    namespace, key = row['namespace'], row['record_key']
                    try:
                        value = decode_tree(row['layout'], grouped[row['document_id']])
                        raw_content = render_content(row['format'], value)
                        _validate_content(key, raw_content)
                        format, value = parse_content(key, raw_content)
                        content = render_content(format, ordered(value))
                    except _CORRUPT_SOURCE_ERRORS as exc:
                        if skip_corrupt_sessions and namespace == 'sessions' and PurePosixPath(key).name != '_index.json':
                            skipped.append((namespace, key))
                            continue
                        raise MigrationError(f'旧版记录无法读取：{namespace}/{key}（{type(exc).__name__}）') from None
                    entries.append(SourceEntry(namespace, key, Path(namespace) / key,
                        content, row['mtime_ns'], _digest(content)))
    return MigrationPlan(tuple(sorted(entries, key=lambda entry: (entry.namespace, entry.key))),
                         skipped_corrupt=tuple(sorted(skipped)))


def import_relational_store(source, target, *, conflict='error', batch_size=100, skip_corrupt_sessions=False):
    """Upgrade v2 without modifying the old schema or reconstructing identities."""
    plan = _relational_plan(source, skip_corrupt_sessions=skip_corrupt_sessions)
    result = _import_with_aliases(plan, target,
        lambda: _relational_plan(source, skip_corrupt_sessions=skip_corrupt_sessions),
        conflict=conflict, batch_size=batch_size)
    issues = tuple({'severity': 'warning', 'code': 'skipped_corrupt_session', 'namespace': ns, 'key': key}
                   for ns, key in plan.skipped_corrupt)
    return replace(result, issues=result.issues + issues)


def verify_relational_store(source, target, *, skip_corrupt_sessions=False):
    return _verify_plan(_relational_plan(source, skip_corrupt_sessions=skip_corrupt_sessions), target)


def _same_database(source, target):
    left, right = source.settings, target.settings
    if left.backend != right.backend:
        return False
    if left.backend == 'sqlite':
        if str(left.sqlite_path) == ':memory:' or str(right.sqlite_path) == ':memory:':
            return source.database.engine is target.database.engine
        return left.sqlite_path.resolve() == right.sqlite_path.resolve()
    return (left.host.casefold(), left.port, left.database) == (right.host.casefold(), right.port, right.database)


def _assert_disjoint_schemas(source, target):
    source_tables = (set(source.metadata.tables) if hasattr(source, 'metadata')
                     else {source._documents, source._metadata})
    if _same_database(source, target) and source_tables & set(target.metadata.tables):
        raise MigrationError('源和目标数据库表名重叠；请使用不同旧前缀或目标数据库')


def drop_legacy_schema(source, target, *, skip_corrupt_sessions=False):
    """Drop only the explicit source metadata after a fresh full verification."""
    _assert_disjoint_schemas(source, target)
    target.check_ready()
    if not verify_relational_store(source, target, skip_corrupt_sessions=skip_corrupt_sessions).ok:
        raise VerificationError('旧版表清理前完整校验失败；没有删除旧表')
    source.metadata.drop_all(source.database.engine)
def _export_relative_path(policy, document):
    namespace, key = document.namespace, document.key
    if not isinstance(namespace, str) or not isinstance(key, str) or not namespace or not key:
        raise MigrationError("数据库文档标识无效")
    if any(character in key for character in ("\\", ":", "\x00")) or key.startswith("/"):
        raise MigrationError("数据库文档键包含不安全路径")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(key).is_absolute():
        raise MigrationError("数据库文档键包含不安全路径")
    try:
        physical = Path(policy.physical_path(namespace, key))
        if policy.identify(physical) != (namespace, key):
            raise ValueError("outside policy")
        relative = physical.resolve().relative_to(Path(policy.root).resolve())
    except (ValueError, KeyError, OSError, RuntimeError):
        raise MigrationError("数据库文档不属于受管目录，或自定义目录位于 root 之外；拒绝导出") from None
    return relative


def export_documents(policy, store, target):
    """Export verified bytes into an exclusively-created directory."""
    if store.check_ready() is False:
        raise MigrationError("数据库尚未完成迁移校验")
    target = Path(target).absolute()
    if target.exists() or target.is_symlink():
        raise MigrationError("导出目录必须为全新路径，不覆盖已有目录")
    with store.transaction():
        documents = list(_database_documents(store).values())
        prepared, paths = [], set()
        for document in sorted(documents, key=lambda item: (item.namespace, item.key)):
            relative = _export_relative_path(policy, document)
            if str(relative).casefold() in paths:
                raise MigrationError("导出路径发生大小写或命名冲突")
            paths.add(str(relative).casefold())
            if _digest(document.content) != document.digest:
                raise VerificationError("数据库文档摘要与正文不符，拒绝导出")
            _validate_content(document.key, document.content)
            prepared.append((relative, document))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    for relative, document in prepared:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(document.content)
        os.utime(destination, ns=(document.mtime_ns, document.mtime_ns))
        if _digest(destination.read_bytes()) != document.digest:
            raise VerificationError("导出后文件摘要校验失败；保留现场，未宣称导出成功")
    return ExportResult(len(prepared), sum(len(item.content) for _, item in prepared))


def _parser():
    parser = argparse.ArgumentParser(description="停止应用后显式迁移结构化业务数据；日志始终保留，清理旧数据必须显式选择。")
    parser.add_argument("--root", type=Path, default=None, help="数据根目录，默认 APP_STORAGE_ROOT 或项目目录")
    parser.add_argument('--backend', choices=('sqlite', 'mysql'), default=None, help='目标数据库，默认进程配置或 SQLite')
    parser.add_argument('--source', choices=('files', 'legacy-mysql', 'relational-v2'), default='files', help='只读源：文件、v1 MySQL 文档或 v2 关系化数据库')
    parser.add_argument('--source-backend', choices=('sqlite', 'mysql'), help='v2 源数据库引擎，默认与目标相同')
    parser.add_argument('--source-sqlite-path', type=Path, help='v2 源 SQLite 文件，相对 root 解析')
    parser.add_argument('--legacy-table-prefix', default='app_', help='旧库表前缀；目标使用无前缀业务表')
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="只验证文件并汇总范围，不连接数据库")
    plan.add_argument("--skip-empty", action="store_true")
    commands.add_parser("init", help="显式建立关系化表，不导入数据，不标记就绪")
    importer = commands.add_parser("import", help="导入并核验，成功后标记就绪")
    importer.add_argument("--stopped", action="store_true", required=True, help="确认应用及所有写入进程已停止")
    importer.add_argument("--conflict", choices=("error", "skip", "overwrite"), default="error")
    importer.add_argument("--batch-size", type=int, default=100)
    importer.add_argument("--skip-empty", action="store_true")
    importer.add_argument('--skip-corrupt-sessions', action='store_true', help='只跳过无法解码的 v2 业务会话，并报告位置')
    importer.add_argument('--drop-legacy', action='store_true', help='v2 完整导入并核验后，仅删除明确选择的旧表')
    importer.add_argument('--remove-source', action='store_true', help='文件完整导入核验后删除受管原文件，不删除短信日志或二进制资源')
    verifier = commands.add_parser("verify", help="核对全部受管记录数量及 SHA256")
    verifier.add_argument("--skip-empty", action="store_true")
    verifier.add_argument('--skip-corrupt-sessions', action='store_true')
    verifier.add_argument('--database-only', action='store_true', help='源文件清理后检查数据库自身完整性，不声称与已删除源文件比对')
    exporter = commands.add_parser("export", help="导出至全新目录，不更改现有文件")
    exporter.add_argument("--output", type=Path, required=True)
    exporter.add_argument("--stopped", action="store_true", required=True)
    return parser


def _policy_from_store(root, store):
    from business_storage import StoragePolicy
    config = store.get('configs', 'config.json')
    if config is None:
        return StoragePolicy(root, {})
    try:
        return StoragePolicy(root, config=json.loads(config.content))
    except (ValueError, UnicodeError, TypeError):
        raise MigrationError('数据库系统配置无效，无法恢复迁移路径') from None


def verify_database(store):
    """Check reconstructed records without claiming comparison to removed files."""
    store.check_ready()
    records = _database_documents(store)
    for document in records.values():
        if _digest(document.content) != document.digest:
            raise VerificationError('数据库记录与保存的摘要不符')
        _validate_content(document.key, document.content)
    return len(records)


def main(argv=None, *, store_factory=None):
    args = _parser().parse_args(argv)
    store = source_store = None
    try:
        from business_storage import StoragePolicy, StorageSettings
        root = Path(args.root or os.environ.get("APP_STORAGE_ROOT") or Path(__file__).resolve().parent).resolve()
        if args.command == 'import':
            if args.remove_source and args.source != 'files':
                raise MigrationError('--remove-source 只适用于文件来源')
            if args.drop_legacy and args.source != 'relational-v2':
                raise MigrationError('--drop-legacy 只适用于 relational-v2 来源')
            if args.skip_corrupt_sessions and args.source != 'relational-v2':
                raise MigrationError('--skip-corrupt-sessions 只适用于 relational-v2 来源')
        if args.command == "plan":
            if args.source != 'files':
                raise MigrationError('plan 仅验证文件来源；数据库来源在 import/verify 中只读验证')
            policy = StoragePolicy(root)
            plan = build_plan(policy, skip_empty=args.skip_empty)
            summary = {"operation": "plan", "records": len(plan.entries), "bytes": plan.total_bytes,
                       "skipped_empty": len(plan.skipped_empty), "by_namespace": dict(Counter(entry.namespace for entry in plan.entries))}
        else:
            if args.command == "import" and args.source == 'files':
                policy = StoragePolicy(root)
                build_plan(policy, skip_empty=args.skip_empty)
            environment = dict(os.environ)
            if args.backend:
                environment['APP_STORAGE_BACKEND'] = args.backend
            settings = StorageSettings.from_env(
                environ=environment, root=root, ignore_table_prefix=True,
            )
            if store_factory is None:
                from persistence.store import RelationalStore
                store_factory = RelationalStore
            store = store_factory(settings)
            database_only = args.command == 'verify' and args.database_only
            if args.source != 'files' and args.command in ('import', 'verify') and not database_only:
                source_backend = ('mysql' if args.source == 'legacy-mysql' else
                    args.source_backend or ('sqlite' if args.source_sqlite_path else settings.backend))
                source_settings = replace(settings, backend=source_backend,
                    sqlite_path=args.source_sqlite_path or settings.sqlite_path,
                    table_prefix=args.legacy_table_prefix)
                if args.source == 'legacy-mysql':
                    from business_storage import MySQLDocumentStore
                    source_store = MySQLDocumentStore(source_settings)
                    _legacy_plan(source_store)
                else:
                    from persistence.store import RelationalStore
                    source_store = RelationalStore(source_settings, schema_version='2')
                    _relational_plan(source_store, skip_corrupt_sessions=args.skip_corrupt_sessions)
                _assert_disjoint_schemas(source_store, store)
            if args.command == "init":
                store.init_schema()
                summary = {"operation": "init", "ok": True, "data_imported": False}
            elif args.command == "import":
                # Explicit import can initialize a new destination alongside
                # disjoint legacy tables; normal startup cannot do so.
                if getattr(store, 'normalized', False) and source_store is not None:
                    store.init_schema(allow_legacy=True)
                else:
                    store.init_schema()
                if source_store is not None:
                    if args.source == 'relational-v2':
                        result = import_relational_store(source_store, store, conflict=args.conflict,
                            batch_size=args.batch_size, skip_corrupt_sessions=args.skip_corrupt_sessions)
                    else:
                        result = import_legacy_store(source_store, store, conflict=args.conflict, batch_size=args.batch_size)
                else:
                    result = import_documents(policy, store, conflict=args.conflict, batch_size=args.batch_size,
                                              skip_empty=args.skip_empty, remove_source=args.remove_source)
                if args.drop_legacy:
                    drop_legacy_schema(source_store, store, skip_corrupt_sessions=args.skip_corrupt_sessions)
                summary = {"operation": "import", "ok": True, "imported": result.imported, "unchanged": result.unchanged,
                           "skipped_conflict": result.skipped_conflict, "skipped_empty": result.skipped_empty, "ready": True,
                           'source_removed': args.remove_source, 'legacy_tables_removed': args.drop_legacy, 'issues': list(result.issues)}
            elif args.command == "verify":
                if database_only:
                    count = verify_database(store)
                    print(json.dumps({'operation': 'verify', 'scope': 'database-only', 'ok': True,
                                      'database_records': count}, ensure_ascii=False))
                    return 0
                if source_store is not None:
                    result = (verify_relational_store(source_store, store, skip_corrupt_sessions=args.skip_corrupt_sessions)
                              if args.source == 'relational-v2' else verify_legacy_store(source_store, store))
                else:
                    policy = _policy_from_store(root, store)
                    result = verify_documents(policy, store, skip_empty=args.skip_empty)
                summary = {"operation": "verify", "ok": result.ok, "source_records": result.expected, "database_records": result.actual,
                           "missing": len(result.missing), "different": len(result.different), "extra": len(result.extra)}
                print(json.dumps(summary, ensure_ascii=False))
                return 0 if result.ok else 1
            else:
                policy = _policy_from_store(root, store)
                result = export_documents(policy, store, args.output)
                summary = {"operation": "export", "ok": True, "exported": result.exported, "bytes": result.total_bytes}
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except MigrationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        # Connection errors can contain passwords or DSNs. Report type only.
        print(json.dumps({"ok": False, "error": f"迁移失败（{type(exc).__name__}）；未输出连接凭据或记录正文"}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        for owned_store in (source_store, store):
            if owned_store is not None and hasattr(owned_store, 'database'):
                owned_store.database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
