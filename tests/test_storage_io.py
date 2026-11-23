"""Explicit storage adapters preserve filesystem behavior across backend boundaries."""

import configparser as standard_configparser
import contextlib
import hashlib
import io
import os as standard_os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

import storage_io


class ConflictError(RuntimeError):
    pass


class MemoryStore:
    def __init__(self):
        self.documents = {}
        self.fail_put = False

    def get(self, namespace, key):
        return self.documents.get((namespace, key))

    def put(self, namespace, key, content, expected_revision=..., create_only=False, mtime_ns=None):
        if self.fail_put:
            raise RuntimeError("database unavailable")
        previous = self.get(namespace, key)
        if create_only and previous is not None:
            raise FileExistsError(key)
        if expected_revision is not ... and (previous.revision if previous else 0) != expected_revision:
            raise ConflictError(key)
        value = SimpleNamespace(namespace=namespace, key=key, content=bytes(content),
                                revision=(previous.revision if previous else 0) + 1,
                                mtime_ns=mtime_ns or 1_700_000_000_000_000_000,
                                digest=hashlib.sha256(content).hexdigest())
        self.documents[(namespace, key)] = value
        return value

    def delete(self, namespace, key, expected_revision=...):
        previous = self.get(namespace, key)
        if expected_revision is not ... and (previous.revision if previous else 0) != expected_revision:
            raise ConflictError(key)
        self.documents.pop((namespace, key), None)

    def list(self, namespace, prefix=""):
        return [document for (ns, key), document in sorted(self.documents.items())
                if ns == namespace and key.startswith(prefix)]

    @contextlib.contextmanager
    def transaction(self):
        original = dict(self.documents)
        try:
            yield self
        except BaseException:
            self.documents = original
            raise


class Policy:
    def __init__(self, root):
        self.root = Path(root).absolute()

    def relative(self, path):
        try:
            return Path(path).absolute().relative_to(self.root)
        except (ValueError, TypeError):
            return None

    def identify(self, path):
        relative = self.relative(path)
        if relative is not None and relative.suffix in {".json", ".ini"}:
            return "data", relative.as_posix()
        return None

    def directory(self, path):
        relative = self.relative(path)
        if relative is not None and not relative.suffix:
            return "data", "" if str(relative) == "." else relative.as_posix()
        return None

    def physical_path(self, namespace, key):
        assert namespace == "data"
        return self.root / key


@pytest.fixture(params=['sqlite', 'mysql'])
def backend(tmp_path, monkeypatch, request):
    root = tmp_path / "managed"
    root.mkdir()
    runtime = SimpleNamespace(backend=request.param, policy=Policy(root), store=MemoryStore())
    monkeypatch.setattr(storage_io, "get_runtime", lambda *paths: runtime)
    return runtime, root


@pytest.fixture
def real_policy_backend(tmp_path, monkeypatch):
    from business_storage import StoragePolicy

    policy = StoragePolicy(tmp_path, {"System": {"school_accounts_dir": "business/school"},
                                      "Logging": {"log_dir": "business/school/logs"}})
    runtime = SimpleNamespace(backend="mysql", policy=policy, store=MemoryStore())
    monkeypatch.setattr(storage_io, "get_runtime", lambda *paths: runtime)
    return runtime, tmp_path


@pytest.fixture
def live_mysql_backend(tmp_path, monkeypatch):
    """Opt-in live tests own unique ioa_* tables and never use deployment tables."""
    if not standard_os.environ.get("STORAGE_IO_TEST_MYSQL_PORT"):
        pytest.skip("set STORAGE_IO_TEST_MYSQL_PORT and credentials for live MySQL adapter tests")
    from business_storage import MySQLDocumentStore, StoragePolicy, StorageRuntime, StorageSettings

    settings = StorageSettings(
        backend="mysql", root=tmp_path,
        host=standard_os.environ.get("STORAGE_IO_TEST_MYSQL_HOST", "127.0.0.1"),
        port=int(standard_os.environ["STORAGE_IO_TEST_MYSQL_PORT"]),
        user=standard_os.environ.get("STORAGE_IO_TEST_MYSQL_USER", "root"),
        password=standard_os.environ.get("STORAGE_IO_TEST_MYSQL_PASSWORD", ""),
        database=standard_os.environ.get("STORAGE_IO_TEST_MYSQL_DATABASE", "storage_test"),
        table_prefix="ioa_" + uuid.uuid4().hex[:12] + "_",
    )
    store = MySQLDocumentStore(settings)
    store.init_schema()
    runtime = StorageRuntime("mysql", StoragePolicy(tmp_path, {}), store)
    monkeypatch.setattr(storage_io, "get_runtime", lambda *paths: runtime)
    try:
        yield runtime, tmp_path
    finally:
        connection = store._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE " + settings.table_prefix + "documents")
                cursor.execute("DROP TABLE " + settings.table_prefix + "storage_meta")
            connection.commit()
        finally:
            connection.close()


