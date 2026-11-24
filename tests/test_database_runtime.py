"""Database-first runtime setup without opening deployment databases."""
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

import business_storage
import config_adapter
import storage_io
from persistence.engine import DatabaseError
from test_storage_io import MemoryStore


@pytest.fixture
def app_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(business_storage, '__file__', str(tmp_path / 'business_storage.py'))
    monkeypatch.setattr(business_storage, '_runtime', None)
    monkeypatch.delenv('APP_STORAGE_BACKEND', raising=False)
    monkeypatch.setenv('APP_STORAGE_ROOT', str(tmp_path))
    monkeypatch.delenv('SQLITE_DATABASE_PATH', raising=False)
    yield tmp_path
    runtime = business_storage._runtime
    database = getattr(getattr(runtime, 'store', None), 'database', None)
    if database is not None:
        database.dispose()


class FakeStore:
    def __init__(self, config=None, ready=True):
        self.ready = ready
        self.initializations = []
        self.checks = 0
        self.config = config

    def init_schema(self, *, ready=False):
        self.initializations.append(ready)
        self.ready = ready

    def check_ready(self):
        self.checks += 1
        if not self.ready:
            raise DatabaseError('Database migration is incomplete')

    def put(self, namespace, key, content, **kwargs):
        assert (namespace, key) == ('settings', 'trusted_ips.txt')

    def mark_ready(self):
        self.ready = True

    def get(self, namespace, key):
        if (namespace, key) == ('configs', 'config.json') and self.config is not None:
            return SimpleNamespace(content=json.dumps(self.config).encode())
        return None


def install_factory(monkeypatch, store):
    calls = []
    def factory(settings):
        calls.append(settings)
        return store
    monkeypatch.setattr(business_storage, '_create_relational_store', factory, raising=False)
    return calls


def test_new_sqlite_runtime_initializes_only_database_storage(app_root, monkeypatch):
    store = FakeStore()
    calls = install_factory(monkeypatch, store)
    runtime = business_storage.get_runtime()
    assert runtime.backend == 'sqlite'
    assert runtime.store is store
    assert store.initializations == [False]
    assert store.ready
    assert len(calls) == 1
    assert business_storage.get_runtime() is runtime


@pytest.mark.parametrize('source', ['system_accounts/user.json', 'configs/config.json', 'trusted_ips.txt'])
def test_new_database_refuses_to_hide_unmigrated_files(app_root, monkeypatch, source):
    path = app_root / source
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {'System': {}} if source.endswith('.json') else '127.0.0.1'
    path.write_text(json.dumps(content) if isinstance(content, dict) else content, encoding='utf-8')
    calls = install_factory(monkeypatch, FakeStore())
    with pytest.raises(business_storage.StorageError, match='migrate_storage'):
        business_storage.get_runtime()
    assert not calls
    assert not (app_root / 'data/application.sqlite3').exists()


def test_existing_sqlite_uses_database_config_instead_of_stale_source(app_root, monkeypatch):
    target = app_root / 'data/application.sqlite3'
    target.parent.mkdir()
    target.touch()
    config = app_root / 'configs/config.json'
    config.parent.mkdir()
    config.write_text('invalid stale source', encoding='utf-8')
    store = FakeStore({'System': {'school_accounts_dir': 'custom-accounts'},
                       'Logging': {'log_dir': 'custom-accounts/logs'}})
    install_factory(monkeypatch, store)
    runtime = business_storage.get_runtime()
    assert not store.initializations
    assert store.checks == 1
    assert runtime.policy.identify(app_root / 'custom-accounts/10001.ini') == ('school_accounts', '10001.ini')
    assert runtime.policy.identify(app_root / 'custom-accounts/logs/audit.json') is None


def test_invalid_legacy_config_still_explains_explicit_migration(app_root, monkeypatch):
    source = app_root / 'configs/config.json'
    source.parent.mkdir()
    source.write_text('{invalid JSON', encoding='utf-8')
    calls = install_factory(monkeypatch, FakeStore())
    with pytest.raises(business_storage.StorageConfigurationError, match='migrate_storage'):
        business_storage.get_runtime()
    assert not calls
    assert not (app_root / 'data/application.sqlite3').exists()


