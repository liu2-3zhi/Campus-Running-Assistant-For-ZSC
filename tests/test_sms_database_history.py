"""SMS audit events live in business storage, never in the code cache."""
import ast
import configparser
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, g, jsonify, request
import pytest

import main
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def history_store(tmp_path, monkeypatch):
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    store.init_schema(ready=True)
    runtime = StorageRuntime('sqlite', StoragePolicy(tmp_path, {}), store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *args: runtime)
    yield store
    store.database.dispose()


def test_new_event_keeps_audit_metadata_and_omits_verification_secrets(history_store):
    from sms_history import SMSHistoryRepository
    repository = SMSHistoryRepository(history_store)
    repository.append({'phone': '13800138000', 'scene': 'register', 'status': 'sent',
                       'response_code': '0', 'timestamp': 1730000000,
                       'code': '654321', 'content': 'secret 654321', 'api_key': 'provider-secret',
                       'auth_username': 'owner', 'ip': '127.0.0.1'})
    stored = history_store.list('sms_records')
    assert len(stored) == 1
    value = json.loads(stored[0].content)
    assert value['phone'] == '13800138000' and value['status'] == 'sent'
    assert value['auth_username'] == 'owner' and value['timestamp'] == 1730000000
    assert value['datetime']
    assert not {'code', 'content', 'api_key'} & set(value)
    assert b'654321' not in stored[0].content and b'provider-secret' not in stored[0].content


def test_query_filters_and_caps_database_records_without_file_fallback(history_store, tmp_path):
    from sms_history import SMSHistoryRepository
    repository = SMSHistoryRepository(history_store)
    for index in range(105):
        history_store.put('sms_records', f'{index}.json', json.dumps({
            'phone': '13800138000', 'timestamp': index, 'datetime': f'2026-11-24 12:00:{index % 60:02}',
            'status': 'sent'}).encode())
    history_store.put('sms_records', 'other.json', b'{"phone":"13900139000","timestamp":999,"datetime":"2026-11-23 12:00:00"}')
    records = repository.list(date='2026-11-24', phone='1380')
    assert len(records) == 100
    assert [r['timestamp'] for r in records] == list(reversed(range(5, 105)))
    assert repository.list(date='2020-01-01') == []


def test_database_query_decodes_only_the_newest_hundred_matching_candidates(history_store, monkeypatch):
    from sms_history import SMSHistoryRepository
    for index in range(240):
        history_store.put('sms_records', f'candidate-{index}.json', json.dumps({
            'phone': '13800138000' if index < 220 else '13900139000',
            'timestamp': index, 'datetime': '2026-11-24 12:00:00' if index >= 20 else '2026-11-23 12:00:00'}).encode())
    decoded = []
    original = history_store._documents
    def reconstruct(connection, rows):
        rows = list(rows)
        decoded.extend(row['record_key'] for row in rows)
        return original(connection, rows)
    monkeypatch.setattr(history_store, '_documents', reconstruct)
    result = SMSHistoryRepository(history_store).list(date='2026-11-24', phone='138')
    assert [r['timestamp'] for r in result] == list(reversed(range(120, 220)))
    assert len(decoded) == 100


def test_database_phone_filter_matches_percent_and_underscore_literally(history_store):
    from sms_history import SMSHistoryRepository
    for key, phone in [('literal', 'x%_y'), ('wildcard', 'xyyz')]:
        history_store.put('sms_records', key + '.json', json.dumps({'phone': phone, 'timestamp': 1}).encode())
    result = SMSHistoryRepository(history_store).list(phone='%_')
    assert [r['phone'] for r in result] == ['x%_y']


def test_legacy_reader_is_repeatable_preserves_payload_types_and_duplicate_lines(tmp_path):
    from sms_history import iter_legacy_sms_records
    path = tmp_path / 'sms_history.jsonl'
    payload = {'phone': '13800138000', 'timestamp': '123.5', 'content': 'historical 654321',
               'unknown_legacy': [True, None]}
    path.write_text(json.dumps(payload) + '\n' + json.dumps(payload) + '\n', encoding='utf-8')
    first = list(iter_legacy_sms_records(path))
    assert first == list(iter_legacy_sms_records(path))
    assert len({row[0] for row in first}) == 2
    assert all(json.loads(row[1]) == payload for row in first)
    assert all(isinstance(row[2], int) for row in first)


def test_legacy_reader_reports_bad_json_instead_of_dropping_history(tmp_path):
    from sms_history import iter_legacy_sms_records
    path = tmp_path / 'sms_history.jsonl'
    path.write_text('{"phone":"13800138000"}\n{broken\n', encoding='utf-8')
    with pytest.raises(ValueError, match=r'line 2'):
        list(iter_legacy_sms_records(path))


def test_history_write_failure_is_logged_and_does_not_escape(history_store, monkeypatch, caplog):
    from sms_history import record_sms_event
    monkeypatch.setattr(history_store, 'put', Mock(side_effect=RuntimeError('synthetic history unavailable')))
    with caplog.at_level(logging.ERROR):
        assert record_sms_event(phone='13800138000', scene='register', status='sent') is False
    assert 'synthetic history unavailable' in caplog.text


