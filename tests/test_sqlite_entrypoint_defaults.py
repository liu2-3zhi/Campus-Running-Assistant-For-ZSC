"""Default application storage belongs beside the program, not the launch cwd."""
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect

import business_storage
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def program(tmp_path, monkeypatch):
    directory = tmp_path / 'program'
    directory.mkdir()
    launch = tmp_path / 'launch'
    launch.mkdir()
    monkeypatch.setattr(business_storage, '__file__', str(directory / 'business_storage.py'))
    monkeypatch.setattr(business_storage, '_runtime', None)
    for name in ('APP_STORAGE_ROOT', 'APP_STORAGE_BACKEND', 'SQLITE_DATABASE_PATH', 'MYSQL_TABLE_PREFIX'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(launch)
    yield SimpleNamespace(directory=directory, launch=launch)
    database = getattr(getattr(business_storage._runtime, 'store', None), 'database', None)
    if database is not None:
        database.dispose()


def test_default_start_from_another_cwd_creates_sqlite_next_to_program(program, caplog):
    with caplog.at_level(logging.INFO):
        runtime = business_storage.get_runtime()
    expected = program.directory / 'data/application.sqlite3'
    assert runtime.backend == 'sqlite'
    assert runtime.store.settings.root == program.directory
    assert runtime.store.settings.sqlite_path == expected
    assert expected.is_file()
    assert not (program.launch / 'data').exists()
    runtime.store.check_ready()
    assert any('backend=SQLite' in record.getMessage() and str(expected) in record.getMessage()
               for record in caplog.records if record.levelno == logging.INFO)


def test_default_start_at_program_directory_also_logs_sqlite_mode(program, monkeypatch, caplog):
    monkeypatch.chdir(program.directory)
    with caplog.at_level(logging.INFO):
        business_storage.get_runtime()
    assert 'backend=SQLite' in caplog.text


def test_fresh_sqlite_preserves_the_builtin_only_proxy_trust_default_in_database(program):
    import trusted_ip

    runtime = business_storage.get_runtime()
    path = program.directory / 'trusted_ips.txt'
    document = runtime.store.get('settings', 'trusted_ips.txt')
    assert document is not None
    matcher = trusted_ip._load_trusted_ip_networks(str(path))
    assert not matcher.match_all
    assert matcher.entries == ()
    assert not path.exists()


def test_existing_database_missing_proxy_rules_is_not_silently_reconfigured(program):
    store = RelationalStore(DatabaseSettings(root=program.directory))
    try:
        store.init_schema(ready=True)
    finally:
        store.database.dispose()
    runtime = business_storage.get_runtime()
    assert runtime.store.get('settings', 'trusted_ips.txt') is None


def test_fresh_database_is_not_ready_if_default_proxy_rules_cannot_be_written(program, monkeypatch):
    store = RelationalStore(DatabaseSettings(root=program.directory))
    monkeypatch.setattr(business_storage, '_create_relational_store', lambda settings: store)
    def fail_default_write(*args, **kwargs):
        raise business_storage.StorageError('synthetic default write failure')
    monkeypatch.setattr(store, 'put', fail_default_write)
    try:
        with pytest.raises(business_storage.StorageError, match='default write failure'):
            business_storage.get_runtime()
        with pytest.raises(business_storage.StorageError):
            store.check_ready()
        assert business_storage._runtime is None
    finally:
        store.database.dispose()


def test_explicit_root_cannot_redirect_application_storage(program, monkeypatch):
    monkeypatch.setenv('APP_STORAGE_ROOT', str(program.launch))
    with pytest.raises(business_storage.StorageConfigurationError, match='root must match'):
        business_storage.get_runtime()
    assert not (program.directory / 'data').exists()
    assert not (program.launch / 'data').exists()


def test_explicit_root_preserves_working_directory_guard(program, monkeypatch):
    monkeypatch.setenv('APP_STORAGE_ROOT', str(program.directory))
    with pytest.raises(business_storage.StorageConfigurationError, match='working directory'):
        business_storage.get_runtime()
    assert not (program.directory / 'data').exists()


def test_default_root_still_refuses_unmigrated_program_files(program):
    legacy = program.directory / 'permissions.json'
    legacy.write_text('{}', encoding='utf-8')
    with pytest.raises(business_storage.StorageConfigurationError, match='explicit migration'):
        business_storage.get_runtime()
    assert legacy.read_text(encoding='utf-8') == '{}'
    assert not (program.directory / 'data').exists()
    assert not (program.launch / 'data').exists()


def test_existing_program_sqlite_opens_from_other_cwd_without_stale_file_fallback(program):
    store = RelationalStore(DatabaseSettings(root=program.directory))
    try:
        store.init_schema(ready=True)
        store.put('configs', 'config.json', b'{"System":{"school_accounts_dir":"db-accounts"}}')
    finally:
        store.database.dispose()
    stale = program.directory / 'configs/config.json'
    stale.parent.mkdir()
    stale.write_text('{invalid old file', encoding='utf-8')
    runtime = business_storage.get_runtime()
    assert runtime.policy.roots['school_accounts'] == program.directory / 'db-accounts'
    assert stale.read_text(encoding='utf-8') == '{invalid old file'
    assert not (program.launch / 'data').exists()


def test_mysql_startup_mode_log_does_not_expose_connection_credentials(program, monkeypatch, caplog):
    monkeypatch.chdir(program.directory)
    monkeypatch.setenv('APP_STORAGE_BACKEND', 'mysql')
    monkeypatch.setenv('MYSQL_USER', 'fixture-user')
    monkeypatch.setenv('MYSQL_PASSWORD', 'fixture-password-must-not-appear')
    monkeypatch.setenv('MYSQL_DATABASE', 'fixture-database')
    monkeypatch.setenv('MYSQL_TABLE_PREFIX', 'app_')
    store = SimpleNamespace(check_ready=lambda: None, get=lambda *args: None)

    def create_store(settings):
        assert settings.table_prefix == ''
        return store

    monkeypatch.setattr(business_storage, '_create_relational_store', create_store)
    with caplog.at_level(logging.INFO):
        runtime = business_storage.get_runtime()
    assert runtime.backend == 'mysql'
    assert 'backend=MySQL' in caplog.text
    assert 'fixture-password-must-not-appear' not in caplog.text
    assert 'fixture-user' not in caplog.text
    assert not (program.directory / 'data').exists()


def test_fresh_sqlite_ignores_even_an_invalid_legacy_prefix(program, monkeypatch):
    monkeypatch.setenv('MYSQL_TABLE_PREFIX', 'invalid-prefix!')
    store = business_storage.get_runtime().store
    assert store.settings.table_prefix == ''
    assert 'schema_migrations' in inspect(store.database.engine).get_table_names()


def test_ignoring_legacy_prefix_does_not_open_old_tables_or_create_a_schema(program, monkeypatch):
    settings = DatabaseSettings(root=program.directory, table_prefix='app_')
    source = RelationalStore(settings, schema_version='2')
    monkeypatch.setenv('MYSQL_TABLE_PREFIX', 'app_')
    try:
        source.init_schema(ready=True)
        before = set(inspect(source.database.engine).get_table_names())
        with pytest.raises(DatabaseError, match='run tools/migrate_storage.py'):
            business_storage.get_runtime()
        assert set(inspect(source.database.engine).get_table_names()) == before
        assert 'app_schema_meta' in before
        assert business_storage._runtime is None
    finally:
        source.database.dispose()
