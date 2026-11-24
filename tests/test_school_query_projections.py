"""Account pickers and statistics read bounded, non-secret SQL projections."""
from contextlib import contextmanager
import json

import pytest
from sqlalchemy import event, update

from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore
from test_relational_mysql import relational_mysql


@pytest.fixture(params=['sqlite', 'mysql'])
def school_store(tmp_path, request):
    if request.param == 'mysql':
        yield request.getfixturevalue('relational_mysql')
        return
    store = RelationalStore(DatabaseSettings(root=tmp_path, sqlite_path=':memory:'))
    store.init_schema(ready=True)
    try:
        yield store
    finally:
        store.database.dispose()


def bindings(store, owner, values):
    key = owner
    store.put('system_accounts', key + '.json', json.dumps({'auth_username': owner}).encode())
    store.put('school_accounts', 'user_accounts/' + key + '.json', json.dumps(values).encode())


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


def test_picker_keeps_owned_empty_passwords_and_excludes_other_owners(school_store):
    store = school_store
    bindings(store, 'Owner', {'00101': {'password': '', 'ua': 'private'},
                              '00102': None, '00103': 'legacy',
                              'bad-name': {'password': 'not-an-account'}})
    bindings(store, 'owner', {'00999': {'password': 'other'}})
    assert store.list_school_account_names('Owner') == ['00101', '00102', '00103']
    assert store.list_school_account_names('owner') == ['00999']
    assert store.list_school_account_names('absent') == []


def test_admin_picker_adds_only_usable_links_and_legacy_global_credentials(school_store):
    store = school_store
    bindings(store, 'owner', {'00101': {'password': None}})
    bindings(store, 'other', {'00101': {'password': 'shared'}, '00102': 'legacy',
        '00103': {'password': '\t\n\u00a0 '}, '00104': None,
        '00105': {'password': '\t usable \n'}, '00106': {'password': '\u2003\u3000\x85'},
        'bad-name': 'excluded'})
    store.put('school_accounts', '00201.ini', b'[Config]\nPassword=global\n[System]\nUA=secret-UA\n')
    store.put('school_accounts', '00202.ini', b'[Config]\npassword=   \n')
    store.put('school_accounts', '00203.ini', b'[DEFAULT]\nPassword=inherited\n[Config]\nUsername=00203\n')
    store.put('school_accounts', '00204.ini', b'[DEFAULT]\npassword=not-a-config\n[System]\nUA=private\n')
    store.put('school_accounts', 'notes.ini', b'[Config]\npassword=excluded\n')
    assert store.list_school_account_names('owner', include_all=True) == [
        '00101', '00102', '00105', '00201', '00203']


def test_picker_ignores_nested_compatibility_sources(school_store):
    store = school_store
    bindings(store, 'owner', {'00101': {'password': 'own'}})
    store.put('school_accounts', 'nested/user_accounts/owner.json', b'{"00102":"hidden"}')
    store.put('school_accounts', 'nested/00201.ini', b'[Config]\npassword=hidden\n')
    store.put('school_accounts', 'nested/00202.ini', b'[stats]\noverdue_count=9\n')
    assert store.get_school_account_stats(['00202']) == {
        '00202': {'overdue_count': 0, 'completed_count': 0},
    }
    assert store.list_school_account_names('owner', include_all=True) == ['00101']


def test_picker_never_rebuilds_documents_or_selects_credentials(school_store, monkeypatch):
    store = school_store
    for index in range(12):
        bindings(store, 'owner-' + str(index), {str(10000 + index): {'password': 'fixture-private', 'ua': 'secret'}})
    def forbid_documents(*args):
        raise AssertionError('picker must not reconstruct credentials or compatibility documents')
    monkeypatch.setattr(store, '_documents', forbid_documents)
    with selects(store) as queries:
        assert len(store.list_school_account_names('owner-0', include_all=True)) == 12
    assert 1 <= len(queries) <= 2
    for sql in queries:
        projection = sql.lower().split('from', 1)[0]
        assert all(secret not in projection for secret in ('password', 'device_ua', '.configuration', '.fields', '.layout', '.extra'))


