"""Identity documents must reconstruct from independently editable entity rows."""

import hashlib

import pytest

from persistence import identity
from persistence.codec import Builder, decode_tree


def encode_document(namespace, key, value):
    document_id = hashlib.sha256(f'{namespace}/{key}'.encode()).hexdigest()
    builder = Builder(document_id, identity.TABLES)
    tree = identity.encode(builder, namespace, key, value)
    assert tree is not None
    layout = builder.finish(tree)
    assert decode_tree(layout, builder.rows) == value
    return layout, builder.rows


def test_user_identity_fields_and_session_links_are_relational():
    source = {'auth_username': 'Alice', 'password': 'stored-hash', 'group': 'user',
              'created_at': 100.5, 'last_login': None, '2fa_enabled': False,
              'session_ids': ['session-one', 'session-two'], 'available_runs': -1,
              'nickname': '', 'dynamic': {'unset': None, 'literal': 'NA'}}
    layout, rows = encode_document('system_accounts', 'hash.json', source)
    user = rows['users'][0]
    assert user['auth_username'] == 'Alice'
    assert user['password'] == 'stored-hash'
    assert user['legacy_group'] == 'user'
    assert user['available_runs'] == -1
    assert 'password' not in user['extra']
    assert [row['session_id'] for row in rows['user_session_links']] == ['session-one', 'session-two']
    user['nickname'] = 'Changed in SQL'
    assert decode_tree(layout, rows)['nickname'] == 'Changed in SQL'
    assert source['nickname'] == ''


def test_usernames_keep_case_and_leading_zero_school_ids():
    _, first = encode_document('system_accounts', 'upper.json', {'auth_username': 'Alice'})
    _, second = encode_document('system_accounts', 'lower.json', {'auth_username': 'alice'})
    assert first['users'][0]['auth_username'] != second['users'][0]['auth_username']
    _, bindings = encode_document('school_accounts', 'user_accounts/Alice.json',
                                  {'00042': {'password': 'one', 'ua': 'UA-one'}})
    assert bindings['user_school_accounts'][0]['school_username'] == '00042'


def test_same_school_account_retains_owner_specific_password_and_ua():
    _, first = encode_document('school_accounts', 'user_accounts/owner-a.json',
                               {'00042': {'password': 'one', 'ua': 'UA-one'}})
    _, second = encode_document('school_accounts', 'user_accounts/owner-b.json',
                                {'00042': {'password': 'two', 'ua': 'UA-two'}})
    a, b = first['user_school_accounts'][0], second['user_school_accounts'][0]
    assert (a['owner_username'], a['school_username'], a['password'], a['device_ua']) == ('owner-a', '00042', 'one', 'UA-one')
    assert (b['owner_username'], b['school_username'], b['password'], b['device_ua']) == ('owner-b', '00042', 'two', 'UA-two')
    assert all('owner_username' not in row or row['owner_username'] is None
               for row in first.get('school_accounts', []))


def test_legacy_binding_scalar_password_is_queryable_and_preserves_shape():
    layout, rows = encode_document('school_accounts', 'user_accounts/owner.json',
                                  {'00042': 'legacy-password', '00043': {'password': None, 'ua': ''}})
    assert rows['user_school_accounts'][0]['password'] == 'legacy-password'
    rows['user_school_accounts'][0]['password'] = 'new-password'
    assert decode_tree(layout, rows)['00042'] == 'new-password'
    assert decode_tree(layout, rows)['00043'] == {'password': None, 'ua': ''}


def test_binding_missing_null_and_empty_ua_never_inherit_another_ua():
    source = {'00042': {'password': 'one', 'ua': 'first-UA'},
              '00043': {'password': 'two'},
              '00044': {'password': 'three', 'ua': None},
              '00045': {'password': 'four', 'ua': ''}}
    _, rows = encode_document('school_accounts', 'user_accounts/owner.json', source)
    bindings = rows['user_school_accounts']
    assert 'device_ua' not in bindings[1]
    assert bindings[2]['device_ua'] is None
    assert bindings[3]['device_ua'] == ''


def test_legacy_binding_counters_are_school_scoped_and_not_owner_counters():
    source = {'00042': {'password': 'one', 'ua': 'first-UA',
                         'overdue_count': 2, 'completed_count': 13}}
    layout, rows = encode_document('school_accounts', 'user_accounts/owner.json', source)
    assert rows['school_account_stats'][0]['school_username'] == '00042'
    assert 'owner_username' not in rows['school_account_stats'][0]
    assert 'overdue_count' not in identity.TABLES['user_school_accounts']
    rows['school_account_stats'][0]['completed_count'] = 14
    assert decode_tree(layout, rows)['00042']['completed_count'] == 14


