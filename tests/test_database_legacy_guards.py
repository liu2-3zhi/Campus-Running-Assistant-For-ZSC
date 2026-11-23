"""Managed credentials and background state never pass through disk backups."""

import builtins
import configparser
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import api_runtime
import business_storage
import storage_io
import theme_background_state
from persistence.engine import DatabaseError, DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def database(tmp_path, monkeypatch):
    root = tmp_path / 'app'
    root.mkdir()
    (root / 'school_accounts').mkdir()
    store = RelationalStore(DatabaseSettings(root=root))
    store.init_schema(ready=True)
    runtime = SimpleNamespace(backend='sqlite', policy=business_storage.StoragePolicy(root, {}), store=store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    yield root, store
    store.database.dispose()


def physical_writes(monkeypatch):
    writes = []
    original = builtins.open

    def observe(path, mode='r', *args, **kwargs):
        if not isinstance(path, int) and any(flag in mode for flag in 'wax+'):
            writes.append(Path(path))
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', observe)
    return writes


def api_for(directory, monkeypatch):
    runtime = SimpleNamespace(
        chardet=None,
        is_valid_school_username=lambda value: value.isdigit() and len(value) >= 4,
        _read_config_ini=lambda path: configparser.RawConfigParser(),
        _write_config_with_comments=lambda config, path: None,
    )
    monkeypatch.setattr(api_runtime, '_main', lambda: runtime)
    api = object.__new__(api_runtime.Api)
    api.user_dir = str(directory)
    api.config_path = str(directory / 'main.ini')
    api.global_params = {'speed_mps': '1'}
    api.params = {}
    api.accounts = {}
    api.is_multi_account_mode = False
    api.auth_username = 'owner-a'
    return api


def read_ini(content):
    result = configparser.RawConfigParser()
    result.read_string(content.decode('utf-8'))
    return result


def test_managed_background_save_never_writes_disk_temporary_file(database, monkeypatch):
    root, store = database
    state_store = theme_background_state.BackgroundStateStore(str(root / 'random_background_image'))
    state = theme_background_state.empty_state()
    state['next_revision'] = 9
    writes = physical_writes(monkeypatch)

    state_store.save(state)

    assert json.loads(store.get('background_state', 'background_state.json').content)['next_revision'] == 9
    assert writes == []
    assert not Path(state_store.path).exists()


def test_failed_managed_background_save_never_spills_data_to_disk(database, monkeypatch):
    root, store = database
    state_store = theme_background_state.BackgroundStateStore(str(root / 'random_background_image'))
    state_store.save(theme_background_state.empty_state())
    previous = store.get('background_state', 'background_state.json')
    writes = physical_writes(monkeypatch)

    def unavailable(*args, **kwargs):
        raise DatabaseError('Database unavailable')

    monkeypatch.setattr(store, 'put', unavailable)
    with pytest.raises(DatabaseError):
        state_store.save(dict(theme_background_state.empty_state(), next_revision=12))

    assert writes == []
    assert store.get('background_state', 'background_state.json').content == previous.content


def test_unmanaged_background_save_keeps_atomic_disk_temporary_file(database, tmp_path, monkeypatch):
    directory = tmp_path / 'unmanaged-images'
    state_store = theme_background_state.BackgroundStateStore(str(directory))
    writes = physical_writes(monkeypatch)

    state_store.save(dict(theme_background_state.empty_state(), next_revision=7))

    assert json.loads(Path(state_store.path).read_text(encoding='utf-8'))['next_revision'] == 7
    assert any(path.parent == directory and path.name.endswith('.tmp') for path in writes)
    assert not list(directory.glob('*.tmp'))


@pytest.mark.parametrize('existing_backup', [False, True])
def test_managed_ini_normalization_never_creates_or_overwrites_disk_backup(database, monkeypatch, existing_backup):
    root, store = database
    path = root / 'school_accounts' / '10001.ini'
    path.write_text('[Config]\npassword=stale-physical\n', encoding='utf-8')
    backup = Path(str(path) + '.bak')
    if existing_backup:
        backup.write_bytes(b'previous-backup-must-stay-untouched')
    store.put('school_accounts', '10001.ini', '[配置]\n用户名=10001\n密码=database-password\n速度=3.2\n[stats]\ncompleted_count=4\n'.encode())
    api = api_for(path.parent, monkeypatch)
    writes = physical_writes(monkeypatch)

    api.normalize_chinese_config_to_english(str(path))

    normalized = read_ini(store.get('school_accounts', '10001.ini').content)
    assert normalized.get('Config', 'password') == 'database-password'
    assert normalized.get('Config', 'speed_mps') == '3.2'
    assert normalized.get('stats', 'completed_count') == '4'
    assert writes == []
    assert path.read_text(encoding='utf-8') == '[Config]\npassword=stale-physical\n'
    if existing_backup:
        assert backup.read_bytes() == b'previous-backup-must-stay-untouched'
    else:
        assert not backup.exists()


def test_unmanaged_ini_normalization_preserves_original_disk_backup(database, tmp_path, monkeypatch):
    directory = tmp_path / 'unmanaged-configs'
    directory.mkdir()
    path = directory / '10001.ini'
    raw = '[配置]\n用户名=10001\n密码=local-password\n速度=3.2\n'.encode()
    path.write_bytes(raw)

    api_for(directory, monkeypatch).normalize_chinese_config_to_english(str(path))

    assert Path(str(path) + '.bak').read_bytes() == raw
    assert read_ini(path.read_bytes()).get('Config', 'password') == 'local-password'


@pytest.mark.parametrize('saved_password', [None, '', 'verified-password'])
def test_managed_ini_password_never_recovers_from_stale_physical_backup(database, monkeypatch, saved_password):
    root, store = database
    path = root / 'school_accounts' / '10001.ini'
    content = '[Config]\nUsername=10001\n'
    if saved_password is not None:
        content += 'password=' + saved_password + '\n'
    content += '[System]\nua=database-UA\n[stats]\noverdue_count=2\n'
    store.put('school_accounts', '10001.ini', content.encode())
    Path(str(path) + '.bak').write_text('[配置]\n密码=another-owner-stale-password\n', encoding='utf-8')
    owners = {
        'owner-a': {'auth_username': 'owner-a', 'school_accounts': {'10001': {'password': 'verified-a', 'ua': 'UA-a'}}},
        'owner-b': {'auth_username': 'owner-b', 'school_accounts': {'10001': {'password': 'verified-b', 'ua': 'UA-b'}}},
    }
    for owner, value in owners.items():
        store.put('system_accounts', owner + '.json', json.dumps(value).encode())

    api_for(path.parent, monkeypatch)._save_config('10001')

    saved = read_ini(store.get('school_accounts', '10001.ini').content)
    if saved_password is None:
        assert not saved.has_option('Config', 'password')
    else:
        assert saved.get('Config', 'password') == saved_password
    assert saved.get('System', 'ua') == 'database-UA'
    assert saved.get('stats', 'overdue_count') == '2'
    for owner, expected in owners.items():
        assert json.loads(store.get('system_accounts', owner + '.json').content) == expected


def test_unmanaged_ini_password_can_recover_from_local_backup(database, tmp_path, monkeypatch):
    directory = tmp_path / 'unmanaged-configs'
    directory.mkdir()
    path = directory / '10001.ini'
    path.write_text('[Config]\nUsername=10001\n[System]\nua=local-UA\n', encoding='utf-8')
    Path(str(path) + '.bak').write_text('password=local-backup-password\n', encoding='utf-8')

    api_for(directory, monkeypatch)._save_config('10001')

    saved = read_ini(path.read_bytes())
    assert saved.get('Config', 'password') == 'local-backup-password'
    assert saved.get('System', 'ua') == 'local-UA'
