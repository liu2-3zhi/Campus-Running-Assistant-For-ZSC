"""Selecting one saved account must not load every account's billing stats."""
import ast
import configparser
import json
import logging
from contextlib import contextmanager
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import event
from flask import Flask, jsonify, request

import api_runtime
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def credential_runtime(tmp_path, monkeypatch):
    store = RelationalStore(DatabaseSettings(root=tmp_path, sqlite_path=':memory:'))
    store.init_schema(ready=True)
    policy = StoragePolicy(tmp_path, {})
    runtime = StorageRuntime('sqlite', policy, store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    check_permission = Mock(return_value=False)
    facade = SimpleNamespace(
        SCHOOL_ACCOUNTS_DIR=str(tmp_path / 'school_accounts'),
        _auth_username_storage_key=lambda owner: owner,
        is_valid_school_username=lambda value: isinstance(value, str) and value.isdigit() and len(value) >= 4,
        auth_system=SimpleNamespace(check_permission=check_permission),
    )
    monkeypatch.setattr(api_runtime, '_main', lambda: facade)
    api = object.__new__(api_runtime.Api)
    api.user_dir = facade.SCHOOL_ACCOUNTS_DIR
    api.auth_username = 'owner'
    api.auth_group = 'super_admin'
    api.is_guest = False
    api.is_authenticated = True
    api.params = {'test-only': True}
    api.device_ua = 'session-UA'
    api.user_data = SimpleNamespace(name='', student_id='')
    api._load_school_account_stats_from_ini = Mock(side_effect=AssertionError('selection must not read stats'))
    yield store, api, facade
    store.database.dispose()


def put_owner(store, facade, owner, accounts):
    key = facade._auth_username_storage_key(owner)
    store.put('system_accounts', key + '.json', json.dumps({'auth_username': owner}).encode())
    store.put('school_accounts', 'user_accounts/' + key + '.json', json.dumps(accounts).encode())


@contextmanager
def selects(store):
    statements = []
    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(store.database.engine, 'before_cursor_execute', record)
    try:
        yield statements
    finally:
        event.remove(store.database.engine, 'before_cursor_execute', record)


def test_selecting_one_of_446_owned_accounts_skips_stats_and_global_scans(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    accounts = {str(10000 + index): {'password': 'fixture-' + str(index), 'ua': 'UA-' + str(index)}
                for index in range(446)}
    put_owner(store, facade, 'owner', accounts)
    monkeypatch.setattr(store, 'list', Mock(side_effect=AssertionError('owned selection must not scan bindings')))
    with selects(store) as statements:
        result = api.on_user_selected('10223')
    api._load_school_account_stats_from_ini.assert_not_called()
    store.list.assert_not_called()
    assert len(statements) <= 6
    assert result['password'] == 'fixture-223'
    assert result['ua'] == 'UA-223'
    assert result['params'] == api.params


def test_owned_credentials_win_and_keep_each_owners_ua(credential_runtime):
    store, api, facade = credential_runtime
    for owner in ('owner', 'other'):
        put_owner(store, facade, owner, {'10001': {'password': owner + '-password', 'ua': owner + '-UA'}})
    facade.auth_system.check_permission.return_value = True
    for owner in ('owner', 'other'):
        api.auth_username = owner
        result = api.on_user_selected('10001')
        assert result['password'] == owner + '-password'
        assert result['ua'] == owner + '-UA'
    api._load_school_account_stats_from_ini.assert_not_called()


def test_legacy_string_password_uses_session_ua_without_stats(credential_runtime):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'owner', {'10001': 'fixture-legacy'})
    result = api.on_user_selected('10001')
    assert result['password'] == 'fixture-legacy'
    assert result['ua'] == 'session-UA'
    api._load_school_account_stats_from_ini.assert_not_called()


def test_ordinary_owner_cannot_load_another_owners_credentials(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'other', {'10001': {'password': 'other-password', 'ua': 'other-UA'}})
    api.auth_group = 'user'
    api.auth_system = facade.auth_system
    monkeypatch.setattr(store, 'list', Mock(side_effect=AssertionError('ordinary owner must not scan bindings')))
    result = api.on_user_selected('10001')
    assert result['password'] == ''
    assert result['ua'] == ''
    store.list.assert_not_called()
    api._load_school_account_stats_from_ini.assert_not_called()


def test_admin_group_alone_does_not_grant_global_aggregation(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'other', {'10001': {'password': 'other-password', 'ua': 'other-UA'}})
    monkeypatch.setattr(store, 'list', Mock(side_effect=AssertionError('manage_users permission is required')))
    result = api.on_user_selected('10001')
    assert result['password'] == ''
    assert result['ua'] == 'session-UA'
    store.list.assert_not_called()


def test_admin_target_lookup_bulk_reads_bindings_but_never_stats(credential_runtime):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'other', {'10001': {'password': 'other-password', 'ua': 'other-UA'}})
    facade.auth_system.check_permission.return_value = True
    with selects(store) as statements:
        result = api.on_user_selected('10001')
    assert result['password'] == 'other-password'
    assert result['ua'] == 'other-UA'
    assert len(statements) <= 8
    api._load_school_account_stats_from_ini.assert_not_called()