def test_ini_statistics_are_global_and_backup_ua_is_not_owner_binding():
    source = {'Config': {'Username': '00042', 'password': 'backup', 'speed': '2.6'},
              'System': {'ua': 'legacy-backup-UA'},
              'stats': {'overdue_count': '2', 'completed_count': '13', 'custom': 'NA'},
              'Account': {'Tag': ''}, 'Custom': {'empty': '', 'literal': 'NULL'}}
    layout, rows = encode_document('school_accounts', '00042.ini', source)
    assert rows['school_accounts'][0]['school_username'] == '00042'
    stats = rows['school_account_stats'][0]
    assert (stats['overdue_count'], stats['completed_count']) == (2, 13)
    assert not rows.get('user_school_accounts')
    assert rows['school_account_settings'][0]['legacy_device_ua'] == 'legacy-backup-UA'
    stats['overdue_count'] = 3
    assert decode_tree(layout, rows)['stats']['overdue_count'] == '3'


def test_permissions_are_split_and_deny_precedence_is_preserved():
    source = {'permission_groups': {'user': {'display_name': 'User', 'is_system': True,
              'permissions': {'run': True, 'manage_users': False}}},
              'user_groups': {'Alice': 'user'},
              'user_custom_permissions': {'Alice': {'added': ['read', 'run'], 'removed': ['run']}},
              'extension': {'version': 7}}
    layout, rows = encode_document('settings', 'permissions.json', source)
    assert rows['permission_groups'][0]['group_name'] == 'user'
    assert [(r['permission'], r['enabled']) for r in rows['group_permissions']] == [('run', True), ('manage_users', False)]
    assert rows['user_groups'][0]['auth_username'] == 'Alice'
    assert rows['user_groups'][0]['group_name'] == 'user'
    assert [(r['permission'], r['effect']) for r in rows['user_permission_overrides']] == [('read', 'allow'), ('run', 'allow'), ('run', 'deny')]
    rows['group_permissions'][1]['enabled'] = True
    assert decode_tree(layout, rows)['permission_groups']['user']['permissions']['manage_users'] is True


def test_school_profile_backup_is_separate_from_owner_credentials():
    source = {'userInfo': {'name': 'Student', 'username': '00042', 'id': 7,
                           'external_field': {'literal': 'NA'}},
              'deptInfo': {'name': 'Department', 'external_id': '001'},
              'backup_timestamp': 100.5, 'overdue_count': 2, 'completed_count': 13}
    layout, rows = encode_document('school_accounts', '00042/00042_backup.json', source)
    assert rows['school_account_profiles'][0]['school_username'] == '00042'
    assert len(rows['school_profile_sections']) == 2
    assert not rows.get('user_school_accounts')
    rows['school_profile_sections'][0]['name'] = 'Updated Student'
    assert decode_tree(layout, rows)['userInfo']['name'] == 'Updated Student'


def test_session_snapshots_and_account_state_keep_independent_ua():
    source = {'session_id': 'session-one', 'auth_username': 'Alice',
              'device_ua': 'parent-UA', 'is_multi_account_mode': True,
              'created_at': 100.0, 'last_accessed': 101.0,
              'params': {'speed': 2.6}, 'api_cookies': {'session': 'cookie'},
              'loaded_tasks': [{'run_name': 'run', 'extension': None}],
              'multi_account_usernames': ['00042', '00043'],
              'multi_account_states': {
                  '00042': {'device_ua': 'first-UA', 'params': {'speed': 2.2}, 'progress_pct': 12},
                  '00043': {'device_ua': '', 'status_text': 'waiting', 'unknown': 'NA'}}}
    layout, rows = encode_document('sessions', 'hash.json', source)
    assert rows['sessions'][0]['auth_username'] == 'Alice'
    assert len(rows['session_snapshots']) == 1
    assert [row['device_ua'] for row in rows['session_account_states']] == ['first-UA', '']
    assert rows['session_account_states'][1]['school_username'] == '00043'
    rows['session_account_states'][0]['device_ua'] = 'changed-UA'
    restored = decode_tree(layout, rows)
    assert restored['multi_account_states']['00042']['device_ua'] == 'changed-UA'
    assert restored['multi_account_states']['00043']['device_ua'] == ''
    assert restored['device_ua'] == 'parent-UA'


def test_partial_session_preserves_missing_fields_and_unrecognized_state_values():
    source = {'session_id': 'partial', 'is_guest': False, 'user_info': None,
              'multi_account_states': {'00042': None, '00043': {'params': {}, 'extension': 'NA'}},
              'dynamic': {'missing_value': None}}
    layout, rows = encode_document('sessions', 'partial.json', source)
    assert 'device_ua' not in rows['sessions'][0]
    assert len(rows['session_account_states']) == 1
    assert 'device_ua' not in rows['session_account_states'][0]
    assert 'created_at' not in decode_tree(layout, rows)


def test_regular_token_is_one_per_user_without_session_ownership():
    source = {'token': 'synthetic-token', 'created_at': 100.0, 'expires_at': 200.0, 'last_activity': 101.0}
    layout, rows = encode_document('tokens', 'Alice.json', source)
    token = rows['user_tokens'][0]
    assert token['auth_username'] == 'Alice'
    assert token['token_hash'] == hashlib.sha256(b'synthetic-token').hexdigest()
    assert 'session_id' not in identity.TABLES['user_tokens']
    token['expires_at'] = 300.0
    assert decode_tree(layout, rows)['expires_at'] == 300.0


