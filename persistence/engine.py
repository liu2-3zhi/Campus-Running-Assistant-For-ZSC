"""Database configuration and transaction ownership for SQLite and MySQL.

Only process environment variables are read. Legacy document files and env
files are never opened by this module. Business SQL stays in repositories.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import threading
import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.pool import QueuePool


class DatabaseError(RuntimeError):
    """Database setup or transaction ownership prevents a safe operation."""


class DatabaseConfigurationError(DatabaseError):
    """Deployment configuration is unsupported or incomplete."""


def _integer(name, value, maximum):
    try:
        if isinstance(value, bool):
            raise ValueError
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        raise DatabaseConfigurationError(f'{name} must be an integer') from None
    if number < 1 or number > maximum:
        raise DatabaseConfigurationError(f'{name} is outside the allowed range')
    return number


@dataclass(frozen=True)
class DatabaseSettings:
    backend: str = 'sqlite'
    root: Path = field(default_factory=Path.cwd)
    sqlite_path: Path | None = None
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

    def __post_init__(self):
        backend = str(self.backend).strip().lower()
        if backend not in {'sqlite', 'mysql'}:
            raise DatabaseConfigurationError(
                'APP_STORAGE_BACKEND must be sqlite or mysql; the file backend is frozen'
            )
        prefix = str(self.table_prefix)
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}', prefix) is None:
            raise DatabaseConfigurationError(
                'MYSQL_TABLE_PREFIX must start with a letter and contain only letters, numbers and underscores'
            )
        try:
            root = Path(self.root).resolve()
            sqlite_path = Path(self.sqlite_path) if self.sqlite_path is not None else root / 'data/application.sqlite3'
            if str(sqlite_path) != ':memory:':
                sqlite_path = (root / sqlite_path).resolve()
        except (OSError, TypeError, ValueError):
            raise DatabaseConfigurationError('Database root or SQLite path is invalid') from None
        user = str(self.user).strip()
        database = str(self.database).strip()
        if backend == 'mysql' and (not user or not database):
            raise DatabaseConfigurationError('MySQL requires MYSQL_USER and MYSQL_DATABASE')
        object.__setattr__(self, 'backend', backend)
        object.__setattr__(self, 'root', root)
        object.__setattr__(self, 'sqlite_path', sqlite_path)
        object.__setattr__(self, 'user', user)
        object.__setattr__(self, 'database', database)
        object.__setattr__(self, 'table_prefix', prefix)
        for name, maximum in (('port', 65535), ('connect_timeout', 3600),
                              ('read_timeout', 3600), ('write_timeout', 3600)):
            object.__setattr__(self, name, _integer(name, getattr(self, name), maximum))

    @classmethod
    def from_env(cls, environ=None, root=None):
        environment = os.environ if environ is None else environ
        return cls(
            backend=environment.get('APP_STORAGE_BACKEND', 'sqlite'),
            root=root if root is not None else environment.get('APP_STORAGE_ROOT') or Path.cwd(),
            sqlite_path=environment.get('SQLITE_DATABASE_PATH') or None,
            host=environment.get('MYSQL_HOST', '127.0.0.1'),
            port=environment.get('MYSQL_PORT', 3306),
            user=environment.get('MYSQL_USER', ''),
            password=environment.get('MYSQL_PASSWORD', ''),
            database=environment.get('MYSQL_DATABASE', ''),
            table_prefix=environment.get('MYSQL_TABLE_PREFIX', 'app_'),
            connect_timeout=environment.get('MYSQL_CONNECT_TIMEOUT', 5),
            read_timeout=environment.get('MYSQL_READ_TIMEOUT', 15),
            write_timeout=environment.get('MYSQL_WRITE_TIMEOUT', 15),
            ssl_ca=environment.get('MYSQL_SSL_CA') or None,
        )


@dataclass
class _TransactionState:
    connection: Connection
    owner_thread: int
    rollback_only: bool = False
    active: bool = True


class Database:
    """Own an Engine and share a Connection only in its transaction context.

    Nested scopes intentionally share one transaction. Even when a caller
    catches a nested exception, the outer transaction cannot commit partial
    business state. A copied context entering another thread opens its own
    connection instead of sharing the parent thread's connection.
    """

    def __init__(self, settings: DatabaseSettings, connection_factory=None):
        self.settings = settings
        self._context: ContextVar[_TransactionState | None] = ContextVar(
            f'database_transaction_{id(self)}', default=None,
        )
        options = dict(hide_parameters=True, pool_pre_ping=True,
                       pool_timeout=settings.connect_timeout)
        if connection_factory is not None:
            options['creator'] = connection_factory
        if settings.backend == 'sqlite':
            in_memory = str(settings.sqlite_path) == ':memory:'
            if in_memory:
                # A distinct shared-cache URI per Database permits separate
                # thread connections without sharing their transactions. The
                # pool retains connections until dispose(), keeping data alive.
                url = URL.create('sqlite+pysqlite',
                    database='file:application_' + uuid.uuid4().hex,
                    query={'mode': 'memory', 'cache': 'shared', 'uri': 'true'})
            else:
                try:
                    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                except OSError:
                    raise DatabaseConfigurationError('Cannot create SQLite database directory') from None
                url = URL.create('sqlite+pysqlite', database=str(settings.sqlite_path))
            options.update(poolclass=QueuePool, connect_args={
                'check_same_thread': False, 'timeout': settings.connect_timeout,
            })
        else:
            in_memory = False
            url = URL.create('mysql+pymysql', username=settings.user, password=settings.password,
                host=settings.host, port=settings.port, database=settings.database,
                query={'charset': 'utf8mb4'})
            connect_args = {
                'connect_timeout': settings.connect_timeout,
                'read_timeout': settings.read_timeout,
                'write_timeout': settings.write_timeout,
                'charset': 'utf8mb4',
            }
            if settings.ssl_ca:
                connect_args.update(ssl_ca=str(settings.ssl_ca),
                    ssl_verify_cert=True, ssl_verify_identity=True)
            options['connect_args'] = connect_args
        try:
            self.engine: Engine = create_engine(url, **options)
        except Exception as exc:
            raise DatabaseConfigurationError(
                f'Cannot configure database engine ({type(exc).__name__})'
            ) from None
        if settings.backend == 'sqlite':
            timeout_ms = settings.connect_timeout * 1000
            @event.listens_for(self.engine, 'connect')
            def configure_sqlite(connection, _record):
                # sqlite3's legacy transaction mode otherwise commits DDL
                # outside SQLAlchemy's transaction. BEGIN is emitted below.
                connection.isolation_level = None
                cursor = connection.cursor()
                try:
                    cursor.execute(f'PRAGMA busy_timeout={timeout_ms}')
                    cursor.execute('PRAGMA foreign_keys=ON')
                    if not in_memory:
                        cursor.execute('PRAGMA journal_mode=WAL')
                        cursor.fetchone()
                finally:
                    cursor.close()
            @event.listens_for(self.engine, 'begin')
            def begin_sqlite(connection):
                connection.exec_driver_sql('BEGIN')

    @contextmanager
    def transaction(self):
        current = self._context.get()
        owner_thread = threading.get_ident()
        if current is not None and current.active and current.owner_thread == owner_thread:
            try:
                yield current.connection
            except BaseException:
                current.rollback_only = True
                raise
            return
        connection = None
        try:
            connection = self.engine.connect()
            transaction = connection.begin()
        except Exception as exc:
            if connection is not None:
                connection.close()
            raise DatabaseError(
                f'Database connection failed ({type(exc).__name__}); file fallback is disabled'
            ) from None
        state = _TransactionState(connection, owner_thread)
        token = self._context.set(state)
        try:
            yield connection
            if state.rollback_only:
                raise DatabaseError('Transaction was marked for rollback by a nested failure')
            if not transaction.is_active:
                raise DatabaseError('Transaction ended before its owning scope completed')
            transaction.commit()
        except BaseException:
            if transaction.is_active:
                try:
                    transaction.rollback()
                except Exception:
                    pass
            raise
        finally:
            state.active = False
            self._context.reset(token)
            connection.close()

    @contextmanager
    def connection(self):
        """Open a transaction, or reuse the connection in the current scope."""
        with self.transaction() as connection:
            yield connection

    def dispose(self):
        self.engine.dispose()
