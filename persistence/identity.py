"""Relational identity, account, permission and authentication document codecs.

Only compatibility structure remains in collection layouts. Credentials and UA
belong to an owner/school binding; global school configuration and statistics do
not acquire an owner. Historical deletion snapshots never create live users.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath


TABLES = {
    'users': {
        'auth_username': 'text', 'password': 'text', 'legacy_group': 'text',
        'created_at': 'float', 'last_login': 'float', 'last_login_ip': 'text',
        'last_login_city': 'text', 'banned': 'bool', 'phone': 'text',
        'nickname': 'text', 'avatar_url': 'text', 'max_sessions': 'int',
        'available_runs': 'int', 'two_factor_enabled': 'bool',
        'two_factor_secret': 'text', 'last_used_school_account': 'text',
        'theme': 'text', 'theme_config': 'json', 'account_cancellation': 'json',
    },
    'user_session_links': {'auth_username': 'text', 'session_id': 'text'},
    'identity_collections': {'collection_kind': 'text', 'owner_username': 'text'},
    'identity_indexes': {'index_kind': 'text', 'updated_at': 'text'},
    'identity_index_entries': {'index_kind': 'text', 'index_key': 'text', 'target': 'json'},
    'permission_groups': {'group_name': 'text', 'display_name': 'text', 'is_system': 'bool'},
    'group_permissions': {'group_name': 'text', 'permission': 'text', 'enabled': 'bool'},
    'user_groups': {'auth_username': 'text', 'group_name': 'text'},
    'user_permission_sets': {'auth_username': 'text'},
    'user_permission_overrides': {'auth_username': 'text', 'permission': 'text', 'effect': 'text'},
    'user_school_accounts': {
        'owner_username': 'text', 'school_username': 'text',
        'password': 'text', 'device_ua': 'text', 'legacy_value': 'json',
    },
    'school_accounts': {'school_username': 'text', 'source_kind': 'text'},
    'school_account_settings': {
        'school_username': 'text', 'configured_username': 'text',
        'legacy_password': 'text', 'legacy_device_ua': 'text',
    },
    'school_account_parameters': {
        'school_username': 'text', 'section': 'text', 'option_name': 'text', 'value': 'json',
    },
    'school_account_stats': {
        'school_username': 'text', 'source_kind': 'text',
        'overdue_count': 'int', 'completed_count': 'int',
    },
    'school_account_tags': {'school_username': 'text', 'tag': 'text'},
    'school_account_profiles': {'school_username': 'text', 'backup_timestamp': 'float'},
    'school_profile_sections': {
        'school_username': 'text', 'profile_kind': 'text', 'name': 'text',
        'username': 'text', 'student_id': 'text', 'external_id': 'json',
        'school_name': 'text', 'phone': 'text', 'gender': 'json',
    },
    'sessions': {
        'session_id': 'text', 'auth_username': 'text', 'auth_group': 'text',
        'created_at': 'float', 'last_accessed': 'float', 'last_saved': 'float',
        'is_guest': 'bool', 'is_authenticated': 'bool',
        'school_account_logged_in': 'bool', 'login_success': 'bool',
        'device_ua': 'text', 'is_multi_account_mode': 'bool',
        'is_offline_mode': 'bool', 'stop_run_flag_set': 'bool',
    },
    'session_snapshots': {
        'session_id': 'text', 'params': 'json', 'api_cookies': 'json',
        'loaded_tasks': 'json', 'cached_notifications': 'json',
        'current_run_idx': 'int', 'multi_global_params': 'json',
        'multi_account_usernames': 'json', 'multi_dashboard_info': 'json',
        'dashboard_info': 'json', 'ui_state': 'json', 'user_settings': 'json',
    },
    'session_profiles': {
        'session_id': 'text', 'profile_kind': 'text', 'name': 'text',
        'username': 'text', 'student_id': 'text', 'external_id': 'json',
        'school_name': 'text', 'phone': 'text', 'gender': 'json',
    },
    'session_account_states': {
        'session_id': 'text', 'school_username': 'text', 'device_ua': 'text',
        'status_text': 'text', 'is_first_login_verified': 'bool',
        'school_account_logged_in': 'bool', 'summary': 'json',
        'progress_pct': 'float', 'progress_text': 'text', 'progress_extra': 'json',
        'current_position': 'json', 'params': 'json',
    },
    'user_tokens': {
        'auth_username': 'text', 'token': 'text', 'token_hash': 'text',
        'created_at': 'float', 'expires_at': 'float', 'last_activity': 'float',
    },
    'guest_tokens': {
        'session_key': 'text', 'session_id': 'text', 'principal_type': 'text',
        'username': 'text', 'token': 'text', 'token_hash': 'text',
        'created_at': 'float', 'expires_at': 'float', 'last_activity': 'float',
    },
    'deleted_user_archives': {
        'archive_id': 'text', 'legacy_archive_id': 'text',
        'source_archive_id': 'json', 'source_id': 'json',
        'auth_username': 'text', 'deleted_at': 'text',
        'user_data': 'json', 'school_accounts': 'json', 'permissions': 'json',
    },
}

INDEXES = [
    ('users', ('auth_username',), True),
    ('users', ('phone',), False),
    ('user_session_links', ('auth_username', 'session_id'), False),
    ('permission_groups', ('group_name',), True),
    ('group_permissions', ('group_name', 'permission'), True),
    ('user_groups', ('auth_username',), True),
    ('user_permission_overrides', ('auth_username', 'permission', 'effect'), False),
    ('user_school_accounts', ('owner_username', 'school_username'), True),
    ('school_accounts', ('school_username',), True),
    ('school_account_stats', ('school_username',), False),
    ('school_account_parameters', ('school_username', 'section', 'option_name'), False),
    ('school_account_profiles', ('school_username',), False),
    ('sessions', ('session_id',), True),
    ('sessions', ('auth_username',), False),
    ('sessions', ('last_accessed',), False),
    ('session_account_states', ('session_id', 'school_username'), True),
    ('user_tokens', ('auth_username',), True),
    ('user_tokens', ('token_hash',), False),
    ('guest_tokens', ('session_key',), True),
    ('guest_tokens', ('token_hash',), False),
    ('deleted_user_archives', ('archive_id',), True),
    ('deleted_user_archives', ('auth_username',), False),
]

_USER_FIELDS = {name: name for name in TABLES['users']}
_USER_FIELDS.update({'group': 'legacy_group', '2fa_enabled': 'two_factor_enabled',
                     '2fa_secret': 'two_factor_secret'})
# Compatibility aliases above are source keys, not additional authorities.
for _name in ('legacy_group', 'two_factor_enabled', 'two_factor_secret'):
    _USER_FIELDS.pop(_name, None)

_PROFILE_FIELDS = {
    'name': 'name', 'username': 'username', 'student_id': 'student_id',
    'id': 'external_id', 'school_name': 'school_name', 'phone': 'phone', 'gender': 'gender',
}
_SESSION_FIELDS = {name: name for name in TABLES['sessions']}
_SNAPSHOT_FIELDS = {name: name for name in TABLES['session_snapshots'] if name != 'session_id'}
_STATE_FIELDS = {name: name for name in TABLES['session_account_states']
                 if name not in ('session_id', 'school_username')}
_TOKEN_FIELDS = {name: name for name in ('token', 'created_at', 'expires_at', 'last_activity')}
_STATS_FIELDS = {'overdue_count': 'overdue_count', 'completed_count': 'completed_count'}


def _project(ref, field):
    """Reference a source field without storing its value a second time."""
    return type(ref)(ref.table, ref.row_id, field)


def _collection(builder, tree, kind, **constants):
    return builder.record('identity_collections', tree, {}, collection_kind=kind, **constants)


def _flatten_record(builder, tree, table, fields, **constants):
    selected = {key: tree[key] for key in fields if key in tree}
    if selected:
        ref = builder.record(table, selected, fields, **constants)
        for key in selected:
            tree[key] = _project(ref, key)


def _index(builder, namespace, key, value):
    tree = dict(value)
    kind = f'{namespace}:{key}'
    containers = ('accounts', 'sessions', 'removed_accounts')
    for name in containers:
        if isinstance(tree.get(name), dict):
            tree[name] = {entry: builder.scalar('identity_index_entries', target,
                column_name='target', kind='json', index_kind=kind, index_key=entry)
                for entry, target in tree[name].items()}
    if namespace == 'sessions' or (namespace == 'tokens' and key == '_health_token_index.json'):
        for entry, target in tuple(tree.items()):
            if entry not in containers and entry != 'updated_at':
                tree[entry] = builder.scalar('identity_index_entries', target,
                    column_name='target', kind='json', index_kind=kind, index_key=entry)
    return builder.record('identity_indexes', tree, {'updated_at': 'updated_at'}, index_kind=kind)


def _user(builder, value):
    tree = dict(value)
    username = value.get('auth_username')
    if isinstance(value.get('session_ids'), list):
        tree['session_ids'] = [builder.scalar('user_session_links', session_id,
            column_name='session_id', kind='text', auth_username=username)
            for session_id in value['session_ids']]
    return builder.record('users', tree, _USER_FIELDS)


def _permissions(builder, value):
    tree = dict(value)
    groups = tree.get('permission_groups')
    if isinstance(groups, dict):
        encoded = {}
        for name, data in groups.items():
            if not isinstance(data, dict):
                encoded[name] = data
                continue
            group = dict(data)
            if isinstance(group.get('permissions'), dict):
                group['permissions'] = {permission: builder.scalar('group_permissions', enabled,
                    column_name='enabled', kind='bool', group_name=name, permission=permission)
                    for permission, enabled in group['permissions'].items()}
            encoded[name] = builder.record('permission_groups', group,
                {'display_name': 'display_name', 'is_system': 'is_system'}, group_name=name)
        tree['permission_groups'] = encoded
    if isinstance(tree.get('user_groups'), dict):
        tree['user_groups'] = {username: builder.scalar('user_groups', group,
            column_name='group_name', kind='text', auth_username=username)
            for username, group in tree['user_groups'].items()}
    overrides = tree.get('user_custom_permissions')
    if isinstance(overrides, dict):
        encoded = {}
        for username, data in overrides.items():
            if not isinstance(data, dict):
                encoded[username] = data
                continue
            custom = dict(data)
            for source, effect in (('added', 'allow'), ('removed', 'deny')):
                if isinstance(custom.get(source), list):
                    custom[source] = [builder.scalar('user_permission_overrides', permission,
                        column_name='permission', kind='text', auth_username=username, effect=effect)
                        for permission in custom[source]]
            encoded[username] = builder.record('user_permission_sets', custom, {}, auth_username=username)
        tree['user_custom_permissions'] = encoded
    return _collection(builder, tree, 'permissions')


def _bindings(builder, key, value):
    owner_key = PurePosixPath(key).stem
    owner = getattr(builder, 'owner_aliases', {}).get(owner_key, owner_key)
    tree = {}
    for school_username, data in value.items():
        constants = {'owner_username': owner, 'school_username': school_username}
        if isinstance(data, dict):
            binding = dict(data)
            _flatten_record(builder, binding, 'school_account_stats', _STATS_FIELDS,
                            school_username=school_username, source_kind='legacy_binding')
            fields = {'password': 'password'}
            fields['ua' if 'ua' in data else 'device_ua'] = 'device_ua'
            tree[school_username] = builder.record('user_school_accounts', binding, fields, **constants)
        elif isinstance(data, str):
            tree[school_username] = builder.scalar('user_school_accounts', data,
                column_name='password', kind='text', **constants)
        else:
            tree[school_username] = builder.scalar('user_school_accounts', data,
                column_name='legacy_value', kind='json', **constants)
    return _collection(builder, tree, 'owner_school_accounts', owner_username=owner)


def _school_ini(builder, key, value):
    school_username = PurePosixPath(key).stem
    tree = {section: dict(options) if isinstance(options, dict) else options
            for section, options in value.items()}
    settings = {}
    setting_paths = []
    for section, source, virtual_key, column in (
        ('Config', 'Username', 'config_username', 'configured_username'),
        ('Config', 'password', 'config_password', 'legacy_password'),
        ('System', 'ua', 'system_ua', 'legacy_device_ua'),
    ):
        options = tree.get(section)
        if isinstance(options, dict) and source in options:
            settings[virtual_key] = options[source]
            setting_paths.append((section, source, virtual_key, column))
    if settings:
        ref = builder.record('school_account_settings', settings,
            {virtual: column for _, _, virtual, column in setting_paths}, school_username=school_username)
        for section, source, virtual, _ in setting_paths:
            tree[section][source] = _project(ref, virtual)
    special = {(section, source) for section, source, _, _ in setting_paths}
    for section, options in tuple(tree.items()):
        if not isinstance(options, dict):
            continue
        if section == 'stats':
            tree[section] = builder.record('school_account_stats', options, _STATS_FIELDS,
                                          school_username=school_username, source_kind='ini')
            continue
        if section == 'Account':
            _flatten_record(builder, options, 'school_account_tags', {'Tag': 'tag'},
                            school_username=school_username)
        for option, data in tuple(options.items()):
            if (section, option) in special or (section == 'Account' and option == 'Tag'):
                continue
            options[option] = builder.scalar('school_account_parameters', data,
                column_name='value', kind='json', school_username=school_username,
                section=section, option_name=option)
    return builder.record('school_accounts', tree, {}, school_username=school_username, source_kind='ini')


def _school_profile(builder, key, value):
    filename = PurePosixPath(key).name
    school_username = filename[:-len('_backup.json')]
    tree = dict(value)
    _flatten_record(builder, tree, 'school_account_stats', _STATS_FIELDS,
                    school_username=school_username, source_kind='backup')
    for name in ('userInfo', 'deptInfo'):
        if isinstance(tree.get(name), dict):
            tree[name] = builder.record('school_profile_sections', tree[name], _PROFILE_FIELDS,
                                        school_username=school_username, profile_kind=name)
    return builder.record('school_account_profiles', tree, {'backup_timestamp': 'backup_timestamp'},
                          school_username=school_username)


def _session(builder, value):
    tree = dict(value)
    session_id = value.get('session_id')
    _flatten_record(builder, tree, 'session_snapshots', _SNAPSHOT_FIELDS, session_id=session_id)
    for name in ('user_info', 'user_data'):
        if isinstance(tree.get(name), dict):
            tree[name] = builder.record('session_profiles', tree[name], _PROFILE_FIELDS,
                                        session_id=session_id, profile_kind=name)
    states = tree.get('multi_account_states')
    if isinstance(states, dict):
        tree['multi_account_states'] = {username: (builder.record('session_account_states', data,
            _STATE_FIELDS, session_id=session_id, school_username=username) if isinstance(data, dict) else data)
            for username, data in states.items()}
    return builder.record('sessions', tree, _SESSION_FIELDS)


def _token(builder, key, value):
    fields = dict(_TOKEN_FIELDS)
    token = value.get('token')
    constants = {'token_hash': hashlib.sha256(token.encode('utf-8')).hexdigest() if isinstance(token, str) else None}
    if PurePosixPath(key).parts[0] in ('guests', '.guest_store'):
        fields.update({name: name for name in ('session_id', 'principal_type', 'username')})
        return builder.record('guest_tokens', value, fields,
            session_key=PurePosixPath(key).stem, **constants)
    return builder.record('user_tokens', value, fields,
        auth_username=PurePosixPath(key).stem, **constants)


def _archive(builder, namespace, key, value):
    archive_id = hashlib.sha256(f'{namespace}\0{key}'.encode('utf-8')).hexdigest()
    return builder.record('deleted_user_archives', value,
        {**{name: name for name in ('auth_username', 'deleted_at', 'user_data', 'school_accounts', 'permissions')},
         'archive_id': 'source_archive_id', 'id': 'source_id'},
        archive_id=archive_id, legacy_archive_id=PurePosixPath(key).stem)


def encode(builder, namespace, key, value):
    """Return a relational tree for owned namespaces, otherwise ``None``."""
    if not isinstance(value, dict):
        return None
    path = PurePosixPath(key)
    if namespace == 'tokens' and key == '_health_token_index.json':
        return _index(builder, namespace, key, value)
    if namespace in ('system_accounts', 'school_accounts', 'sessions', 'tokens',
                     'deleted_accounts', 'legacy_deleted_accounts') and path.name == '_index.json':
        return _index(builder, namespace, key, value)
    if namespace in ('deleted_accounts', 'legacy_deleted_accounts'):
        return _archive(builder, namespace, key, value)
    if namespace == 'system_accounts':
        if 'user_data' in value and ('deleted_at' in value or 'remove' in path.parts):
            return _archive(builder, namespace, key, value)
        return _user(builder, value)
    if namespace == 'settings' and key == 'permissions.json':
        return _permissions(builder, value)
    if namespace == 'school_accounts':
        if len(path.parts) >= 2 and path.parts[-2] == 'user_accounts' and path.suffix == '.json':
            return _bindings(builder, key, value)
        if path.suffix == '.ini':
            return _school_ini(builder, key, value)
        if path.name.endswith('_backup.json'):
            return _school_profile(builder, key, value)
        return None
    if namespace == 'sessions':
        return _session(builder, value)
    if namespace == 'tokens':
        return _token(builder, key, value)
    return None
