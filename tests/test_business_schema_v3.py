"""The v3 business schema stays readable without losing old document values."""
import hashlib

import pytest

from persistence.codec import decode_tree


def encode(namespace, key, value, owner_aliases=None):
    from persistence.codec_v3 import BusinessBuilder, encode as encode_value
    from persistence.schema_v3 import TABLES
    builder = BusinessBuilder('fixture-document', TABLES)
    builder.owner_aliases = owner_aliases or {}
    tree = encode_value(builder, namespace, key, value)
    assert tree is not None
    layout = builder.finish(tree)
    assert decode_tree(layout, builder.rows) == value
    return builder, layout


def test_business_tables_have_explicit_names_without_old_shape_fragments():
    from persistence.schema_v3 import TABLES, INDEXES
    expected = {'system_accounts', 'school_accounts', 'account_school_links',
        'school_account_information', 'system_settings', 'access_permissions',
        'account_sessions', 'authentication_tokens', 'deleted_account_archives',
        'payment_orders', 'billing_records', 'payment_order_bills', 'payment_refunds',
        'sms_records', 'messages', 'reminders', 'background_tasks',
        'background_image_state', 'storage_indexes'}
    assert set(TABLES) == expected
    assert all(not name.startswith('app_') for name in TABLES)
    assert ('account_school_links', ('owner_username', 'school_username'), True) in INDEXES
    assert {'owner_username', 'school_username', 'password', 'device_ua'} <= TABLES['account_school_links'].keys()


def test_system_account_keeps_session_links_in_the_account_row():
    value = {'auth_username': 'owner', 'password': 'hashed', 'group': 'custom',
             'session_ids': ['a', 'b'], '2fa_enabled': False,
             'theme_config': {'palette': ['blue', 'gray']}, 'available_runs': '0003'}
    builder, _ = encode('system_accounts', 'owner.json', value)
    assert set(builder.rows) == {'system_accounts'}
    row = builder.rows['system_accounts'][0]
    assert row['legacy_group'] == 'custom'
    assert row['available_runs'] == 3
    assert len(builder.rows['system_accounts']) == 1


def test_school_configuration_is_one_row_with_named_sections():
    value = {'Config': {'Username': '00123', 'password': 'global-legacy', 'speed_mps': '03.2'},
             'System': {'ua': 'legacy-UA', 'enabled': 'true'},
             'stats': {'overdue_count': '01', 'completed_count': '002'},
             'Account': {'Tag': 'my-tag'}, 'DEFAULT': {'option': 'inherited'},
             'UnknownSection': {'custom': ['keep', None, False]}}
    builder, _ = encode('school_accounts', '00123.ini', value)
    assert set(builder.rows) == {'school_accounts'}
    row = builder.rows['school_accounts'][0]
    assert row['school_username'] == '00123'
    assert {'configuration', 'system_parameters', 'statistics', 'account_options', 'defaults'} <= row.keys()
    assert len(builder.rows['school_accounts']) == 1


def test_school_information_keeps_conflicting_provider_sections_separate():
    value = {'backup_timestamp': 1763950001.1234567,
             'userInfo': {'name': 'student', 'id': 42, 'school_name': 'user-school'},
             'deptInfo': {'name': 'department', 'id': '00042', 'school_name': 'dept-school'},
             'completed_count': '001', 'custom': {'float': -0.0}}
    builder, _ = encode('school_accounts', '00123_backup.json', value)
    assert set(builder.rows) == {'school_account_information'}
    row = builder.rows['school_account_information'][0]
    assert row['school_username'] == '00123'
    assert {'user_info', 'department_info', 'completed_count'} <= row.keys()


