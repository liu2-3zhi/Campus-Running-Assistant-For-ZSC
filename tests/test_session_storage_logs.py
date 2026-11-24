"""Persisted session messages describe database records, not physical files."""
import hashlib
import json
import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
import session_state
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def persisted_session(tmp_path, monkeypatch):
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    store.init_schema(ready=True)
    runtime = StorageRuntime('sqlite', StoragePolicy(tmp_path, {}), store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *args: runtime)
    sid = '11111111-1111-4111-8111-111111111111'
    key = hashlib.sha256(sid.encode()).hexdigest() + '.json'
    facade = SimpleNamespace(SESSION_STORAGE_DIR=str(tmp_path / 'sessions'),
        session_file_locks_lock=threading.Lock(), session_file_locks={},
        _load_session_index=lambda: {sid: key[:-5]})
    monkeypatch.setattr(session_state, '_main', lambda: facade)
    yield SimpleNamespace(store=store, sid=sid, key=key, facade=facade)
    store.database.dispose()


def put_session(h, *, sid=None, last_accessed=None):
    state = {'session_id': sid or h.sid, 'last_accessed': time.time() if last_accessed is None else last_accessed,
             'auth_username': 'owner', 'login_success': False}
    h.store.put('sessions', h.key, json.dumps(state).encode())
    return state


def test_sqlite_session_load_reports_a_persistent_record(persisted_session, caplog):
    h = persisted_session
    expected = put_session(h)
    with caplog.at_level(logging.INFO):
        assert session_state.load_session_state(h.sid) == expected
    assert '持久化会话' in caplog.text and '记录键' in caplog.text
    assert '从文件' not in caplog.text


def test_expired_sqlite_session_cleanup_reports_a_record_key(persisted_session, caplog):
    h = persisted_session
    put_session(h, last_accessed=time.time() - 8 * 86400)
    with caplog.at_level(logging.INFO):
        assert session_state.load_session_state(h.sid) is None
    assert not h.store.exists('sessions', h.key)
    assert '会话记录' in caplog.text and '记录键' in caplog.text
    assert '会话文件' not in caplog.text


def test_mismatched_sqlite_session_reports_a_record(persisted_session, caplog):
    h = persisted_session
    put_session(h, sid='22222222-2222-4222-8222-222222222222')
    with caplog.at_level(logging.WARNING):
        assert session_state.load_session_state(h.sid) is None
    assert '会话记录UUID不匹配' in caplog.text
    assert '会话文件' not in caplog.text


def test_startup_restore_reports_the_record_key(persisted_session, caplog, monkeypatch):
    h = persisted_session
    put_session(h)
    monkeypatch.setattr(main, 'SESSION_STORAGE_DIR', h.facade.SESSION_STORAGE_DIR)
    monkeypatch.setattr(main, '_load_session_index', h.facade._load_session_index)
    monkeypatch.setattr(main, '_save_session_index', Mock())
    monkeypatch.setattr(main, 'web_sessions', {}, raising=False)
    monkeypatch.setattr(main, 'session_activity', {}, raising=False)
    monkeypatch.setattr(main, 'Api', lambda args: SimpleNamespace(auth_username='owner'))
    monkeypatch.setattr(main, 'restore_session_to_api_instance', lambda *args: None)
    with caplog.at_level(logging.INFO):
        main.load_all_sessions(SimpleNamespace())
    assert h.sid in main.web_sessions
    assert '记录键' in caplog.text and '持久化会话' in caplog.text
    assert '文件:' not in caplog.text
