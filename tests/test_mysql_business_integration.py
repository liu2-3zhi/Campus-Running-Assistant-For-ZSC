"""Exercise actual business entry points against a document backend."""
import hashlib
import json
from types import SimpleNamespace

import pytest

import auth_system
import api_runtime
import runtime_models
import guest_token_store
from business_storage import StoragePolicy, StorageRuntime
from test_storage_io import MemoryStore
from test_mysql_store import live_store
import storage_io


@pytest.fixture(params=['memory', 'mysql'])
def database_runtime(tmp_path, monkeypatch, request):
    store = MemoryStore() if request.param == 'memory' else request.getfixturevalue('live_store')
    policy = StoragePolicy(tmp_path)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda: StorageRuntime('mysql', policy, store))
    runtime = SimpleNamespace(
        SYSTEM_ACCOUNTS_DIR=str(tmp_path / 'system_accounts'),
        SCHOOL_ACCOUNTS_DIR=str(tmp_path / 'school_accounts'),
        GuestTokenStore=guest_token_store.GuestTokenStore,
        auth_system=SimpleNamespace(check_permission=lambda *args: False),
        is_valid_school_username=lambda value: value.isdigit() and len(value) >= 4,
    )
    for module in (auth_system, api_runtime, runtime_models):
        monkeypatch.setattr(module, '_main', lambda: runtime)
    return tmp_path, policy, store, runtime


def test_user_data_and_cache_signature_are_database_backed(database_runtime):
    root, policy, store, runtime = database_runtime
    auth = object.__new__(auth_system.AuthSystem)
    auth.invalidate_user_list_cache = lambda: None
    user_path = root / 'system_accounts' / 'test-user.json'
    user_path.parent.mkdir()
    auth._save_user_data(str(user_path), {'name': '数据库用户'})
    assert store.get('system_accounts', 'test-user.json').content
    assert not user_path.exists()
    paths = auth._user_list_cache_paths()
    assert str(user_path) in paths
    assert auth._user_list_cache_signature_for_paths(paths)[0][2] > 0


def test_school_account_ua_persists_without_creating_json_file(database_runtime):
    root, policy, store, runtime = database_runtime
    account_path = root / 'school_accounts/user_accounts/owner.json'
    account_path.parent.mkdir(parents=True)
    api = object.__new__(api_runtime.Api)
    api._get_user_accounts_file = lambda owner: str(account_path)
    api._load_school_account_stats_from_ini = lambda user: {'overdue_count': 0, 'completed_count': 0}
    api._save_school_account_stats_to_ini = lambda *args: None
    api._save_user_school_accounts('owner', {'10001': {'password': 'test-only-password', 'ua': 'account-UA'}})
    assert not account_path.exists()
    assert api._load_user_school_accounts('owner')['10001']['ua'] == 'account-UA'
    assert store.get('school_accounts', 'user_accounts/owner.json') is not None


def test_user_token_and_guest_token_round_trip_in_database(database_runtime):
    root, policy, store, runtime = database_runtime
    tokens = runtime_models.TokenManager(str(root / 'tokens'))
    token = tokens.create_token('test-owner')
    assert tokens.verify_token('test-owner', 'session', token) == (True, 'valid')
    guest = tokens.guest_store.create('guest-session')
    assert len(guest) > 20
    assert store.get('tokens', 'guests/guest-session.json') is not None
    assert not list((root / 'tokens').glob('*.json'))


def test_business_log_file_stays_on_disk(database_runtime):
    root, policy, store, runtime = database_runtime
    target = root / 'logs' / 'audit.jsonl'
    target.parent.mkdir()
    with storage_io.open(target, 'a', encoding='utf-8') as handle:
        handle.write('{"action":"test"}\n')
    assert target.read_text(encoding='utf-8') == '{"action":"test"}\n'
    assert not any(store.list(namespace) for namespace in policy.roots)


def test_main_directory_index_reads_existing_database_document(database_runtime):
    import main
    root, policy, store, runtime = database_runtime
    target = root / 'background_tasks/_index.json'
    store.put('background_tasks', '_index.json', b'{"tasks":{"existing-record":{}}}')
    main._ensure_json_index_file(str(target), 'tasks')
    assert json.loads(store.get('background_tasks', '_index.json').content)['tasks'] == {'existing-record': {}}
    assert not target.exists()


def test_mysql_startup_configuration_failure_returns_nonzero_exit():
    import os
    import subprocess
    import sys
    from pathlib import Path
    environment = dict(os.environ, APP_STORAGE_BACKEND='mysql', MYSQL_USER='', MYSQL_DATABASE='')
    process = subprocess.run([sys.executable, 'main.py', '--port', '5000'],
        cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, timeout=20)
    assert process.returncode != 0
