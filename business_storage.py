"""Database-first runtime policy and frozen v1 document migration support."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import threading
import time
from persistence.engine import (DatabaseError, DatabaseConfigurationError,
                                DatabaseSettings as StorageSettings)


StorageError = DatabaseError
StorageConfigurationError = DatabaseConfigurationError


class ConflictError(StorageError):
    pass


ANY_REVISION = object()
SCHEMA_VERSION = '1'
DEFAULT_TRUSTED_IP_RULES = (
    '# Trusted external proxy addresses, one per line.\n'
    '# Private, loopback and link-local proxies are trusted automatically.\n'
    '# No external proxy is trusted until an address is added.\n'
).encode('utf-8')


class StoragePolicy:
    """Map only known business documents; logs and binary assets never route."""
    SINGLE_FILES = frozenset({'permissions.json', 'messages.json', 'reminders.json',
                              'payment_methods.json', 'amap_watermark_control.json',
                              'trusted_ips.txt'})

    def __init__(self, root, config=None):
        self.root = Path(root).resolve()
        if config is None:
            config_path = self.root / 'configs' / 'config.json'
            try:
                with open(config_path, encoding='utf-8-sig') as handle:
                    config = json.load(handle)
            except FileNotFoundError:
                config = {}
            except (OSError, ValueError):
                raise StorageConfigurationError('Cannot read local configs/config.json directory settings') from None
        if not isinstance(config, dict):
            raise StorageConfigurationError('Local bootstrap config must be a JSON object')
        system, logging_config = config.get('System', {}), config.get('Logging', {})
        if not isinstance(system, dict) or not isinstance(logging_config, dict):
            raise StorageConfigurationError('System and Logging directory settings must be objects')

        def location(value):
            return (self.root / str(value)).resolve()

        self.roots = {
            'system_accounts': location(system.get('system_accounts_dir', 'system_accounts')),
            'school_accounts': location(system.get('school_accounts_dir', 'school_accounts')),
            'sessions': location(system.get('sessions_dir', 'sessions')),
            'tokens': location(system.get('tokens_dir', 'tokens')),
            'payment_orders': self.root / 'payment_orders',
            'billing': self.root / 'User_Billing',
            'background_tasks': self.root / 'background_tasks',
            'sms_records': self.root / 'sms_records',
            'deleted_accounts': self.root / 'Remove_Acoount',
            'legacy_deleted_accounts': self.root / 'remove',
            'configs': self.root / 'configs',
            'background_state': self.root / 'random_background_image',
            'settings': self.root,
        }
        self.excluded_roots = tuple({location(logging_config.get('log_dir', 'logs')),
                                     self.root / 'logs', self.root / 'cache',
                                     self.root / 'uploads', self.root / 'ssl'})
        # Audit history is a read-only migration input, never a managed file.
        self.sms_history_path = location(logging_config.get('log_dir', 'logs')) / 'sms_history.jsonl'
        self._ordered_roots = sorted(((name, path) for name, path in self.roots.items()
                                      if name != 'settings'), key=lambda item: len(str(item[1])), reverse=True)

    @staticmethod
    def _below(path, parent):
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _path(self, path):
        return Path(os.fsdecode(path)).absolute()

    def is_excluded(self, path):
        path = self._path(path).resolve()
        return any(self._below(path, excluded) for excluded in self.excluded_roots)

    def directory(self, path):
        path = self._path(path).resolve()
        if self.is_excluded(path):
            return None
        if path == self.root:
            return 'settings', ''
        for namespace, base in self._ordered_roots:
            if self._below(path, base):
                key = path.relative_to(base).as_posix()
                return namespace, '' if key == '.' else key.rstrip('/') + '/'
        return None

    def identify(self, path):
        if isinstance(path, int):
            return None
        path = self._path(path).resolve()
        if self.is_excluded(path):
            return None
        if path.parent == self.root and path.name in self.SINGLE_FILES:
            return 'settings', path.name
        if path.parent == self.root:
            return None
        directory = self.directory(path.parent)
        if directory is None:
            return None
        namespace, prefix = directory
        key = prefix + path.name
        if path.suffix.lower() not in {'.json', '.ini'}:
            return None
        if namespace == 'background_state' and key != 'background_state.json':
            return None
        return namespace, key

    def physical_path(self, namespace, key):
        if namespace not in self.roots or not isinstance(key, str) or not key or chr(92) in key or chr(0) in key:
            raise StorageConfigurationError('Invalid document namespace/key')
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {'..', '.'} for part in relative.parts) or ':' in key:
            raise StorageConfigurationError('Document key must remain inside its namespace')
        path = self.roots[namespace].joinpath(*relative.parts)
        if self.identify(path) != (namespace, key):
            raise StorageConfigurationError('Document path is outside the allowed business scope')
        return path

    def iter_files(self):
        seen = set()
        for namespace, base in self.roots.items():
            candidates = (base / name for name in sorted(self.SINGLE_FILES)) if namespace == 'settings' else self._walk(base)
            for path in candidates:
                if path.is_symlink() or not path.is_file():
                    continue
                identity = self.identify(path)
                if identity and identity not in seen:
                    seen.add(identity)
                    yield path

    def _walk(self, base):
        if self.is_excluded(base):
            return
        for folder, directories, files in os.walk(base, followlinks=False):
            directories[:] = sorted(name for name in directories if not Path(folder, name).is_symlink()
                                     and not self.is_excluded(Path(folder, name)))
            for name in sorted(files):
                yield Path(folder, name)


@dataclass(frozen=True)
class Document:
    namespace: str
    key: str
    content: bytes
    mtime_ns: int
    revision: int
    content_sha256: str | None = None

    @property
    def digest(self):
        return self.content_sha256 if self.content_sha256 is not None else hashlib.sha256(self.content).hexdigest()


class MySQLDocumentStore:
    """Atomic versioned documents; connections belong to one operation/transaction."""
    def __init__(self, settings, connection_factory=None):
        self.settings = settings
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}', settings.table_prefix):
            raise StorageConfigurationError('Invalid MySQL table prefix')
        self._factory = connection_factory
        self._local = threading.local()
        self._documents = settings.table_prefix + 'documents'
        self._metadata = settings.table_prefix + 'storage_meta'

    def _connect(self):
        try:
            if self._factory:
                return self._factory()
            try:
                import pymysql
            except ImportError:
                raise StorageConfigurationError('MySQL mode requires PyMySQL; install ssl/requirements.txt') from None
            kwargs = dict(host=self.settings.host, port=self.settings.port, user=self.settings.user,
                          password=self.settings.password, database=self.settings.database,
                          charset='utf8mb4', autocommit=False,
                          connect_timeout=self.settings.connect_timeout, read_timeout=self.settings.read_timeout,
                          write_timeout=self.settings.write_timeout)
            if self.settings.ssl_ca:
                kwargs.update(ssl_ca=self.settings.ssl_ca, ssl_verify_cert=True, ssl_verify_identity=True)
            return pymysql.connect(**kwargs)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'MySQL connection failed ({type(exc).__name__}); file fallback is disabled') from None

    @contextmanager
    def transaction(self):
        existing = getattr(self._local, 'connection', None)
        if existing is not None:
            try:
                yield self
            except BaseException:
                self._local.rollback_only = True
                raise
            return
        connection = self._connect()
        self._local.connection, self._local.rollback_only = connection, False
        try:
            connection.begin()
            yield self
            if self._local.rollback_only:
                raise StorageError('Transaction was marked for rollback')
            connection.commit()
        except BaseException:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
        finally:
            self._local.connection = None
            connection.close()

    @contextmanager
    def _cursor(self):
        try:
            with self.transaction():
                with self._local.connection.cursor() as cursor:
                    yield cursor
        except (StorageError, FileNotFoundError, FileExistsError):
            raise
        except Exception as exc:
            if getattr(exc, 'args', ()) and exc.args[0] == 1062:
                raise ConflictError('Concurrent document creation conflict') from None
            raise StorageError(f'MySQL operation failed ({type(exc).__name__}); file fallback is disabled') from None

    @staticmethod
    def _identity(namespace, key):
        if not isinstance(namespace, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', namespace):
            raise StorageConfigurationError('Invalid document namespace')
        if not isinstance(key, str) or not key or len(key.encode('utf-8')) > 768 or chr(0) in key:
            raise StorageConfigurationError('Invalid or oversized document key')
        return namespace.encode('utf-8'), key.encode('utf-8')

    @staticmethod
    def _document(namespace, key, row):
        return Document(namespace, key, bytes(row[0]), int(row[1]), int(row[2]), row[3])

    def init_schema(self):
        with self._cursor() as cursor:
            cursor.execute(f'CREATE TABLE IF NOT EXISTS {self._documents} ('
                           'namespace VARBINARY(64) NOT NULL, record_key VARBINARY(768) NOT NULL, '
                           'content LONGBLOB NOT NULL, content_sha256 CHAR(64) CHARACTER SET ascii NOT NULL, '
                           'mtime_ns BIGINT UNSIGNED NOT NULL, revision BIGINT UNSIGNED NOT NULL, '
                           'PRIMARY KEY (namespace, record_key)) ENGINE=InnoDB')
            cursor.execute(f'CREATE TABLE IF NOT EXISTS {self._metadata} ('
                           'meta_key VARCHAR(64) CHARACTER SET ascii PRIMARY KEY, '
                           'meta_value TEXT NOT NULL) ENGINE=InnoDB')
            cursor.execute(f'SELECT meta_value FROM {self._metadata} WHERE meta_key=%s', ('schema_version',))
            row = cursor.fetchone()
            if row and row[0] != SCHEMA_VERSION:
                raise StorageConfigurationError('Unsupported MySQL storage schema version')
            if not row:
                cursor.execute(f'INSERT INTO {self._metadata} (meta_key,meta_value) VALUES (%s,%s)',
                               ('schema_version', SCHEMA_VERSION))

    def check_ready(self):
        with self._cursor() as cursor:
            cursor.execute(f'SELECT meta_key,meta_value FROM {self._metadata} WHERE meta_key IN (%s,%s)',
                           ('schema_version', 'ready'))
            values = dict(cursor.fetchall())
            if values.get('schema_version') != SCHEMA_VERSION or values.get('ready') != '1':
                raise StorageConfigurationError('MySQL storage is not migrated and verified; run tools/migrate_storage.py')

    def _set_ready(self, value):
        with self._cursor() as cursor:
            cursor.execute(f'INSERT INTO {self._metadata} (meta_key,meta_value) VALUES (%s,%s) '
                           'ON DUPLICATE KEY UPDATE meta_value=%s', ('ready', value, value))

    def mark_ready(self):
        self._set_ready('1')

    def mark_pending(self):
        self._set_ready('0')

    def get(self, namespace, key):
        identity = self._identity(namespace, key)
        with self._cursor() as cursor:
            cursor.execute(f'SELECT content,mtime_ns,revision,content_sha256 FROM {self._documents} WHERE namespace=%s AND record_key=%s', identity)
            row = cursor.fetchone()
            return self._document(namespace, key, row) if row else None

    def put(self, namespace, key, content, expected_revision=ANY_REVISION, create_only=False, mtime_ns=None):
        identity = self._identity(namespace, key)
        if not isinstance(content, bytes):
            raise TypeError('Document content must be bytes')
        with self._cursor() as cursor:
            cursor.execute(f'SELECT revision,mtime_ns FROM {self._documents} WHERE namespace=%s AND record_key=%s FOR UPDATE', identity)
            row = cursor.fetchone()
            revision = int(row[0]) if row else 0
            if create_only and row:
                raise FileExistsError(key)
            if expected_revision is not ANY_REVISION and expected_revision != revision:
                raise ConflictError('Document changed since it was read')
            modified = int(mtime_ns) if mtime_ns is not None else max(time.time_ns(), int(row[1]) + 1 if row else 0)
            document = Document(namespace, key, content, modified, revision + 1)
            if row:
                cursor.execute(f'UPDATE {self._documents} SET content=%s,content_sha256=%s,mtime_ns=%s,revision=%s '
                               'WHERE namespace=%s AND record_key=%s',
                               (content, document.digest, modified, revision + 1, *identity))
            else:
                cursor.execute(f'INSERT INTO {self._documents} '
                               '(namespace,record_key,content,content_sha256,mtime_ns,revision) VALUES (%s,%s,%s,%s,%s,%s)',
                               (*identity, content, document.digest, modified, 1))
            return document

    def delete(self, namespace, key, expected_revision=ANY_REVISION):
        identity = self._identity(namespace, key)
        with self._cursor() as cursor:
            cursor.execute(f'SELECT revision FROM {self._documents} WHERE namespace=%s AND record_key=%s FOR UPDATE', identity)
            row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(key)
            if expected_revision is not ANY_REVISION and expected_revision != int(row[0]):
                raise ConflictError('Document changed since it was read')
            cursor.execute(f'DELETE FROM {self._documents} WHERE namespace=%s AND record_key=%s', identity)

    def list(self, namespace, prefix=''):
        self._identity(namespace, prefix or '_')
        with self._cursor() as cursor:
            encoded = prefix.encode('utf-8')
            cursor.execute(f'SELECT record_key,content,mtime_ns,revision,content_sha256 FROM {self._documents} '
                           'WHERE namespace=%s AND LEFT(record_key,%s)=%s ORDER BY record_key',
                           (namespace.encode('utf-8'), len(encoded), encoded))
            return [self._document(namespace, bytes(row[0]).decode('utf-8'), row[1:]) for row in cursor.fetchall()]

    def namespaces(self):
        with self._cursor() as cursor:
            cursor.execute(f'SELECT DISTINCT namespace FROM {self._documents} ORDER BY namespace')
            return [bytes(row[0]).decode('utf-8') for row in cursor.fetchall()]


@dataclass
class StorageRuntime:
    backend: str
    policy: StoragePolicy | None = None
    store: object | None = None


_runtime = None
_runtime_lock = threading.RLock()

def _create_relational_store(settings):
    from persistence.store import RelationalStore
    return RelationalStore(settings)


def _stored_config(store):
    document = store.get('configs', 'config.json')
    if document is None:
        return {}
    try:
        config = json.loads(document.content.decode('utf-8-sig'))
    except (UnicodeError, ValueError):
        raise StorageConfigurationError('Database application configuration is invalid') from None
    if not isinstance(config, dict):
        raise StorageConfigurationError('Database application configuration must be an object')
    return config


def get_runtime():
    """Initialize database storage without importing or falling back to files."""
    global _runtime
    if _runtime is not None:
        return _runtime
    with _runtime_lock:
        if _runtime is None:
            application_root = Path(__file__).resolve().parent
            configured_root = os.environ.get('APP_STORAGE_ROOT')
            settings = StorageSettings.from_env(
                root=configured_root or application_root, ignore_table_prefix=True,
            )
            if settings.root != application_root:
                raise StorageConfigurationError('Database application root must match the code directory; use --root only for offline migration')
            if configured_root and Path.cwd().resolve() != settings.root:
                raise StorageConfigurationError('Start the database application with its working directory set to the application root')
            new_sqlite = settings.backend == 'sqlite' and (
                str(settings.sqlite_path) == ':memory:' or not settings.sqlite_path.exists())
            if new_sqlite:
                # This policy is used only to detect legacy input. Once a
                # database is ready, its own configuration controls runtime paths.
                try:
                    source_policy = StoragePolicy(settings.root)
                except StorageConfigurationError:
                    raise StorageConfigurationError(
                        'Legacy business configuration requires explicit migration; run tools/migrate_storage.py plan/import before starting'
                    ) from None
                if next(iter(source_policy.iter_files()), None) is not None:
                    raise StorageConfigurationError(
                        'Legacy business files require explicit migration; run tools/migrate_storage.py plan/import before starting'
                    )
            store = _create_relational_store(settings)
            if new_sqlite:
                store.init_schema(ready=False)
                # The former shipped comment-only file must remain a database
                # default: a missing record deliberately has different semantics.
                store.put('settings', 'trusted_ips.txt', DEFAULT_TRUSTED_IP_RULES,
                          create_only=True)
                store.mark_ready()
            else:
                store.check_ready()
            policy = StoragePolicy(settings.root, _stored_config(store))
            _runtime = StorageRuntime(settings.backend, policy, store)
            if settings.backend == 'sqlite':
                logging.getLogger(__name__).info('[存储] backend=SQLite database=%s', settings.sqlite_path)
            else:
                logging.getLogger(__name__).info('[存储] backend=MySQL')
    return _runtime


def require_storage_ready():
    return get_runtime()


def get_runtime_for_paths(*paths):
    """Avoid initializing business storage for standalone resource I/O.

    Application configuration is in the default managed scope and bootstraps
    the full database policy before custom directories are used. Once ready,
    that policy also covers custom paths outside the application directory.
    """
    if _runtime is not None:
        return _runtime
    root = os.environ.get('APP_STORAGE_ROOT') or Path(__file__).resolve().parent
    policy = StoragePolicy(root, {})
    for path in paths:
        if isinstance(path, int):
            continue
        if policy.identify(path) is not None or policy.directory(path) is not None:
            return get_runtime()
    return None


def get_entrypoint_ssl_settings():
    """Expose only deployment booleans, never configuration or credentials."""
    config = _stored_config(get_runtime().store)
    ssl = config.get('SSL', {})
    if not isinstance(ssl, dict):
        raise StorageConfigurationError('Database SSL configuration must be an object')
    def boolean(name):
        value = ssl.get(name, config.get(name, False))
        if isinstance(value, (bool, int, float)):
            return bool(value)
        return isinstance(value, str) and value.strip().lower() in {'true', '1', 'yes', 'on'}
    return {name: boolean(name) for name in ('ssl_enabled', 'https_only')}
