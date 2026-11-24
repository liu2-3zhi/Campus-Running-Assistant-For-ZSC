"""Lossless document compatibility over the v3 business aggregates.

Business fields stay authoritative SQL columns. Flexible provider data and
aggregate-owned collections use named JSON columns; a config option or session
profile no longer needs its own table and entity-reference chain.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from .codec import Builder
from . import domains as _v2_domains
from .schema_v3 import TABLES


class BusinessBuilder(Builder):
    """Use native SQL JSON only for v3's mapped business columns.

    The v2 Builder, compatibility layout and unmapped extras retain their
    original representation. Inherited scalar() calls record(), which also
    covers JSON fields produced by the reused financial/content codecs.
    """

    def record(self, table, data, fields=None, **constants):
        native_fields = None if fields is None else {}
        for source, spec in (fields or {}).items():
            column, kind = spec if isinstance(spec, (tuple, list)) else (
                spec, self.schemas.get(table, {}).get(spec, 'text'))
            native_fields[source] = (column, 'json_native' if kind == 'json' else kind)
        return super().record(table, data, native_fields, **constants)


def _record(builder, table, value, fields=None, **constants):
    fields = fields if fields is not None else {name: name for name in TABLES[table] if name in value}
    typed = {source: (column, TABLES[table][column]) for source, column in fields.items()}
    return builder.record(table, value, typed, **constants)


def _scalar(builder, table, value, **constants):
    return builder.scalar(table, value, kind='json', **constants)


def _account(builder, value):
    fields = {name: name for name in TABLES['system_accounts'] if name in value}
    for source, column in (('group', 'legacy_group'), ('2fa_enabled', 'two_factor_enabled'),
                           ('2fa_secret', 'two_factor_secret')):
        if source in value:
            fields[source] = column
            # Both names can occur in old extension data. Only the documented
            # source key owns the typed column; preserve the other as an extra.
            fields.pop(column, None)
    return _record(builder, 'system_accounts', value, fields)


def _bindings(builder, key, value):
    owner_key = PurePosixPath(key).stem
    owner = getattr(builder, 'owner_aliases', {}).get(owner_key, owner_key)
    result = {}
    for school_username, data in value.items():
        constants = {'owner_username': owner, 'school_username': school_username}
        if isinstance(data, dict):
            fields = {}
            for source, column in (('password', 'password'), ('overdue_count', 'legacy_overdue_count'),
                                   ('completed_count', 'legacy_completed_count')):
                if source in data:
                    fields[source] = column
            source_ua = 'ua' if 'ua' in data else 'device_ua'
            if source_ua in data:
                fields[source_ua] = 'device_ua'
            result[school_username] = _record(builder, 'account_school_links', data, fields, **constants)
        elif isinstance(data, str):
            result[school_username] = builder.scalar('account_school_links', data,
                column_name='password', kind='text', **constants)
        else:
            result[school_username] = builder.scalar('account_school_links', data,
                column_name='legacy_value', kind='json', **constants)
    return result


def _school_configuration(builder, key, value):
    # Config/System contain legacy global credentials. They remain clearly
    # separate from owner-bound credentials and never populate a binding UA.
    fields = {name: column for name, column in (
        ('Config', 'configuration'), ('System', 'system_parameters'),
        ('stats', 'statistics'), ('Account', 'account_options'), ('DEFAULT', 'defaults'))
        if name in value}
    return _record(builder, 'school_accounts', value, fields,
        school_username=PurePosixPath(key).stem, source_key=key)


def _school_information(builder, key, value):
    filename = PurePosixPath(key).name
    fields = {name: name for name in ('backup_timestamp', 'overdue_count', 'completed_count') if name in value}
    fields.update({name: column for name, column in (
        ('userInfo', 'user_info'), ('deptInfo', 'department_info')) if name in value})
    return _record(builder, 'school_account_information', value, fields,
        school_username=filename[:-len('_backup.json')], source_key=key)


def _permissions(builder, key, value):
    return _record(builder, 'access_permissions', value,
        {name: column for name, column in (
            ('permission_groups', 'permission_groups'), ('user_groups', 'account_groups'),
            ('user_custom_permissions', 'account_overrides')) if name in value}, document_key=key)


def _token(builder, key, value):
    path = PurePosixPath(key)
    is_guest = path.parts[0] in ('guests', '.guest_store')
    token = value.get('token')
    fields = {name: name for name in ('session_id', 'principal_type', 'username', 'token',
        'created_at', 'expires_at', 'last_activity') if name in value}
    return _record(builder, 'authentication_tokens', value, fields,
        token_kind='guest' if is_guest else 'user',
        owner_username='' if is_guest else path.stem,
        session_key=path.stem if is_guest else '',
        token_hash=hashlib.sha256(token.encode('utf-8')).hexdigest() if isinstance(token, str) else None)


def _archive(builder, namespace, key, value):
    fields = {name: name for name in ('auth_username', 'deleted_at', 'user_data',
                                     'school_accounts', 'permissions') if name in value}
    fields.update({name: column for name, column in (
        ('archive_id', 'source_archive_id'), ('id', 'source_id')) if name in value})
    return _record(builder, 'deleted_account_archives', value, fields,
        archive_id=hashlib.sha256(f'{namespace}\0{key}'.encode('utf-8')).hexdigest(),
        legacy_archive_id=PurePosixPath(key).stem, source_namespace=namespace, source_key=key)


def _task(builder, value):
    fields = {name: name for name in TABLES['background_tasks']
              if name in value and name not in {'processed_points', 'total_points'}}
    fields.update({name: column for name, column in (
        ('singleProcessedPoints', 'processed_points'), ('singleTotalPoints', 'total_points')) if name in value})
    return _record(builder, 'background_tasks', value, fields)


def _settings(builder, namespace, key, value):
    if isinstance(value, dict):
        return {section: _scalar(builder, 'system_settings', data,
            category=namespace, document_key=key, section=section)
            for section, data in value.items()}
    return _scalar(builder, 'system_settings', value,
        category=namespace, document_key=key, section='')


def encode(builder, namespace, key, value):
    """Encode every legacy path without creating scalar/shape-only tables."""
    path = PurePosixPath(key)
    if path.name == '_index.json' or (namespace == 'tokens' and key == '_health_token_index.json') or (
            namespace == 'payment_orders' and path.name == 'qr_cache_index.json'):
        return _scalar(builder, 'storage_indexes', value, namespace=namespace, document_key=key)
    if namespace in ('deleted_accounts', 'legacy_deleted_accounts') and isinstance(value, dict):
        return _archive(builder, namespace, key, value)
    if namespace == 'system_accounts' and isinstance(value, dict):
        if 'user_data' in value and ('deleted_at' in value or 'remove' in path.parts):
            return _archive(builder, namespace, key, value)
        return _account(builder, value)
    if namespace == 'school_accounts' and isinstance(value, dict):
        if len(path.parts) >= 2 and path.parts[-2] == 'user_accounts' and path.suffix == '.json':
            return _bindings(builder, key, value)
        if path.suffix == '.ini':
            return _school_configuration(builder, key, value)
        if path.name.endswith('_backup.json'):
            return _school_information(builder, key, value)
    if namespace == 'sessions' and isinstance(value, dict):
        return _record(builder, 'account_sessions', value)
    if namespace == 'tokens' and isinstance(value, dict):
        return _token(builder, key, value)
    if namespace == 'settings' and key == 'permissions.json' and isinstance(value, dict):
        return _permissions(builder, key, value)
    if namespace == 'payment_orders' and isinstance(value, dict):
        return _v2_domains._order(builder, value)
    if namespace == 'billing' and isinstance(value, dict):
        return _v2_domains._bill(builder, key, value)
    if namespace == 'background_tasks' and isinstance(value, dict):
        return _task(builder, value)
    if namespace == 'background_state' and key == 'background_state.json' and isinstance(value, dict):
        return _record(builder, 'background_image_state', value)
    if namespace == 'settings' and key in {'messages.json', 'reminders.json'}:
        table = 'messages' if key == 'messages.json' else 'reminders'
        result = _v2_domains._content_list(builder, table, value, table)
        if result is not None:
            return result
    if namespace == 'sms_records' and isinstance(value, dict):
        fields = {name: name for name in TABLES['sms_records'] if name in value and name != 'record_key'}
        return _record(builder, 'sms_records', value, fields, record_key=key)
    return _settings(builder, namespace, key, value)
