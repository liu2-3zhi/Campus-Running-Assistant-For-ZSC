"""Migration preserves data bytes and rejects partial or unsafe cutovers."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

import storage_migration as migration


@dataclass(frozen=True)
class Document:
    namespace: str
    key: str
    content: bytes
    mtime_ns: int
    revision: int
    digest: str


class MemoryStore:
    def __init__(self):
        self.documents = {}
        self.ready = False
        self.fail_key = None

    def init_schema(self):
        pass

    def check_ready(self):
        if not self.ready:
            raise migration.MigrationError("not ready")

    def mark_ready(self):
        self.ready = True

    def mark_pending(self):
        self.ready = False

    def get(self, namespace, key):
        return self.documents.get((namespace, key))

    def put(self, namespace, key, content, *, expected_revision=..., create_only=False, mtime_ns=None):
        if key == self.fail_key:
            raise RuntimeError("injected write failure")
        existing = self.get(namespace, key)
        if create_only and existing is not None:
            raise migration.MigrationError("concurrent create")
        if expected_revision is not ... and (existing is None or existing.revision != expected_revision):
            raise migration.MigrationError("concurrent update")
        document = Document(namespace, key, bytes(content), mtime_ns or 1, existing.revision + 1 if existing else 1, hashlib.sha256(content).hexdigest())
        self.documents[(namespace, key)] = document
        return document

    def list(self, namespace, prefix=""):
        return [document for document in self.documents.values() if document.namespace == namespace and document.key.startswith(prefix)]

    def namespaces(self):
        return sorted({document.namespace for document in self.documents.values()})

    @contextmanager
    def transaction(self):
        snapshot = copy.deepcopy((self.documents, self.ready))
        try:
            yield self
        except BaseException:
            self.documents, self.ready = snapshot
            raise


class FilePolicy:
    """The store's policy boundary, with no OS or database mocks."""
    def __init__(self, root, config=None):
        self.root = Path(root).resolve()
        self.roots = {"accounts": self.root / "school_accounts", "users": self.root / "system_accounts"}
        self.log_root = self.root / "logs"
        self.singleton = {"permissions": self.root / "permissions.json"}
        if config:
            self.roots["accounts"] = Path(config["accounts"])

    def identify(self, path):
        path = Path(path).absolute()
        if self.log_root == path or self.log_root in path.parents:
            return None
        for namespace, candidate in self.singleton.items():
            if path == candidate:
                return namespace, candidate.name
        for namespace, root in self.roots.items():
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if relative.parts and path.suffix in {".json", ".ini"}:
                return namespace, relative.as_posix()
        return None

    def physical_path(self, namespace, key):
        if namespace in self.singleton and key == self.singleton[namespace].name:
            return self.singleton[namespace]
        if namespace not in self.roots:
            raise ValueError("unknown namespace")
        return self.roots[namespace] / key

    def iter_files(self):
        return sorted(path for path in self.root.rglob("*") if path.is_file() and self.identify(path))


