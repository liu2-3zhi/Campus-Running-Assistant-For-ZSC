"""Business aggregates for schema v3, without legacy table-name prefixes.

The v2 declarations remain unchanged for the offline migration reader. Small
collections that belong to one aggregate use named JSON columns rather than a
separate table for every section, option, profile or compatibility wrapper.
"""
from __future__ import annotations

from . import domains as _v2_domains
from . import identity as _v2_identity


SCHEMA_VERSION = '3'

TABLES = {
    'system_accounts': {
        **_v2_identity.TABLES['users'], 'session_ids': 'json',
    },
    'account_school_links': {
        'owner_username': 'text', 'school_username': 'text',
        'password': 'text', 'device_ua': 'text', 'legacy_value': 'json',
        'legacy_overdue_count': 'int', 'legacy_completed_count': 'int',
    },
    'school_accounts': {
        'school_username': 'text', 'source_key': 'text',
        'configuration': 'json', 'system_parameters': 'json',
        'statistics': 'json', 'account_options': 'json', 'defaults': 'json',
    },
    'school_account_information': {
        'school_username': 'text', 'source_key': 'text',
        'backup_timestamp': 'float', 'overdue_count': 'int', 'completed_count': 'int',
        'user_info': 'json', 'department_info': 'json',
    },
    'account_sessions': {
        **_v2_identity.TABLES['sessions'],
        **_v2_identity.TABLES['session_snapshots'],
        'user_info': 'json', 'user_data': 'json', 'multi_account_states': 'json',
    },
    'access_permissions': {
        'document_key': 'text', 'permission_groups': 'json',
        'account_groups': 'json', 'account_overrides': 'json',
    },
    'authentication_tokens': {
        'token_kind': 'text', 'owner_username': 'text', 'session_key': 'text',
        'session_id': 'text', 'principal_type': 'text', 'username': 'text',
        'token': 'text', 'token_hash': 'text', 'created_at': 'float',
        'expires_at': 'float', 'last_activity': 'float',
    },
    'deleted_account_archives': {
        **_v2_identity.TABLES['deleted_user_archives'],
        'source_namespace': 'text', 'source_key': 'text',
    },
    'background_tasks': {
        **_v2_domains.TABLES['background_task_states'], 'task_indices': 'json',
    },
    'background_image_state': {
        'schema_version': 'int', 'next_revision': 'int',
        'assignments': 'json', 'bundles': 'json', 'identity_bindings': 'json',
        'guest_bindings': 'json', 'auth_claims': 'json',
    },
    'system_settings': {
        'category': 'text', 'document_key': 'text', 'section': 'text', 'value': 'json',
    },
    'storage_indexes': {
        'namespace': 'text', 'document_key': 'text', 'value': 'json',
    },
    'sms_records': {
        'record_key': 'text', 'phone': 'text', 'status': 'text',
        'provider': 'text', 'response_code': 'text', 'response_message': 'text',
        'auth_username': 'text', 'source': 'text',
        'timestamp': 'float', 'datetime': 'text', 'username': 'text',
        'scene': 'text', 'ip': 'text',
    },
}

# These business boundaries were already meaningful in v2. Preserve their typed
# values and record codecs instead of changing financial semantics during a
# schema consolidation.
_UNCHANGED = {'payment_orders', 'billing_records', 'payment_order_bills',
              'payment_refunds', 'messages', 'reminders'}
TABLES.update({name: dict(_v2_domains.TABLES[name]) for name in sorted(_UNCHANGED)})

INDEXES = [
    ('system_accounts', ('auth_username',), True),
    ('system_accounts', ('phone',), False),
    ('account_school_links', ('owner_username', 'school_username'), True),
    ('account_school_links', ('school_username',), False),
    ('school_accounts', ('school_username',), True),
    ('school_account_information', ('school_username',), False),
    ('school_account_information', ('source_key',), True),
    ('account_sessions', ('session_id',), True),
    ('account_sessions', ('auth_username',), False),
    ('account_sessions', ('last_accessed',), False),
    ('access_permissions', ('document_key',), True),
    ('authentication_tokens', ('token_kind', 'owner_username', 'session_key'), True),
    ('authentication_tokens', ('token_hash',), False),
    ('authentication_tokens', ('expires_at',), False),
    ('deleted_account_archives', ('archive_id',), True),
    ('deleted_account_archives', ('auth_username',), False),
    ('background_tasks', ('session_id', 'execution_id'), False),
    ('background_tasks', ('status', 'last_update'), False),
    ('system_settings', ('category', 'document_key', 'section'), True),
    ('storage_indexes', ('namespace', 'document_key'), True),
    ('sms_records', ('record_key',), True),
    ('sms_records', ('timestamp',), False),
    ('sms_records', ('phone', 'timestamp'), False),
    ('sms_records', ('auth_username', 'timestamp'), False),
    ('sms_records', ('scene', 'status', 'timestamp'), False),
]
INDEXES.extend(index for index in _v2_domains.INDEXES if index[0] in _UNCHANGED)
