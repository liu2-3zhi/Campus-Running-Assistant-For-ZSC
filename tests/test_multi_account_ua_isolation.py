"""Account UA survives loading, relogin and concurrent request construction."""

import itertools
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

import api_client
import api_runtime
import runtime_models
import session_state
import business_storage
import storage_io
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore


@pytest.fixture
def runtime(monkeypatch):
    value = SimpleNamespace(
        requests=requests,
        ApiClient=api_client.ApiClient,
        AccountSession=runtime_models.AccountSession,
        UserData=runtime_models.UserData,
        MAX_USERNAME_LENGTH=128, MAX_PASSWORD_LENGTH=128, MAX_TAG_LENGTH=128,
        USERNAME_PATTERN=None,
        is_valid_school_username=lambda value: value.isdigit() and len(value) >= 4,
        is_valid_school_password=lambda value: True,
        socketio=Mock(),
        _redact_sensitive_log_value=lambda value: value,
    )
    for module in (api_client, api_runtime, runtime_models):
        monkeypatch.setattr(module, "_main", lambda: value)
    return value


def account_bridge(tmp_path=None):
    api = object.__new__(api_runtime.Api)
    api.window = None
    api.accounts = {}
    api.global_params = {}
    api.device_ua = "parent-UA"
    api.user_dir = str(tmp_path or ".")
    api.log_and_notify_frontend = Mock()
    api._load_account_tag = Mock(return_value="")
    api._save_account_tag = Mock()
    api._save_config = Mock()
    api._get_auth_user_and_check_admin = Mock(return_value=("test-owner", False))
    api._load_accounts_by_permission = Mock(return_value={})
    api._update_multi_global_buttons = Mock()
    api.multi_get_all_accounts_status = Mock(return_value={"success": True, "accounts": []})
    api._reset_account_session_for_relogin = Mock()
    return api


@pytest.fixture
def owner_binding_store(runtime, tmp_path, monkeypatch):
    root = tmp_path / "app"
    store = RelationalStore(DatabaseSettings(root=root, sqlite_path=":memory:"))
    store.init_schema(ready=True)
    backend = business_storage.StorageRuntime(
        "sqlite", business_storage.StoragePolicy(root, {}), store
    )
    monkeypatch.setattr(storage_io, "get_runtime", lambda *paths: backend)
    runtime.SCHOOL_ACCOUNTS_DIR = str(root / "school_accounts")
    runtime._auth_username_storage_key = lambda owner: hashlib.sha256(owner.encode()).hexdigest()
    runtime.auth_system = SimpleNamespace(check_permission=Mock(return_value=False))
    api = account_bridge(root)
    api.auth_username = "test-owner"
    owner_key = runtime._auth_username_storage_key(api.auth_username)
    store.put("system_accounts", owner_key + ".json", json.dumps({"auth_username": api.auth_username}).encode())
    binding_key = "user_accounts/" + owner_key + ".json"
    yield SimpleNamespace(store=store, api=api, binding_key=binding_key)
    store.database.dispose()


def put_owner_bindings(harness, values):
    harness.store.put("school_accounts", harness.binding_key,
                      json.dumps(values, ensure_ascii=False, indent=2).encode())


def get_owner_bindings(harness):
    document = harness.store.get("school_accounts", harness.binding_key)
    return json.loads(document.content.decode())


def test_explicit_password_keeps_each_accounts_saved_ua(runtime, tmp_path):
    api = account_bridge(tmp_path)
    api._load_accounts_by_permission.return_value = {
        "10001": {"password": "old-password", "ua": "Android account-A"},
        "10002": {"password": "old-password", "ua": "iPhone account-B"},
    }
    for username in ("10001", "10002"):
        assert api.multi_add_account(username, "explicit-password")["success"]

    first, second = api.accounts.values()
    assert first.device_ua == "Android account-A"
    assert second.device_ua == "iPhone account-B"
    assert first.password == second.password == "explicit-password"
    assert first.api_client.app is first
    assert second.api_client.app is second
    assert first.api_client.session is not second.api_client.session
    api.device_ua = "changed-parent-UA"
    assert first.api_client._get_headers()["User-Agent"] == "Android account-A" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["User-Agent"] == "iPhone account-B" + api_client.ApiClient.UA_SUFFIX
    assert first.api_client._get_headers()["platform"] == "android"
    assert second.api_client._get_headers()["platform"] == "ios"


