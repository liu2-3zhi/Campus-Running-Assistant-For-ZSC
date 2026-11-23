import json
from pathlib import Path

import pytest

from business_storage import StorageSettings, StoragePolicy, StorageConfigurationError


def test_default_sqlite_mode_does_not_require_mysql_credentials(tmp_path):
    settings = StorageSettings.from_env({}, root=tmp_path)
    assert settings.backend == 'sqlite'
    assert settings.root == tmp_path.resolve()


@pytest.mark.parametrize('env', [
    {'APP_STORAGE_BACKEND': 'unknown'},
    {'APP_STORAGE_BACKEND': 'mysql'},
    {'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_DATABASE': 'test', 'MYSQL_USER': 'test', 'MYSQL_TABLE_PREFIX': 'bad;sql'},
    {'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_DATABASE': 'test', 'MYSQL_USER': 'test', 'MYSQL_PORT': '0'},
])
def test_invalid_storage_settings_fail_explicitly(tmp_path, env):
    with pytest.raises(StorageConfigurationError):
        StorageSettings.from_env(env, root=tmp_path)


def test_mysql_password_is_not_exposed_in_settings_repr(tmp_path):
    settings = StorageSettings.from_env({'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_USER': 'test', 'MYSQL_PASSWORD': 'secret-for-test', 'MYSQL_DATABASE': 'test'}, root=tmp_path)
    assert 'secret-for-test' not in repr(settings)


def test_policy_only_routes_business_documents_and_preserves_logs(tmp_path):
    policy = StoragePolicy(tmp_path)
    assert policy.identify(tmp_path / 'school_accounts' / '10001.ini') == ('school_accounts', '10001.ini')
    assert policy.identify(tmp_path / 'payment_orders' / 'order.json') == ('payment_orders', 'order.json')
    for name in ('logs/a.json', 'logs/payment_logs/a.json', 'uploads/a.json', 'cache/a.json', 'system_accounts/images/a.png', 'random_background_image/index.json'):
        assert policy.identify(tmp_path / name) is None, name
    assert policy.identify(tmp_path / 'configs/config.json') == ('configs', 'config.json')
    assert policy.identify(tmp_path / 'trusted_ips.txt') == ('settings', 'trusted_ips.txt')
    assert policy.identify(tmp_path / 'random_background_image/background_state.json') == ('background_state', 'background_state.json')
    assert policy.identify(tmp_path / 'arbitrary.json') is None


def test_connection_password_comes_from_environment_not_a_file(tmp_path):
    password_file = tmp_path / 'secret'
    password_file.write_bytes(b'password-ending-in-rn\r\n')
    settings = StorageSettings.from_env({'APP_STORAGE_BACKEND': 'mysql', 'MYSQL_USER': 'test',
        'MYSQL_DATABASE': 'test', 'MYSQL_PASSWORD': 'environment-test-password',
        'MYSQL_PASSWORD_FILE': str(password_file)}, root=tmp_path)
    assert settings.password == 'environment-test-password'


def test_custom_directories_and_custom_logs_are_used(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'configs/config.json').write_text(json.dumps({'System': {'school_accounts_dir': 'data/accounts', 'tokens_dir': 'data/tokens'}, 'Logging': {'log_dir': 'data/accounts/logs'}}), encoding='utf-8')
    policy = StoragePolicy(tmp_path)
    assert policy.identify(tmp_path / 'data/accounts/10001.ini') == ('school_accounts', '10001.ini')
    assert policy.identify(tmp_path / 'data/tokens/t.json') == ('tokens', 't.json')
    assert policy.identify(tmp_path / 'data/accounts/logs/a.json') is None
    assert policy.physical_path('school_accounts', '10001.ini') == tmp_path / 'data/accounts/10001.ini'


@pytest.mark.parametrize('key', ['../outside.json', '/outside.json', 'a/../../outside.json', 'a\\outside.json'])
def test_export_path_cannot_escape_namespace(tmp_path, key):
    with pytest.raises(StorageConfigurationError):
        StoragePolicy(tmp_path).physical_path('system_accounts', key)


def test_policy_scan_ignores_logs_and_binary_files(tmp_path):
    for name in ('system_accounts/a.json', 'school_accounts/a.ini', 'logs/a.json', 'uploads/a.json', 'system_accounts/images/a.png'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{}')
    assert {path.relative_to(tmp_path).as_posix() for path in StoragePolicy(tmp_path).iter_files()} == {'system_accounts/a.json', 'school_accounts/a.ini'}


def test_runtime_rejects_storage_root_detached_from_actual_application(tmp_path, monkeypatch):
    import business_storage
    monkeypatch.setattr(business_storage, '_runtime', None)
    monkeypatch.setenv('APP_STORAGE_BACKEND', 'mysql')
    monkeypatch.setenv('APP_STORAGE_ROOT', str(tmp_path))
    monkeypatch.setenv('MYSQL_USER', 'test')
    monkeypatch.setenv('MYSQL_DATABASE', 'test')
    class UnexpectedStore:
        def __init__(self, settings):
            pytest.fail('Root mismatch must fail before connecting')
    monkeypatch.setattr(business_storage, 'MySQLDocumentStore', UnexpectedStore)
    with pytest.raises(StorageConfigurationError, match='root'):
        business_storage.get_runtime()
