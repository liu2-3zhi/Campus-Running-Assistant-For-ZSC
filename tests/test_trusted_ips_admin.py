"""Pure-text proxy rules are authenticated, versioned database settings."""
import ast
import copy
import functools
import logging
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, g, jsonify, request
import pytest

import business_storage
import main
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore
import trusted_ip


SERVER_PATH = Path(__file__).resolve().parents[1] / 'web_server.py'
RULES_PATH = '/api/admin/trusted-ips'
SESSION_ID = '11111111-1111-4111-8111-111111111111'
ORIGIN_SESSION_ID = '22222222-2222-4222-8222-222222222222'


def _load_function(name, namespace):
    tree = ast.parse(SERVER_PATH.read_text(encoding='utf-8'))
    node = next((node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == name), None)
    if node is not None:
        module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]))
        exec(compile(module, str(SERVER_PATH), 'exec'), namespace)


@pytest.fixture
def rules_app(tmp_path, monkeypatch):
    root = tmp_path / 'program'
    store = RelationalStore(DatabaseSettings(root=root))
    store.init_schema(ready=True)
    runtime = business_storage.StorageRuntime('sqlite', business_storage.StoragePolicy(root, {}), store)
    monkeypatch.setattr(business_storage, '_runtime', runtime)
    monkeypatch.setattr(trusted_ip, '_trusted_ip_networks_cache', None)
    monkeypatch.setattr(trusted_ip, '_trusted_ip_networks_cache_mtime', None)
    app = Flask(__name__)
    app.config['TESTING'] = True
    auth = SimpleNamespace(
        check_permission=Mock(return_value=True),
        get_account_cancellation_status=Mock(return_value=None),
        log_audit=Mock(),
    )
    session = SimpleNamespace(is_authenticated=True, is_guest=False,
                              auth_username='administrator', _web_session_id=SESSION_ID)
    facade = SimpleNamespace(
        request=request, jsonify=jsonify, g=g, auth_system=auth,
        normalize_session_uuid=main.normalize_session_uuid,
        _is_safe_auth_username=main._is_safe_auth_username,
        ADMIN_ORIGIN_SESSION_HEADER='X-Admin-Origin-Session-ID',
        resolve_admin_origin_session_context=Mock(return_value=None),
        resolve_admin_view_identity=Mock(return_value=None),
        _verify_session_cookie_token=lambda sid, user, token: (
            sid == SESSION_ID and user == 'administrator' and token == 'fixture-token'),
        TRUSTED_IPS_FILE=str(root / 'trusted_ips.txt'),
        _trusted_ip_networks_lock=threading.Lock(),
        _BUILTIN_TRUSTED_PROXY_NETWORKS=main._BUILTIN_TRUSTED_PROXY_NETWORKS,
    )
    monkeypatch.setattr(trusted_ip, '_main', lambda: facade)
    namespace = {
        'app': app, '_main': lambda: facade, 'functools': functools,
        'web_sessions': {SESSION_ID: session}, 'web_sessions_lock': threading.Lock(),
        'logging': logging, 'time': time,
    }
    _load_function('login_required', namespace)
    _load_function('admin_trusted_ips_load', namespace)
    _load_function('admin_trusted_ips_save', namespace)
    client = app.test_client()
    client.set_cookie('auth_token', 'fixture-token')
    try:
        yield SimpleNamespace(app=app, client=client, store=store, root=root,
                              headers={'X-Session-ID': SESSION_ID}, auth=auth, facade=facade)
    finally:
        store.database.dispose()


@pytest.mark.parametrize('method', ['get', 'post'])
def test_routes_require_verified_login_before_storage_access(rules_app, monkeypatch, method):
    read = Mock(wraps=rules_app.store.get)
    monkeypatch.setattr(rules_app.store, 'get', read)
    response = getattr(rules_app.client, method)(RULES_PATH, json={'content': '', 'revision': 0})
    assert response.status_code == 401
    read.assert_not_called()
    rules_app.auth.check_permission.assert_not_called()


def test_cookie_must_match_the_selected_session(rules_app):
    rules_app.client.set_cookie('auth_token', 'wrong-cookie')
    response = rules_app.client.get(RULES_PATH, headers=rules_app.headers)
    assert response.status_code == 401
    rules_app.auth.check_permission.assert_not_called()


