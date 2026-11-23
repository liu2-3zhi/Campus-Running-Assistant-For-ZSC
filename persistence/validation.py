"""Read-only, whole-source migration checks for identity relationships.

Findings deliberately contain only a stable code and document location. Values,
credentials, UA strings and permission assignments are never copied to reports.
Warnings retain competing legacy authorities; callers must not resolve them by
granting permissions or by copying a global UA into an owner binding.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import PurePosixPath


_AUTH_NAME = re.compile(r'^[a-zA-Z0-9_\-.@]+$')
_SCHOOL_NAME = re.compile(r'^[0-9]{4,}$')
_NAMESPACES = frozenset(('system_accounts', 'school_accounts', 'sessions', 'tokens',
                         'deleted_accounts', 'legacy_deleted_accounts'))


def _field(entry, name):
    return entry[name] if isinstance(entry, Mapping) else getattr(entry, name)


def _location(entry):
    return _field(entry, 'namespace'), _field(entry, 'key')


def _owned(namespace, key):
    return namespace in _NAMESPACES or (namespace == 'settings' and key == 'permissions.json')


def _decode(entry):
    content = _field(entry, 'content')
    text = content.decode('utf-8-sig') if isinstance(content, bytes) else content
    if _field(entry, 'key').lower().endswith('.ini'):
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(text)
        return {section: dict(parser.items(section)) for section in parser.sections()}
    return json.loads(text)


def _is_index(namespace, key):
    return PurePosixPath(key).name == '_index.json' or (
        namespace == 'tokens' and key == '_health_token_index.json')


def _is_live_user(namespace, key, value):
    return (namespace == 'system_accounts' and not _is_index(namespace, key)
            and not ('user_data' in value and ('deleted_at' in value or 'remove' in PurePosixPath(key).parts)))


def _storage_alias(username):
    normalized = username.strip()
    if normalized and len(normalized) <= 200 and _AUTH_NAME.fullmatch(normalized):
        return normalized
    return 'invalid_' + hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def aliases_from_usernames(names):
    """Rebuild legacy owner filename aliases, refusing ambiguous ownership."""
    result = {}
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        alias = _storage_alias(name)
        if alias in result and result[alias] != name:
            raise ValueError('Ambiguous owner alias')
        result[alias] = name
    return result


def build_owner_aliases(entries):
    """Derive aliases solely from live user identities in migration entries."""
    names = []
    for entry in entries:
        namespace, key = _location(entry)
        if namespace != 'system_accounts' or _is_index(namespace, key):
            continue
        try:
            value = _decode(entry)
        except (ValueError, UnicodeError, TypeError, configparser.Error):
            continue
        if isinstance(value, dict) and _is_live_user(namespace, key, value):
            names.append(value.get('auth_username'))
    return aliases_from_usernames(names)


def _ua(value):
    if not isinstance(value, dict):
        return None
    ua = value.get('ua') if 'ua' in value else value.get('device_ua')
    return ua if isinstance(ua, str) and ua.strip() else None


def validate_entries(entries):
    """Return identity consistency findings without changing source entries.

    Entries follow ``SourceEntry(namespace, key, content, ...)``; equivalent
    mappings are also accepted. Duplicate keys, identities and alias collisions
    are errors. Legacy permission divergence and missing/shared UAs are reported
    as warnings so an offline copy can be preserved without inventing authority.
    """
    issues = []

    def report(severity, code, namespace, key):
        issue = {'severity': severity, 'code': code, 'namespace': namespace, 'key': key}
        if issue not in issues:
            issues.append(issue)

    decoded = []
    seen_documents = set()
    for entry in entries:
        namespace, key = _location(entry)
        location = namespace, key
        if location in seen_documents:
            report('error', 'duplicate_source_document', namespace, key)
        seen_documents.add(location)
        if not _owned(namespace, key):
            continue
        try:
            value = _decode(entry)
        except (ValueError, UnicodeError, TypeError, configparser.Error):
            report('error', 'invalid_identity_document', namespace, key)
            continue
        if not isinstance(value, dict):
            report('warning', 'legacy_identity_document_shape', namespace, key)
            continue
        if not _is_index(namespace, key):
            decoded.append((namespace, key, value))

    users = {}
    aliases = {}
    ambiguous_aliases = set()
    permission_documents = []
    for namespace, key, value in decoded:
        if _is_live_user(namespace, key, value):
            username = value.get('auth_username')
            if not isinstance(username, str) or not username.strip():
                report('warning', 'user_identity_missing', namespace, key)
                continue
            if username in users:
                report('error', 'duplicate_user_identity', namespace, key)
            else:
                users[username] = (key, value)
            alias = _storage_alias(username)
            if alias in aliases and aliases[alias] != username:
                ambiguous_aliases.add(alias)
                report('error', 'ambiguous_owner_alias', namespace, key)
            else:
                aliases[alias] = username
        elif namespace == 'settings' and key == 'permissions.json':
            permission_documents.append((namespace, key, value))

    for namespace, key, value in permission_documents:
        user_groups = value.get('user_groups')
        if not isinstance(user_groups, dict):
            continue
        groups = value.get('permission_groups')
        for username, group in user_groups.items():
            user = users.get(username)
            if user is None:
                report('warning', 'orphan_permission_user', namespace, key)
            elif 'group' in user[1] and user[1]['group'] != group:
                report('warning', 'permission_group_conflict', 'system_accounts', user[0])
            if isinstance(groups, dict) and (not isinstance(group, str) or group not in groups):
                report('warning', 'unknown_permission_group', namespace, key)

    seen_bindings = {}
    ua_owners = defaultdict(set)
    token_owners = set()
    guest_sessions = set()
    sessions = set()
    for namespace, key, value in decoded:
        path = PurePosixPath(key)
        if namespace == 'school_accounts' and len(path.parts) >= 2 and path.parts[-2] == 'user_accounts':
            alias = path.stem
            if alias in ambiguous_aliases:
                report('error', 'ambiguous_owner_alias', namespace, key)
                continue
            owner = aliases.get(alias, alias)
            if owner not in users:
                report('warning', 'orphan_school_account_owner', namespace, key)
            elif owner != alias:
                report('warning', 'legacy_owner_alias', namespace, key)
            for school_username, account in value.items():
                if not _SCHOOL_NAME.fullmatch(school_username):
                    report('warning', 'invalid_school_identity', namespace, key)
                ua = _ua(account)
                identity = owner, school_username
                if identity in seen_bindings:
                    report('error', 'duplicate_owner_school_binding', namespace, key)
                    if seen_bindings[identity] != ua:
                        report('error', 'owner_school_ua_conflict', namespace, key)
                else:
                    seen_bindings[identity] = ua
                if ua is None:
                    report('warning', 'binding_ua_missing', namespace, key)
                else:
                    owners = ua_owners[(school_username, ua)]
                    if owners and owner not in owners:
                        report('warning', 'shared_school_account_ua', namespace, key)
                    owners.add(owner)
        elif namespace == 'sessions':
            session_id = value.get('session_id')
            if not isinstance(session_id, str) or not session_id:
                report('warning', 'session_identity_missing', namespace, key)
            elif session_id in sessions:
                report('error', 'duplicate_session_identity', namespace, key)
            else:
                sessions.add(session_id)
        elif namespace == 'tokens':
            if path.parts[0] in ('guests', '.guest_store'):
                session_key = path.stem
                if session_key in guest_sessions:
                    report('error', 'duplicate_guest_token', namespace, key)
                guest_sessions.add(session_key)
                if 'session_id' in value and value['session_id'] != session_key:
                    report('error', 'guest_session_identity_conflict', namespace, key)
            else:
                owner = path.stem
                if owner in token_owners:
                    report('error', 'duplicate_user_token', namespace, key)
                token_owners.add(owner)
                if owner not in users:
                    report('warning', 'orphan_user_token', namespace, key)
    return issues