def test_unmanaged_paths_delegate_and_never_mutate_standard_library(backend, tmp_path):
    runtime, _ = backend
    path = tmp_path / "plain.json"
    with storage_io.open(path, "w", encoding="utf-8") as target:
        target.write("physical")
    assert path.read_text() == "physical"
    assert not runtime.store.documents
    assert standard_os.path.exists is not storage_io.os.path.exists
    assert standard_configparser.ConfigParser is not storage_io.configparser.ConfigParser


def test_file_backend_cannot_be_enabled_through_the_compatibility_adapter(backend):
    from business_storage import StorageConfigurationError
    runtime, root = backend
    runtime.backend = 'file'
    with pytest.raises(StorageConfigurationError, match='frozen'):
        storage_io.open(root / 'business.json', 'w', encoding='utf-8')


def test_managed_open_never_falls_back_to_stale_files_and_commits_unicode(backend):
    runtime, root = backend
    path = root / "profile.json"
    path.write_text("stale")
    assert not storage_io.os.path.exists(path)
    with pytest.raises(FileNotFoundError):
        storage_io.open(path, encoding="utf-8")
    with storage_io.open(path, "w", encoding="utf-8") as target:
        target.write("测试用户")
    assert storage_io.open(path, encoding="utf-8").read() == "测试用户"
    assert path.read_text() == "stale"
    assert runtime.store.get("data", "profile.json").content == "测试用户".encode()


def test_failed_context_does_not_write_and_flush_makes_changes_visible(backend):
    runtime, root = backend
    path = root / "state.json"
    with pytest.raises(ValueError):
        with storage_io.open(path, "w") as target:
            target.write("discard")
            raise ValueError("failed operation")
    assert runtime.store.get("data", "state.json") is None
    with storage_io.open(path, "w") as target:
        target.write("visible")
        target.flush()
        assert runtime.store.get("data", "state.json").content == b"visible"


def test_append_exclusive_binary_and_read_update_conflicts(backend):
    runtime, root = backend
    path = root / "state.json"
    with storage_io.open(path, "xb") as target:
        target.write(b"first")
    with pytest.raises(FileExistsError):
        storage_io.open(path, "x")
    with storage_io.open(path, "a+") as target:
        target.seek(0)
        target.write("-second")
    assert storage_io.open(path, "rb").read() == b"first-second"
    left = storage_io.open(path, "r+")
    right = storage_io.open(path, "r+")
    left.write("LEFT")
    left.close()
    right.write("RIGHT")
    with pytest.raises(ConflictError):
        right.close()
    assert storage_io.open(path).read() == "LEFTt-second"


def test_mixed_directory_and_recursive_glob_hide_stale_managed_files(backend):
    runtime, root = backend
    (root / "stale.json").write_text("stale")
    (root / "photo.png").write_bytes(b"image")
    runtime.store.put("data", "virtual/state.json", b"state")
    runtime.store.put("data", "profile.json", b"profile")
    assert set(storage_io.os.listdir(root)) == {"photo.png", "virtual", "profile.json"}
    assert storage_io.os.path.isdir(root / "virtual")
    assert storage_io.os.path.isfile(root / "virtual/state.json")
    assert not storage_io.os.path.isfile(root / "stale.json")
    assert set(storage_io.glob.glob(str(root / "**/*.json"), recursive=True)) == {
        str(root / "profile.json"), str(root / "virtual/state.json"),
    }
    assert storage_io.os.path.getsize(root / "profile.json") == 7
    assert storage_io.os.stat(root / "profile.json").st_mtime_ns == 1_700_000_000_000_000_000