@pytest.mark.parametrize('method', ['get', 'post'])
def test_routes_require_modify_config_before_storage_access(rules_app, monkeypatch, method):
    rules_app.auth.check_permission.return_value = False
    read = Mock(wraps=rules_app.store.get)
    write = Mock(wraps=rules_app.store.put)
    monkeypatch.setattr(rules_app.store, 'get', read)
    monkeypatch.setattr(rules_app.store, 'put', write)
    response = getattr(rules_app.client, method)(RULES_PATH, headers=rules_app.headers,
                                               json={'content': '', 'revision': 0})
    assert response.status_code == 403
    rules_app.auth.check_permission.assert_called_once_with('administrator', 'modify_config')
    read.assert_not_called()
    write.assert_not_called()


def test_origin_view_checks_the_verified_admin_instead_of_target_owner(rules_app):
    rules_app.facade.resolve_admin_origin_session_context.return_value = {
        'username': 'original-admin', 'api_instance': SimpleNamespace(),
        'session_id': ORIGIN_SESSION_ID,
    }
    response = rules_app.client.get(RULES_PATH, headers={
        **rules_app.headers, 'X-Admin-Origin-Session-ID': ORIGIN_SESSION_ID,
    })
    assert response.status_code == 200
    rules_app.auth.check_permission.assert_called_once_with('original-admin', 'modify_config')


def test_missing_rule_record_is_empty_revision_zero_without_creating_a_file(rules_app):
    response = rules_app.client.get(RULES_PATH, headers=rules_app.headers)
    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'content': '', 'revision': 0}
    assert 'no-store' in response.headers.get('Cache-Control', '')
    assert not (rules_app.root / 'trusted_ips.txt').exists()


def test_plain_text_and_crlf_round_trip_without_normalizing_or_touching_disk(rules_app):
    content = '# 管理员的规则\r\n\r\n 203.0.113.4  # 注释保留  \r\n198.51.100.0/24\r\n'
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': content, 'revision': 0})
    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True and result['content'] == content
    assert result['revision'] == 1
    stored = rules_app.store.get('settings', 'trusted_ips.txt')
    assert stored.content == content.encode('utf-8')
    assert rules_app.client.get(RULES_PATH, headers=rules_app.headers).get_json() == {
        'success': True, 'content': content, 'revision': 1,
    }
    assert not (rules_app.root / 'trusted_ips.txt').exists()
    assert not list(rules_app.root.glob('*.tmp'))


@pytest.mark.parametrize('content', ['', ' \r\n\t\n', '*\n', '# comments only\n',
    '203.0.113.1\n2001:db8::1\n198.51.100.0/24\n203.0.113.2-203.0.113.4\n198.51.*\n'])
def test_original_supported_rule_formats_remain_available(rules_app, content):
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': content, 'revision': 0})
    assert response.status_code == 200
    assert rules_app.store.get('settings', 'trusted_ips.txt').content.decode() == content


@pytest.mark.parametrize('payload', [None, [], 'text', 3, True, {},
    {'content': None, 'revision': 0}, {'content': ['203.0.113.1'], 'revision': 0},
    {'content': '*'}, {'content': '*', 'revision': True}, {'content': '*', 'revision': -1},
    {'content': '*', 'revision': 1.0}, {'content': '*', 'revision': '0'}])
def test_save_rejects_invalid_json_payload_types_without_writing(rules_app, payload):
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers, json=payload)
    assert response.status_code == 400
    assert rules_app.store.get('settings', 'trusted_ips.txt') is None


@pytest.mark.parametrize('content_type', ['text/plain', 'application/json'])
def test_save_rejects_missing_or_malformed_json(rules_app, content_type):
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     data='{broken', content_type=content_type)
    assert response.status_code == 400
    assert rules_app.store.get('settings', 'trusted_ips.txt') is None


def test_invalid_rule_reports_line_number_without_echoing_text_or_changing_record(rules_app):
    original = rules_app.store.put('settings', 'trusted_ips.txt', b'# previous rules\n')
    bad_content = '# heading\r\n\r\nprivate-invalid-address\n'
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': bad_content, 'revision': original.revision})
    assert response.status_code == 400
    assert '3' in response.get_json()['message']
    assert 'private-invalid-address' not in response.get_data(as_text=True)
    assert rules_app.store.get('settings', 'trusted_ips.txt') == original
    rules_app.auth.log_audit.assert_not_called()