def test_statistics_use_the_global_stats_authority_and_preserve_defaults(school_store):
    store = school_store
    bindings(store, 'owner', {'00101': {'password': 'private', 'overdue_count': 80, 'completed_count': 90}})
    store.put('school_accounts', '00101.ini', b'[Config]\npassword=private\n[stats]\noverdue_count=002\ncompleted_count=0007\n')
    store.put('school_accounts', '00102.ini', b'[DEFAULT]\noverdue_count=5\ncompleted_count=8\n[stats]\ncompleted_count=9\n')
    store.put('school_accounts', '00103.ini', b'[DEFAULT]\noverdue_count=10\n[System]\nUA=private\n')
    store.put('school_accounts', '00104_backup.json', b'{"completed_count":99,"overdue_count":88}')
    assert store.get_school_account_stats(['00101', '00102', '00103', '00104', '00105']) == {
        '00101': {'overdue_count': 2, 'completed_count': 7},
        '00102': {'overdue_count': 5, 'completed_count': 9},
        '00103': {'overdue_count': 0, 'completed_count': 0},
        '00104': {'overdue_count': 0, 'completed_count': 0},
        '00105': {'overdue_count': 0, 'completed_count': 0},
    }


def test_statistics_bad_values_match_existing_zero_fallback(school_store):
    store = school_store
    store.put('school_accounts', '00101.ini', b'[stats]\noverdue_count=bad\ncompleted_count=7\n')
    store.put('school_accounts', '00102.ini', b'[stats]\noverdue_count=3\ncompleted_count=2.5\n')
    assert store.get_school_account_stats(['00101', '00102']) == {
        '00101': {'overdue_count': 0, 'completed_count': 0},
        '00102': {'overdue_count': 0, 'completed_count': 0},
    }


def test_stats_select_only_two_json_fields_in_parameter_bounded_batches(school_store, monkeypatch):
    store = school_store
    store.put('school_accounts', '10000.ini', b'[Config]\npassword=private\n[System]\nUA=private-UA\n[stats]\ncompleted_count=7\n')
    def forbid_documents(*args):
        raise AssertionError('statistics must not reconstruct credentials or compatibility documents')
    monkeypatch.setattr(store, '_documents', forbid_documents)
    with selects(store) as queries:
        result = store.get_school_account_stats([str(10000 + index) for index in range(1001)])
    assert len(result) == 1001
    assert result['10000'] == {'overdue_count': 0, 'completed_count': 7}
    assert result['11000'] == {'overdue_count': 0, 'completed_count': 0}
    assert 1 <= len(queries) <= 3
    for sql in queries:
        assert ' IN ' in sql.upper()
        projection = sql.lower().split('from', 1)[0]
        assert all(secret not in projection for secret in ('password', 'device_ua', '.configuration', '.system_parameters', '.fields', '.layout', '.extra'))


def test_projection_reflects_direct_typed_sql_updates_without_registry_changes(school_store):
    store = school_store
    bindings(store, 'owner', {'00101': 'own'})
    bindings(store, 'other', {'00102': {'password': 'before'}})
    store.put('school_accounts', '00101.ini', b'[stats]\ncompleted_count=2\n')
    assert store.list_school_account_names('owner', include_all=True) == ['00101', '00102']
    with store.database.connection() as connection:
        links = store.entities['account_school_links']
        schools = store.entities['school_accounts']
        connection.execute(update(links).where(links.c.owner_username == 'other').values(password=''))
        connection.execute(update(schools).where(schools.c.school_username == '00101').values(statistics={'completed_count': '4'}))
    assert store.list_school_account_names('owner', include_all=True) == ['00101']
    assert store.get_school_account_stats(['00101']) == {'00101': {'overdue_count': 0, 'completed_count': 4}}


def test_empty_or_invalid_names_do_not_open_a_database_query(school_store):
    store = school_store
    with selects(store) as queries:
        assert store.list_school_account_names('') == []
        assert store.list_school_account_names('guest', include_all=True) == []
        assert store.get_school_account_stats([]) == {}
        assert store.get_school_account_stats(['invalid', '../00101', None]) == {}
    assert queries == []


@pytest.mark.parametrize('owned,expected', [
    ({'password': 'own-password', 'ua': 'own-UA'}, {'password': 'own-password', 'ua': 'own-UA'}),
    ({'password': '', 'ua': ''}, {'password': '', 'ua': ''}),
    ({}, {'password': None, 'ua': None}),
    ('legacy-password', {'password': 'legacy-password', 'ua': None}),
    ('', {'password': '', 'ua': None}),
    ({'password': 0, 'ua': None}, {'password': 0, 'ua': None}),
    ({'password': 'own-password', 'device_ua': 'legacy-extension'}, {'password': 'own-password', 'ua': None}),
])
def test_target_credentials_keep_owned_mapping_or_string_even_when_blank(school_store, owned, expected):
    store = school_store
    bindings(store, 'owner', {'00101': owned})
    bindings(store, 'other', {'00101': {'password': 'other-password', 'ua': 'other-UA'}})
    store.put('school_accounts', '00101.ini', b'[Config]\npassword=global-password\n[System]\nUA=global-UA\n')
    assert store.get_school_account_credentials('owner', '00101', include_all=True) == expected