@pytest.mark.parametrize("lost_ua", [None, "", "  ", "null", "None", "undefined"])
def test_request_repairs_lost_ua_from_its_own_last_value(runtime, monkeypatch, lost_ua):
    api = account_bridge()
    first = runtime.AccountSession("10001", "test-password", api)
    second = runtime.AccountSession("10002", "test-password", api)
    first.device_ua, second.device_ua = "Android account-A", "iPhone account-B"
    assert first.api_client._get_headers()["User-Agent"].startswith("Android account-A")
    assert second.api_client._get_headers()["platform"] == "ios"
    first.device_ua = lost_ua
    second.device_ua = lost_ua
    generator = Mock(return_value="unexpected-new-UA")
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", generator)

    assert first.api_client._get_headers()["User-Agent"] == "Android account-A" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["User-Agent"] == "iPhone account-B" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["platform"] == "ios"
    assert first.device_ua == "Android account-A"
    assert second.device_ua == "iPhone account-B"
    generator.assert_not_called()


def test_missing_ua_is_generated_once_per_client_during_concurrent_requests(runtime, monkeypatch):
    api = account_bridge()
    first = runtime.AccountSession("10001", "test-password", api)
    second = runtime.AccountSession("10002", "test-password", api)
    generated = []
    counter = itertools.count()
    generation_lock = threading.Lock()

    def generate():
        with generation_lock:
            value = f"Android isolated-{next(counter)}"
            generated.append(value)
            return value

    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(generate))
    with ThreadPoolExecutor(max_workers=8) as pool:
        headers = list(pool.map(lambda index: (first if index % 2 else second).api_client._get_headers(), range(64)))
    assert len(generated) == 2
    assert first.device_ua != second.device_ua
    assert {item["User-Agent"] for item in headers} == {
        first.device_ua + api_client.ApiClient.UA_SUFFIX,
        second.device_ua + api_client.ApiClient.UA_SUFFIX,
    }
    assert api.device_ua == "parent-UA"


@pytest.mark.parametrize("missing_ua", [None, "", "  ", "null"])
def test_password_update_with_missing_ua_preserves_saved_account_identity(owner_binding_store, missing_ua):
    harness = owner_binding_store
    api = harness.api
    put_owner_bindings(harness, {"10001": {"password": "old", "ua": "saved-account-UA", "completed_count": 7}})

    api._update_school_account_password("test-owner", "10001", "new", ua=missing_ua, login_verified=True)

    assert get_owner_bindings(harness)["10001"] == {
        "ua": "saved-account-UA", "password": "new", "completed_count": 7,
    }


def test_legacy_password_entry_is_upgraded_with_ua_without_losing_password(owner_binding_store):
    harness = owner_binding_store
    api = harness.api
    put_owner_bindings(harness, {"10001": "old"})

    api._update_school_account_password("test-owner", "10001", "new", ua="new-UA", login_verified=True)

    assert get_owner_bindings(harness)["10001"] == {"password": "new", "ua": "new-UA"}


def test_status_reports_each_accounts_runtime_ua(runtime):
    api = account_bridge()
    del api.multi_get_all_accounts_status
    api._is_multi_account_execution_active = lambda acc: False
    api._get_account_login_verification = lambda acc: {}
    api._can_skip_multi_task_wait = lambda acc: False
    for username, ua in (("10001", "Android account-A"), ("10002", "iPhone account-B")):
        acc = runtime.AccountSession(username, "test-password", api)
        acc.device_ua = ua
        acc.user_data.gender = "test"
        api.accounts[username] = acc

    result = api.multi_get_all_accounts_status()

    assert {row["username"]: row.get("device_ua") for row in result["accounts"]} == {
        "10001": "Android account-A", "10002": "iPhone account-B",
    }


def test_status_restores_account_ua_from_client_before_reporting(runtime):
    api = account_bridge()
    del api.multi_get_all_accounts_status
    api._is_multi_account_execution_active = lambda acc: False
    api._get_account_login_verification = lambda acc: {}
    api._can_skip_multi_task_wait = lambda acc: False
    acc = runtime.AccountSession("10001", "test-password", api)
    acc.user_data.gender = "test"
    acc.device_ua = "last-known-account-UA"
    acc.api_client._get_headers()
    acc.device_ua = None
    api.accounts[acc.username] = acc

    result = api.multi_get_all_accounts_status()

    assert result["accounts"][0]["device_ua"] == "last-known-account-UA"
    assert acc.device_ua == "last-known-account-UA"