def test_physical_temporary_replace_does_not_remove_source_on_database_failure(backend, tmp_path):
    runtime, root = backend
    source = tmp_path / "temporary.tmp"
    source.write_bytes(b"new")
    runtime.store.fail_put = True
    with pytest.raises(RuntimeError):
        storage_io.os.replace(source, root / "target.json")
    assert source.read_bytes() == b"new"
    runtime.store.fail_put = False
    storage_io.os.replace(source, root / "target.json")
    assert not source.exists()
    assert storage_io.open(root / "target.json", "rb").read() == b"new"


def test_copy_move_and_tree_removal_work_across_storage_boundary(backend, tmp_path):
    runtime, root = backend
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    storage_io.shutil.copy2(source, root / "a.json")
    assert source.exists()
    destination = tmp_path / "export.bin"
    storage_io.shutil.copy(root / "a.json", destination)
    assert destination.read_bytes() == b"payload"
    storage_io.shutil.move(root / "a.json", root / "nested/b.json")
    assert not storage_io.os.path.exists(root / "a.json")
    assert storage_io.open(root / "nested/b.json", "rb").read() == b"payload"
    storage_io.shutil.rmtree(root / "nested")
    assert not storage_io.os.path.exists(root / "nested/b.json")


def test_db_to_db_rename_rolls_back_if_destination_write_fails(backend):
    runtime, root = backend
    runtime.store.put("data", "source.json", b"original")
    runtime.store.fail_put = True
    with pytest.raises(RuntimeError):
        storage_io.os.rename(root / "source.json", root / "destination.json")
    assert storage_io.open(root / "source.json", "rb").read() == b"original"


def test_configparser_reads_database_ini_and_leaves_standard_class_untouched(backend):
    runtime, root = backend
    path = root / "settings.ini"
    runtime.store.put("data", "settings.ini", b"[Config]\nua = account-UA\n")
    config = storage_io.configparser.ConfigParser()
    assert isinstance(config, storage_io.configparser.RawConfigParser)
    assert config.read(path, encoding="utf-8") == [str(path)]
    assert config.get("Config", "ua") == "account-UA"
    assert standard_configparser.ConfigParser().read(path) == []


def test_logs_and_binary_assets_remain_physical_even_in_mysql(backend, tmp_path):
    runtime, root = backend
    log = tmp_path / "logs/test.json"
    storage_io.os.makedirs(log.parent)
    with storage_io.open(log, "w") as target:
        target.write("log")
    with storage_io.open(root / "photo.png", "wb") as target:
        target.write(b"image")
    assert log.read_text() == "log"
    assert (root / "photo.png").read_bytes() == b"image"
    assert storage_io.os.path.exists(root / 'photo.png')
    assert storage_io.os.path.lexists(root / 'photo.png')
    assert storage_io.os.path.isfile(root / 'photo.png')
    assert not runtime.store.documents


def test_real_policy_preserves_nested_binary_asset_visibility(real_policy_backend):
    runtime, root = real_policy_backend
    avatar = root / 'system_accounts/images/avatar.png'
    avatar.parent.mkdir(parents=True)
    avatar.write_bytes(b'image')
    assert storage_io.os.path.exists(avatar)
    assert storage_io.os.path.lexists(avatar)
    assert storage_io.os.path.isfile(avatar)
    assert storage_io.glob.glob(str(avatar.parent / '*.png')) == [str(avatar)]
    assert not runtime.store.documents


def test_mode_permissions_update_truncate_and_empty_file_commit(backend):
    _, root = backend
    path = root / "modes.json"
    with storage_io.open(path, "w+") as target:
        target.write("abc\nsecond")
        target.seek(0)
        assert target.readline() == "abc\n"
        target.seek(0)
        target.truncate(3)
    with storage_io.open(path, "br") as source:
        assert source.read() == b"abc"
        with pytest.raises(io.UnsupportedOperation):
            source.write(b"x")
    with storage_io.open(path, "w") as target:
        with pytest.raises(io.UnsupportedOperation):
            target.read()
    assert storage_io.os.path.getsize(path) == 0
    with storage_io.open(root / "new.json", "a"):
        pass
    assert storage_io.os.path.exists(root / "new.json")


def test_recursive_terminal_glob_includes_files_and_virtual_directories(backend):
    runtime, root = backend
    runtime.store.put("data", "folder/state.json", b"state")
    assert set(storage_io.glob.glob(str(root / "**"), recursive=True)) == {
        str(root) + standard_os.sep, str(root / "folder"), str(root / "folder/state.json"),
    }


