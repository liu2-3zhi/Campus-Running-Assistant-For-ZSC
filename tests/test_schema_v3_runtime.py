"""Runtime defaults and legacy guards for the explicit business schema."""
from dataclasses import replace
import json

import pytest
from sqlalchemy import inspect

from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore


def test_new_database_settings_use_no_table_prefix(tmp_path):
    settings = DatabaseSettings.from_env({}, root=tmp_path)
    assert settings.table_prefix == ''
    assert settings.sqlite_path == tmp_path / 'data' / 'application.sqlite3'


def test_new_schema_has_explicit_business_tables_without_old_fragments(tmp_path):
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    try:
        store.init_schema(ready=True)
        tables = set(inspect(store.database.engine).get_table_names())
        assert {'system_accounts', 'school_accounts', 'account_school_links',
                'school_account_information', 'system_settings', 'payment_orders',
                'sms_records', 'storage_documents', 'schema_migrations'} <= tables
        assert len(tables) <= 25
        assert not any(name.startswith('app_') for name in tables)
        assert not {'session_snapshots', 'identity_collections', 'identity_index_entries',
                    'school_account_parameters', 'compatibility_values'} & tables
        assert store.check_ready()
    finally:
        store.database.dispose()


def test_old_v2_reader_keeps_original_table_names_and_types(tmp_path):
    settings = DatabaseSettings(root=tmp_path, table_prefix='app_')
    store = RelationalStore(settings, schema_version='2')
    try:
        store.init_schema(ready=True)
        payload = {'auth_username': 'owner', 'password': 'fixture', 'enabled': False,
                   'point': [1.123456789, 2**90], 'missing': None}
        store.put('system_accounts', 'owner.json', json.dumps(payload).encode())
        assert json.loads(store.get('system_accounts', 'owner.json').content) == payload
        assert 'app_users' in inspect(store.database.engine).get_table_names()
    finally:
        store.database.dispose()


def test_new_initialization_refuses_to_hide_existing_v2_database(tmp_path):
    old_settings = DatabaseSettings(root=tmp_path, table_prefix='app_')
    old = RelationalStore(old_settings, schema_version='2')
    new = RelationalStore(replace(old_settings, table_prefix=''))
    try:
        old.init_schema(ready=True)
        with pytest.raises(DatabaseError, match='[Ll]egacy|[Mm]igrat'):
            new.init_schema(ready=True)
        assert 'storage_documents' not in inspect(new.database.engine).get_table_names()
        new.init_schema(allow_legacy=True)
        assert 'storage_documents' in inspect(new.database.engine).get_table_names()
        with pytest.raises(DatabaseError):
            new.check_ready()
    finally:
        old.database.dispose()
        new.database.dispose()


def test_default_entrypoint_prepares_the_program_directory(tmp_path, monkeypatch):
    import main
    monkeypatch.delenv('APP_STORAGE_ROOT', raising=False)
    monkeypatch.chdir(tmp_path)
    main._prepare_application_working_directory()
    from pathlib import Path
    assert Path.cwd() == Path(main.__file__).resolve().parent


def test_explicit_application_root_is_not_silently_changed(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv('APP_STORAGE_ROOT', str(tmp_path))
    monkeypatch.chdir(tmp_path)
    main._prepare_application_working_directory()
    from pathlib import Path
    assert Path.cwd() == tmp_path