def test_admin_target_legacy_ini_lookup_only_reads_requested_account(credential_runtime):
    store, api, facade = credential_runtime
    store.put('school_accounts', '10001.ini', b'[Config]\npassword=ini-password\n[System]\nUA=ini-UA\n')
    facade.auth_system.check_permission.return_value = True
    result = api.on_user_selected('10001')
    assert result['password'] == 'ini-password'
    assert result['ua'] == 'ini-UA'
    api._load_school_account_stats_from_ini.assert_not_called()


def test_single_account_credentials_own_only_ignores_management_privileges(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'other', {'10001': {'password': 'other-password', 'ua': 'other-UA'}})
    facade.auth_system.check_permission.return_value = True
    monkeypatch.setattr(store, 'list', Mock(side_effect=AssertionError('own-only lookup must not scan bindings')))
    assert api._load_school_account_credentials('owner', '10001', own_only=True) is None
    store.list.assert_not_called()


def test_single_account_lookup_propagates_database_errors(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    monkeypatch.setattr(store, 'get_school_account_credentials',
                        Mock(side_effect=DatabaseError('synthetic database offline')))
    with pytest.raises(DatabaseError, match='synthetic database offline'):
        api._load_school_account_credentials('owner', '10001')


@pytest.mark.parametrize('payload', [{'username': '10001'}, ['10001']])
@pytest.mark.parametrize('visibility,owned,password', [('own', True, 'owner-password'),
                                                      ('own', False, ''), ('none', True, '')])
def test_http_visibility_uses_single_owned_lookup_for_object_and_array(credential_runtime, monkeypatch, payload,
                                                                     visibility, owned, password):
    import route_failure_visibility
    store, api, facade = credential_runtime
    put_owner(store, facade, 'owner', {'10001' if owned else '10002':
                                     {'password': 'owner-password', 'ua': 'owner-UA'}})
    api.auth_group = 'user'
    api.auth_system = facade.auth_system
    facade.auth_system.check_permission.side_effect = lambda owner, permission: permission == 'view_user_details'
    api._load_user_school_accounts = Mock(side_effect=AssertionError('visibility must not load account statistics'))
    facade.request, facade.jsonify = request, jsonify
    facade._is_api_method_allowed = lambda method: method == 'on_user_selected'
    facade.normalize_session_uuid = lambda value: value or ''
    facade.ADMIN_ORIGIN_SESSION_HEADER = 'X-Admin-Origin-Session-ID'
    facade._is_safe_auth_username = lambda owner: True
    facade.token_manager = SimpleNamespace(verify_token=lambda *args: (True, 'valid'), refresh_token=lambda *args: None)
    facade.update_session_activity = lambda session: None
    facade._redact_sensitive_log_value = lambda value: value
    monkeypatch.setattr(route_failure_visibility, 'project_route_failure_response', lambda result, session: result)
    source = Path(api_runtime.__file__).with_name('web_server.py')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'api_call')
    app = Flask(__name__)
    namespace = {'app': app, '_main': lambda: facade, 'API_BLACKLIST_PREFIXES': ['_'],
                 'web_sessions': {'business-session': api}, 'web_sessions_lock': threading.RLock(),
                 '_resolve_password_visibility': lambda caller: visibility, 'logging': logging}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    with app.test_client() as client:
        client.set_cookie('auth_token', 'fixture-only')
        result = client.post('/api/on_user_selected', json=payload, headers={'X-Session-ID': 'business-session'})
    assert result.status_code == 200
    assert result.json['password'] == password
    assert result.json['ua'] == ('owner-UA' if owned else '')
    api._load_user_school_accounts.assert_not_called()
    api._load_school_account_stats_from_ini.assert_not_called()


