"""V3 JSON is readable in SQL while v2 and exact-number semantics survive."""
import hashlib
import json
import math

import pytest
from sqlalchemy import insert, select, update

from persistence.codec import Builder, decode_tree


def native_builder():
    from persistence.codec_v3 import BusinessBuilder
    from persistence.schema_v3 import TABLES
    return BusinessBuilder('native-document', TABLES)


def test_ordinary_configuration_is_a_plain_sql_json_object():
    from persistence.codec_v3 import encode
    value = {'stats': {'completed_count': '3', 'enabled': True, 'optional': None}}
    builder = native_builder()
    tree = encode(builder, 'school_accounts', '00123.ini', value)
    row = builder.rows['school_accounts'][0]
    assert row['statistics'] == value['stats']
    assert row['fields'][0]['kind'] == 'json_native'
    assert decode_tree(builder.finish(tree), builder.rows) == value


def test_native_json_keeps_normal_collections_and_scalars_readable():
    from persistence.json_values import encode_native_json, decode_native_json
    value = {'list': [None, False, True, 0, -1, '00123', [], {}], 'empty': {}}
    encoded = encode_native_json(value)
    assert encoded == value
    assert decode_native_json(json.loads(json.dumps(encoded))) == value


@pytest.mark.parametrize('value', [0.0, -0.0, 1.2345678912345678, 1.7976931348623157e308,
                                  5e-324, 2**53, -(2**53), 2**200])
def test_special_numbers_round_trip_exactly_through_standard_json(value):
    from persistence.json_values import encode_native_json, decode_native_json
    encoded = encode_native_json(value)
    assert isinstance(encoded, dict) and '$storage' in encoded
    actual = decode_native_json(json.loads(json.dumps(encoded)))
    assert type(actual) is type(value)
    assert actual == value
    if isinstance(value, float):
        assert actual.hex() == value.hex()


@pytest.mark.parametrize('value', [None, False, True, 0, -1, 2**53 - 1, -(2**53 - 1), '', '00123', [], {}])
def test_safe_values_keep_their_native_json_types(value):
    from persistence.json_values import encode_native_json, decode_native_json
    encoded = encode_native_json(value)
    assert type(encoded) is type(value)
    assert encoded == value
    actual = decode_native_json(json.loads(json.dumps(encoded)))
    assert type(actual) is type(value)
    assert actual == value


@pytest.mark.parametrize('value', [
    {'$storage': 'provider-value', 'other': False},
    {'$storage': ['float', '0x1.0p+0']},
    {'$storage': ['int', '9007199254740992']},
    {'$storage': ['object', [['fixture', True]]]},
    {'outer': {'$storage': {'nested': [{'$storage': ['float', 'not-a-number']}]}}, 'float': -0.0},
])
def test_reserved_key_collisions_are_escaped_without_losing_provider_data(value):
    from persistence.json_values import encode_native_json, decode_native_json
    encoded = encode_native_json(value)
    assert decode_native_json(json.loads(json.dumps(encoded))) == value


@pytest.mark.parametrize('value', [math.inf, -math.inf, math.nan])
def test_nonfinite_values_are_rejected(value):
    from persistence.json_values import encode_native_json
    with pytest.raises(ValueError, match='finite'):
        encode_native_json({'nested': [value]})


def test_business_builder_converts_implicit_json_fields_and_keeps_extra_internal():
    from persistence.codec_v3 import BusinessBuilder
    builder = BusinessBuilder('fixture', {'fixture_table': {'payload': 'json'}})
    value = {'payload': {'readable': True}, 'extension': {'untouched': 'internal'}}
    tree = builder.record('fixture_table', value, {'payload': 'payload'})
    row = builder.rows['fixture_table'][0]
    assert row['payload'] == {'readable': True}
    assert row['extra'][0] == 'dict'
    assert decode_tree(builder.finish(tree), builder.rows) == value


def test_business_builder_does_not_duplicate_json_string_values_in_metadata():
    builder = native_builder()
    tree = builder.scalar('system_settings', 'ordinary-json-string', kind='json')
    row = builder.rows['system_settings'][0]
    assert row['value'] == 'ordinary-json-string'
    assert 'representation' not in row['fields'][0]
    assert decode_tree(builder.finish(tree), builder.rows) == 'ordinary-json-string'


def test_reused_financial_codec_uses_native_json_without_changing_money_columns():
    from persistence.codec_v3 import encode
    value = {'order_id': 'fixture-order', 'amount': '01.25',
             'billing_scope': {'owner': 'fixture', 'accounts': ['00123'], 'empty': None},
             'billing_items': [{'billing_id': 'bill-a', 'amount': 1.25, 'quantity': 1}]}
    builder = native_builder()
    tree = encode(builder, 'payment_orders', 'fixture-order.json', value)
    row = builder.rows['payment_orders'][0]
    assert row['billing_scope'] == value['billing_scope']
    assert row['amount_minor'] == 125
    assert decode_tree(builder.finish(tree), builder.rows) == value


def test_v2_builder_keeps_its_original_tagged_json_representation():
    builder = Builder('legacy-document', {'legacy': {'payload': 'json'}})
    value = {'payload': {'list': [1.2345678912345678, 2**100, False]}}
    tree = builder.record('legacy', value, {'payload': 'payload'})
    row = builder.rows['legacy'][0]
    assert row['payload'][0] == 'dict'
    assert row['fields'][0]['kind'] == 'json'
    assert decode_tree(builder.finish(tree), builder.rows) == value


def test_direct_sql_json_column_updates_change_reconstructed_configuration(tmp_path):
    from persistence.codec_v3 import encode
    from persistence.engine import DatabaseSettings
    from persistence.store import RelationalStore, render_content
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    try:
        store.init_schema(ready=True)
        value = {'Guest': {'allow_guest_login': False, 'max_active_guest_sessions': 3}}
        builder = native_builder()
        builder.document_id = store._identity('configs', 'config.json')
        tree = encode(builder, 'configs', 'config.json', value)
        layout = builder.finish(tree)
        content = render_content('json', value)
        with store.database.connection() as connection:
            connection.execute(insert(store.registry).values(
                document_id=builder.document_id, namespace='configs', record_key='config.json', format='json',
                layout=layout, entity_tables=list(builder.rows), revision=1, mtime_ns=1,
                content_sha256=hashlib.sha256(content).hexdigest()))
            connection.execute(insert(store.entities['system_settings']), builder.rows['system_settings'])
            table = store.entities['system_settings']
            assert connection.execute(select(table.c.value)).scalar_one() == value['Guest']
            connection.execute(update(table).values(value={'allow_guest_login': True, 'max_active_guest_sessions': 7}))
        assert json.loads(store.get('configs', 'config.json').content) == {
            'Guest': {'allow_guest_login': True, 'max_active_guest_sessions': 7}}
    finally:
        store.database.dispose()