def test_recursive_directory_only_glob_excludes_files_and_duplicate_separators(backend):
    runtime, root = backend
    runtime.store.put("data", "folder/state.json", b"state")
    pattern = str(root / "**") + standard_os.sep
    assert set(storage_io.glob.glob(pattern, recursive=True)) == {
        str(root) + standard_os.sep, str(root / "folder") + standard_os.sep,
    }


def test_unmanaged_glob_is_delegated_with_its_original_path_spelling(backend, tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / "entry.json").write_text("log")
    pattern = str(folder / ".") + standard_os.sep + "*.json"
    import glob
    assert storage_io.glob.glob(pattern) == glob.glob(pattern)


def test_copy_failure_preserves_both_physical_and_database_source(backend, tmp_path):
    runtime, root = backend
    original = tmp_path / "source.bin"
    original.write_bytes(b"physical")
    runtime.store.put("data", "source.json", b"database")
    runtime.store.fail_put = True
    with pytest.raises(RuntimeError):
        storage_io.shutil.move(original, root / "a.json")
    with pytest.raises(RuntimeError):
        storage_io.shutil.move(root / "source.json", root / "b.json")
    assert original.read_bytes() == b"physical"
    assert storage_io.open(root / "source.json", "rb").read() == b"database"


def test_move_directory_merges_virtual_documents_and_physical_assets(backend, tmp_path):
    runtime, root = backend
    folder = root / "folder"
    folder.mkdir()
    (folder / "image.png").write_bytes(b"image")
    runtime.store.put("data", "folder/state.json", b"state")
    target = tmp_path / "exported"
    storage_io.shutil.move(folder, target)
    assert (target / "state.json").read_bytes() == b"state"
    assert (target / "image.png").read_bytes() == b"image"
    assert not storage_io.os.path.exists(folder)


def test_rmtree_preserves_managed_physical_migration_sources(backend):
    runtime, root = backend
    folder = root / "accounts"
    folder.mkdir()
    stale = folder / "stale.json"
    stale.write_bytes(b"migration-source")
    (folder / "avatar.png").write_bytes(b"image")
    runtime.store.put("data", "accounts/stale.json", b"database")
    storage_io.shutil.rmtree(folder)
    assert runtime.store.get("data", "accounts/stale.json") is None
    assert stale.read_bytes() == b"migration-source"
    assert not (folder / "avatar.png").exists()
    assert not storage_io.os.path.isfile(stale)
    assert storage_io.os.listdir(folder) == []


def test_real_policy_merges_settings_and_custom_account_paths(real_policy_backend):
    runtime, root = real_policy_backend
    (root / "messages.json").write_bytes(b"old-settings")
    (root / "unmanaged.json").write_bytes(b"unmanaged")
    config = root / "configs/config.json"
    config.parent.mkdir()
    config.write_bytes(b"local-bootstrap")
    log = root / "business/school/logs/audit.json"
    log.parent.mkdir(parents=True)
    log.write_bytes(b"log")
    account = root / "business/school/user/accounts.ini"
    runtime.store.put("school_accounts", "user/accounts.ini", b"[Config]\nua=isolated\n")
    runtime.store.put("settings", "messages.json", b"new-settings")
    runtime.store.put("configs", "config.json", b"database-config")
    assert storage_io.open(root / "messages.json", "rb").read() == b"new-settings"
    assert storage_io.open(root / "unmanaged.json", "rb").read() == b"unmanaged"
    assert storage_io.open(config, "rb").read() == b"database-config"
    assert config.read_bytes() == b"local-bootstrap"
    assert storage_io.open(log, "rb").read() == b"log"
    assert set(storage_io.os.listdir(account.parent)) == {"accounts.ini"}
    parser = storage_io.configparser.ConfigParser()
    assert parser.read(account, encoding="utf-8") == [str(account)]
    assert parser.get("Config", "ua") == "isolated"
    assert set(storage_io.glob.glob(str(root / "*.json"))) == {
        str(root / "messages.json"), str(root / "unmanaged.json"),
    }


