"""Relational domain contracts use synthetic records and no live services."""
import copy
import importlib
import json

import pytest


def encode_record(namespace, key, value):
    codec = importlib.import_module('persistence.codec')
    domains = importlib.import_module('persistence.domains')
    builder = codec.Builder()
    tree = domains.encode(builder, namespace, key, copy.deepcopy(value))
    assert tree is not None
    layout = builder.finish(tree)
    return builder, layout, codec.decode_tree(layout, builder.rows)


def test_financial_columns_use_integer_minor_units():
    domains = importlib.import_module('persistence.domains')
    assert domains.TABLES['payment_orders']['amount_minor'] == 'money'
    assert domains.TABLES['billing_records']['amount_minor'] == 'money'
    assert domains.TABLES['payment_refunds']['amount_minor'] == 'money'


def test_order_refunds_and_bill_items_are_entities_with_lossless_roundtrip():
    source = {'order_id': 'order-A', 'auth_username': '', 'username': 'payer-A',
              'amount': 12.25, 'status': 'pending', 'billing_scope': None,
              'billing_items': [{'billing_id': 'bill-A', 'school_username': '0012',
                                 'amount': '12.25', 'custom': {'NA': None}}],
              'refund_records': [{'refund_amount': 1.25, 'refund_time': 'raw-time',
                                  'operator': 'admin-A', 'remote_detail': {'ok': True}}],
              'provider_data': {'unchanged': [None, 'NA', False]}}
    builder, _, restored = encode_record('payment_orders', 'order-A.json', source)
    assert restored == source
    orders = builder.rows['payment_orders']
    assert len(orders) == 1 and orders[0]['amount_minor'] == 1225
    extra_fields = {pair[0] for pair in orders[0]['extra'][1]}
    assert 'amount' not in extra_fields
    assert 'bill-A' not in json.dumps(orders[0]['extra'])
    assert builder.rows['payment_order_bills'][0]['order_row_id'] == orders[0]['row_id']
    assert builder.rows['payment_order_bills'][0]['school_username'] == '0012'
    assert builder.rows['payment_refunds'][0]['amount_minor'] == 125
    assert builder.rows['payment_refunds'][0]['order_row_id'] == orders[0]['row_id']


@pytest.mark.parametrize('scope', [None, '', {}, {'school_id': '', 'billing_id': None}, ['invalid']])
def test_order_scope_and_empty_auth_identity_are_never_normalized(scope):
    source = {'order_id': 'order-A', 'auth_username': '', 'billing_scope': scope}
    _, _, restored = encode_record('payment_orders', 'order-A.json', source)
    assert restored == source


def test_invalid_fractional_money_is_rejected_instead_of_rounded():
    with pytest.raises((ValueError, ArithmeticError)):
        encode_record('payment_orders', 'invalid.json', {'amount': '1.001'})


def test_bill_order_relations_preserve_list_order_and_shared_school_ownership():
    source = {'billing_id': 'bill-A', 'school_username': '0012', 'auth_username': '',
              'amount': '3.50', 'status': 'pending',
              'payment_orders': ['order-B', 'order-A', 'order-B'],
              'final_payment_order': None}
    builder, _, restored = encode_record('billing', 'School_Bills/0012/bill-A.json', source)
    assert restored == source
    bill = builder.rows['billing_records'][0]
    assert bill['school_username'] == '0012'
    assert bill['auth_username'] == ''
    assert bill['amount_minor'] == 350
    assert len(builder.rows['payment_order_bills']) == 3
    assert all(row['billing_row_id'] == bill['row_id'] for row in builder.rows['payment_order_bills'])


def test_malformed_legacy_bill_order_entries_remain_unmodified():
    source = {'billing_id': 'bill-A', 'payment_orders': ['order-A', False, 0, None, {'raw': 'NA'}]}
    _, _, restored = encode_record('billing', 'legacy-owner/bill-A.json', source)
    assert json.dumps(restored, sort_keys=True) == json.dumps(source, sort_keys=True)


def test_core_column_changes_are_authoritative_when_decoding():
    builder, layout, _ = encode_record('billing', 'School_Bills/0012/bill-A.json',
        {'billing_id': 'bill-A', 'amount': 1.25, 'status': 'pending'})
    builder.rows['billing_records'][0]['amount_minor'] = 425
    builder.rows['billing_records'][0]['status'] = 'paid'
    codec = importlib.import_module('persistence.codec')
    assert codec.decode_tree(layout, builder.rows) == {'billing_id': 'bill-A', 'amount': 4.25, 'status': 'paid'}


