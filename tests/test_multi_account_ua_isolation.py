"""Account UA survives loading, relogin and concurrent request construction."""

import itertools
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
from persistence.validation import _storage_alias
from test_relational_mysql import relational_mysql


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
        chardet=None,
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
def owner_binding_store(runtime, tmp_path, monkeypatch, request):
    root = tmp_path / "app"
    if getattr(request, "param", "sqlite") == "mysql":
        store = request.getfixturevalue("relational_mysql")
    else:
        store = RelationalStore(DatabaseSettings(root=root, sqlite_path=":memory:"))
        store.init_schema(ready=True)
    backend = business_storage.StorageRuntime(
        store.settings.backend, business_storage.StoragePolicy(root, {}), store
    )
    monkeypatch.setattr(storage_io, "get_runtime", lambda *paths: backend)
    runtime.SCHOOL_ACCOUNTS_DIR = str(root / "school_accounts")
    runtime._auth_username_storage_key = _storage_alias
    runtime.auth_system = SimpleNamespace(
        check_permission=Mock(return_value=False), get_user_group=Mock(return_value="user")
    )
    api = account_bridge(root)
    api.auth_username = "test-owner"
    owner_key = runtime._auth_username_storage_key(api.auth_username)
    store.put("system_accounts", owner_key + ".json", json.dumps({"auth_username": api.auth_username}).encode())
    binding_key = "user_accounts/" + owner_key + ".json"
    yield SimpleNamespace(store=store, api=api, binding_key=binding_key)
    if store.settings.backend == "sqlite":
        store.database.dispose()


def put_owner_bindings(harness, values):
    harness.store.put("school_accounts", harness.binding_key,
                      json.dumps(values, ensure_ascii=False, indent=2).encode())


def get_owner_bindings(harness):
    document = harness.store.get("school_accounts", harness.binding_key)
    return json.loads(document.content.decode())