def test_existing_unready_sqlite_does_not_initialize_over_migration(app_root, monkeypatch):
    target = app_root / 'data/application.sqlite3'
    target.parent.mkdir()
    target.touch()
    store = FakeStore(ready=False)
    install_factory(monkeypatch, store)
    with pytest.raises(business_storage.StorageError):
        business_storage.get_runtime()
    assert not store.initializations


def test_mysql_runtime_only_checks_ready_and_never_creates_schema(app_root, monkeypatch):
    monkeypatch.setenv('APP_STORAGE_BACKEND', 'mysql')
    monkeypatch.setenv('MYSQL_USER', 'test-user')
    monkeypatch.setenv('MYSQL_DATABASE', 'test-db')
    store = FakeStore()
    install_factory(monkeypatch, store)
    assert business_storage.get_runtime().backend == 'mysql'
    assert store.checks == 1
    assert not store.initializations


def test_database_errors_are_also_storage_errors():
    assert issubclass(DatabaseError, business_storage.StorageError)


def test_managed_config_save_never_creates_disk_temporary_files(app_root, monkeypatch):
    store = MemoryStore()
    runtime = SimpleNamespace(backend='sqlite', policy=business_storage.StoragePolicy(app_root, {}), store=store)
    monkeypatch.setattr(storage_io, 'get_runtime', lambda *paths: runtime)
    def forbid_temporary_file(*args, **kwargs):
        pytest.fail('Managed config writes must be committed directly to the database')
    monkeypatch.setattr(config_adapter.tempfile, 'NamedTemporaryFile', forbid_temporary_file)
    target = app_root / 'configs/config.json'
    adapter = config_adapter.JsonConfigAdapter(str(target))
    adapter.set('SSL', 'ssl_enabled', 'true')
    adapter.save()
    record = store.get('configs', 'config.json')
    assert json.loads(record.content)['SSL']['ssl_enabled'] == 'true'
    assert not target.exists()
    assert not target.parent.exists()


def test_entrypoint_ssl_values_are_read_from_database_only(app_root, monkeypatch):
    store = FakeStore({'SSL': {'ssl_enabled': 'yes', 'https_only': False}})
    monkeypatch.setattr(business_storage, 'get_runtime',
        lambda: SimpleNamespace(backend='sqlite', store=store))
    assert business_storage.get_entrypoint_ssl_settings() == {'ssl_enabled': True, 'https_only': False}


def test_entrypoint_ssl_failure_does_not_fall_back_to_file(app_root, monkeypatch):
    def fail_runtime():
        raise DatabaseError('Unavailable')
    monkeypatch.setattr(business_storage, 'get_runtime', fail_runtime)
    with pytest.raises(business_storage.StorageError):
        business_storage.get_entrypoint_ssl_settings()


def test_container_entrypoint_uses_database_boolean_reader(monkeypatch, capsys):
    script = (Path(__file__).resolve().parents[1] / 'docker/docker-entrypoint.sh').read_text(encoding='utf-8')
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY", script, re.DOTALL)
    assert match, 'Container SSL setup must load values through the database runtime'
    monkeypatch.setitem(sys.modules, 'business_storage', SimpleNamespace(
        get_entrypoint_ssl_settings=lambda: {'ssl_enabled': True, 'https_only': False}))
    exec(compile(match.group(1), '<entrypoint-ssl>', 'exec'), {})
    assert capsys.readouterr().out.strip() == 'true false'
    assert 'get_json_bool_value' not in script