@pytest.mark.parametrize('owned', [None, False, 0, [], ['invalid']])
def test_target_credentials_do_not_treat_invalid_owned_scalar_as_a_binding(school_store, owned):
    store = school_store
    bindings(store, 'owner', {'00101': owned})
    assert store.get_school_account_credentials('owner', '00101') is None


def test_target_credentials_cannot_reach_another_owner_without_explicit_all_scope(school_store):
    store = school_store
    bindings(store, 'other', {'00101': {'password': 'other-password', 'ua': 'other-UA'}})
    store.put('school_accounts', '00101.ini', b'[Config]\npassword=global-password\n')
    assert store.get_school_account_credentials('owner', '00101') is None
    assert store.get_school_account_credentials('owner', '00101', include_all=True) == {
        'password': 'other-password', 'ua': 'other-UA'}


def test_admin_target_credentials_preserve_record_order_and_skip_unusable_bindings(school_store):
    store = school_store
    bindings(store, 'z-owner', {'00101': {'password': 'z-password', 'ua': 'z-UA'}})
    bindings(store, 'c-owner', {'00101': {'password': 'c-password', 'ua': 'c-UA'}})
    bindings(store, 'a-owner', {'00101': None})
    bindings(store, 'b-owner', {'00101': {'password': '\u2003\t '}})
    bindings(store, 'bb-owner', {'00101': {'password': 0}})
    assert store.get_school_account_credentials('owner', '00101', include_all=True) == {
        'password': 'c-password', 'ua': 'c-UA'}


def test_admin_target_credentials_use_global_config_and_system_only_as_final_fallback(school_store):
    store = school_store
    bindings(store, 'other', {'00101': {'password': '\t '}})
    store.put('school_accounts', '00101.ini', b'[DEFAULT]\npassword=global-default\nua=default-UA\n[Config]\nUsername=00101\n[System]\nUA=global-UA\n[stats]\ncompleted_count=7\n')
    assert store.get_school_account_credentials('owner', '00101', include_all=True) == {
        'password': 'global-default', 'ua': 'global-UA'}


def test_admin_target_credentials_do_not_invent_global_sections_or_read_nested_sources(school_store):
    store = school_store
    store.put('school_accounts', '00101.ini', b'[DEFAULT]\npassword=not-a-config\nua=not-a-system\n[stats]\ncompleted_count=7\n')
    store.put('school_accounts', 'nested/user_accounts/owner.json', b'{"00102":{"password":"hidden"}}')
    store.put('school_accounts', 'nested/00102.ini', b'[Config]\npassword=hidden\n')
    assert store.get_school_account_credentials('owner', '00101', include_all=True) is None
    assert store.get_school_account_credentials('owner', '00102', include_all=True) is None


def test_target_credentials_bound_queries_to_requested_school_before_selecting_any_secret(school_store, monkeypatch):
    store = school_store
    bindings(store, 'other', {str(10000 + index): {'password': 'private-' + str(index), 'ua': 'UA-' + str(index)}
                              for index in range(446)})
    def forbid_documents(*args):
        raise AssertionError('target credentials must not reconstruct any compatibility document')
    monkeypatch.setattr(store, '_documents', forbid_documents)
    with selects(store) as queries:
        assert store.get_school_account_credentials('owner', '10223', include_all=True) == {
            'password': 'private-223', 'ua': 'UA-223'}
    assert 1 <= len(queries) <= 3
    for sql in queries:
        assert '.school_username = ' in sql.lower()
        assert 'limit' in sql.lower()
        assert all(secret not in sql.lower() for secret in ('.layout', '.extra', '.statistics', '.api_cookies'))


def test_invalid_target_credentials_request_never_reads_storage(school_store):
    with selects(school_store) as queries:
        assert school_store.get_school_account_credentials('', '00101', include_all=True) is None
        assert school_store.get_school_account_credentials('guest', '00101', include_all=True) is None
        assert school_store.get_school_account_credentials('owner', '../00101', include_all=True) is None
    assert queries == []


def test_legacy_reader_cannot_use_v3_projections(tmp_path):
    old = RelationalStore(DatabaseSettings(root=tmp_path, sqlite_path=':memory:', table_prefix='app_'), schema_version='2')
    old.init_schema(ready=True)
    try:
        with pytest.raises(DatabaseError, match='v3'):
            old.list_school_account_names('owner')
        with pytest.raises(DatabaseError, match='v3'):
            old.get_school_account_stats(['00101'])
        with pytest.raises(DatabaseError, match='v3'):
            old.get_school_account_credentials('owner', '00101')
    finally:
        old.database.dispose()
