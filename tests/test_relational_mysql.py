"""Optional real v2 checks; use only an isolated test database."""
import hashlib
import json
import os
import uuid

import pytest
from sqlalchemy import select


@pytest.fixture
def relational_mysql(tmp_path):
    port = os.environ.get('STORAGE_IO_TEST_MYSQL_PORT')
    if not port:
        pytest.skip('Set STORAGE_IO_TEST_MYSQL_PORT for an isolated MySQL test database')
    import pymysql
    from persistence.engine import DatabaseSettings
    from persistence.store import RelationalStore
    settings = DatabaseSettings(backend='mysql', root=tmp_path,
        host=os.environ.get('STORAGE_IO_TEST_MYSQL_HOST', '127.0.0.1'), port=int(port),
        user=os.environ.get('STORAGE_IO_TEST_MYSQL_USER', 'root'),
        password=os.environ.get('STORAGE_IO_TEST_MYSQL_PASSWORD', ''),
        database=os.environ.get('STORAGE_IO_TEST_MYSQL_DATABASE', 'storage_test'),
        table_prefix='v2_' + uuid.uuid4().hex[:12] + '_')
    # A custom creator intentionally lacks CLIENT_FOUND_ROWS. Reassigning a
    # metadata value must not be mistaken for a missing row.
    def factory():
        return pymysql.connect(host=settings.host, port=settings.port, user=settings.user,
            password=settings.password, database=settings.database, charset='utf8mb4')
    store = RelationalStore(settings, factory)
    try:
        store.init_schema(ready=True)
        yield store
    finally:
        try:
            store.metadata.drop_all(store.database.engine)
        finally:
            store.database.dispose()


def test_exact_numeric_columns_and_json_extension_round_trip(relational_mysql):
    store = relational_mysql
    value = {'auth_username': 'fixture-owner', 'created_at': 1763950001.1234567,
        'point': [113.12345678912345, 22.45678912345678], 'huge': 2**100}
    store.put('system_accounts', 'owner.json', json.dumps(value).encode())
    result = store.get('system_accounts', 'owner.json')
    assert json.loads(result.content) == value
    assert result.digest == hashlib.sha256(result.content).hexdigest()
    store.put('system_accounts', 'legacy.json', b'{"auth_username":"legacy","created_at":"001.2500"}')
    assert json.loads(store.get('system_accounts', 'legacy.json').content)['created_at'] == '001.2500'


def test_full_value_uniqueness_has_no_prefix_or_case_collision(relational_mysql):
    store = relational_mysql
    for index, name in enumerate(('x' * 200 + 'one', 'x' * 200 + 'two', 'Owner', 'owner')):
        store.put('system_accounts', f'{index}.json', json.dumps({'auth_username': name}).encode())
    assert len(store.list('system_accounts')) == 4


def test_mysql_metadata_reassignment_cas_and_rollback(relational_mysql):
    from business_storage import ConflictError
    store = relational_mysql
    store.mark_pending()
    store.mark_pending()
    store.mark_ready()
    store.mark_ready()
    assert store.check_ready()
    first = store.put('settings', 'messages.json', b'[]', expected_revision=0)
    with pytest.raises(ConflictError):
        store.put('settings', 'messages.json', b'[1]', expected_revision=0)
    with pytest.raises(ValueError):
        with store.transaction():
            store.put('settings', 'messages.json', b'[1]', expected_revision=first.revision)
            store.put('settings', 'reminders.json', b'[]')
            raise ValueError('rollback')
    assert json.loads(store.get('settings', 'messages.json').content) == []
    assert store.get('settings', 'reminders.json') is None