def source_file(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_plan_keeps_original_json_ini_and_indexes_without_logs_or_bootstrap(tmp_path):
    root = tmp_path / "source"
    source_file(root, "school_accounts/user_accounts/test-owner.json", '{"ua":"测试","password":"fixture-password"}\n'.encode())
    source_file(root, "school_accounts/10001.ini", b"[System]\nua = device-A\n")
    source_file(root, "system_accounts/_index.json", b'{"accounts":{"fixture":"hash"}}')
    source_file(root, "logs/audit.json", b"sensitive log content is outside migration")
    source_file(root, "configs/config.json", b"bootstrap is outside migration")

    plan = migration.build_plan(FilePolicy(root))

    assert len(plan.entries) == 3
    assert {(entry.namespace, entry.key) for entry in plan.entries} == {
        ("accounts", "10001.ini"), ("accounts", "user_accounts/test-owner.json"), ("users", "_index.json"),
    }
    assert next(entry for entry in plan.entries if entry.key == "10001.ini").content == b"[System]\nua = device-A\n"


@pytest.mark.parametrize("name,content", [
    ("bad.json", b'{"password":"do-not-print",'),
    ("bad.json", b'{"number":NaN}'),
    ("bad.ini", b"ua = do-not-print"),
    ("bad.json", b"\xff\xfeinvalid"),
    ("bad.ini", b"   \n"),
])
def test_invalid_source_is_rejected_before_any_database_mutation(tmp_path, name, content):
    source_file(tmp_path, "school_accounts/good.json", b"{}")
    source_file(tmp_path, f"school_accounts/{name}", content)
    store = MemoryStore()

    with pytest.raises(migration.MigrationError) as error:
        migration.import_documents(FilePolicy(tmp_path), store)

    assert store.documents == {}
    assert store.ready is False
    assert "do-not-print" not in str(error.value)


def test_explicit_empty_skip_is_reported_and_can_be_verified(tmp_path):
    source_file(tmp_path, "school_accounts/empty.json", b"\n  ")
    source_file(tmp_path, "school_accounts/good.json", b"{}")
    store = MemoryStore()

    result = migration.import_documents(FilePolicy(tmp_path), store, skip_empty=True)

    assert result.skipped_empty == 1
    assert store.ready is True
    assert store.get("accounts", "empty.json") is None
    assert migration.verify_documents(FilePolicy(tmp_path), store, skip_empty=True).ok


def test_import_is_idempotent_and_never_changes_source_bytes(tmp_path):
    path = source_file(tmp_path, "school_accounts/a.json", b'{ "password" : "fixture-password" }\r\n')
    original = path.read_bytes(), path.stat().st_mtime_ns
    store = MemoryStore()

    first = migration.import_documents(FilePolicy(tmp_path), store)
    second = migration.import_documents(FilePolicy(tmp_path), store)

    assert first.imported == 1
    assert second.unchanged == 1
    assert store.get("accounts", "a.json").revision == 1
    assert (path.read_bytes(), path.stat().st_mtime_ns) == original
    assert store.ready is True


def test_default_conflict_preflight_does_not_partially_import_earlier_keys(tmp_path):
    source_file(tmp_path, "school_accounts/a.json", b"{}")
    source_file(tmp_path, "school_accounts/z.json", b"[]")
    store = MemoryStore()
    store.put("accounts", "z.json", b'{"existing":true}')

    with pytest.raises(migration.MigrationError):
        migration.import_documents(FilePolicy(tmp_path), store)

    assert store.get("accounts", "a.json") is None
    assert store.get("accounts", "z.json").content == b'{"existing":true}'
    assert store.ready is False


def test_explicit_overwrite_is_verified_before_ready(tmp_path):
    source_file(tmp_path, "school_accounts/a.json", b'{"new":true}')
    store = MemoryStore()
    store.put("accounts", "a.json", b'{"old":true}')

    result = migration.import_documents(FilePolicy(tmp_path), store, conflict="overwrite")

    assert result.imported == 1
    assert store.get("accounts", "a.json").content == b'{"new":true}'
    assert store.get("accounts", "a.json").revision == 2
    assert store.ready is True


def test_skip_conflicts_never_marks_inconsistent_database_ready(tmp_path):
    source_file(tmp_path, "school_accounts/a.json", b"[]")
    store = MemoryStore()
    store.put("accounts", "a.json", b"{}")

    with pytest.raises(migration.VerificationError):
        migration.import_documents(FilePolicy(tmp_path), store, conflict="skip")

    assert store.get("accounts", "a.json").content == b"{}"
    assert store.ready is False


def test_failed_batch_rolls_back_current_batch_and_resume_finishes(tmp_path):
    for key in ("a.json", "b.json", "c.json", "d.json"):
        source_file(tmp_path, f"school_accounts/{key}", b"{}")
    store = MemoryStore()
    store.fail_key = "d.json"

    with pytest.raises(RuntimeError):
        migration.import_documents(FilePolicy(tmp_path), store, batch_size=2)

    assert set(store.documents) == {("accounts", "a.json"), ("accounts", "b.json")}
    assert store.ready is False
    store.fail_key = None
    result = migration.import_documents(FilePolicy(tmp_path), store, batch_size=2)
    assert result.unchanged == 2
    assert result.imported == 2
    assert store.ready is True


def test_verify_detects_missing_different_and_extra_records(tmp_path):
    source_file(tmp_path, "school_accounts/missing.json", b"{}")
    source_file(tmp_path, "school_accounts/different.json", b"[]")
    store = MemoryStore()
    store.put("accounts", "different.json", b"{}")
    store.put("accounts", "extra.json", b"{}")

    result = migration.verify_documents(FilePolicy(tmp_path), store)

    assert result.ok is False
    assert result.missing == (("accounts", "missing.json"),)
    assert result.different == (("accounts", "different.json"),)
    assert result.extra == (("accounts", "extra.json"),)


def test_export_preserves_bytes_and_reimports_into_separate_store(tmp_path):
    source = tmp_path / "source"
    source_file(source, "school_accounts/a.json", b'{ "name": "fixture" }\n')
    source_file(source, "permissions.json", b'{"groups":[]}')
    store = MemoryStore()
    migration.import_documents(FilePolicy(source), store)
    target = tmp_path / "export"

    result = migration.export_documents(FilePolicy(source), store, target)

    assert result.exported == 2
    assert (target / "school_accounts/a.json").read_bytes() == b'{ "name": "fixture" }\n'
    assert not (target / "configs/config.json").exists()
    imported = MemoryStore()
    migration.import_documents(FilePolicy(target), imported)
    assert imported.get("accounts", "a.json").content == store.get("accounts", "a.json").content


@pytest.mark.parametrize("namespace,key", [
    ("accounts", "../outside.json"), ("accounts", "/absolute.json"),
    ("accounts", "C:/outside.json"), ("accounts", "..\\outside.json"),
    ("accounts", "folder/../outside.json"), ("unknown", "a.json"),
])
def test_export_rejects_unsafe_keys_before_creating_destination(tmp_path, namespace, key):
    policy = FilePolicy(tmp_path / "source")
    store = MemoryStore()
    store.put(namespace, key, b"{}")
    store.ready = True
    target = tmp_path / "export"

    with pytest.raises(migration.MigrationError):
        migration.export_documents(policy, store, target)

    assert not target.exists()


def test_export_rejects_existing_destination_and_external_custom_directory(tmp_path):
    root = tmp_path / "source"
    store = MemoryStore()
    store.put("accounts", "a.json", b"{}")
    store.ready = True
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(migration.MigrationError):
        migration.export_documents(FilePolicy(root), store, existing)
    external_policy = FilePolicy(root, config={"accounts": str(tmp_path / "external")})
    target = tmp_path / "export"
    with pytest.raises(migration.MigrationError):
        migration.export_documents(external_policy, store, target)
    assert not target.exists()


def test_import_never_marks_ready_when_database_contains_extra_records(tmp_path):
    source_file(tmp_path, "school_accounts/a.json", b"{}")
    store = MemoryStore()
    store.put("accounts", "extra.json", b"{}")
    with pytest.raises(migration.VerificationError):
        migration.import_documents(FilePolicy(tmp_path), store)
    assert store.ready is False


def test_failed_overwrite_revokes_previous_ready_state(tmp_path):
    source_file(tmp_path, "school_accounts/a.json", b"{}")
    store = MemoryStore()
    store.ready = True
    store.fail_key = "a.json"
    with pytest.raises(RuntimeError):
        migration.import_documents(FilePolicy(tmp_path), store)
    assert store.ready is False


def test_cli_plan_runs_from_another_directory_without_mysql_configuration(tmp_path):
    root = tmp_path / "source"
    source_file(root, "school_accounts/a.json", b'{"password":"fixture-secret"}')
    source_file(root, "logs/audit.json", b"invalid log is excluded")
    source_file(root, "configs/config.json", b"{}")
    script = Path(__file__).resolve().parents[1] / "tools/migrate_storage.py"
    env = {key: value for key, value in os.environ.items() if not key.startswith("MYSQL_")}
    env["APP_STORAGE_BACKEND"] = "file"
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run([sys.executable, str(script), "--root", str(root), "plan"], cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["records"] == 2
    assert "fixture-secret" not in result.stdout + result.stderr


def test_cli_verify_returns_nonzero_for_extra_database_document(tmp_path, monkeypatch, capsys):
    source_file(tmp_path, "school_accounts/a.json", b"{}")
    monkeypatch.setenv("APP_STORAGE_BACKEND", "mysql")
    monkeypatch.setenv("MYSQL_USER", "test-user")
    monkeypatch.setenv("MYSQL_DATABASE", "test-database")
    store = MemoryStore()
    store.put("school_accounts", "extra.json", b"{}")

    result = migration.main(["--root", str(tmp_path), "verify"], store_factory=lambda settings: store)

    assert result == 1
    output = json.loads(capsys.readouterr().out)
    assert (output["missing"], output["extra"]) == (1, 1)


def test_cli_validates_source_before_constructing_database_store(tmp_path, monkeypatch, capsys):
    source_file(tmp_path, "school_accounts/a.json", b"invalid fixture")
    monkeypatch.setenv("APP_STORAGE_BACKEND", "mysql")
    monkeypatch.setenv("MYSQL_USER", "test-user")
    monkeypatch.setenv("MYSQL_DATABASE", "test-database")

    def unavailable_database(settings):
        raise AssertionError("database construction happened before validation")

    result = migration.main(["--root", str(tmp_path), "import", "--stopped"], store_factory=unavailable_database)

    assert result == 2
    assert "AssertionError" not in capsys.readouterr().err


def test_database_commands_read_mysql_settings_without_changing_runtime_mode(tmp_path, monkeypatch):
    source_file(tmp_path, "school_accounts/a.json", b"{}")
    monkeypatch.setenv("APP_STORAGE_BACKEND", "file")
    monkeypatch.setenv("MYSQL_USER", "test-user")
    monkeypatch.setenv("MYSQL_DATABASE", "test-database")
    received = []

    def database(settings):
        received.append(settings)
        return MemoryStore()

    assert migration.main(["--root", str(tmp_path), '--backend', 'mysql', "init"], store_factory=database) == 0
    assert received[0].backend == "mysql"
    assert received[0].user == "test-user"
    assert os.environ["APP_STORAGE_BACKEND"] == "file"


def test_real_policy_rejects_unregistered_namespace_without_creating_target(tmp_path):
    from business_storage import StoragePolicy
    store = MemoryStore()
    store.put("unknown", "a.json", b"{}")
    store.ready = True
    target = tmp_path / "target"
    with pytest.raises(migration.MigrationError):
        migration.export_documents(StoragePolicy(tmp_path / "root"), store, target)
    assert not target.exists()


def test_real_policy_migrates_bootstrap_and_keeps_custom_logs_outside(tmp_path):
    from business_storage import StoragePolicy
    root = tmp_path / "source"
    config = {"System": {"school_accounts_dir": "business/school"}, "Logging": {"log_dir": "business/school/logs"}}
    bootstrap = source_file(root, "configs/config.json", json.dumps(config).encode())
    business = source_file(root, "business/school/user_accounts/a.json", b'{"ua":"device-A"}')
    custom_log = source_file(root, "business/school/logs/audit.json", b"invalid-log-fixture")
    regular_log = source_file(root, "logs/audit.json", b"another-invalid-log-fixture")
    original = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (bootstrap, business, custom_log, regular_log)}
    store = MemoryStore()
    policy = StoragePolicy(root)

    migration.import_documents(policy, store)
    target = tmp_path / "export"
    migration.export_documents(policy, store, target)

    assert set(store.documents) == {("school_accounts", "user_accounts/a.json"), ('configs', 'config.json')}
    assert (target / "business/school/user_accounts/a.json").read_bytes() == b'{"ua":"device-A"}'
    assert json.loads((target / "configs/config.json").read_bytes()) == config
    assert not (target / "logs").exists()
    assert not (target / "business/school/logs").exists()
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in original} == original
    source_file(target, "configs/config.json", bootstrap.read_bytes())
    reimported = MemoryStore()
    migration.import_documents(StoragePolicy(target), reimported)
    assert reimported.get("school_accounts", "user_accounts/a.json").content == business.read_bytes()


def test_source_changes_during_import_prevent_ready_marker(tmp_path):
    path = source_file(tmp_path, "school_accounts/a.json", b"{}")

    class ChangingStore(MemoryStore):
        def put(self, *args, **kwargs):
            result = super().put(*args, **kwargs)
            path.write_bytes(b"[]")
            return result

    store = ChangingStore()
    with pytest.raises(migration.VerificationError):
        migration.import_documents(FilePolicy(tmp_path), store)
    assert store.ready is False


def test_cli_requires_explicit_stopped_acknowledgement_before_import(tmp_path):
    with pytest.raises(SystemExit) as error:
        migration.main(["--root", str(tmp_path), "import"])
    assert error.value.code == 2


def test_cli_help_is_utf8_even_with_legacy_windows_pipe_encoding(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools/migrate_storage.py"
    env = dict(os.environ, PYTHONIOENCODING="gbk")
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 0
    help_text = result.stdout.decode("utf-8")
    assert "停止应用" in help_text
    assert "{plan,init,import,verify,export}" in help_text
