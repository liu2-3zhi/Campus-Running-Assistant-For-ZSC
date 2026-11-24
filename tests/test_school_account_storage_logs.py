"""Account storage logs identify the backend without per-account read noise."""
import json
import logging
import configparser
from types import SimpleNamespace

import pytest

import api_runtime
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def account_storage(tmp_path, monkeypatch):
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    store.init_schema(ready=True)
    runtime = StorageRuntime('sqlite', StoragePolicy(tmp_path, {}), store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    facade = SimpleNamespace(SCHOOL_ACCOUNTS_DIR=str(tmp_path / 'school_accounts'),
        _auth_username_storage_key=lambda owner: owner,
        is_valid_school_username=lambda value: isinstance(value, str) and value.isdigit() and len(value) >= 4,
        auth_system=SimpleNamespace(check_permission=lambda *args: False), chardet=None)
    monkeypatch.setattr(api_runtime, '_main', lambda: facade)
    api = object.__new__(api_runtime.Api)
    api.user_dir = facade.SCHOOL_ACCOUNTS_DIR
    api.global_params = {}
    yield SimpleNamespace(store=store, runtime=runtime, api=api, root=tmp_path)
    store.database.dispose()


def account_messages(caplog):
    return [record.getMessage() for record in caplog.records if record.pathname == api_runtime.__file__]


def test_successful_and_missing_stats_reads_do_not_log_per_account(account_storage, caplog):
    h = account_storage
    h.store.put('school_accounts', '10001.ini', b'[stats]\noverdue_count=2\ncompleted_count=3\n')
    with caplog.at_level(logging.DEBUG):
        assert h.api._load_school_account_stats_from_ini('10001') == {'overdue_count': 2, 'completed_count': 3}
        for index in range(10002, 10022):
            assert h.api._load_school_account_stats_from_ini(str(index)) == {'overdue_count': 0, 'completed_count': 0}
    assert account_messages(caplog) == []


@pytest.mark.parametrize('backend', ['sqlite', 'mysql'])
def test_bulk_account_load_logs_one_backend_summary_without_credentials(account_storage, caplog, backend):
    h = account_storage
    # The same real SQLite I/O validates the records. Switching the runtime tag
    # here tests log provenance only; it is not a MySQL integration fixture.
    h.runtime.backend = backend
    accounts = {str(index): {'password': 'fixture-secret-password', 'ua': 'fixture-private-UA'}
                for index in range(10001, 10041)}
    h.store.put('school_accounts', 'user_accounts/owner.json', json.dumps(accounts).encode())
    with caplog.at_level(logging.DEBUG):
        loaded = h.api._load_user_school_accounts('owner')
    assert set(loaded) == set(accounts)
    messages = account_messages(caplog)
    assert len(messages) == 1
    assert f'storage={backend}' in messages[0]
    assert 'count=40' in messages[0] and 'elapsed_ms=' in messages[0]
    assert 'INI' not in messages[0] and 'JSON' not in messages[0]
    assert 'fixture-secret-password' not in caplog.text
    assert 'fixture-private-UA' not in caplog.text


@pytest.mark.parametrize('backend', ['sqlite', 'mysql'])
def test_failed_stats_write_names_backend_and_keeps_error_diagnostic(account_storage, caplog, monkeypatch, backend):
    h = account_storage
    h.runtime.backend = backend
    def unavailable(*args, **kwargs):
        raise RuntimeError('synthetic storage failure')
    monkeypatch.setattr(h.store, 'put', unavailable)
    with caplog.at_level(logging.DEBUG):
        assert h.api._save_school_account_stats_to_ini('10001', 2, 3) is False
    messages = account_messages(caplog)
    assert len(messages) == 1
    assert f'storage={backend}' in messages[0] and 'synthetic storage failure' in messages[0]
    assert 'INI' not in messages[0]
    assert caplog.records[-1].exc_info is not None


@pytest.mark.parametrize('backend', ['sqlite', 'mysql'])
def test_credential_compatibility_write_does_not_claim_a_physical_backup(account_storage, caplog, backend):
    h = account_storage
    h.runtime.backend = backend
    with caplog.at_level(logging.DEBUG):
        assert h.api._save_school_account_password_to_ini('10001', 'fixture-secret-password', 'fixture-private-UA')
    messages = account_messages(caplog)
    assert len(messages) == 1
    assert f'storage={backend}' in messages[0]
    assert 'INI' not in messages[0] and '备份' not in messages[0]
    assert 'fixture-secret-password' not in caplog.text
    assert 'fixture-private-UA' not in caplog.text


def test_bulk_save_logs_one_backend_summary(account_storage, caplog):
    h = account_storage
    accounts = {str(index): {'password': 'fixture-secret-password', 'ua': 'fixture-private-UA',
                             'overdue_count': 2, 'completed_count': 3}
                for index in range(10001, 10011)}
    with caplog.at_level(logging.DEBUG):
        h.api._save_user_school_accounts('owner', accounts)
    assert h.store.exists('school_accounts', 'user_accounts/owner.json')
    messages = account_messages(caplog)
    assert len(messages) == 1
    assert 'storage=sqlite' in messages[0] and 'count=10' in messages[0] and 'elapsed_ms=' in messages[0]
    assert 'INI' not in messages[0] and 'JSON' not in messages[0]
    assert 'fixture-secret-password' not in caplog.text and 'fixture-private-UA' not in caplog.text


def test_unmanaged_invalid_stats_report_file_source(account_storage, tmp_path, caplog):
    h = account_storage
    external = tmp_path / 'external'
    external.mkdir()
    (external / '10001.ini').write_text('[stats]\noverdue_count=invalid\n', encoding='utf-8')
    h.api.user_dir = str(external)
    with caplog.at_level(logging.DEBUG):
        assert h.api._load_school_account_stats_from_ini('10001') == {'overdue_count': 0, 'completed_count': 0}
    messages = account_messages(caplog)
    assert len(messages) == 1 and 'storage=file' in messages[0]


def test_account_config_save_logs_backend_summary_without_raw_sections(account_storage, caplog, monkeypatch):
    h = account_storage
    h.store.put('school_accounts', '10001.ini', b'[Config]\nUsername=10001\n[stats]\noverdue_count=2\ncompleted_count=3\n')
    facade = api_runtime._main()
    facade._read_config_ini = lambda path: configparser.RawConfigParser()
    facade._write_config_with_comments = lambda *args: None
    h.api.config_path = str(h.root / 'configs' / 'config.json')
    h.api.params = {}
    h.api.is_multi_account_mode = False
    with caplog.at_level(logging.DEBUG):
        h.api._save_config('10001')
    messages = account_messages(caplog)
    assert len(messages) == 2
    assert 'storage=sqlite' in messages[0] and 'preserved_stats=2' in messages[0]
    assert 'storage=sqlite' in messages[1]
    assert all('INI' not in message and 'JSON' not in message for message in messages)