@pytest.mark.parametrize('owner,ua', [('owner-a', 'UA-a'), ('owner-b', 'UA-b')])
def test_owner_binding_keeps_password_ua_and_legacy_statistics_isolated(owner, ua):
    value = {'00123': {'password': owner + '-password', 'ua': ua,
                       'overdue_count': 8, 'completed_count': 2}}
    builder, _ = encode('school_accounts', 'user_accounts/alias.json', value,
                        {'alias': owner})
    assert set(builder.rows) == {'account_school_links'}
    row = builder.rows['account_school_links'][0]
    assert row['owner_username'] == owner
    assert row['school_username'] == '00123'
    assert row['password'] == owner + '-password'
    assert row['device_ua'] == ua
    assert row['legacy_overdue_count'] == 8


@pytest.mark.parametrize('legacy', ['legacy-password', None, False, 0, {}])
def test_legacy_binding_shapes_are_lossless_without_fabricating_an_owner(legacy):
    builder, _ = encode('school_accounts', 'user_accounts/orphan-owner.json', {'00123': legacy})
    assert set(builder.rows) == {'account_school_links'}
    assert builder.rows['account_school_links'][0]['owner_username'] == 'orphan-owner'


def test_session_snapshots_and_multi_account_states_share_the_session_row():
    value = {'session_id': 'session-a', 'auth_username': 'owner', 'last_accessed': 1763950001.1234567,
             'is_authenticated': True, 'user_info': {'id': 22}, 'user_data': {'student_id': '00123'},
             'params': {'speed': '3.2'}, 'api_cookies': {'fixture': 'cookie'},
             'multi_account_states': {'00123': {'device_ua': 'isolated-UA', 'progress_pct': 0.0}},
             'loaded_tasks': [], 'ui_state': {'custom': False}}
    builder, _ = encode('sessions', 'session-a.json', value)
    assert set(builder.rows) == {'account_sessions'}
    assert len(builder.rows['account_sessions']) == 1
    assert {'params', 'api_cookies', 'user_info', 'user_data', 'multi_account_states'} <= builder.rows['account_sessions'][0].keys()


def test_permission_document_is_one_row_with_explicit_authorities():
    value = {'permission_groups': {'custom': {'permissions': {'run': False}}},
             'user_groups': {'owner': 'custom'},
             'user_custom_permissions': {'owner': {'added': ['view'], 'removed': ['run']}}}
    builder, _ = encode('settings', 'permissions.json', value)
    assert set(builder.rows) == {'access_permissions'}
    assert {'permission_groups', 'account_groups', 'account_overrides'} <= builder.rows['access_permissions'][0].keys()


@pytest.mark.parametrize('key,kind', [('owner.json', 'user'), ('guests/session-a.json', 'guest')])
def test_tokens_keep_kind_owner_and_hash_in_one_domain_table(key, kind):
    value = {'token': 'fixture-token', 'created_at': 1.25, 'expires_at': '003.00'}
    builder, _ = encode('tokens', key, value)
    assert set(builder.rows) == {'authentication_tokens'}
    row = builder.rows['authentication_tokens'][0]
    assert row['token_kind'] == kind
    assert row['token_hash'] == hashlib.sha256(b'fixture-token').hexdigest()


def test_settings_use_one_row_per_section_without_expanding_nested_leaves():
    value = {'System': {'nested': {'list': [False, None, '0001', 2**100, 1.2345678912345678]}},
             'Guest': {'enabled': False}, 'empty': {}}
    builder, _ = encode('configs', 'config.json', value)
    assert set(builder.rows) == {'system_settings'}
    assert len(builder.rows['system_settings']) == 3
    assert {row['section'] for row in builder.rows['system_settings']} == set(value)


def test_financial_entities_keep_separate_order_items_and_refunds():
    value = {'order_id': 'order-a', 'amount': '001.25', 'status': 'paid',
             'billing_items': [{'billing_id': 'bill-a', 'amount': 1.25, 'quantity': 1}],
             'refund_records': [{'refund_no': 'refund-a', 'refund_amount': 0.25}]}
    builder, _ = encode('payment_orders', 'order-a.json', value)
    assert set(builder.rows) == {'payment_orders', 'payment_order_bills', 'payment_refunds'}
    assert builder.rows['payment_orders'][0]['amount_minor'] == 125


