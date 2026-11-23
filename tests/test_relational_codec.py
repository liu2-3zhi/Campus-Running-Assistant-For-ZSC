import pytest


def test_core_fields_are_columns_and_extensions_round_trip():
    from persistence.codec import Builder, decode_tree
    source = {'username': '000123', 'ua': 'owner-ua', 'count': '02', 'optional': None, 'nested': {'x': [1, False]}}
    builder = Builder('document', {'accounts': {'username': 'text', 'device_ua': 'text', 'count': 'int'}})
    ref = builder.record('accounts', source, {'username': 'username', 'ua': 'device_ua', 'count': 'count'})
    layout = builder.finish(ref)
    row = builder.rows['accounts'][0]
    assert row['username'] == '000123' and row['device_ua'] == 'owner-ua'
    assert row['count'] == 2
    assert decode_tree(layout, builder.rows) == source
    assert 'owner-ua' not in str(row['extra'])


def test_relations_and_scalar_references_preserve_shapes():
    from persistence.codec import Builder, decode_tree
    builder = Builder('document', {'items': {'value': 'json'}, 'owners': {'name': 'text'}})
    scalar = builder.scalar('items', 'bill-id')
    ref = builder.record('owners', {'name': 'owner', 'bills': [scalar]}, {'name': 'name'})
    value = {'owner': ref, 'empty': [], 'none': None, 'marker': ['row', 'owners', 'literal']}
    assert decode_tree(builder.finish(value), builder.rows) == {'owner': {'name': 'owner', 'bills': ['bill-id']}, 'empty': [], 'none': None, 'marker': ['row', 'owners', 'literal']}


def test_money_is_exact_integer_minor_units():
    from persistence.codec import Builder, decode_tree
    builder = Builder('document', {'bills': {'amount_minor': 'money'}})
    source = {'amount': '12.30'}
    ref = builder.record('bills', source, {'amount': ('amount_minor', 'money')})
    assert builder.rows['bills'][0]['amount_minor'] == 1230
    assert decode_tree(builder.finish(ref), builder.rows) == source
    with pytest.raises(ValueError):
        builder.record('bills', {'amount': '1.234'}, {'amount': ('amount_minor', 'money')})


def test_missing_and_null_and_false_are_distinct():
    from persistence.codec import Builder, decode_tree
    builder = Builder('document', {'items': {'flag': 'bool', 'value': 'json'}})
    refs = [builder.record('items', obj, {'flag': 'flag', 'value': 'value'}) for obj in ({}, {'value': None}, {'flag': False}, {'flag': 'false'})]
    assert decode_tree(builder.finish(refs), builder.rows) == [{}, {'value': None}, {'flag': False}, {'flag': 'false'}]


def test_float_extension_and_large_integer_do_not_use_native_json_numbers():
    import json
    from persistence.codec import Builder, decode_tree
    builder = Builder('document', {'events': {'created_at': 'float'}})
    source = {'created_at': 1763950001.1234567, 'point': [113.12345678912345, 22.45678912345678], 'huge': 2**100}
    ref = builder.record('events', source, {'created_at': 'created_at'})
    assert decode_tree(builder.finish(ref), builder.rows) == source
    extra = json.dumps(builder.rows['events'][0]['extra'])
    assert str(source['point'][0]) not in extra
