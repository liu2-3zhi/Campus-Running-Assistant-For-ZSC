"""Runtime database writes must never stage structured business data on disk."""
import builtins
import configparser
import ipaddress
import json
import os as physical_os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

import business_storage
import auth_system
import guest_token_store
import main
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore
import storage_io
import trusted_ip


@pytest.fixture
def database_runtime(tmp_path, monkeypatch):
    root = tmp_path / 'app'
    store = RelationalStore(DatabaseSettings(root=root))
    store.init_schema(ready=True)
    runtime = business_storage.StorageRuntime('sqlite', business_storage.StoragePolicy(root, {}), store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    try:
        yield root, store
    finally:
        store.database.dispose()


@pytest.fixture
def physical_writes(monkeypatch):
    written = []
    original = builtins.open
    original_descriptor = physical_os.open

    def observe(file, mode='r', *args, **kwargs):
        if not isinstance(file, int) and any(flag in mode for flag in 'wxa+'):
            written.append(Path(file))
        return original(file, mode, *args, **kwargs)

    def observe_descriptor(file, flags, *args, **kwargs):
        if not isinstance(file, int) and flags & (physical_os.O_WRONLY | physical_os.O_RDWR | physical_os.O_CREAT):
            written.append(Path(file))
        return original_descriptor(file, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', observe)
    monkeypatch.setattr(physical_os, 'open', observe_descriptor)
    return written


def test_guest_index_commits_to_database_without_a_disk_temporary(database_runtime, physical_writes):
    root, store = database_runtime
    guests = guest_token_store.GuestTokenStore(str(root / 'tokens' / 'guests'))
    value = {'sessions': {'synthetic-session': {'token_hash': 'synthetic-hash', 'expires_at': 101.5}}}
    guests._save_index(value)
    document = store.get('tokens', 'guests/_index.json')
    assert json.loads(document.content) == value
    assert physical_writes == []
    assert not list((root / 'tokens').rglob('*.tmp'))


def test_guest_external_file_still_uses_atomic_temporary(database_runtime, tmp_path, monkeypatch):
    root, _ = database_runtime
    directory = tmp_path / 'external-guests'
    guests = guest_token_store.GuestTokenStore(str(directory))
    original = guest_token_store.os.replace
    staged = []

    def observe(source, target):
        staged.append(Path(source).is_file())
        return original(source, target)

    monkeypatch.setattr(guest_token_store.os, 'replace', observe)
    guests._save_index({'sessions': {}})
    assert staged == [True]
    assert json.loads((directory / '_index.json').read_text()) == {'sessions': {}}


def test_configparser_json_write_commits_without_disk_temporary(database_runtime, physical_writes):
    root, store = database_runtime
    config = configparser.RawConfigParser()
    config['SSL'] = {'ssl_enabled': 'true'}
    target = root / 'configs' / 'config.json'
    main._write_config_with_comments(config, str(target))
    assert json.loads(store.get('configs', 'config.json').content) == {'SSL': {'ssl_enabled': 'true'}}
    assert physical_writes == []
    assert not target.exists()
    assert not target.parent.exists()


def test_external_configparser_json_write_remains_atomic(database_runtime, tmp_path, monkeypatch):
    config = configparser.RawConfigParser()
    config['SSL'] = {'ssl_enabled': 'true'}
    target = tmp_path / 'external-config' / 'config.json'
    original = main.os.replace
    staged = []

    def observe(source, destination):
        staged.append(Path(source).is_file())
        return original(source, destination)

    monkeypatch.setattr(main.os, 'replace', observe)
    main._write_config_with_comments(config, str(target))
    assert staged == [True]
    assert json.loads(target.read_text()) == {'SSL': {'ssl_enabled': 'true'}}


def test_managed_config_read_error_cannot_overwrite_unread_existing_values(database_runtime, monkeypatch):
    root, store = database_runtime
    existing = {'System': {'private_setting': 'preserve-this'}, 'SSL': {'ssl_enabled': 'false'}}
    store.put('configs', 'config.json', json.dumps(existing).encode())
    original = store.get
    fail_next = True

    def read(namespace, key):
        nonlocal fail_next
        if fail_next and (namespace, key) == ('configs', 'config.json'):
            fail_next = False
            raise DatabaseError('Synthetic transient read failure')
        return original(namespace, key)

    monkeypatch.setattr(store, 'get', read)
    config = configparser.RawConfigParser()
    config['SSL'] = {'ssl_enabled': 'true'}
    with pytest.raises(DatabaseError):
        main._write_config_with_comments(config, str(root / 'configs' / 'config.json'))
    assert json.loads(original('configs', 'config.json').content) == existing


@pytest.mark.parametrize('kind', ['storage', 'sqlalchemy'])
def test_trusted_network_database_errors_never_become_trust_all(tmp_path, monkeypatch, kind):
    failure = (DatabaseError('Synthetic read failure') if kind == 'storage' else
               OperationalError('SELECT synthetic', {}, sqlite3.OperationalError('Synthetic statement failure')))

    class BrokenStore:
        def get(self, *args):
            raise failure

    runtime = business_storage.StorageRuntime('sqlite', business_storage.StoragePolicy(tmp_path, {}), BrokenStore())
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    monkeypatch.setattr(trusted_ip, '_main', lambda: SimpleNamespace(TRUSTED_IPS_FILE=str(tmp_path / 'trusted_ips.txt')))
    with pytest.raises(type(failure)):
        trusted_ip._load_trusted_ip_networks()


def test_trusted_networks_use_database_document_without_physical_file(database_runtime, monkeypatch):
    root, store = database_runtime
    store.put('settings', 'trusted_ips.txt', b'127.0.0.1\n')
    monkeypatch.setattr(trusted_ip, '_main', lambda: SimpleNamespace(TRUSTED_IPS_FILE=str(root / 'trusted_ips.txt')))
    matcher = trusted_ip._load_trusted_ip_networks()
    assert matcher.matches(ipaddress.ip_address('127.0.0.1'))
    assert not matcher.matches(ipaddress.ip_address('203.0.113.10'))
    assert not (root / 'trusted_ips.txt').exists()


@pytest.mark.parametrize('fail_at', [1, 2, 3])
def test_config_database_read_error_reaches_caller(database_runtime, monkeypatch, fail_at):
    root, store = database_runtime
    store.put('configs', 'config.json', b'{"SSL":{"ssl_enabled":"true"}}')
    original = store.get
    original_exists = store.exists
    count = 0

    def fail_operation(operation, namespace, key):
        nonlocal count
        count += 1
        if count == fail_at:
            raise DatabaseError('Synthetic configuration read failure')
        return operation(namespace, key)

    # Existence, validation and adapter loading are three separate DB reads.
    monkeypatch.setattr(store, 'exists', lambda *args: fail_operation(original_exists, *args))
    monkeypatch.setattr(store, 'get', lambda *args: fail_operation(original, *args))
    with pytest.raises(DatabaseError):
        main._read_config_ini(str(root / 'configs' / 'config.json'))


@pytest.mark.parametrize('helper', ['create_default', 'migrate_ini'])
def test_config_database_write_error_is_not_suppressed(database_runtime, monkeypatch, helper):
    root, store = database_runtime
    config = configparser.RawConfigParser()
    config['SSL'] = {'ssl_enabled': 'true'}
    monkeypatch.setattr(main, '_get_default_config', lambda: config)

    def fail_write(*args, **kwargs):
        raise DatabaseError('Synthetic configuration write failure')

    monkeypatch.setattr(store, 'put', fail_write)
    target = str(root / 'configs' / 'config.json')
    with pytest.raises(DatabaseError):
        if helper == 'create_default':
            main._create_default_json_config(target)
        else:
            main._migrate_ini_to_json(config, target)
    assert not Path(target).exists()


def test_corrupt_database_configuration_never_creates_backup_or_defaults(database_runtime, monkeypatch, physical_writes):
    root, store = database_runtime
    original_content = b'{"System":{"private_setting":"preserve-this"}}'
    store.put('configs', 'config.json', original_content)
    original = store.get
    record = original('configs', 'config.json')
    damaged = SimpleNamespace(content=b'{invalid configuration', revision=record.revision, mtime_ns=record.mtime_ns)

    def read(namespace, key):
        return damaged if (namespace, key) == ('configs', 'config.json') else original(namespace, key)

    monkeypatch.setattr(store, 'get', read)
    with pytest.raises(DatabaseError):
        main._read_config_ini(str(root / 'configs' / 'config.json'))
    assert json.loads(original('configs', 'config.json').content) == {'System': {'private_setting': 'preserve-this'}}
    assert physical_writes == []
    assert not list(root.rglob('*.bak'))


def test_corrupt_external_config_still_recovers_defaults_and_backup(database_runtime, tmp_path, monkeypatch):
    target = tmp_path / 'external-config.json'
    corrupted = '{invalid external configuration'
    target.write_text(corrupted, encoding='utf-8')
    defaults = configparser.RawConfigParser()
    defaults['SSL'] = {'ssl_enabled': 'true'}
    monkeypatch.setattr(main, '_get_default_config', lambda: defaults)
    adapter = main._read_config_ini(str(target))
    assert adapter.get('SSL', 'ssl_enabled') == 'true'
    assert json.loads(target.read_text(encoding='utf-8'))['SSL']['ssl_enabled'] == 'true'
    backups = list(tmp_path.glob('external-config.json.corrupted.*.bak'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == corrupted


@pytest.mark.parametrize('phase', ['load', 'save'])
def test_startup_config_updates_propagate_database_failures(database_runtime, monkeypatch, phase):
    root, store = database_runtime
    existing = {'SSL': {'ssl_enabled': 'false'}}
    store.put('configs', 'config.json', json.dumps(existing).encode())
    original = store.get
    defaults = configparser.RawConfigParser()
    defaults['SSL'] = {'ssl_enabled': 'false', 'new_option': 'default'}
    monkeypatch.setattr(main, '_get_default_config', lambda: defaults)
    monkeypatch.setattr(main, 'CONFIG_FILE', str(root / 'configs' / 'config.json'))
    if phase == 'load':
        count = 0

        def read(namespace, key):
            nonlocal count
            count += 1
            if count == 3:
                raise DatabaseError('Synthetic startup configuration read failure')
            return original(namespace, key)

        monkeypatch.setattr(store, 'get', read)
    else:
        def fail_write(*args, **kwargs):
            raise DatabaseError('Synthetic startup configuration write failure')

        monkeypatch.setattr(store, 'put', fail_write)
    with pytest.raises(DatabaseError):
        main._create_config_ini()
    assert json.loads(original('configs', 'config.json').content) == existing


@pytest.mark.parametrize('phase', ['existing', 'new', 'after_recovery'])
def test_permission_database_read_errors_propagate_in_every_read_branch(database_runtime, monkeypatch, phase):
    root, store = database_runtime
    target = root / 'permissions.json'
    existing = {'permission_groups': {'custom': {'permissions': {'run': False}}},
                'user_groups': {'synthetic-owner': 'custom'}}
    defaults = {'permission_groups': {}, 'user_groups': {}}
    if phase != 'new':
        store.put('settings', 'permissions.json', json.dumps(existing).encode())
    original = store.get
    state = {'reads': 0, 'created': False, 'fail_next': False}
    failure = DatabaseError('Synthetic permission database read failure')

    def create_permissions(force=False):
        store.put('settings', 'permissions.json', json.dumps(defaults).encode())
        state.update(created=True, fail_next=True)

    def read(namespace, key):
        if (namespace, key) != ('settings', 'permissions.json'):
            return original(namespace, key)
        state['reads'] += 1
        if state['fail_next'] or (phase == 'existing' and state['reads'] == 1):
            state['fail_next'] = False
            raise failure
        if phase == 'after_recovery' and not state['created']:
            return SimpleNamespace(content=b'{invalid permissions', revision=1, mtime_ns=1)
        return original(namespace, key)

    monkeypatch.setattr(store, 'get', read)
    runtime = SimpleNamespace(PERMISSIONS_FILE=str(target),
        _create_permissions_json=create_permissions,
        _backup_and_reset_corrupted_file=lambda *args: None)
    monkeypatch.setattr(auth_system, '_main', lambda: runtime)
    auth = object.__new__(auth_system.AuthSystem)
    with pytest.raises(DatabaseError) as caught:
        auth._load_permissions()
    assert caught.value is failure
    if phase == 'existing':
        assert not state['created']
        assert json.loads(original('settings', 'permissions.json').content) == existing


@pytest.mark.parametrize('exists', [True, False])
def test_generic_recovery_refuses_managed_database_documents(database_runtime, monkeypatch, physical_writes, exists):
    root, store = database_runtime
    monkeypatch.chdir(root)
    existing = {'permission_groups': {'custom': {'permissions': {'run': False}}},
                'user_groups': {'synthetic-owner': 'custom'}}
    if exists:
        store.put('settings', 'permissions.json', json.dumps(existing).encode())
    with pytest.raises(DatabaseError):
        main._backup_and_reset_corrupted_file(str(root / 'permissions.json'), {}, 'json')
    document = store.get('settings', 'permissions.json')
    assert (json.loads(document.content) if document else None) == (existing if exists else None)
    assert physical_writes == []
    assert not (root / 'logs').exists()


def test_generic_recovery_preserves_unmanaged_file_behavior(database_runtime, tmp_path, monkeypatch):
    root, store = database_runtime
    monkeypatch.chdir(root)
    target = tmp_path / 'external-damaged.json'
    corrupted = '{invalid external JSON'
    target.write_text(corrupted, encoding='utf-8')
    assert main._backup_and_reset_corrupted_file(str(target), {'replacement': True}, 'json') is True
    assert json.loads(target.read_text(encoding='utf-8')) == {'replacement': True}
    backups = list((root / 'logs' / 'backup').glob('*.backup'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == corrupted
    assert store.namespaces() == []