def prepare_initial_data(api, facade):
    api.auth_group = 'user'
    api.config_path = 'fixture-config'
    api._load_global_config = Mock()
    api.global_params = {}
    api.login_success = False
    facade.auth_system.resolve_password_visibility = lambda owner: 'own'
    facade.auth_system.get_user_details = lambda owner: {}
    facade.auth_system.get_theme_config = lambda *args, **kwargs: {}
    facade.auth_system.get_user_theme = lambda owner: {'success': False}
    facade.auth_system.get_available_theme_styles = lambda: []
    facade._read_config_ini = lambda path: configparser.ConfigParser()
    facade.RANDOM_BACKGROUND_IMAGE_DIR = 'fixture-background'
    facade._apply_identity_bundle_to_theme_config = lambda config, session: config
    facade._build_public_map_provider_frontend_payload = lambda *args, **kwargs: {
        'map_provider': 'fixture', 'map_providers': {}, 'map_provider_key_bundle': {},
    }
    facade.js_cache_lock = threading.RLock()
    facade.CDN_FILES = {}
    facade.js_cache_storage, facade.js_cache_last_update = {}, {}


def test_initial_data_own_visibility_reads_only_owned_names_without_stats_or_scans(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    owned = {str(10000 + index): {'password': 'fixture-only', 'ua': 'owner-UA'} for index in range(446)}
    owned.update({'1': {'password': 'invalid'}, 'not-a-school-id': 'invalid'})
    put_owner(store, facade, 'owner', owned)
    put_owner(store, facade, 'unrelated', {'90001': {'password': 'unrelated-only', 'ua': 'unrelated-UA'}})
    prepare_initial_data(api, facade)
    monkeypatch.setattr(store, 'list', Mock(side_effect=AssertionError('own initialization must not scan bindings')))
    result = api.get_initial_data()
    assert result['success'] is True
    api._load_school_account_stats_from_ini.assert_not_called()
    store.list.assert_not_called()
    assert result['users'] == [str(10000 + index) for index in range(446)]


def test_own_names_lookup_propagates_database_failure_and_initial_data_reports_failure(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    prepare_initial_data(api, facade)
    monkeypatch.setattr(store, 'list_school_account_names',
                        Mock(side_effect=DatabaseError('synthetic names database failure')))
    with pytest.raises(DatabaseError, match='synthetic names database failure'):
        api._load_owned_school_account_names('owner')
    result = api.get_initial_data()
    assert result['success'] is False
    assert result['offline'] is True
    assert 'users' not in result


def test_multi_account_picker_reuses_names_and_refreshes_after_write(credential_runtime, monkeypatch):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'owner', {'10001': {'password': 'fixture-only'}})
    put_owner(store, facade, 'unrelated', {'20001': {'password': 'fixture-only'}})
    api._load_user_school_accounts = Mock(side_effect=AssertionError('picker must not rebuild accounts'))
    query = Mock(wraps=store.list_school_account_names)
    monkeypatch.setattr(store, 'list_school_account_names', query)

    assert api.multi_get_all_config_users() == {'users': ['10001']}
    assert api.multi_get_all_config_users() == {'users': ['10001']}
    assert query.call_count == 1
    facade.auth_system.check_permission.return_value = True
    assert api.multi_get_all_config_users() == {'users': ['10001', '20001']}
    facade.auth_system.check_permission.return_value = False
    store.put('school_accounts', 'user_accounts/owner.json', b'{"10002": {}}')
    assert api.multi_get_all_config_users() == {'users': ['10002']}


def test_multi_account_picker_does_not_cache_rolled_back_names(credential_runtime):
    store, api, facade = credential_runtime
    put_owner(store, facade, 'owner', {'10001': {}})
    assert api.multi_get_all_config_users() == {'users': ['10001']}
    with pytest.raises(RuntimeError, match='rollback'):
        with store.transaction():
            store.put('school_accounts', 'user_accounts/owner.json', b'{"10002": {}}')
            assert api.multi_get_all_config_users() == {'users': ['10002']}
            raise RuntimeError('rollback')
    assert api.multi_get_all_config_users() == {'users': ['10001']}