def test_rmtree_real_policy_preserves_nested_logs_and_migration_sources(real_policy_backend):
    runtime, root = real_policy_backend
    folder = root / "business/school"
    logs = folder / "logs"
    logs.mkdir(parents=True)
    (logs / "audit.json").write_bytes(b"log")
    (folder / "source.json").write_bytes(b"source")
    (folder / "photo.png").write_bytes(b"image")
    runtime.store.put("school_accounts", "source.json", b"database")
    storage_io.shutil.rmtree(folder)
    assert runtime.store.get("school_accounts", "source.json") is None
    assert (logs / "audit.json").read_bytes() == b"log"
    assert (folder / "source.json").read_bytes() == b"source"
    assert not (folder / "photo.png").exists()


@pytest.mark.parametrize("mode", ["w", "w+", "a", "a+", "x", "x+"])
def test_live_mysql_open_creates_missing_documents(live_mysql_backend, mode):
    runtime, root = live_mysql_backend
    path = root / "school_accounts/new.json"
    with storage_io.open(path, mode, encoding="utf-8") as target:
        target.write("新账号")
    assert runtime.store.get("school_accounts", "new.json").content == "新账号".encode()
    assert not path.exists()


@pytest.mark.parametrize("mode,expected", [("w", b"new"), ("w+", b"new"),
                                            ("a", b"oldnew"), ("a+", b"oldnew")])
def test_live_mysql_open_updates_existing_documents(live_mysql_backend, mode, expected):
    runtime, root = live_mysql_backend
    runtime.store.put("school_accounts", "existing.json", b"old")
    with storage_io.open(root / "school_accounts/existing.json", mode) as target:
        target.write("new")
    assert runtime.store.get("school_accounts", "existing.json").content == expected


def test_live_mysql_exclusive_and_cas_updates(live_mysql_backend):
    from business_storage import ConflictError as DatabaseConflictError

    runtime, root = live_mysql_backend
    path = root / "school_accounts/state.json"
    runtime.store.put("school_accounts", "state.json", b"old")
    with pytest.raises(FileExistsError):
        storage_io.open(path, "x")
    with pytest.raises(FileNotFoundError):
        storage_io.open(root / "school_accounts/missing.json", "r+")
    first, second = storage_io.open(path, "r+b"), storage_io.open(path, "r+b")
    first.write(b"one")
    first.close()
    second.write(b"two")
    with pytest.raises(DatabaseConflictError):
        second.close()
    assert runtime.store.get("school_accounts", "state.json").content == b"one"


def test_live_mysql_rename_configparser_and_failed_context(live_mysql_backend):
    runtime, root = live_mysql_backend
    source = root / "school_accounts/source.ini"
    target = root / "school_accounts/nested/target.ini"
    with storage_io.open(source, "w", encoding="utf-8") as handle:
        handle.write("[Config]\nua = isolated-UA\n")
    storage_io.os.rename(source, target)
    assert not storage_io.os.path.exists(source)
    parser = storage_io.configparser.ConfigParser()
    assert parser.read(target, encoding="utf-8") == [str(target)]
    assert parser.get("Config", "ua") == "isolated-UA"
    original = runtime.store.get("school_accounts", "nested/target.ini").content
    with pytest.raises(RuntimeError):
        with storage_io.open(target, "w") as handle:
            handle.write("discard")
            raise RuntimeError("abort")
    assert runtime.store.get("school_accounts", "nested/target.ini").content == original


def test_live_mysql_physical_replace_metadata_and_source_preserving_rmtree(live_mysql_backend):
    runtime, root = live_mysql_backend
    physical_source = root / "incoming.tmp"
    physical_source.write_bytes(b"new-json")
    folder = root / "school_accounts/owner"
    folder.mkdir(parents=True)
    target = folder / "state.json"
    target.write_bytes(b"migration-original")
    (folder / "avatar.png").write_bytes(b"image")
    storage_io.os.replace(physical_source, target)
    assert not physical_source.exists()
    document = runtime.store.get("school_accounts", "owner/state.json")
    assert document.content == b"new-json"
    assert storage_io.os.path.getsize(target) == len(document.content)
    assert storage_io.os.stat(target).st_mtime_ns == document.mtime_ns
    assert storage_io.os.listdir(folder) == ["avatar.png", "state.json"]
    storage_io.shutil.rmtree(folder)
    assert runtime.store.get("school_accounts", "owner/state.json") is None
    assert target.read_bytes() == b"migration-original"
    assert not (folder / "avatar.png").exists()