def test_stale_revision_cannot_overwrite_newer_rules(rules_app):
    original = rules_app.store.put('settings', 'trusted_ips.txt', b'203.0.113.1\n')
    updated = rules_app.store.put('settings', 'trusted_ips.txt', b'203.0.113.2\n')
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': '*', 'revision': original.revision})
    assert response.status_code == 409
    assert rules_app.store.get('settings', 'trusted_ips.txt') == updated
    rules_app.auth.log_audit.assert_not_called()


def test_concurrent_creation_is_protected_by_missing_revision_zero(rules_app):
    rules_app.store.put('settings', 'trusted_ips.txt', b'203.0.113.1\n')
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': '*', 'revision': 0})
    assert response.status_code == 409
    assert rules_app.store.get('settings', 'trusted_ips.txt').content == b'203.0.113.1\n'


@pytest.mark.parametrize('method,operation', [('get', 'get'), ('post', 'put')])
@pytest.mark.parametrize('failure_type', [DatabaseError, ValueError])
def test_database_failure_returns_500_without_falling_back_to_a_stale_file(rules_app, monkeypatch, method, operation, failure_type):
    stale = rules_app.root / 'trusted_ips.txt'
    stale.write_bytes(b'*\n')
    monkeypatch.setattr(rules_app.store, operation,
                        Mock(side_effect=failure_type('synthetic database failure')))
    response = getattr(rules_app.client, method)(RULES_PATH, headers=rules_app.headers,
                                               json={'content': '# new rules\n', 'revision': 0})
    assert response.status_code == 500
    assert response.get_json()['success'] is False
    assert 'synthetic database failure' not in response.get_data(as_text=True)
    assert stale.read_bytes() == b'*\n'


def test_only_fixed_rule_record_is_written_when_payload_contains_a_path(rules_app):
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers, json={
        'content': '# valid rules\n', 'revision': 0, 'path': '../../other.txt',
        'filename': 'another-setting.txt', 'namespace': 'system_accounts',
    })
    assert response.status_code == 200
    assert rules_app.store.keys('settings') == ['trusted_ips.txt']
    assert rules_app.store.keys('system_accounts') == []
    assert not (rules_app.root / 'another-setting.txt').exists()


def test_invalid_unicode_is_a_validation_error_without_echoing_the_string(rules_app):
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': '# \ud800', 'revision': 0})
    assert response.status_code == 400
    assert '\\ud800' not in response.get_data(as_text=True)
    assert rules_app.store.get('settings', 'trusted_ips.txt') is None


def test_save_invalidates_actual_proxy_cache_and_next_request_reloads_rules(rules_app):
    rules_app.store.put('settings', 'trusted_ips.txt', b'203.0.113.1\n')
    previous = trusted_ip._get_trusted_ip_networks()
    assert previous.matches('203.0.113.1')
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': '198.51.100.4\n', 'revision': 1})
    assert response.status_code == 200
    assert trusted_ip._trusted_ip_networks_cache is None
    updated = trusted_ip._get_trusted_ip_networks()
    assert updated is not previous and updated.matches('198.51.100.4')
    assert not updated.matches('203.0.113.1')


def test_audit_contains_metadata_without_rule_content(rules_app):
    content = '# secret operator comment\n203.0.113.9\n'
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': content, 'revision': 0})
    assert response.status_code == 200
    rules_app.auth.log_audit.assert_called_once()
    arguments = rules_app.auth.log_audit.call_args.args
    assert arguments[0] == 'administrator'
    assert arguments[1] == 'update_trusted_ips'
    assert 'bytes=' in arguments[2] and 'lines=' in arguments[2] and 'revision=1' in arguments[2]
    assert 'secret operator comment' not in str(arguments)
    assert '203.0.113.9' not in str(arguments)


def test_audit_failure_does_not_report_a_committed_save_as_failed(rules_app):
    rules_app.auth.log_audit.side_effect = RuntimeError('synthetic audit failure')
    response = rules_app.client.post(RULES_PATH, headers=rules_app.headers,
                                     json={'content': '# valid rules\n', 'revision': 0})
    assert response.status_code == 200
    assert rules_app.store.get('settings', 'trusted_ips.txt').revision == 1