def test_background_task_items_keep_index_types_and_execution_identity():
    source = {'session_id': 'session-A', 'execution_id': 'execution-A', 'status': 'running',
              'task_indices': [3, 1, 3], 'completed_tasks': 0, 'current_task_index': 0,
              'auto_generate': False, 'run_coords': [[1.1, 2.2], [3.3, 4.4]],
              'future_value': {'raw': None}}
    builder, _, restored = encode_record('background_tasks', 'synthetic-hash.json', source)
    assert restored == source
    task = builder.rows['background_task_states'][0]
    assert task['execution_id'] == 'execution-A'
    assert [row['task_index'] for row in builder.rows['background_task_items']] == [3, 1, 3]
    assert all(row['task_row_id'] == task['row_id'] for row in builder.rows['background_task_items'])


def test_messages_are_individual_rows_and_keep_guest_snapshots():
    source = [{'id': 'message-A', 'content': 'synthetic', 'auth_username': None,
               'nickname': 'guest snapshot', 'is_guest': True, 'timestamp': 123.5},
              {'id': 'message-B', 'content': '', 'is_guest': False, 'email': ''}]
    builder, _, restored = encode_record('settings', 'messages.json', source)
    assert restored == source
    assert len(builder.rows['messages']) == 2
    assert builder.rows['messages'][0]['auth_username'] is None
    assert 'content' not in {pair[0] for pair in builder.rows['messages'][0]['extra'][1]}


def test_reminders_keep_wrapper_metadata_and_individual_entities():
    source = {'reminders': [{'id': 'reminder-A', 'title': 'synthetic', 'message': '',
                             'enabled': False, 'allow_guest_view': True,
                             'start_time': None, 'end_time': ''}], 'version': 3}
    builder, _, restored = encode_record('settings', 'reminders.json', source)
    assert restored == source
    assert len(builder.rows['reminders']) == 1
    assert builder.rows['reminders'][0]['enabled'] is False


def test_background_assignments_bundles_and_each_binding_are_separate_rows():
    source = {'schema_version': 2, 'next_revision': 8,
              'assignments': {'pc-A': {'target': 'pc', 'image_url': '/image/pc.png', 'expires_at': None},
                              'mb-A': {'target': 'mb', 'image_url': '/image/mb.png'}},
              'bundles': {'bundle-A': {'pc_assignment_id': 'pc-A', 'mobile_assignment_id': 'mb-A',
                                       'state': 'consumed', 'revision': 7}},
              'identity_bindings': {'user:owner-A': {'bundle_id': 'bundle-A', 'source': 'login'}},
              'guest_bindings': {'guest-A': {'bundle_id': 'bundle-A', 'bound_at': 'raw-time'}},
              'auth_claims': {'claim-A': {'bundle_id': 'bundle-A'}}, 'future': {}}
    builder, _, restored = encode_record('background_state', 'background_state.json', source)
    assert restored == source
    assert len(builder.rows['background_assignments']) == 2
    assert len(builder.rows['background_bundles']) == 1
    assert len(builder.rows['background_bindings']) == 3
    assert {row['binding_kind'] for row in builder.rows['background_bindings']} == {
        'identity_bindings', 'guest_bindings', 'auth_claims'}


def test_configuration_is_split_to_leaves_and_distinguishes_empty_collections():
    source = {'System': {'enabled': False, 'count': 0, 'UA': '', 'missing_value': None},
              'providers': [{'name': 'first', 'key': 'synthetic'}, {'name': 'second'}],
              'empty_object': {}, 'empty_list': [], 'NA': 'NA'}
    builder, _, restored = encode_record('configs', 'config.json', source)
    assert restored == source
    rows = builder.rows['application_settings']
    assert len(rows) >= 8
    codec = importlib.import_module('persistence.codec')
    values = [codec.decode_tree(row['value'], builder.rows) if row['value'] is not None else None for row in rows]
    assert all(not isinstance(value, (dict, list)) or not value for value in values)
    assert any(row['setting_key'] == 'UA' and row['section'] == 'System' for row in rows)


def test_application_setting_leaf_core_value_is_authoritative():
    builder, layout, _ = encode_record('configs', 'config.json', {'System': {'UA': 'device-A'}})
    row = builder.rows['application_settings'][0]
    codec = importlib.import_module('persistence.codec')
    row['value'] = builder.finish('device-B')
    assert codec.decode_tree(layout, builder.rows) == {'System': {'UA': 'device-B'}}


@pytest.mark.parametrize(('namespace', 'key'), [
    ('payment_orders', '_index.json'), ('payment_orders', 'qr_cache_index.json'),
    ('billing', '_index.json'), ('background_tasks', '_index.json'),
    ('settings', 'permissions.json'), ('unknown', 'unknown.json'),
])
def test_other_domain_and_index_documents_are_not_claimed(namespace, key):
    domains = importlib.import_module('persistence.domains')
    codec = importlib.import_module('persistence.codec')
    assert domains.encode(codec.Builder(), namespace, key, {'data': 'synthetic'}) is None