def test_container_database_failure_has_migration_hint_and_exits(monkeypatch, capsys):
    script = (Path(__file__).resolve().parents[1] / 'docker/docker-entrypoint.sh').read_text(encoding='utf-8')
    snippet = re.search(r"python3 - <<'PY'\n(.*?)\nPY", script, re.DOTALL).group(1)

    def unavailable():
        raise DatabaseError('Database is not initialized')

    monkeypatch.setenv('APP_STORAGE_BACKEND', 'mysql')
    monkeypatch.setattr(business_storage, 'get_entrypoint_ssl_settings', unavailable)
    with pytest.raises(SystemExit) as result:
        exec(compile(snippet, '<entrypoint-ssl>', 'exec'), {})
    output = capsys.readouterr()
    assert result.value.code == 1
    assert not output.out
    assert 'Database is not initialized' in output.err
    assert 'import/verify' in output.err


def test_default_runtime_writes_config_to_real_sqlite_without_json(app_root):
    runtime = business_storage.get_runtime()
    config = config_adapter.JsonConfigAdapter(str(app_root / 'configs/config.json'))
    config.set('SSL', 'ssl_enabled', 'true')
    config.save()
    runtime.store.check_ready()
    stored = json.loads(runtime.store.get('configs', 'config.json').content)
    assert stored['SSL']['ssl_enabled'] == 'true'
    assert business_storage.get_entrypoint_ssl_settings()['ssl_enabled'] is True
    assert (app_root / 'data/application.sqlite3').is_file()
    assert not (app_root / 'configs/config.json').exists()
    assert not (app_root / 'configs').exists()


def test_unmanaged_resources_do_not_initialize_the_database(app_root, monkeypatch):
    # An unmigrated business file makes accidental initialization observable.
    (app_root / 'permissions.json').write_text('{}', encoding='utf-8')
    calls = install_factory(monkeypatch, FakeStore())
    logs = app_root / 'logs'
    logs.mkdir()
    resource = logs / 'entry.json'
    with storage_io.open(resource, 'w', encoding='utf-8') as target:
        target.write('log resource')
    assert not storage_io.is_managed_path(resource)
    assert storage_io.os.path.exists(resource)
    assert storage_io.os.path.lexists(resource)
    assert storage_io.os.path.isfile(resource)
    assert storage_io.os.path.isdir(logs)
    assert storage_io.os.stat(resource).st_size == len('log resource')
    assert storage_io.os.listdir(logs) == ['entry.json']
    assert storage_io.glob.glob(str(logs / '*.json')) == [str(resource)]
    copied = logs / 'copy.json'
    storage_io.shutil.copy2(resource, copied)
    moved = logs / 'moved.json'
    storage_io.shutil.move(copied, moved)
    renamed = logs / 'renamed.json'
    storage_io.os.rename(moved, renamed)
    replaced = logs / 'replaced.json'
    storage_io.os.replace(renamed, replaced)
    storage_io.os.remove(replaced)
    storage_io.shutil.rmtree(logs)
    assert not logs.exists()
    assert not calls
    assert business_storage._runtime is None
    assert not (app_root / 'data/application.sqlite3').exists()


def test_unmanaged_external_temp_files_do_not_apply_application_root_guard(app_root, monkeypatch):
    external = app_root / 'external'
    external.mkdir()
    monkeypatch.setattr(business_storage, '__file__', str(app_root / 'code/business_storage.py'))
    monkeypatch.delenv('APP_STORAGE_ROOT')
    calls = install_factory(monkeypatch, FakeStore())
    target = external / 'permissions.json'
    with storage_io.open(target, 'w', encoding='utf-8') as handle:
        handle.write('{}')
    assert target.read_text(encoding='utf-8') == '{}'
    assert not calls


def test_initialized_runtime_routes_external_custom_directories_to_database(app_root, monkeypatch):
    runtime = business_storage.get_runtime()
    external = app_root.parent / (app_root.name + '-custom')
    runtime.policy = business_storage.StoragePolicy(app_root, {
        'System': {'school_accounts_dir': str(external)}})
    key = '11111111-1111-4111-8111-111111111111/account.ini'
    target = external / key
    with storage_io.open(target, 'w', encoding='utf-8') as handle:
        handle.write('[Account]\nusername=test-user\nua=isolated\n')
    assert runtime.store.get('school_accounts', key) is not None
    assert storage_io.os.path.exists(target)
    assert not target.exists()
    assert not external.exists()
