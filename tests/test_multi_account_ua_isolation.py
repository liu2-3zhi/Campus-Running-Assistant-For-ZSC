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
def test_password_update_with_missing_ua_preserves_saved_account_identity(runtime, missing_ua):
    api = account_bridge()
    accounts = {"10001": {"password": "old", "ua": "saved-account-UA", "completed_count": 7}}
    api._load_user_school_accounts = Mock(return_value=accounts)
    saved = []
    api._save_user_school_accounts = lambda owner, data: saved.append(data)

    api._update_school_account_password("test-owner", "10001", "new", ua=missing_ua, login_verified=True)

    assert saved[0]["10001"]["ua"] == "saved-account-UA"
    assert saved[0]["10001"]["password"] == "new"
    assert saved[0]["10001"]["completed_count"] == 7


def test_legacy_password_entry_is_upgraded_with_ua_without_losing_password(runtime):
    api = account_bridge()
    api._load_user_school_accounts = Mock(return_value={"10001": "old"})
    saved = []
    api._save_user_school_accounts = lambda owner, data: saved.append(data)

    api._update_school_account_password("test-owner", "10001", "new", ua="new-UA", login_verified=True)

    assert saved[0]["10001"] == {"password": "new", "ua": "new-UA"}


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


def test_unverified_password_update_only_fills_missing_ua(runtime):
    api = account_bridge()
    accounts = {"10001": {"password": "verified-password", "ua": ""}}
    api._load_user_school_accounts = lambda owner: accounts
    saved = []
    api._save_user_school_accounts = lambda owner, data: saved.append(data)

    api._update_school_account_password("test-owner", "10001", "unverified-password", ua="recovered-UA")

    assert saved == [{"10001": {"password": "verified-password", "ua": "recovered-UA"}}]
    api._update_school_account_password("test-owner", "10001", "unverified-password", ua="different-UA")
    assert accounts["10001"] == {"password": "verified-password", "ua": "recovered-UA"}
    assert len(saved) == 1


def test_restored_generated_ua_is_saved_without_changing_account_password(runtime, monkeypatch):
    api = account_bridge()
    api.auth_username = "test-owner"
    api.all_run_data = []
    api.current_run_idx = -1
    api._multi_refresh_worker = Mock()
    stored = {"10001": {"password": "verified-password", "ua": None}}
    api._load_user_school_accounts = lambda owner: stored
    saved = []
    api._save_user_school_accounts = lambda owner, data: saved.append(data)
    monkeypatch.setattr(session_state, "_main", lambda: runtime)
    monkeypatch.setattr(session_state, "threading", SimpleNamespace(Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)))
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(lambda: "recovered-account-UA"))

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True, "multi_account_states": {"10001": {}},
    })

    assert api.accounts["10001"].device_ua == "recovered-account-UA"
    assert saved == [{"10001": {"password": "verified-password", "ua": "recovered-account-UA"}}]
