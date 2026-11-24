"""Real MySQL upgrade in an isolated database, including unprefixed DDL."""
from dataclasses import replace
import hashlib
import json
import uuid

import pytest
from sqlalchemy import inspect, text

from persistence.engine import DatabaseError
from persistence.store import RelationalStore
from storage_migration import import_relational_store, verify_relational_store, drop_legacy_schema, verify_database
from test_relational_mysql import relational_mysql


def test_mysql_v2_upgrade_preserves_owners_money_and_json_then_drops_only_old_tables(relational_mysql):
    old = RelationalStore(replace(relational_mysql.settings, table_prefix='old_' + uuid.uuid4().hex[:10] + '_'),
                          schema_version='2')
    new = RelationalStore(replace(relational_mysql.settings, table_prefix=''))
    try:
        old.init_schema(ready=True)
        for owner in ('owner-a', 'owner-b'):
            key = hashlib.sha256(owner.encode()).hexdigest()
            old.put('system_accounts', key + '.json', json.dumps({'auth_username': owner}).encode())
            old.put('school_accounts', 'user_accounts/' + key + '.json', json.dumps({
                '10001': {'password': owner + '-fixture', 'ua': owner + '-UA'}}).encode())
        old.put('school_accounts', '10001.ini', b'[System]\nzzzz=last\na=first\n[stats]\ncompleted_count=002\n')
        old.put('payment_orders', 'order.json', b'{"order_id":"fixture-order","amount":"13.37","status":"paid"}')
        old.put('sessions', 'fixture.json', b'{"session_id":"fixture","auth_username":"owner-a","params":{"z":-0.0,"a":null}}')
        old.put('configs', 'config.json', b'{"System":{"zzzz":"last","a":"first","big":1267650600228229401496703205376}}')
        old.put('sms_records', 'fixture.json', b'{"phone":"13800000000","timestamp":1.25,"scene":"register"}')
        with pytest.raises(DatabaseError, match='[Ll]egacy'):
            new.init_schema(ready=True)
        new.init_schema(allow_legacy=True)
        result = import_relational_store(old, new)
        assert result.imported == 9 and result.verification.ok
        assert verify_relational_store(old, new).ok
        assert verify_database(new) == 9
        for owner in ('owner-a', 'owner-b'):
            key = hashlib.sha256(owner.encode()).hexdigest()
            binding = json.loads(new.get('school_accounts', 'user_accounts/' + key + '.json').content)['10001']
            assert binding == {'password': owner + '-fixture', 'ua': owner + '-UA'}
        assert json.loads(new.get('payment_orders', 'order.json').content)['amount'] == '13.37'
        with new.database.connection() as connection:
            assert connection.execute(text('SELECT amount_minor FROM payment_orders')).scalar_one() == 1337
        assert new.entities['school_accounts'].name == 'school_accounts'
        assert new.registry.name == 'storage_documents'
        old_names = set(old.metadata.tables)
        drop_legacy_schema(old, new)
        remaining = set(inspect(new.database.engine).get_table_names())
        assert not old_names & remaining
        assert set(new.metadata.tables) <= remaining
        assert set(relational_mysql.metadata.tables) <= remaining
        assert verify_database(new) == 9
    finally:
        new.metadata.drop_all(new.database.engine)
        old.metadata.drop_all(old.database.engine)
        new.database.dispose()
        old.database.dispose()
