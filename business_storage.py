"""Opt-in MySQL document storage; the default filesystem remains unchanged."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import threading
import time


class StorageError(RuntimeError):
    pass


class StorageConfigurationError(StorageError):
    pass


class ConflictError(StorageError):
    pass


ANY_REVISION = object()
SCHEMA_VERSION = '1'


@dataclass(frozen=True)
class StorageSettings:
    backend: str = 'file'
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    host: str = '127.0.0.1'
    port: int = 3306
    user: str = ''
    password: str = field(default='', repr=False)
    database: str = ''
    table_prefix: str = 'app_'
    connect_timeout: int = 5
    read_timeout: int = 15
    write_timeout: int = 15
    ssl_ca: str | None = None

    @classmethod
    def from_env(cls, environ=None, root=None):
        env = os.environ if environ is None else environ
        backend = str(env.get('APP_STORAGE_BACKEND', 'file')).strip().lower()
        if backend not in {'file', 'mysql'}:
            raise StorageConfigurationError('APP_STORAGE_BACKEND must be file or mysql')
        root = Path(root or env.get('APP_STORAGE_ROOT') or Path(__file__).resolve().parent).resolve()
        if backend == 'file':
            return cls(backend=backend, root=root)

        def integer(name, default, maximum=3600):
            try:
                value = int(env.get(name, default))
            except (TypeError, ValueError):
                raise StorageConfigurationError(f'{name} must be an integer') from None
            if not 1 <= value <= maximum:
                raise StorageConfigurationError(f'{name} is outside the allowed range')
            return value

        prefix = str(env.get('MYSQL_TABLE_PREFIX', 'app_'))
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}', prefix):
            raise StorageConfigurationError('MYSQL_TABLE_PREFIX must contain only letters, numbers and underscores')
        user, database = str(env.get('MYSQL_USER', '')).strip(), str(env.get('MYSQL_DATABASE', '')).strip()
        if not user or not database:
            raise StorageConfigurationError('MySQL mode requires MYSQL_USER and MYSQL_DATABASE')
        password = env.get('MYSQL_PASSWORD', '')
        password_file = env.get('MYSQL_PASSWORD_FILE')
        if password_file:
            try:
                password = Path(password_file).read_text(encoding='utf-8').rstrip(chr(13) + chr(10))
            except OSError:
                raise StorageConfigurationError('Cannot read MYSQL_PASSWORD_FILE') from None
        return cls(backend=backend, root=root, host=str(env.get('MYSQL_HOST', '127.0.0.1')),
                   port=integer('MYSQL_PORT', 3306, 65535), user=user, password=password,
                   database=database, table_prefix=prefix,
                   connect_timeout=integer('MYSQL_CONNECT_TIMEOUT', 5),
                   read_timeout=integer('MYSQL_READ_TIMEOUT', 15),
                   write_timeout=integer('MYSQL_WRITE_TIMEOUT', 15),
                   ssl_ca=env.get('MYSQL_SSL_CA') or None)


class StoragePolicy:
    """Map only known business documents; logs and binary assets never route."""
    SINGLE_FILES = frozenset({'permissions.json', 'messages.json', 'reminders.json',
                              'payment_methods.json', 'amap_watermark_control.json'})

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
            'deleted_accounts': self.root / 'Remove_Acoount',
            'legacy_deleted_accounts': self.root / 'remove',
            'configs': self.root / 'configs',
            'background_state': self.root / 'random_background_image',
            'settings': self.root,
        }
        self.excluded_roots = tuple({location(logging_config.get('log_dir', 'logs')),
                                     self.root / 'logs', self.root / 'cache',
                                     self.root / 'uploads', self.root / 'ssl'})
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
        if namespace == 'configs' and key == 'config.json':
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
    store: MySQLDocumentStore | None = None


_runtime = None
_runtime_lock = threading.RLock()
_file_runtime = StorageRuntime('file')


def get_runtime():
    """Lazy opt-in initialization; default file mode never connects to MySQL."""
    global _runtime
    if _runtime is not None:
        return _runtime
    backend = os.environ.get('APP_STORAGE_BACKEND', 'file').strip().lower()
    if backend == 'file':
        return _file_runtime
    with _runtime_lock:
        if _runtime is None:
            settings = StorageSettings.from_env()
            if settings.root != Path(__file__).resolve().parent:
                raise StorageConfigurationError('MySQL application root must match the code directory; use --root only for offline migration')
            if Path.cwd().resolve() != settings.root:
                raise StorageConfigurationError('Start the MySQL application with its working directory set to the application root')
            policy = StoragePolicy(settings.root)
            store = MySQLDocumentStore(settings)
            store.check_ready()
            _runtime = StorageRuntime(settings.backend, policy, store)
    return _runtime


def require_storage_ready():
    return get_runtime()