def test_snapshot_repairs_account_ua_from_client_before_writing(runtime, monkeypatch, tmp_path):
    api = account_bridge(tmp_path)
    api.is_multi_account_mode = True
    acc = runtime.AccountSession("10001", "test-password", api)
    acc.device_ua = "last-known-account-UA"
    acc.api_client._get_headers()
    acc.device_ua = ""
    api.accounts[acc.username] = acc
    runtime.normalize_session_uuid = lambda value: value
    runtime.SESSION_STORAGE_DIR = str(tmp_path)
    runtime.session_file_locks = {}
    runtime.session_file_locks_lock = threading.Lock()
    runtime.get_business_session_login_success = lambda api: False
    runtime.is_multi_account_logged_in = lambda acc: False
    runtime._load_session_index = lambda: {}
    runtime._save_session_index = lambda index: None
    monkeypatch.setattr(session_state, "_main", lambda: runtime)

    session_state.save_session_state("test-session", api, force_save=True)

    state = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert state["multi_account_states"]["10001"]["device_ua"] == "last-known-account-UA"
    assert acc.device_ua == "last-known-account-UA"


def test_restore_does_not_replace_existing_clients_cached_identity(runtime, monkeypatch):
    api = account_bridge()
    api.all_run_data = []
    api.current_run_idx = -1
    api._multi_refresh_worker = Mock()
    acc = runtime.AccountSession("10001", "test-password", api)
    acc.device_ua = "live-cached-UA"
    acc.api_client._get_headers()
    acc.device_ua = None
    api.accounts[acc.username] = acc
    monkeypatch.setattr(session_state, "_main", lambda: runtime)
    monkeypatch.setattr(session_state, "threading", SimpleNamespace(Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)))

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"10001": {"device_ua": "stale-snapshot-UA"}},
    })

    assert acc.device_ua == "live-cached-UA"
    assert acc.api_client._get_headers()["User-Agent"] == "live-cached-UA" + api_client.ApiClient.UA_SUFFIX


def test_unverified_password_update_only_fills_missing_ua(owner_binding_store):
    harness = owner_binding_store
    api = harness.api
    put_owner_bindings(harness, {"10001": {"password": "verified-password", "ua": ""}})

    api._update_school_account_password("test-owner", "10001", "unverified-password", ua="recovered-UA")

    assert get_owner_bindings(harness) == {"10001": {"password": "verified-password", "ua": "recovered-UA"}}
    api._update_school_account_password("test-owner", "10001", "unverified-password", ua="different-UA")
    assert get_owner_bindings(harness) == {"10001": {"password": "verified-password", "ua": "recovered-UA"}}


def test_verified_login_updates_only_owned_binding_without_loading_or_saving_all_accounts(owner_binding_store):
    harness = owner_binding_store
    put_owner_bindings(harness, {
        "10001": {"password": "old-password", "ua": "old-UA", "custom": "preserve"},
        "10002": {"password": "other-password", "ua": "other-UA"},
    })
    harness.api._load_user_school_accounts = Mock(side_effect=AssertionError("login must not aggregate all school accounts"))
    harness.api._save_user_school_accounts = Mock(side_effect=AssertionError("login must not bulk-save all school accounts"))
    harness.api._load_school_account_stats_from_ini = Mock(side_effect=AssertionError("login must not read account stats"))
    harness.api._save_school_account_stats_to_ini = Mock(side_effect=AssertionError("login must not rewrite account stats"))

    harness.api._update_school_account_password(
        "test-owner", "10001", "new-password", ua="new-UA", login_verified=True
    )

    assert get_owner_bindings(harness) == {
        "10001": {"password": "new-password", "ua": "new-UA", "custom": "preserve"},
        "10002": {"password": "other-password", "ua": "other-UA"},
    }
    harness.api._load_user_school_accounts.assert_not_called()
    harness.api._save_user_school_accounts.assert_not_called()
    harness.api._load_school_account_stats_from_ini.assert_not_called()
    harness.api._save_school_account_stats_to_ini.assert_not_called()


def test_login_binding_conflict_preserves_newer_owned_document(owner_binding_store, monkeypatch, caplog):
    harness = owner_binding_store
    put_owner_bindings(harness, {"10001": {"password": "old-password", "ua": "old-UA"}})
    newer_bindings = {
        "10001": {"password": "old-password", "ua": "old-UA"},
        "10002": {"password": "parallel-password", "ua": "parallel-UA"},
    }
    original_load = api_runtime.json.load

    def load_then_commit_concurrent_update(handle):
        values = original_load(handle)
        put_owner_bindings(harness, newer_bindings)
        return values

    monkeypatch.setattr(api_runtime.json, "load", load_then_commit_concurrent_update)

    result = harness.api._update_school_account_password(
        "test-owner", "10001", "new-password", ua="new-UA", login_verified=True
    )

    assert result is False
    assert get_owner_bindings(harness) == newer_bindings
    assert "ConflictError" in caplog.text
    assert "new-password" not in caplog.text
    assert "parallel-password" not in caplog.text