def test_background_tasks_do_not_create_item_fragments():
    builder, _ = encode('background_tasks', 'task-a.json',
        {'session_id': 'session-a', 'execution_id': 'run-a', 'task_indices': [2, 0, 1],
         'singleProcessedPoints': 4, 'singleTotalPoints': 12})
    assert set(builder.rows) == {'background_tasks'}
    assert 'task_indices' in builder.rows['background_tasks'][0]


def test_background_image_collections_stay_in_one_state_row():
    value = {'schema_version': 1, 'next_revision': 2, 'assignments': {'a': {'target': 'pc'}},
             'bundles': {'b': {'pc_assignment_id': 'a'}}, 'identity_bindings': {'owner': {'bundle_id': 'b'}},
             'guest_bindings': {}, 'auth_claims': {}}
    builder, _ = encode('background_state', 'background_state.json', value)
    assert set(builder.rows) == {'background_image_state'}
    assert {'assignments', 'bundles', 'identity_bindings', 'guest_bindings', 'auth_claims'} <= builder.rows['background_image_state'][0].keys()


def test_legacy_indexes_remain_compatibility_metadata_without_subtables():
    value = {'accounts': {'owner': 'hash'}, 'updated_at': 'old-format'}
    builder, _ = encode('system_accounts', '_index.json', value)
    assert set(builder.rows) == {'storage_indexes'}
    assert len(builder.rows['storage_indexes']) == 1


def test_deleted_archive_does_not_create_live_accounts():
    value = {'auth_username': 'owner', 'deleted_at': '2026-01-01',
             'user_data': {'group': 'admin'}, 'school_accounts': {'00123': {'ua': 'historical'}}}
    builder, _ = encode('deleted_accounts', 'archived.json', value)
    assert set(builder.rows) == {'deleted_account_archives'}


def test_sms_history_is_a_dedicated_business_record():
    value = {'phone': '13800000000', 'scene': 'test_send', 'status': 'success',
             'provider': 'smsbao', 'response_message': 'accepted', 'timestamp': 123.25,
             'auth_username': 'owner', 'source': 'runtime'}
    builder, _ = encode('sms_records', 'sms-a.json', value)
    assert set(builder.rows) == {'sms_records'}
    assert builder.rows['sms_records'][0]['phone'] == '13800000000'
    assert builder.rows['sms_records'][0]['scene'] == 'test_send'
    assert builder.rows['sms_records'][0]['timestamp'] == 123.25


def test_sms_schema_uses_one_time_and_scene_authority_with_matching_indexes():
    from persistence.schema_v3 import TABLES, INDEXES
    assert not {'action', 'created_at'} & TABLES['sms_records'].keys()
    assert ('sms_records', ('timestamp',), False) in INDEXES
    assert ('sms_records', ('phone', 'timestamp'), False) in INDEXES
    assert ('sms_records', ('auth_username', 'timestamp'), False) in INDEXES
    assert ('sms_records', ('scene', 'status', 'timestamp'), False) in INDEXES


def test_legacy_sms_history_keeps_old_extensions_without_restoring_live_credentials():
    value = {'phone': '13800000000', 'code': 'historical-fixture', 'action': 'old-action',
             'created_at': '001.25', 'content': 'historical content', 'source': 'legacy'}
    builder, _ = encode('sms_records', 'sms-a.json', value)
    assert set(builder.rows) == {'sms_records'}
    assert 'code' not in builder.rows['sms_records'][0]
    assert 'created_at' not in builder.rows['sms_records'][0]


def test_unknown_legacy_documents_use_one_setting_row_instead_of_scalar_rows():
    value = [None, False, 42, {'huge': 2**100, 'float': 1.2345678912345678}]
    builder, _ = encode('legacy-extension', 'unknown.json', value)
    assert set(builder.rows) == {'system_settings'}
    assert len(builder.rows['system_settings']) == 1
