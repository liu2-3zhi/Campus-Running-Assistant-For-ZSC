"""Bound database metadata reads without exposing business bodies or credentials."""
import hashlib
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import event, update

import auth_system
import storage_io
from business_storage import StoragePolicy, StorageRuntime
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore
from test_relational_mysql import relational_mysql


@pytest.fixture(params=['sqlite', 'mysql'])
def listing_runtime(tmp_path, monkeypatch, request):
    if request.param == 'mysql':
        store = request.getfixturevalue('relational_mysql')
    else:
        store = RelationalStore(DatabaseSettings(root=tmp_path, sqlite_path=':memory:'))
        store.init_schema(ready=True)
    for index in range(12):
        owner = 'probe-' + str(index)
        key = hashlib.sha256(owner.encode()).hexdigest()
        store.put('system_accounts', key + '.json', json.dumps({
            'auth_username': owner, 'nickname': 'before', 'group': 'user',
            'session_ids': [], 'last_login': 1,
        }).encode())
        store.put('school_accounts', 'user_accounts/' + key + '.json', json.dumps({
            'school-' + str(index): {'password': 'fixture-only', 'ua': 'ua-' + str(index)},
        }).encode())
    policy = StoragePolicy(tmp_path, {})
    runtime = StorageRuntime(request.param, policy, store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    facade = SimpleNamespace(SYSTEM_ACCOUNTS_DIR=str(tmp_path / 'system_accounts'),
                             SCHOOL_ACCOUNTS_DIR=str(tmp_path / 'school_accounts'),
                             _auth_username_storage_key=lambda owner: hashlib.sha256(owner.encode()).hexdigest())
    monkeypatch.setattr(auth_system, '_main', lambda: facade)
    auth = object.__new__(auth_system.AuthSystem)
    yield store, auth, facade, tmp_path
    if request.param == 'sqlite':
        store.database.dispose()


@contextmanager
def statements(store):
    queries = []
    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            queries.append(statement)
    event.listen(store.database.engine, 'before_cursor_execute', record)
    try:
        yield queries
    finally:
        event.remove(store.database.engine, 'before_cursor_execute', record)


def test_directory_and_exists_queries_never_reconstruct_entities(listing_runtime, record_property):
    store, auth, facade, root = listing_runtime
    with statements(store) as queries:
        assert len(storage_io.os.listdir(facade.SYSTEM_ACCOUNTS_DIR)) == 12
        assert storage_io.os.path.isdir(root / 'school_accounts/user_accounts')
        assert storage_io.os.path.exists(root / 'system_accounts' / (facade._auth_username_storage_key('probe-0') + '.json'))
        assert storage_io.os.path.isfile(root / 'system_accounts' / (facade._auth_username_storage_key('probe-1') + '.json'))
        assert not store.exists('system_accounts', facade._auth_username_storage_key('missing') + '.json')
    assert len(queries) <= 6
    assert all(store.registry.name in query and store.entities['users'].name not in query for query in queries)
    record_property('select_count', len(queries))


def test_auth_signature_uses_fixed_metadata_queries(listing_runtime, record_property):
    store, auth, facade, root = listing_runtime
    with statements(store) as queries:
        first = auth._current_user_list_cache_signature()
    assert len(first) == 24
    assert len(queries) == 2
    assert all(store.registry.name in query and 'layout' not in query for query in queries)
    record_property('select_count', len(queries))


def test_user_list_rebuild_is_bulk_and_keeps_owners_isolated(listing_runtime, record_property):
    store, auth, facade, root = listing_runtime
    with statements(store) as queries:
        result = auth.list_users()
    assert len(result) == 12
    assert len(queries) <= 16
    record_property('select_count', len(queries))
    for entry in result:
        index = entry['auth_username'].split('-')[-1]
        assert entry['school_accounts'] == ['school-' + index]
        assert entry['nickname'] == 'before'
        assert 'password' not in entry and 'ua' not in entry


def test_login_update_does_not_accept_an_unrelated_changed_signature(listing_runtime, record_property):
    store, auth, facade, root = listing_runtime
    auth.list_users()
    other_key = hashlib.sha256(b'probe-1').hexdigest() + '.json'
    data = json.loads(store.get('system_accounts', other_key).content)
    data['nickname'] = 'changed'
    store.put('system_accounts', other_key, json.dumps(data).encode())
    with statements(store) as queries:
        auth._update_user_list_login('probe-0', 100, 'test-ip')
    assert queries == []
    record_property('select_count', len(queries))
    users = {entry['auth_username']: entry for entry in auth.list_users()}
    assert users['probe-1']['nickname'] == 'changed'


def test_hot_user_list_only_checks_registry_versions(listing_runtime, record_property):
    store, auth, facade, root = listing_runtime
    expected = auth.list_users()
    with statements(store) as queries:
        result = auth.list_users()
    assert result == expected
    assert len(queries) == 2
    assert all(store.registry.name in query and 'layout' not in query for query in queries)
    record_property('select_count', len(queries))


def test_direct_sql_change_is_visible_after_one_refresh_period(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    clock = [10.0]
    monkeypatch.setattr(auth_system.time, 'monotonic', lambda: clock[0])
    assert auth.list_users()[0]['nickname'] == 'before'
    with store.database.connection() as connection:
        table = store.entities['users']
        connection.execute(update(table).where(table.c.auth_username == 'probe-0').values(nickname='after!'))
    clock[0] += auth_system.USER_LIST_CACHE_REFRESH_SECONDS + .1
    users = {entry['auth_username']: entry for entry in auth.list_users()}
    assert users['probe-0']['nickname'] == 'after!'


def test_managed_lookup_does_not_fall_back_after_database_error(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    path = root / 'system_accounts/stale.json'
    path.parent.mkdir()
    path.write_text('{}', encoding='utf-8')
    def fail(*args):
        raise DatabaseError('offline')
    monkeypatch.setattr(store, 'exists', fail)
    with pytest.raises(DatabaseError, match='offline'):
        storage_io.os.path.exists(path)


def test_registry_metadata_keeps_literal_prefix_and_nested_directory_names(listing_runtime):
    store, auth, facade, root = listing_runtime
    store.put('system_accounts', 'nested/a%_b.json', b'{}')
    store.put('system_accounts', 'nested/axxb.json', b'{}')
    assert store.keys('system_accounts', 'nested/a%_') == ['nested/a%_b.json']
    assert storage_io.os.listdir(root / 'system_accounts/nested') == ['a%_b.json', 'axxb.json']
    assert storage_io.os.listdir(bytes(root / 'system_accounts/nested')) == [b'a%_b.json', b'axxb.json']


def test_snapshot_rebuild_does_not_hold_login_cache_lock(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    auth.list_users()
    auth._user_list_cache_signature = None
    entered, resume = threading.Event(), threading.Event()
    original = auth._read_user_list_uncached
    def pause_read():
        entered.set()
        assert resume.wait(3)
        return original()
    monkeypatch.setattr(auth, '_read_user_list_uncached', pause_read)
    worker = threading.Thread(target=auth.list_users)
    worker.start()
    try:
        assert entered.wait(2)
        acquired = auth._user_list_cache_lock.acquire(timeout=.2)
        assert acquired, 'background DB read must not block login metadata update'
        if acquired:
            auth._user_list_cache_lock.release()
    finally:
        resume.set()
        worker.join(3)
    assert not worker.is_alive()


def test_bulk_snapshot_and_versions_filter_the_same_direct_json_documents(listing_runtime):
    store, auth, facade, root = listing_runtime
    before = auth._current_user_list_cache_signature()
    store.put('system_accounts', 'nested/hidden.json', b'{"auth_username":"nested-owner"}')
    store.put('system_accounts', '_index.json', b'{"accounts":{}}')
    store.put('school_accounts', 'user_accounts/nested/hidden.json', b'{}')
    assert auth._current_user_list_cache_signature() == before
    users = auth.list_users()
    assert len(users) == 12
    assert {item['auth_username'] for item in users} == {'probe-' + str(i) for i in range(12)}


def test_bulk_snapshot_keeps_bad_shape_defaults_and_plain_owner_paths(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    store.put('system_accounts', 'invalid-shape.json', b'[]')
    store.put('system_accounts', 'missing-owner.json', b'{"nickname":"invalid"}')
    key = hashlib.sha256(b'probe-0').hexdigest()
    store.delete('school_accounts', 'user_accounts/' + key + '.json')
    store.put('school_accounts', 'user_accounts/probe-0.json', b'{"plain-school":"fixture-only"}')
    monkeypatch.setattr(facade, '_auth_username_storage_key',
                        lambda owner: owner if owner == 'probe-0' else hashlib.sha256(owner.encode()).hexdigest())
    users = {item['auth_username']: item for item in auth.list_users()}
    assert len(users) == 12
    assert users['probe-0']['school_accounts'] == ['plain-school']
    assert users['probe-1']['school_accounts'] == ['school-1']
    assert users['probe-0']['available_runs'] == 0
    assert users['probe-0']['last_login_city'] == '未知'


def test_custom_managed_directory_paths_use_the_same_bulk_metadata(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    policy = StoragePolicy(root, {'System': {'system_accounts_dir': 'business/users',
                                            'school_accounts_dir': 'business/schools'}})
    runtime = StorageRuntime(store.settings.backend, policy, store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    monkeypatch.setattr(facade, 'SYSTEM_ACCOUNTS_DIR', str(root / 'business/users'))
    monkeypatch.setattr(facade, 'SCHOOL_ACCOUNTS_DIR', str(root / 'business/schools'))
    signature = auth._current_user_list_cache_signature()
    assert len(signature) == 24
    assert all(str(root / 'business') in entry[0] for entry in signature)
    assert len(auth.list_users()) == 12


def test_bulk_bindings_keep_case_sensitive_owners_separate(listing_runtime, monkeypatch):
    store, auth, facade, root = listing_runtime
    monkeypatch.setattr(facade, '_auth_username_storage_key', lambda owner: owner)
    for owner, school, ua in [('CaseOwner', 'upper-school', 'upper-UA'),
                              ('caseowner', 'lower-school', 'lower-UA')]:
        user_key = hashlib.sha256(owner.encode()).hexdigest() + '.json'
        store.put('system_accounts', user_key, json.dumps({'auth_username': owner}).encode())
        store.put('school_accounts', 'user_accounts/' + owner + '.json', json.dumps({
            school: {'password': 'fixture-only', 'ua': ua},
        }).encode())
    users = {user['auth_username']: user for user in auth.list_users()}
    assert users['CaseOwner']['school_accounts'] == ['upper-school']
    assert users['caseowner']['school_accounts'] == ['lower-school']
    assert json.loads(store.get('school_accounts', 'user_accounts/CaseOwner.json').content)['upper-school']['ua'] == 'upper-UA'
    assert json.loads(store.get('school_accounts', 'user_accounts/caseowner.json').content)['lower-school']['ua'] == 'lower-UA'