def test_missing_ua_recovery_does_not_create_an_empty_binding_document(owner_binding_store):
    harness = owner_binding_store

    harness.api._persist_missing_school_account_ua("test-owner", "10001", "recovered-UA")

    assert harness.store.get("school_accounts", harness.binding_key) is None


def test_verified_login_saves_school_credentials_and_owner_binding_once(owner_binding_store, runtime, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    api._execution_blocks_mode_change = Mock(return_value=False)
    api.api_client = SimpleNamespace(session=SimpleNamespace(close=Mock()))
    api.is_offline_mode = False
    api._persist_school_account_backup = Mock()
    api._save_school_account_password_to_ini = Mock()
    api._fetch_server_attendance_radius_if_needed = Mock()
    api._get_full_user_info_dict = Mock(return_value={"student_id": "10001"})
    api._ensure_account_refresh_thread = Mock()
    api.get_notifications = Mock(return_value={"success": False})
    api.stop_auto_refresh = threading.Event()
    api.server_attendance_radius_m = 30
    api.config_path = "unused"
    verified_client = SimpleNamespace(
        session=SimpleNamespace(close=Mock()),
        login=Mock(return_value={"success": True, "data": {"userInfo": {"id": "test-id"}}}),
    )
    monkeypatch.setattr(runtime, "ApiClient", lambda owner: verified_client)
    runtime._normalize_gender_value = lambda value: ""
    runtime._read_config_ini = lambda *args: object()
    runtime._build_public_map_provider_frontend_payload = lambda *args, **kwargs: {
        "map_provider": "amap", "map_providers": {}, "map_provider_key_bundle": {},
    }
    update_binding = Mock(wraps=api._update_school_account_password)
    monkeypatch.setattr(api, "_update_school_account_password", update_binding)

    response = api.login("10001", "verified-password")

    assert response["success"] is True
    api._save_config.assert_called_once_with(
        "10001", "verified-password", "parent-UA", update_owner_binding=False
    )
    api._save_school_account_password_to_ini.assert_not_called()
    update_binding.assert_called_once_with(
        "test-owner", "10001", "verified-password", "parent-UA", login_verified=True
    )
    assert get_owner_bindings(harness) == {
        "10001": {"password": "verified-password", "ua": "parent-UA"},
    }


@pytest.mark.parametrize("update_owner_binding", [None, False])
def test_save_config_owner_binding_option_preserves_other_callers(
    owner_binding_store, runtime, update_owner_binding
):
    harness = owner_binding_store
    api = harness.api
    api.user_dir = runtime.SCHOOL_ACCOUNTS_DIR
    api.is_multi_account_mode = False
    api.params = {}
    api.config_path = str(harness.store.database.settings.root / "config.ini")
    runtime._read_config_ini = lambda *args: api_runtime.configparser.RawConfigParser()
    runtime._write_config_with_comments = Mock()
    runtime.auth_system.update_user_last_school_account = Mock()
    put_owner_bindings(harness, {"10001": {"password": "verified-password", "ua": ""}})

    kwargs = {} if update_owner_binding is None else {"update_owner_binding": update_owner_binding}
    api_runtime.Api._save_config(api, "10001", "unverified-password", "new-UA", **kwargs)

    expected_ua = "new-UA" if update_owner_binding is None else ""
    assert get_owner_bindings(harness) == {
        "10001": {"password": "verified-password", "ua": expected_ua},
    }


def test_restored_generated_ua_is_saved_without_changing_account_password(owner_binding_store, runtime, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    api.auth_username = "test-owner"
    api.all_run_data = []
    api.current_run_idx = -1
    api._multi_refresh_worker = Mock()
    put_owner_bindings(harness, {"10001": {"password": "verified-password", "ua": None}})
    monkeypatch.setattr(session_state, "_main", lambda: runtime)
    monkeypatch.setattr(session_state, "threading", SimpleNamespace(Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)))
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(lambda: "recovered-account-UA"))

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True, "multi_account_states": {"10001": {}},
    })

    assert api.accounts["10001"].device_ua == "recovered-account-UA"
    assert get_owner_bindings(harness) == {
        "10001": {"password": "verified-password", "ua": "recovered-account-UA"},
    }