@pytest.mark.parametrize("owner_binding_store", ["sqlite", "mysql"], indirect=True)
def test_multi_add_replaces_apple_ua_without_saving_unverified_password(owner_binding_store, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    sibling = {"password": "other-password", "ua": "Android sibling UA"}
    put_owner_bindings(harness, {
        "10001": {"password": "verified-password", "device_ua": "Mozilla/5.0 (iPhone)", "tag": "keep"},
        "10002": sibling,
    })
    replacement = "Mozilla/5.0 (Linux; Android 16; target)"
    generate = Mock(return_value=replacement)
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", generate)

    def assert_repaired_before_login(account, _username):
        assert get_owner_bindings(harness)[account.username]["device_ua"] == replacement

    api._reset_account_session_for_relogin.side_effect = assert_repaired_before_login

    assert api.multi_add_account("10001", "unverified-password")["success"]
    account = api.accounts["10001"]
    assert account.api_client._get_headers()["User-Agent"] == replacement + api_client.ApiClient.UA_SUFFIX
    assert account.password == "unverified-password"
    assert get_owner_bindings(harness) == {
        "10001": {"password": "verified-password", "device_ua": replacement, "tag": "keep"},
        "10002": sibling,
    }
    generate.assert_called_once_with()


def test_account_selection_repairs_apple_ua_for_only_the_selected_school(owner_binding_store, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    api.is_authenticated = True
    api.auth_group = "user"
    api.params = {}
    api.user_data = SimpleNamespace(name="", student_id="")
    first = {"password": "one", "ua": "Mozilla/5.0 (iPhone)"}
    second = {"password": "two", "ua": "Mozilla/5.0 (iPad)"}
    put_owner_bindings(harness, {"10001": first, "10002": second})
    replacement = "Mozilla/5.0 (Linux; Android 16; target)"
    generate = Mock(return_value=replacement)
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", generate)

    assert api.on_user_selected("10001")["ua"] == replacement
    assert api.on_user_selected("10001")["ua"] == replacement
    assert get_owner_bindings(harness) == {"10001": {**first, "ua": replacement}, "10002": second}
    assert api.device_ua == "parent-UA"
    generate.assert_called_once_with()


def test_live_multi_request_repairs_saved_apple_ua(owner_binding_store, runtime, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    old_ua = "Mozilla/5.0 (iPhone)"
    put_owner_bindings(harness, {"10001": {"password": "verified-password", "ua": old_ua}})
    account = runtime.AccountSession("10001", "in-memory-password", api)
    account.device_ua = old_ua
    replacement = "Mozilla/5.0 (Linux; Android 16; target)"
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", Mock(return_value=replacement))

    assert account.api_client._get_headers()["User-Agent"] == replacement + api_client.ApiClient.UA_SUFFIX
    assert get_owner_bindings(harness) == {"10001": {"password": "verified-password", "ua": replacement}}


def test_single_login_repairs_apple_ua_before_verification(owner_binding_store, runtime, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    api._execution_blocks_mode_change = Mock(return_value=False)
    sibling = {"password": "other-password", "ua": "Android other-device"}
    put_owner_bindings(harness, {
        "10001": {"password": "verified-password", "ua": "iPhone outdated-device"},
        "10002": sibling,
    })
    replacement = "Mozilla/5.0 (Linux; Android 16; target)"
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", Mock(return_value=replacement))

    def verify(username, password):
        assert (username, password) == ("10001", "unverified-password")
        assert get_owner_bindings(harness)[username] == {"password": "verified-password", "ua": replacement}
        assert verification.app.device_ua == replacement
        return {"success": False, "message": "fixture rejection"}

    verification = SimpleNamespace(session=SimpleNamespace(close=Mock()), login=verify)

    def verification_factory(owner):
        verification.app = owner
        return verification

    verification_factory.generate_random_ua = api_client.ApiClient.generate_random_ua
    monkeypatch.setattr(runtime, "ApiClient", verification_factory)

    result = api.login("10001", "unverified-password")
    assert result["message"] == "fixture rejection"
    assert get_owner_bindings(harness) == {
        "10001": {"password": "verified-password", "ua": replacement}, "10002": sibling,
    }
    assert api.device_ua == "parent-UA"


def test_explicit_password_keeps_each_accounts_saved_ua(owner_binding_store):
    harness = owner_binding_store
    api = harness.api
    put_owner_bindings(harness, {
        "10001": {"password": "old-password", "ua": "Android account-A"},
        "10002": {"password": "old-password", "ua": "Android account-B"},
    })
    api._load_accounts_by_permission = Mock(side_effect=AssertionError("must not aggregate school accounts"))
    api._load_user_school_accounts = Mock(side_effect=AssertionError("must not aggregate owner bindings"))
    api._save_user_school_accounts = Mock(side_effect=AssertionError("must not bulk-save owner bindings"))
    for username in ("10001", "10002"):
        assert api.multi_add_account(username, "explicit-password")["success"]

    first, second = api.accounts.values()
    assert first.device_ua == "Android account-A"
    assert second.device_ua == "Android account-B"
    assert first.password == second.password == "explicit-password"
    assert first.api_client.app is first
    assert second.api_client.app is second
    assert first.api_client.session is not second.api_client.session
    api.device_ua = "changed-parent-UA"
    assert first.api_client._get_headers()["User-Agent"] == "Android account-A" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["User-Agent"] == "Android account-B" + api_client.ApiClient.UA_SUFFIX
    assert first.api_client._get_headers()["platform"] == "android"
    assert second.api_client._get_headers()["platform"] == "android"
    assert get_owner_bindings(harness) == {
        "10001": {"password": "old-password", "ua": "Android account-A"},
        "10002": {"password": "old-password", "ua": "Android account-B"},
    }
    api._load_accounts_by_permission.assert_not_called()
    api._load_user_school_accounts.assert_not_called()
    api._save_user_school_accounts.assert_not_called()


def configure_multi_storage_runtime(harness, runtime):
    api = harness.api
    api.user_dir = runtime.SCHOOL_ACCOUNTS_DIR
    api.is_multi_account_mode = True
    api.params = {}
    api.config_path = str(harness.store.database.settings.root / "config.ini")
    api._save_config = api_runtime.Api._save_config.__get__(api)
    api._persist_school_account_backup = Mock()
    api._update_account_status_js = Mock()
    api._multi_fetch_and_summarize_tasks = Mock(return_value=False)
    runtime._read_config_ini = lambda *args: api_runtime.configparser.RawConfigParser()
    runtime._write_config_with_comments = Mock()
    runtime._normalize_gender_value = lambda value: ""
    runtime.auth_system.update_user_last_school_account = Mock()
    runtime.auth_system.get_user_group = Mock(return_value="super_admin")


@pytest.mark.parametrize("is_admin", [True, False])
def test_new_multi_account_uses_target_credentials_and_binds_only_after_verification(
    owner_binding_store, runtime, monkeypatch, is_admin
):
    harness = owner_binding_store
    api = harness.api
    configure_multi_storage_runtime(harness, runtime)
    api._get_auth_user_and_check_admin.return_value = ("test-owner", is_admin)
    runtime.auth_system.check_permission.return_value = is_admin
    owned = {"10002": {"password": "owned-password", "ua": "Android owned-UA"}}
    shared = {
        "10001": {"password": "other-owner-password", "ua": "Android target-UA"},
        "10009": {"password": "unrelated-password", "ua": "unrelated-UA"},
    }
    put_owner_bindings(harness, owned)
    other_key = runtime._auth_username_storage_key("other-owner")
    harness.store.put("system_accounts", other_key + ".json", json.dumps({"auth_username": "other-owner"}).encode())
    shared_key = "user_accounts/" + other_key + ".json"
    harness.store.put("school_accounts", shared_key, json.dumps(shared).encode())
    harness.store.put("school_accounts", "10009.ini", b"[stats]\ncompleted_count=7\n")
    unrelated_document = harness.store.get("school_accounts", "10009.ini")
    api._load_accounts_by_permission = Mock(side_effect=AssertionError("must not aggregate school accounts"))
    api._load_user_school_accounts = Mock(side_effect=AssertionError("must not aggregate owner bindings"))
    api._save_user_school_accounts = Mock(side_effect=AssertionError("must not bulk-save owner bindings"))
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(lambda: "generated-target-UA"))
    read_document = Mock(wraps=harness.store.get)
    monkeypatch.setattr(harness.store, "get", read_document)

    result = api.multi_add_account("10001", "unverified-password")

    assert result["success"] is True
    account = api.accounts["10001"]
    expected_ua = "Android target-UA" if is_admin else "generated-target-UA"
    assert account.device_ua == expected_ua
    assert account.password == "unverified-password"
    assert get_owner_bindings(harness) == owned
    account_document = harness.store.get("school_accounts", "10001.ini")
    config = api_runtime.configparser.RawConfigParser()
    config.read_string(account_document.content.decode())
    assert not config.has_option("Config", "password")
    assert config.get("System", "ua") == expected_ua
    assert all(call.args != ("school_accounts", shared_key) for call in read_document.call_args_list)
    assert all(call.args != ("school_accounts", "10009.ini") for call in read_document.call_args_list)

    api._queued_login = Mock(return_value={"success": False, "message": "denied"})
    api._multi_refresh_worker_unlocked(account)
    assert get_owner_bindings(harness) == owned

    api._queued_login.return_value = {
        "success": True,
        "data": {"userInfo": {"id": "school-id", "account": "10001"}},
    }
    api._multi_refresh_worker_unlocked(account)

    assert get_owner_bindings(harness) == {
        **owned, "10001": {"password": "unverified-password", "ua": expected_ua},
    }
    assert json.loads(harness.store.get("school_accounts", shared_key).content) == shared
    assert harness.store.get("school_accounts", "10009.ini") == unrelated_document
    assert api.device_ua == "parent-UA"
    api._load_accounts_by_permission.assert_not_called()
    api._load_user_school_accounts.assert_not_called()
    api._save_user_school_accounts.assert_not_called()


@pytest.mark.parametrize("pending_password", [False, True])
@pytest.mark.parametrize("login_success", [False, True])
def test_multi_relogin_updates_existing_binding_only_after_verification(
    owner_binding_store, runtime, monkeypatch, pending_password, login_success
):
    harness = owner_binding_store
    api = harness.api
    configure_multi_storage_runtime(harness, runtime)
    owned = {"10001": {"password": "old-password", "ua": "Android target-UA"}}
    put_owner_bindings(harness, owned)
    api_runtime.Api._save_config(api, "10001", "old-password", "Android target-UA")
    account = runtime.AccountSession("10001", "old-password", api)
    account.device_ua = "Android target-UA"
    account.is_first_login_verified = True
    api.accounts[account.username] = account
    if pending_password:
        api._stage_pending_account_password(account, "verified-new-password")
    else:
        account.password = "verified-new-password"
    api._queued_login = Mock(return_value={
        "success": login_success, "message": "denied",
        "data": {"userInfo": {"id": "school-id", "account": "10001"}},
    })
    persist_document = Mock(wraps=harness.store.put)
    monkeypatch.setattr(harness.store, "put", persist_document)

    api._multi_refresh_worker_unlocked(account)

    assert get_owner_bindings(harness) == {
        "10001": {
            "password": "verified-new-password" if login_success else "old-password",
            "ua": "Android target-UA",
        },
    }
    written_keys = [call.args[:2] for call in persist_document.call_args_list]
    expected_keys = [
        ("school_accounts", "10001.ini"),
        ("school_accounts", harness.binding_key),
    ] if login_success else []
    assert written_keys == expected_keys


@pytest.mark.parametrize("lost_ua", [None, "", "  ", "null", "None", "undefined"])
def test_request_repairs_lost_ua_from_its_own_last_value(runtime, monkeypatch, lost_ua):
    api = account_bridge()
    first = runtime.AccountSession("10001", "test-password", api)
    second = runtime.AccountSession("10002", "test-password", api)
    first.device_ua, second.device_ua = "Android account-A", "Android account-B"
    assert first.api_client._get_headers()["User-Agent"].startswith("Android account-A")
    assert second.api_client._get_headers()["platform"] == "android"
    first.device_ua = lost_ua
    second.device_ua = lost_ua
    generator = Mock(return_value="unexpected-new-UA")
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", generator)

    assert first.api_client._get_headers()["User-Agent"] == "Android account-A" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["User-Agent"] == "Android account-B" + api_client.ApiClient.UA_SUFFIX
    assert second.api_client._get_headers()["platform"] == "android"
    assert first.device_ua == "Android account-A"
    assert second.device_ua == "Android account-B"
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
    for username, ua in (("10001", "Android account-A"), ("10002", "Android account-B")):
        acc = runtime.AccountSession(username, "test-password", api)
        acc.device_ua = ua
        acc.user_data.gender = "test"
        api.accounts[username] = acc

    result = api.multi_get_all_accounts_status()

    assert {row["username"]: row.get("device_ua") for row in result["accounts"]} == {
        "10001": "Android account-A", "10002": "Android account-B",
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


def test_session_restore_projects_only_the_requested_school_credentials(owner_binding_store, runtime, monkeypatch):
    harness = owner_binding_store
    api = harness.api
    api.all_run_data = []
    api.current_run_idx = -1
    api._multi_refresh_worker = Mock()
    bindings = {
        str(username): {"password": f"password-{username}", "ua": f"device-UA-{username}"}
        for username in range(10000, 10446)
    }
    put_owner_bindings(harness, bindings)
    live_account = runtime.AccountSession("10445", "live-password", api)
    api.accounts[live_account.username] = live_account
    aggregate = Mock(side_effect=AssertionError("session restore must not aggregate account bindings"))
    scan = Mock(side_effect=AssertionError("session restore must not scan unrelated storage records"))
    statistics = Mock(side_effect=AssertionError("session restore must not read school stats"))
    project = Mock(wraps=harness.store.get_school_account_credentials)
    persist = Mock(wraps=api._persist_missing_school_account_ua)
    monkeypatch.setattr(api, "_load_user_school_accounts", aggregate)
    monkeypatch.setattr(harness.store, "list", scan)
    monkeypatch.setattr(harness.store, "get_school_account_stats", statistics)
    monkeypatch.setattr(harness.store, "get_school_account_credentials", project)
    monkeypatch.setattr(api, "_persist_missing_school_account_ua", persist)
    monkeypatch.setattr(session_state, "_main", lambda: runtime)
    monkeypatch.setattr(session_state, "threading", SimpleNamespace(Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)))

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"10001": {}, "10445": {}},
    })

    aggregate.assert_not_called()
    scan.assert_not_called()
    statistics.assert_not_called()
    persist.assert_not_called()
    assert [call.args for call in project.call_args_list] == [("test-owner", "10001"), ("test-owner", "10445")]
    assert api.accounts["10001"].password == "password-10001"
    assert api.accounts["10001"].device_ua == "device-UA-10001"
    assert api.accounts["10445"] is live_account
    assert live_account.password == "live-password"
    assert live_account.device_ua == "device-UA-10445"
