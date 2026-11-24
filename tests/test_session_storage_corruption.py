"""A broken stored session must not break login or unrelated sessions."""
import ast
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, jsonify
import pytest
from sqlalchemy import delete, select

import main
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore
from test_relational_mysql import relational_mysql


@pytest.fixture(params=['sqlite', 'mysql'])
def sessions(tmp_path, monkeypatch, request):
    if request.param == 'mysql':
        store = request.getfixturevalue('relational_mysql')
    else:
        store = RelationalStore(DatabaseSettings(root=tmp_path))
        store.init_schema(ready=True)
    runtime = StorageRuntime(request.param, StoragePolicy(tmp_path, {}), store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    monkeypatch.setattr(main, 'SESSION_STORAGE_DIR', str(tmp_path / 'sessions'))
    ids = {'broken': '11111111-1111-4111-8111-111111111111',
           'healthy': '22222222-2222-4222-8222-222222222222',
           'other': '33333333-3333-4333-8333-333333333333'}
    keys = {name: hashlib.sha256(sid.encode()).hexdigest() + '.json' for name, sid in ids.items()}
    for name, sid in ids.items():
        state = {'session_id': sid, 'auth_username': 'other' if name == 'other' else 'owner',
                 'last_accessed': time.time(), 'created_at': time.time(), 'is_guest': True,
                 'params': {'fixture': name}, 'user_data': {'username': name}}
        store.put('sessions', keys[name], json.dumps(state).encode())
    # Reproduce a registry whose root entity has been removed. In v3 the
    # snapshot/profile belong to that same aggregate, without child-row chains.
    with store.database.connection() as connection:
        connection.execute(delete(store.entities['account_sessions']).where(
            store.entities['account_sessions'].c.document_id == store._identity('sessions', keys['broken'])))
    yield SimpleNamespace(store=store, ids=ids, keys=keys, root=tmp_path,
                          path=lambda name: tmp_path / 'sessions' / keys[name])
    if request.param == 'sqlite':
        store.database.dispose()


def test_existence_uses_metadata_even_when_session_cannot_be_decoded(sessions):
    path = sessions.path('broken')
    assert storage_io.os.path.exists(path)
    assert storage_io.os.path.isfile(path)
    assert storage_io.os.path.lexists(path)
    with pytest.raises(ValueError, match='Missing stored entity reference'):
        storage_io.open(path)


def test_glob_lists_corrupt_session_without_decoding_it(sessions):
    paths = storage_io.glob.glob(str(sessions.root / 'sessions' / '*.json'))
    assert set(paths) == {str(sessions.path(name)) for name in sessions.ids}


def test_remove_corrupt_session_cascades_without_reading_its_body(sessions):
    storage_io.os.remove(sessions.path('broken'))
    assert not sessions.store.exists('sessions', sessions.keys['broken'])
    with sessions.store.database.connection() as connection:
        for name in ('account_sessions',):
            table = sessions.store.entities[name]
            assert connection.execute(select(table.c.row_id).where(table.c.document_id ==
                sessions.store._identity('sessions', sessions.keys['broken']))).first() is None
    assert json.loads(sessions.store.get('sessions', sessions.keys['healthy']).content)['session_id'] == sessions.ids['healthy']
    with pytest.raises(FileNotFoundError):
        storage_io.os.remove(sessions.path('broken'))


@pytest.mark.parametrize('operation', ['exists', 'isfile', 'remove'])
def test_metadata_database_failure_never_uses_a_physical_session(sessions, monkeypatch, operation):
    path = sessions.path('healthy')
    path.parent.mkdir(exist_ok=True)
    path.write_text('{"stale":"physical"}', encoding='utf-8')
    def unavailable(*args, **kwargs):
        raise DatabaseError('synthetic database unavailable')
    monkeypatch.setattr(sessions.store, 'delete' if operation == 'remove' else 'exists', unavailable)
    with pytest.raises(DatabaseError, match='synthetic database unavailable'):
        (storage_io.os.remove if operation == 'remove' else getattr(storage_io.os.path, operation))(path)
    assert path.read_text(encoding='utf-8') == '{"stale":"physical"}'


def route_client(name, facade):
    source = Path(main.__file__).with_name('web_server.py')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    app = Flask(__name__)
    app.config['TESTING'] = True
    namespace = {'app': app, '_main': lambda: facade, 'os': storage_io.os,
                 'open': storage_io.open, 'json': json, 'hashlib': hashlib, 'logging': logging,
                 '_get_config_value': getattr(facade, '_get_config_value', None),
                 'web_sessions_lock': threading.RLock(), 'web_sessions': {
                     'auth-only': SimpleNamespace(auth_username='owner', is_guest=False)}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return app.test_client()


def test_get_config_returns_json_and_counts_readable_guest_sessions(sessions):
    facade = SimpleNamespace(jsonify=jsonify, auth_system=SimpleNamespace(config=None),
        _get_config_value=lambda *args, **kwargs: True,
        _get_guest_config=lambda config: {'guest_session_inactivity_timeout': 300,
                                        'max_active_guest_sessions': 10},
        _count_active_guest_sessions=main._count_active_guest_sessions)
    response = route_client('auth_get_config', facade).get('/auth/get_config')
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['active_guest_sessions'] == 2


def test_auth_only_context_lists_healthy_owned_sessions_and_skips_broken(sessions):
    facade = SimpleNamespace(jsonify=jsonify, resolve_request_session_id=lambda: 'auth-only',
        auth_system=SimpleNamespace(get_user_sessions=lambda owner: list(sessions.ids.values()),
                                   get_user_details=lambda owner: {'max_sessions': 5}),
        get_session_file_path=lambda sid: str(sessions.root / 'sessions' / (hashlib.sha256(sid.encode()).hexdigest() + '.json')))
    response = route_client('auth_user_sessions', facade).get('/auth/user/sessions')
    assert response.status_code == 200
    assert response.json['success'] is True
    assert [item['session_id'] for item in response.json['sessions']] == [sessions.ids['healthy']]


def test_startup_cleans_broken_session_and_keeps_healthy_sessions(sessions, monkeypatch):
    monkeypatch.setattr(main, '_load_session_index', lambda: {})
    monkeypatch.setattr(main, '_save_session_index', Mock())
    monkeypatch.setattr(main, 'web_sessions', {}, raising=False)
    monkeypatch.setattr(main, 'session_activity', {}, raising=False)
    monkeypatch.setattr(main, 'Api', lambda args: SimpleNamespace())
    monkeypatch.setattr(main, 'restore_session_to_api_instance', lambda api, state: None)
    main.load_all_sessions(SimpleNamespace())
    assert not sessions.store.exists('sessions', sessions.keys['broken'])
    assert set(main.web_sessions) == {sessions.ids['healthy'], sessions.ids['other']}
    assert main._save_session_index.call_args.args[0] == {
        sessions.ids[name]: sessions.keys[name][:-5] for name in ('healthy', 'other')}