def test_health_token_index_is_metadata_and_never_a_registered_user_token():
    source = {'synthetic-token-hash': 'Alice'}
    _, rows = encode_document('tokens', '_health_token_index.json', source)
    assert not rows.get('user_tokens')
    assert not rows.get('guest_tokens')


def test_sql_value_replaces_an_original_null_without_losing_json_shape():
    layout, rows = encode_document('system_accounts', 'hash.json',
                                  {'auth_username': 'Alice', 'last_login': None})
    rows['users'][0]['last_login'] = 123.5
    assert decode_tree(layout, rows)['last_login'] == 123.5


def test_sql_null_replaces_an_original_non_null_value():
    layout, rows = encode_document('system_accounts', 'hash.json',
                                  {'auth_username': 'Alice', 'last_login': 123.5})
    rows['users'][0]['last_login'] = None
    assert decode_tree(layout, rows)['last_login'] is None


def test_text_column_mapping_preserves_a_legacy_false_boolean():
    encode_document('school_accounts', 'user_accounts/Alice.json',
                    {'00042': {'password': False, 'ua': False}})


def test_owner_alias_injection_keeps_unsafe_username_at_binding_level():
    builder = Builder('document', identity.TABLES)
    builder.owner_aliases = {'invalid_synthetic_hash': 'unsafe/name'}
    source = {'00042': {'password': 'test', 'ua': 'UA-A'}}
    tree = identity.encode(builder, 'school_accounts', 'user_accounts/invalid_synthetic_hash.json', source)
    assert builder.rows['user_school_accounts'][0]['owner_username'] == 'unsafe/name'
    assert decode_tree(builder.finish(tree), builder.rows) == source


def test_guest_token_is_owned_by_its_uuid_not_guest_username():
    source = {'token': 'synthetic-guest-token', 'session_id': 'guest-session',
              'principal_type': 'guest', 'username': 'guest', 'created_at': 100.0, 'expires_at': 200.0}
    _, rows = encode_document('tokens', 'guests/guest-session.json', source)
    assert not rows.get('user_tokens')
    assert rows['guest_tokens'][0]['session_id'] == 'guest-session'
    assert rows['guest_tokens'][0]['session_key'] == 'guest-session'


@pytest.mark.parametrize(('namespace', 'key', 'source'), [
    ('system_accounts', '_index.json', {'accounts': {'Alice': 'hash'}, 'updated_at': 'now'}),
    ('sessions', '_index.json', {'session-one': 'hash'}),
    ('tokens', 'guests/_index.json', {'sessions': {'guest-session': {'token_hash': 'hash'}}}),
    ('deleted_accounts', '_index.json', {'removed_accounts': {'Alice': ['archive']}}),
])
def test_legacy_indexes_never_create_live_entities(namespace, key, source):
    _, rows = encode_document(namespace, key, source)
    for name in ('users', 'sessions', 'user_tokens', 'guest_tokens', 'deleted_user_archives'):
        assert not rows.get(name)


def test_deletion_archive_retains_history_without_creating_live_identity():
    source = {'auth_username': 'Alice', 'deleted_at': '2026-11-24T10:00:00Z',
              'user_data': {'auth_username': 'Alice', 'password': 'old-hash', 'nickname': None},
              'school_accounts': {'00042': {'password': 'old-password', 'ua': 'old-UA'}},
              'permissions': {'user_groups': 'user', 'user_custom_permissions': {'added': [], 'removed': ['run']}}}
    _, rows = encode_document('deleted_accounts', 'archive-uuid.json', source)
    assert rows['deleted_user_archives'][0]['auth_username'] == 'Alice'
    assert rows['deleted_user_archives'][0]['legacy_archive_id'] == 'archive-uuid'
    assert not rows.get('users')
    assert not rows.get('user_school_accounts')


def test_same_legacy_archive_filename_keeps_each_source_as_distinct_history():
    source = {'auth_username': 'Alice', 'deleted_at': '2026-11-24T10:00:00Z',
              'user_data': {'nickname': 'historical-name'}}
    _, removed = encode_document('deleted_accounts', 'archive-uuid.json', source)
    _, retained = encode_document('system_accounts', 'archive-uuid.json', source)
    a = removed['deleted_user_archives'][0]
    b = retained['deleted_user_archives'][0]
    assert a['archive_id'] != b['archive_id']
    assert a['legacy_archive_id'] == b['legacy_archive_id'] == 'archive-uuid'
    _, repeated = encode_document('deleted_accounts', 'archive-uuid.json', source)
    assert repeated['deleted_user_archives'][0]['archive_id'] == a['archive_id']


def test_unknown_domain_is_not_claimed_by_identity_encoder():
    builder = Builder('document', identity.TABLES)
    assert identity.encode(builder, 'payment_orders', 'order.json', {'status': 'pending'}) is None
    assert builder.rows == {}
