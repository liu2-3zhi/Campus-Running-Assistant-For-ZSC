"""Shared database-engine contracts without contacting external databases."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import FrozenInstanceError
from pathlib import Path
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import persistence.engine as engine_module
from persistence.engine import (
    Database, DatabaseConfigurationError, DatabaseError, DatabaseSettings,
)


@pytest.fixture
def database(tmp_path):
    database = Database(DatabaseSettings(root=tmp_path))
    yield database
    database.dispose()


def test_settings_default_to_sqlite_below_explicit_root(tmp_path):
    settings = DatabaseSettings.from_env({}, root=tmp_path)
    assert settings.backend == 'sqlite'
    assert settings.root == tmp_path.resolve()
    assert settings.sqlite_path == tmp_path / 'data/application.sqlite3'
    with pytest.raises(FrozenInstanceError):
        settings.backend = 'mysql'


def test_settings_resolve_relative_sqlite_path_without_loading_env_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.env').write_text('APP_STORAGE_BACKEND=file\n', encoding='utf-8')
    settings = DatabaseSettings.from_env({'SQLITE_DATABASE_PATH': 'scratch/testing.sqlite3'})
    assert settings.root == tmp_path
    assert settings.sqlite_path == tmp_path / 'scratch/testing.sqlite3'
    assert settings.backend == 'sqlite'


def test_settings_root_argument_takes_priority_over_environment(tmp_path):
    settings = DatabaseSettings.from_env({'APP_STORAGE_ROOT': str(tmp_path / 'ignored')}, root=tmp_path)
    assert settings.root == tmp_path


@pytest.mark.parametrize('backend', ['file', 'postgres', ''])
def test_settings_reject_file_and_unknown_runtime_backends(backend, tmp_path):
    with pytest.raises(DatabaseConfigurationError):
        DatabaseSettings.from_env({'APP_STORAGE_BACKEND': backend}, root=tmp_path)


@pytest.mark.parametrize('name,value', [
    ('MYSQL_PORT', '0'), ('MYSQL_PORT', '65536'), ('MYSQL_PORT', 'invalid'),
    ('MYSQL_CONNECT_TIMEOUT', '0'), ('MYSQL_READ_TIMEOUT', '3601'),
    ('MYSQL_WRITE_TIMEOUT', '-1'), ('MYSQL_TABLE_PREFIX', 'bad-prefix'),
    ('MYSQL_TABLE_PREFIX', '9prefix'), ('MYSQL_TABLE_PREFIX', 'a' * 41),
])
def test_mysql_settings_validate_sql_identifiers_and_timeouts(name, value, tmp_path):
    environment = {'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_USER': 'app-user', 'MYSQL_DATABASE': 'app-db', name: value}
    with pytest.raises(DatabaseConfigurationError):
        DatabaseSettings.from_env(environment, root=tmp_path)


@pytest.mark.parametrize('missing', ['MYSQL_USER', 'MYSQL_DATABASE'])
def test_mysql_settings_require_database_and_user(missing, tmp_path):
    environment = {'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_USER': 'app-user', 'MYSQL_DATABASE': 'app-db'}
    del environment[missing]
    with pytest.raises(DatabaseConfigurationError):
        DatabaseSettings.from_env(environment, root=tmp_path)


def test_mysql_url_preserves_special_credentials_without_repr_leak(tmp_path):
    password = 'test-only:/@?%#[]secret'
    settings = DatabaseSettings.from_env({
        'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_HOST': 'database.example.invalid',
        'MYSQL_USER': 'app-user', 'MYSQL_PASSWORD': password, 'MYSQL_DATABASE': 'app-db',
    }, root=tmp_path)
    database = Database(settings)
    try:
        assert database.engine.url.password == password
        assert database.engine.url.database == 'app-db'
        assert database.engine.url.host == 'database.example.invalid'
        assert password not in repr(settings)
        assert password not in repr(database.engine)
    finally:
        database.dispose()


def test_mysql_connection_factory_and_tls_options_do_not_require_live_connection(tmp_path, monkeypatch):
    captured = {}
    original = engine_module.create_engine
    def capture(*args, **kwargs):
        captured.update(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(engine_module, 'create_engine', capture)
    def creator():
        pytest.fail('Engine creation must not connect to an external database')
    settings = DatabaseSettings(backend='mysql', root=tmp_path, user='app-user', database='app-db', ssl_ca='trusted-ca.pem')
    database = Database(settings, connection_factory=creator)
    try:
        assert captured['creator'] is creator
        assert captured['hide_parameters'] is True
        assert captured['pool_pre_ping'] is True
        arguments = captured['connect_args']
        assert arguments['ssl_ca'] == 'trusted-ca.pem'
        assert arguments['ssl_verify_cert'] is True
        assert arguments['ssl_verify_identity'] is True
    finally:
        database.dispose()


def test_connection_establishment_failure_never_exposes_credentials(tmp_path):
    password = 'test-only-secret-do-not-print'
    def creator():
        raise RuntimeError(password)
    database = Database(DatabaseSettings(backend='mysql', root=tmp_path, user='app-user',
        password=password, database='app-db'), connection_factory=creator)
    try:
        with pytest.raises(DatabaseError) as failure:
            with database.connection():
                pytest.fail('Connection setup must fail')
        assert password not in str(failure.value)
    finally:
        database.dispose()


def test_sqlite_persists_committed_data_to_requested_file(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)'))
        connection.execute(text('INSERT INTO sample VALUES (1, :value)'), {'value': '中文🙂'})
    assert database.settings.sqlite_path.is_file()
    with database.connection() as connection:
        assert connection.scalar(text('SELECT value FROM sample WHERE id=1')) == '中文🙂'


def test_sqlite_every_connection_enforces_foreign_keys_and_busy_timeout(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE parent (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))'))
    with database.connection() as first, database.connection() as nested:
        assert first is nested
        assert first.scalar(text('PRAGMA foreign_keys')) == 1
        assert first.scalar(text('PRAGMA busy_timeout')) == 5000
        assert first.scalar(text('PRAGMA journal_mode')).lower() == 'wal'
    with pytest.raises(IntegrityError):
        with database.transaction() as connection:
            connection.execute(text('INSERT INTO child VALUES (1, 999)'))
    with database.connection() as connection:
        assert connection.scalar(text('SELECT count(*) FROM child')) == 0


def test_failed_transaction_rolls_back_all_mutations(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY)'))
    with pytest.raises(ValueError, match='stop'):
        with database.transaction() as connection:
            connection.execute(text('INSERT INTO sample VALUES (1)'))
            with database.connection() as nested:
                assert nested is connection
                nested.execute(text('INSERT INTO sample VALUES (2)'))
            raise ValueError('stop')
    with database.connection() as connection:
        assert connection.scalar(text('SELECT count(*) FROM sample')) == 0


def test_caught_nested_failure_marks_outer_transaction_for_rollback(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY)'))
    with pytest.raises(DatabaseError, match='rollback'):
        with database.transaction() as connection:
            connection.execute(text('INSERT INTO sample VALUES (1)'))
            try:
                with database.transaction() as nested:
                    nested.execute(text('INSERT INTO sample VALUES (2)'))
                    raise ValueError('nested stop')
            except ValueError:
                pass
    with database.connection() as connection:
        assert connection.scalar(text('SELECT count(*) FROM sample')) == 0
        connection.execute(text('INSERT INTO sample VALUES (3)'))
    with database.connection() as connection:
        assert connection.scalar(text('SELECT id FROM sample')) == 3


def test_sqlite_ddl_is_part_of_explicit_transaction(database):
    with pytest.raises(ValueError):
        with database.transaction() as connection:
            connection.execute(text('CREATE TABLE must_rollback (id INTEGER PRIMARY KEY)'))
            raise ValueError('abort schema')
    with database.connection() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='must_rollback'"
        )) == 0


def test_sql_errors_hide_bound_parameters(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)'))
        connection.execute(text('INSERT INTO sample VALUES (1, :value)'), {'value': 'first'})
    private_value = 'test-only-private-value'
    with pytest.raises(IntegrityError) as failure:
        with database.transaction() as connection:
            connection.execute(text('INSERT INTO sample VALUES (1, :value)'), {'value': private_value})
    assert private_value not in str(failure.value)


def test_copied_context_in_another_thread_never_reuses_parent_connection(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY)'))
    with database.transaction() as parent:
        parent.execute(text('INSERT INTO sample VALUES (1)'))
        context = copy_context()
        def read_from_child():
            with database.connection() as child:
                return child is parent, child.scalar(text('SELECT count(*) FROM sample'))
        with ThreadPoolExecutor(max_workers=1) as executor:
            same_connection, count = executor.submit(context.run, read_from_child).result(timeout=15)
        assert not same_connection
        assert count == 0
    with database.connection() as connection:
        assert connection.scalar(text('SELECT count(*) FROM sample')) == 1


def test_copied_context_after_outer_scope_closes_starts_fresh_transaction(database):
    with database.transaction() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY)'))
        connection.execute(text('INSERT INTO sample VALUES (9)'))
        context = copy_context()
        old_connection = connection
    def read_after_commit():
        with database.connection() as connection:
            assert connection is not old_connection
            return connection.scalar(text('SELECT id FROM sample'))
    assert context.run(read_after_commit) == 9


def test_in_memory_sqlite_shares_data_across_distinct_thread_connections(tmp_path):
    database = Database(DatabaseSettings(root=tmp_path, sqlite_path=Path(':memory:')))
    try:
        with database.transaction() as connection:
            connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY)'))
            connection.execute(text('INSERT INTO sample VALUES (7)'))
        barrier = threading.Barrier(3)
        def read_value():
            with database.connection() as connection:
                barrier.wait(timeout=10)
                return id(connection.connection.driver_connection), connection.scalar(text('SELECT id FROM sample'))
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: read_value(), range(3)))
        assert len({identity for identity, _ in results}) == 3
        assert [value for _, value in results] == [7, 7, 7]
        assert not (tmp_path / ':memory:').exists()
    finally:
        database.dispose()


def test_in_memory_databases_are_isolated_between_instances(tmp_path):
    first = Database(DatabaseSettings(root=tmp_path, sqlite_path=Path(':memory:')))
    second = Database(DatabaseSettings(root=tmp_path, sqlite_path=Path(':memory:')))
    try:
        with first.connection() as connection:
            connection.execute(text('CREATE TABLE private_to_first (id INTEGER PRIMARY KEY)'))
        with second.connection() as connection:
            assert connection.scalar(text(
                "SELECT count(*) FROM sqlite_master WHERE name='private_to_first'"
            )) == 0
    finally:
        first.dispose()
        second.dispose()
