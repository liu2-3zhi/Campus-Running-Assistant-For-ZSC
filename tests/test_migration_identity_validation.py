"""Whole-source identity validation must report issues without exposing values."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from persistence.validation import aliases_from_usernames, build_owner_aliases, validate_entries


def entry(namespace, key, value):
    return SimpleNamespace(namespace=namespace, key=key,
                           content=json.dumps(value).encode('utf-8'))


def user(username='Alice', group='user', key='hash.json'):
    return entry('system_accounts', key, {'auth_username': username, 'group': group})


def permissions(groups=None):
    return entry('settings', 'permissions.json', {
        'permission_groups': {'user': {'permissions': {'run': True}},
                              'admin': {'permissions': {'manage_users': True}}},
        'user_groups': groups if groups is not None else {'Alice': 'user'}})


def bindings(owner='Alice', value=None, prefix='user_accounts'):
    return entry('school_accounts', f'{prefix}/{owner}.json',
                 value if value is not None else {'00042': {'password': 'secret-for-test', 'ua': 'UA-A'}})


def codes(issues, severity=None):
    return {issue['code'] for issue in issues if severity is None or issue['severity'] == severity}


def test_agreeing_group_sources_and_owner_specific_ua_have_no_errors():
    entries = [user(), user('Bob', key='other.json'), permissions(), bindings(),
               bindings('Bob', {'00042': {'password': 'different-password', 'ua': 'UA-B'}})]
    assert not codes(validate_entries(entries), 'error')


def test_group_conflict_is_reported_without_changing_either_authority():
    entries = [user(group='user'), permissions({'Alice': 'admin'})]
    before = [item.content for item in entries]
    issues = validate_entries(entries)
    assert 'permission_group_conflict' in codes(issues, 'warning')
    assert not codes(issues, 'error')
    assert before == [item.content for item in entries]


def test_findings_have_only_location_and_safe_issue_code():
    entries = [user(), permissions({'Alice': 'admin'}),
               bindings(value={'00042': {'password': 'secret-for-test'}})]
    issues = validate_entries(entries)
    assert issues
    for issue in issues:
        assert set(issue) == {'severity', 'code', 'namespace', 'key'}
    assert 'secret-for-test' not in json.dumps(issues)
    assert 'UA-A' not in json.dumps(issues)


def test_duplicate_users_and_alias_collisions_are_blocking():
    assert 'duplicate_user_identity' in codes(validate_entries([user(), user(key='second.json')]), 'error')
    entries = [user('Alice'), user(' Alice ', key='whitespace.json')]
    assert 'ambiguous_owner_alias' in codes(validate_entries(entries), 'error')
    with pytest.raises(ValueError, match='Ambiguous'):
        aliases_from_usernames(['Alice', ' Alice '])


def test_aliases_resolve_unsafe_legacy_names_and_preserve_case():
    alias = 'invalid_' + hashlib.sha256(b'unsafe/name').hexdigest()
    names = ['Alice', 'alice', 'unsafe/name']
    assert aliases_from_usernames(names) == {'Alice': 'Alice', 'alice': 'alice', alias: 'unsafe/name'}
    entries = [user('unsafe/name'), bindings(alias)]
    assert build_owner_aliases(entries) == {alias: 'unsafe/name'}
    assert 'orphan_school_account_owner' not in codes(validate_entries(entries))
    assert not codes(validate_entries(entries), 'error')


def test_duplicate_owner_school_binding_cannot_silently_choose_a_ua():
    entries = [user(), bindings(),
               bindings(value={'00042': {'password': 'other', 'ua': 'UA-B'}}, prefix='archive/user_accounts')]
    issues = validate_entries(entries)
    assert 'duplicate_owner_school_binding' in codes(issues, 'error')
    assert 'owner_school_ua_conflict' in codes(issues, 'error')


def test_reused_ua_across_owners_is_warning_and_never_rewritten():
    entries = [user(), user('Bob', key='bob.json'), bindings(), bindings('Bob')]
    before = [item.content for item in entries]
    issues = validate_entries(entries)
    assert 'shared_school_account_ua' in codes(issues, 'warning')
    assert not codes(issues, 'error')
    assert before == [item.content for item in entries]


@pytest.mark.parametrize('value', [
    'legacy-password', {'password': 'test'}, {'password': 'test', 'ua': None},
    {'password': 'test', 'ua': ''},
])
def test_missing_binding_ua_is_reported_without_global_ua_fallback(value):
    entries = [user(), bindings(value={'00042': value})]
    issues = validate_entries(entries)
    assert 'binding_ua_missing' in codes(issues, 'warning')
    assert not codes(issues, 'error')


def test_indexes_are_not_users_or_tokens_and_deleted_users_remain_archived():
    entries = [entry('system_accounts', '_index.json', {'accounts': {'Alice': 'hash'}}),
               entry('tokens', '_health_token_index.json', {'synthetic-hash': 'Alice'}),
               entry('deleted_accounts', 'archive.json', {'auth_username': 'Alice', 'user_data': {'group': 'admin'}})]
    assert validate_entries(entries) == []


def test_guest_session_mismatch_and_duplicate_user_tokens_are_errors():
    entries = [user(), entry('tokens', 'Alice.json', {'token': 'first-secret'}),
               entry('tokens', 'backup/Alice.json', {'token': 'second-secret'}),
               entry('tokens', 'guests/session-one.json', {'token': 'guest-secret', 'session_id': 'session-two'})]
    issues = validate_entries(entries)
    assert 'duplicate_user_token' in codes(issues, 'error')
    assert 'guest_session_identity_conflict' in codes(issues, 'error')


def test_duplicate_source_document_and_invalid_json_are_reported_safely():
    bad = SimpleNamespace(namespace='system_accounts', key='broken.json', content=b'{password: secret}')
    issues = validate_entries([user(), user(), bad])
    assert 'duplicate_source_document' in codes(issues, 'error')
    assert 'invalid_identity_document' in codes(issues, 'error')
    assert 'secret' not in json.dumps(issues)