@pytest.fixture
def domain_store(tmp_path):
    from persistence.engine import DatabaseSettings
    from persistence.store import RelationalStore
    store = RelationalStore(DatabaseSettings(root=tmp_path))
    store.init_schema(ready=True)
    yield store
    store.database.dispose()


@pytest.mark.parametrize(('namespace', 'key', 'source'), [
    ('payment_orders', 'order-A.json', {
        'order_id': 'order-A', 'amount': '10.00', 'refund_total': 1.25,
        'billing_scope': None, 'auth_username': '',
        'billing_items': [{'billing_id': 'bill-A', 'school_username': '0012'}],
        'refund_records': [{'refund_amount': '1.25', 'operator': 'synthetic'}],
        'future_provider_data': {'zero': 0, 'disabled': False, 'null': None}}),
    ('billing', 'School_Bills/0012/bill-A.json', {
        'billing_id': 'bill-A', 'school_username': '0012', 'auth_username': '',
        'amount': 10.0, 'status': 'pending', 'payment_orders': ['order-A', 'order-B']}),
    ('billing', 'Reomve/0012/old-bill.json', {
        'billing_id': 'old-bill', 'school_username': '0012', 'amount': 0, 'status': 'paid'}),
    ('background_tasks', 'task-A.json', {
        'session_id': 'session-A', 'task_indices': [2, 4, 2], 'auto_generate': False,
        'last_update': 1.25, 'completed_tasks': 0, 'run_coords': [[1.5, 2.5]]}),
    ('settings', 'messages.json', [
        {'id': 'message-A', 'content': 'synthetic', 'is_guest': True, 'timestamp': 123.5},
        {'id': 'message-B', 'content': '', 'auth_username': None}]),
    ('settings', 'reminders.json', {'reminders': [
        {'id': 'reminder-A', 'message': 'synthetic', 'enabled': False, 'end_time': None}]}),
    ('settings', 'messages.json', []),
    ('configs', 'config.json', {'System': {'zero': 0, 'enabled': False, 'none': None,
                                          'NA': 'NA'}, 'empty': {}, 'list': []}),
    ('configs', 'compat.ini', {'Section': {'one': '001', 'flag': 'False', 'empty': ''}}),
])
def test_sqlite_store_roundtrips_typed_domain_records(domain_store, namespace, key, source):
    from persistence.store import parse_content, render_content
    format = 'ini' if key.endswith('.ini') else 'json'
    content = render_content(format, source)
    domain_store.put(namespace, key, content, mtime_ns=1234567)
    stored = domain_store.get(namespace, key)
    _, restored = parse_content(key, stored.content)
    assert json.dumps(restored, sort_keys=True) == json.dumps(source, sort_keys=True)
    assert stored.mtime_ns == 1234567


def test_sqlite_authoritative_financial_child_columns_change_reconstructed_order(domain_store):
    from sqlalchemy import select, update
    source = {'order_id': 'order-A', 'amount': '2.00', 'status': 'pending',
              'refund_records': [{'refund_amount': 0.25, 'operator': 'synthetic'}]}
    domain_store.put('payment_orders', 'order-A.json', json.dumps(source).encode())
    order = domain_store.entities['payment_orders']
    refund = domain_store.entities['payment_refunds']
    with domain_store.database.connection() as connection:
        assert connection.execute(select(order.c.amount_minor)).scalar_one() == 200
        assert connection.execute(select(refund.c.amount_minor)).scalar_one() == 25
        connection.execute(update(order).values(amount_minor=350, status='paid'))
        connection.execute(update(refund).values(amount_minor=75))
    restored = json.loads(domain_store.get('payment_orders', 'order-A.json').content)
    assert restored['amount'] == '3.5'
    assert restored['status'] == 'paid'
    assert restored['refund_records'][0]['refund_amount'] == 0.75


def test_sqlite_configurations_keep_each_section_in_one_readable_authoritative_row(domain_store):
    from sqlalchemy import select, update
    source = {'System': {'UA': 'device-A', 'enabled': False, 'count': 0}}
    domain_store.put('configs', 'config.json', json.dumps(source).encode())
    settings = domain_store.entities['system_settings']
    with domain_store.database.connection() as connection:
        assert len(connection.execute(select(settings.c.row_id)).all()) == 1
        assert connection.execute(select(settings.c.value)).scalar_one() == source['System']
        connection.execute(update(settings).where(settings.c.section == 'System')
                           .values(value={'UA': 'device-B', 'enabled': False, 'count': 0}))
    restored = json.loads(domain_store.get('configs', 'config.json').content)
    assert restored == {'System': {'UA': 'device-B', 'enabled': False, 'count': 0}}
