import json

import pytest
from sqlalchemy import inspect, select, text


@pytest.fixture
def store(tmp_path):
    from persistence.engine import DatabaseSettings
    from persistence.store import RelationalStore
    result = RelationalStore(DatabaseSettings(root=tmp_path))
    result.init_schema(ready=True)
    yield result
    result.database.dispose()


def test_document_is_split_and_reconstructed_without_body_blob(store):
    payload = {'auth_username': '000123', 'password': 'hashed', 'group': 'user', 'enabled': True}
    saved = store.put('system_accounts', '000123.json', json.dumps(payload).encode(), create_only=True)
    assert saved.revision == 1
    assert json.loads(store.get('system_accounts', '000123.json').content) == payload
    schema = inspect(store.database.engine)
    assert 'app_users' in schema.get_table_names()
    assert 'app_documents' not in schema.get_table_names()
    columns = {col['name'] for col in schema.get_columns('app_document_registry')}
    assert not {'content', 'body', 'payload'} & columns
    with store.database.connection() as connection:
        assert connection.execute(text('SELECT auth_username FROM app_users')).scalar_one() == '000123'


def test_revision_and_transaction_are_atomic(store):
    from business_storage import ConflictError
    first = store.put('settings', 'messages.json', b'[]', create_only=True)
    with pytest.raises(ConflictError):
        store.put('settings', 'messages.json', b'[1]', create_only=True)
    with pytest.raises(ConflictError):
        store.put('settings', 'messages.json', b'[1]', expected_revision=0)
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.put('settings', 'messages.json', b'[1]', expected_revision=first.revision)
            store.put('settings', 'reminders.json', b'[]')
            raise RuntimeError('rollback')
    assert json.loads(store.get('settings', 'messages.json').content) == []
    assert store.get('settings', 'reminders.json') is None


def test_ini_and_arbitrary_settings_round_trip(store):
    import configparser
    value = b'[System]\nUserID = 000123\nToken = sensitive\n[Stats]\ntotal = 02\n'
    store.put('school_accounts', '000123.ini', value)
    output = configparser.RawConfigParser(strict=False)
    output.optionxform = str
    output.read_string(store.get('school_accounts', '000123.ini').content.decode())
    assert dict(output['System']) == {'UserID': '000123', 'Token': 'sensitive'}
    store.put('configs', 'extra.json', b'{"empty":{},"list":[null,false,0,""]}')
    assert json.loads(store.get('configs', 'extra.json').content) == {'empty': {}, 'list': [None, False, 0, '']}


def test_delete_cascades_only_document_entities(store):
    store.put('settings', 'messages.json', b'[{"id":"one","content":"hello"}]')
    store.put('settings', 'reminders.json', b'[{"id":"two","content":"stay"}]')
    assert store.delete('settings', 'messages.json') is True
    assert store.delete('settings', 'messages.json') is False
    assert len(store.list('settings')) == 1
    assert store.get('settings', 'reminders.json') is not None


def test_ready_schema_guard_and_metadata(store):
    assert store.check_ready()
    store.mark_pending()
    with pytest.raises(RuntimeError):
        store.check_ready()
    store.mark_ready()
    assert store.check_ready()
    assert store.namespaces() == []


def test_long_identifiers_are_unique_by_full_value(store):
    common = 'a' * 200
    for suffix in ('one', 'two'):
        store.put('system_accounts', suffix + '.json', json.dumps({'auth_username': common + suffix}).encode())
    assert len(store.list('system_accounts')) == 2
    from sqlalchemy.dialects.mysql import dialect
    from sqlalchemy.schema import CreateIndex
    for table in store.entities.values():
        for index in table.indexes:
            if index.unique:
                assert '(191)' not in str(CreateIndex(index).compile(dialect=dialect()))


def test_ini_defaults_remain_inherited_instead_of_becoming_overrides(store):
    from persistence.store import parse_content
    value = b'[DEFAULT]\nvalue = inherited\n[Config]\nUsername = 00042\n'
    store.put('school_accounts', '00042.ini', value)
    _, parsed = parse_content('a.ini', store.get('school_accounts', '00042.ini').content)
    assert parsed == {'DEFAULT': {'value': 'inherited'}, 'Config': {'Username': '00042'}}


def test_create_many_is_atomic_and_preserves_heterogeneous_fields(store):
    import hashlib
    from types import SimpleNamespace
    from business_storage import ConflictError
    def entry(key, value):
        content = json.dumps(value).encode()
        return SimpleNamespace(namespace='system_accounts', key=key, content=content, mtime_ns=1, digest=hashlib.sha256(content).hexdigest())
    store.create_many([entry('one.json', {'auth_username': 'one'}), entry('two.json', {'auth_username': 'two', 'phone': '123'})])
    assert json.loads(store.get('system_accounts', 'two.json').content)['phone'] == '123'
    with pytest.raises(ConflictError):
        store.create_many([entry('three.json', {'auth_username': 'three'}), entry('duplicate.json', {'auth_username': 'one'})])
    assert store.get('system_accounts', 'three.json') is None


def test_relational_prefix_limit_fails_before_ddl():
    from persistence.engine import DatabaseConfigurationError
    from persistence.schema import make_schema
    with pytest.raises(DatabaseConfigurationError, match='identifier limit'):
        make_schema('p' * 40)


def test_rewriting_migrated_trimmed_owner_alias_keeps_original_identity(store):
    store.put('system_accounts', 'Alice.json', b'{"auth_username":" Alice "}')
    store.migration_owner_aliases = {'Alice': ' Alice '}
    content = b'{"10001":{"password":"fixture","ua":"owner-UA"}}'
    store.put('school_accounts', 'user_accounts/Alice.json', content)
    store.migration_owner_aliases = {}
    store.put('school_accounts', 'user_accounts/Alice.json', content)
    with store.database.connection() as connection:
        table = store.entities['user_school_accounts']
        assert connection.execute(select(table.c.owner_username)).scalar_one() == ' Alice '