def configure_send_routes(monkeypatch, result=b'0', response_error=None):
    config = configparser.RawConfigParser()
    config.read_dict({'Features': {'enable_sms_service': 'true'}, 'SMS_Service_SMSBao': {
        'username': 'fixture-provider', 'api_key': 'fixture-provider-secret',
        'signature': 'test', 'template_register': 'code {code}', 'code_expire_minutes': '5'}})
    monkeypatch.setattr(main, '_read_config_ini', lambda *args: config)
    monkeypatch.setattr(main, 'verify_captcha', lambda *args: (True, ''))
    monkeypatch.setattr(main, 'cache', {}, raising=False)
    monkeypatch.setattr(main, 'sms_verification_codes', {})
    opener = Mock(side_effect=response_error) if response_error else Mock(return_value=SimpleNamespace(read=lambda: result))
    monkeypatch.setattr(main.urllib.request, 'urlopen', opener)
    monkeypatch.setattr(main, 'auth_system', SimpleNamespace(get_user_group=lambda user: 'super_admin'), raising=False)
    app = Flask(__name__)
    @app.before_request
    def user_context():
        g.user = 'owner'
    main._register_sms_routes(app, lambda func: func)
    return app.test_client(), opener


@pytest.mark.parametrize('result,status', [(b'0', 'sent'), (b'30', 'rejected')])
def test_send_code_persists_provider_result_and_keeps_codes_only_in_memory(history_store, monkeypatch, result, status):
    client, opener = configure_send_routes(monkeypatch, result)
    response = client.post('/api/sms/send_code', json={'phone': '13800138000', 'scene': 'register'})
    assert response.json['success'] is (status == 'sent')
    records = history_store.list('sms_records')
    assert len(records) == 1
    record = json.loads(records[0].content)
    assert record['status'] == status and record['response_code'] == result.decode()
    assert record['scene'] == 'register' and 'code' not in record and 'content' not in record
    assert opener.call_count == 1
    assert ('13800138000' in main.sms_verification_codes) is (status == 'sent')


def test_send_code_preserves_success_when_history_database_fails(history_store, monkeypatch):
    client, opener = configure_send_routes(monkeypatch)
    monkeypatch.setattr(history_store, 'put', Mock(side_effect=RuntimeError('synthetic history unavailable')))
    response = client.post('/api/sms/send_code', json={'phone': '13800138000'})
    assert response.json['success'] is True
    assert opener.call_count == 1 and '13800138000' in main.sms_verification_codes


def test_provider_exception_is_recorded_without_request_url_credentials(history_store, monkeypatch):
    client, opener = configure_send_routes(monkeypatch, response_error=OSError('synthetic connection error'))
    response = client.post('/api/sms/send_code', json={'phone': '13800138000'})
    assert response.json['success'] is False
    record = json.loads(history_store.list('sms_records')[0].content)
    assert record['status'] == 'error'
    assert b'fixture-provider-secret' not in history_store.list('sms_records')[0].content
    assert opener.call_count == 1


def test_admin_test_send_persists_audit_without_custom_code(history_store, monkeypatch):
    client, opener = configure_send_routes(monkeypatch)
    response = client.post('/api/sms/test_send', json={'phone': '13800138000', 'code': '654321'})
    assert response.json['success'] is True
    record = history_store.list('sms_records')[0]
    value = json.loads(record.content)
    assert value['source'] == 'admin_test' and value['auth_username'] == 'owner'
    assert b'654321' not in record.content and opener.call_count == 1


def history_route_client(facade, *, manual=False):
    source = Path(main.__file__).with_name('web_server.py')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    name = 'add_manual_verification_code' if manual else 'get_sms_history'
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    app = Flask(__name__)
    namespace = {'app': app, 'login_required': lambda f: f, '_main': lambda: facade,
                 'g': g, 'time': __import__('time'), 'configparser': configparser,
                 'os': storage_io.os, 'open': storage_io.open, 'json': json,
                 're': __import__('re'), 'sms_verification_codes': main.sms_verification_codes,
                 '_emit_verification_codes_update': lambda *args: None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    @app.before_request
    def user_context():
        g.user = 'owner'
        g.api_instance = SimpleNamespace(_web_session_id='fixture-session')
    return app.test_client()


def history_facade(root, allowed=True):
    return SimpleNamespace(auth_system=SimpleNamespace(check_permission=lambda *args: allowed),
        g=g, jsonify=jsonify, request=request,
        LOGIN_LOGS_DIR=str(root / 'logs'),
        _redact_sensitive_display_value=lambda records: [{**r, 'phone': '138****8000'} for r in records])


def test_admin_history_reads_database_and_keeps_permissions_and_redaction(history_store):
    history_store.put('sms_records', 'fixture.json', b'{"phone":"13800138000","timestamp":1,"datetime":"2026-11-24 12:00:00"}')
    client = history_route_client(history_facade(history_store.settings.root))
    response = client.get('/api/admin/sms/history?date=2026-11-24&phone=138')
    assert response.status_code == 200 and response.json['success'] is True
    assert response.json['records'][0]['phone'] == '138****8000'
    denied = history_route_client(history_facade(history_store.settings.root, False)).get('/api/admin/sms/history')
    assert denied.status_code == 403


def test_manual_code_audit_is_database_metadata_only(history_store):
    facade = history_facade(history_store.settings.root)
    config = configparser.RawConfigParser()
    facade._read_config_ini = lambda *args: config
    facade.CONFIG_JSON_FILE = 'unused-config-path'
    facade._cleanup_expired_sms_verification_codes = lambda **kwargs: None
    facade._reset_sms_extend_once_for_phone = lambda phone: None
    response = history_route_client(facade, manual=True).post('/api/admin/sms/add_manual_code',
        json={'phone': '13800138000', 'code': '654321'})
    assert response.json['success'] is True
    document = history_store.list('sms_records')[0]
    record = json.loads(document.content)
    assert record['source'] == 'admin_manual' and record['auth_username'] == 'owner'
    assert b'654321' not in document.content
