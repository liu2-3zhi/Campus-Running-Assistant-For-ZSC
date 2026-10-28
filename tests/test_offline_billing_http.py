"""Exercise the production billing handlers with isolated authenticated sessions."""

import ast
import configparser
import json
import logging
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g, jsonify, request

import api_runtime
import main as main_module
from api_runtime import Api


@pytest.fixture
def billing_http(tmp_path):
    app = Flask(__name__)
    api = SimpleNamespace(
        is_authenticated=True,
        auth_username="test-administrator",
        is_offline_mode=False,
        _load_user_school_accounts=Mock(return_value={"10001": {}, "10002": {}}),
    )
    auth = SimpleNamespace(
        get_user_group=Mock(return_value="super_admin"),
        check_permission=Mock(return_value=True),
        get_available_runs=Mock(return_value=0),
        permissions={},
    )
    config = configparser.ConfigParser()
    config["Payment_Settings"] = {"require_payment": "true"}
    runtime = SimpleNamespace(
        g=g, request=request, jsonify=jsonify, auth_system=auth,
        _read_config_ini=Mock(return_value=config),
        _count_pending_bills_for_school=Mock(return_value=1),
        SCHOOL_ACCOUNTS_DIR=str(tmp_path / "accounts"),
        _migrate_billing_record_beijing_times=main_module._migrate_billing_record_beijing_times,
        _migrate_billing_file_beijing_times=Mock(side_effect=AssertionError("GET must not rewrite bills")),
        is_valid_school_username=main_module.is_valid_school_username,
    )
    web_sessions = {"offline-target": api}
    runtime.web_sessions = web_sessions
    runtime.web_sessions_lock = threading.Lock()

    def authenticated(view):
        def handler(*args, **kwargs):
            target_session_id = request.headers.get("X-Session-ID")
            source_session_id = request.headers.get("X-Admin-Origin-Session-ID")
            g.user = "test-administrator"
            g.api_instance = api
            if source_session_id and source_session_id != target_session_id:
                g.session_id = source_session_id
                g.viewed_session_id = target_session_id
            else:
                g.session_id = target_session_id or "admin-origin"
                g.viewed_session_id = None
            return view(*args, **kwargs)
        handler.__name__ = view.__name__
        return handler

    source = Path(api_runtime.__file__).with_name("web_server.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {
        "_resolve_business_billing_context", "check_overdue", "billing_list",
        "admin_billing_list", "admin_removed_account_detail",
    }
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = {
        "app": app, "login_required": authenticated, "admin_required": authenticated,
        "_main": lambda: runtime, "os": os, "json": json, "logging": logging,
        "web_sessions": web_sessions, "web_sessions_lock": runtime.web_sessions_lock,
        "__file__": str(tmp_path / "web_server.py"),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    root = tmp_path / "User_Billing" / "School_Bills"
    originals = {}
    for school in ("10001", "10002", "10003"):
        path = root / school / "old-bill.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "billing_id": f"bill-{school}", "school_username": school,
            "status": "pending", "amount": 1, "created_at": "2026-10-01 00:00:00",
        }), encoding="utf-8")
        originals[path] = (path.read_bytes(), path.stat().st_mtime_ns)
    removed = tmp_path / "Remove_Acoount"
    removed.mkdir()
    (removed / "_index.json").write_text(json.dumps({"removed_accounts": {
        "deleted-test": {"backup_file": "test-backup.json"},
    }}), encoding="utf-8")
    (removed / "test-backup.json").write_text(json.dumps({
        "school_accounts": {"10001": {}},
    }), encoding="utf-8")
    return app.test_client(), api, runtime, originals


def test_verified_offline_context_never_reads_account_or_bill_data(billing_http):
    client, api, runtime, _ = billing_http
    api.is_offline_mode = True
    response = client.post("/api/check_overdue", json={"school_username": "NULL"}, headers={
        "X-Session-ID": "offline-target", "X-Admin-Origin-Session-ID": "admin-origin",
    })
    assert response.status_code == 200
    assert response.json["has_overdue"] is False
    assert response.json["overdue_accounts"] == []
    api._load_user_school_accounts.assert_not_called()
    runtime._count_pending_bills_for_school.assert_not_called()


def test_admin_source_online_target_offline_short_circuits_billing(billing_http):
    client, source_api, runtime, _ = billing_http
    target_api = SimpleNamespace(
        is_authenticated=True, auth_username="target-user", is_offline_mode=True,
        _load_user_school_accounts=Mock(return_value={"10003": {}}),
    )
    runtime.web_sessions["business-target"] = target_api
    headers = {
        "X-Session-ID": "business-target",
        "X-Admin-Origin-Session-ID": "admin-origin",
    }

    overdue = client.post("/api/check_overdue", json={}, headers=headers)
    bills = client.get("/api/billing/list", headers=headers)

    assert overdue.status_code == 200 and overdue.json["is_offline_mode"] is True
    assert overdue.json["overdue_accounts"] == []
    assert bills.status_code == 200 and bills.json["is_offline_mode"] is True
    assert bills.json["records"] == []
    source_api._load_user_school_accounts.assert_not_called()
    target_api._load_user_school_accounts.assert_not_called()
    runtime._count_pending_bills_for_school.assert_not_called()


def test_admin_source_uses_target_online_account_scope_for_overdue_and_bills(billing_http):
    client, source_api, runtime, _ = billing_http
    target_api = SimpleNamespace(
        is_authenticated=True, auth_username="target-user", is_offline_mode=False,
        _load_user_school_accounts=Mock(return_value={"10003": {}}),
    )
    runtime.web_sessions["business-target"] = target_api
    headers = {
        "X-Session-ID": "business-target",
        "X-Admin-Origin-Session-ID": "admin-origin",
    }

    overdue = client.post("/api/check_overdue", json={}, headers=headers)
    bills = client.get("/api/billing/list", headers=headers)

    assert [row["username"] for row in overdue.json["overdue_accounts"]] == ["10003"]
    assert [row["school_username"] for row in bills.json["records"]] == ["10003"]
    source_api._load_user_school_accounts.assert_not_called()
    assert target_api._load_user_school_accounts.call_count == 2
    assert all(args == ("target-user",) for args, _ in target_api._load_user_school_accounts.call_args_list)
    runtime._count_pending_bills_for_school.assert_called_once_with("10003")


@pytest.mark.parametrize("scope", [
    {"school_username": "NULL"}, {"school_username": "undefined"},
    {"school_username": ""}, {"school_usernames": []},
    {"school_usernames": ["NULL", ""]}, {"school_username": None},
])
def test_explicit_empty_scope_never_expands_to_all_accounts(billing_http, scope):
    client, api, runtime, _ = billing_http
    response = client.post("/api/check_overdue", json=scope)
    assert response.status_code == 200
    assert response.json["overdue_accounts"] == []
    api._load_user_school_accounts.assert_not_called()
    runtime._count_pending_bills_for_school.assert_not_called()


def test_absent_scope_preserves_authorized_query_and_valid_scope_is_limited(billing_http):
    client, api, runtime, _ = billing_http
    assert len(client.post("/api/check_overdue", json={}).json["overdue_accounts"]) == 2
    runtime._count_pending_bills_for_school.reset_mock()
    response = client.post("/api/check_overdue", json={"school_usernames": ["10002", "10003"]})
    assert [r["username"] for r in response.json["overdue_accounts"]] == ["10002"]
    runtime._count_pending_bills_for_school.assert_called_once_with("10002")


def test_empty_json_array_is_not_an_unrestricted_query(billing_http):
    client, api, runtime, _ = billing_http
    assert client.post("/api/check_overdue", json=[]).status_code == 400
    api._load_user_school_accounts.assert_not_called()
    runtime._count_pending_bills_for_school.assert_not_called()


def test_ordinary_account_query_cannot_escape_authorized_scope(billing_http):
    client, api, runtime, _ = billing_http
    runtime.auth_system.get_user_group.return_value = "user"
    api._load_user_school_accounts.return_value = {"10001": {}}
    response = client.post("/api/check_overdue", json={"school_usernames": ["10002", "10003"]})
    assert response.status_code == 200
    assert response.json["overdue_accounts"] == []
    runtime._count_pending_bills_for_school.assert_not_called()


@pytest.mark.parametrize("query,expected", [
    ("?school_usernames=10002&school_usernames=10003", ["10002"]),
    ("?school_usernames=NULL", []), ("?school_username=", []),
    ("?school_username=10001", ["10001"]), ("", ["10001", "10002"]),
])
def test_bill_list_scope_is_filtered_by_server_permissions(billing_http, query, expected):
    client, _, _, _ = billing_http
    response = client.get("/api/billing/list" + query)
    assert response.status_code == 200
    assert sorted(r["school_username"] for r in response.json["records"]) == expected


@pytest.mark.parametrize("url", ["/api/billing/list", "/api/admin/billing/list"])
def test_bill_get_fills_display_times_without_rewriting_existing_files(billing_http, url):
    client, _, runtime, originals = billing_http
    response = client.get(url)
    assert response.status_code == 200
    assert all(r["created_at_beijing"] for r in response.json["records"])
    runtime._migrate_billing_file_beijing_times.assert_not_called()
    for path, (content, modified) in originals.items():
        assert path.read_bytes() == content
        assert path.stat().st_mtime_ns == modified


def test_removed_account_bill_display_is_also_read_only(billing_http):
    client, _, runtime, originals = billing_http
    response = client.get("/api/admin/removed_account_detail?auth_username=deleted-test")
    assert response.status_code == 200
    runtime._migrate_billing_file_beijing_times.assert_not_called()
    for path, (content, modified) in originals.items():
        assert path.read_bytes() == content
        assert path.stat().st_mtime_ns == modified


def make_login_runtime():
    api = Api.__new__(Api)
    api.is_offline_mode = True
    api.is_multi_account_mode = False
    api.user_data = main_module.UserData()
    api.user_data.username = "offline"
    api.user_data.student_id = "NULL"
    api.all_run_data = [object()]
    api.current_run_idx = 0
    api.device_ua = "test-ua"
    api._web_session_id = "test-session"
    api.stop_run_flag = threading.Event()
    api.stop_run_flag.set()
    api.single_execution_lock = threading.Lock()
    api.api_client = SimpleNamespace(session=SimpleNamespace(close=Mock()))
    api.accounts = {}
    api.log_and_notify_frontend = Mock()
    api._persist_school_account_backup = Mock()
    api._save_config = Mock()
    api._save_school_account_password_to_ini = Mock()
    api._fetch_server_attendance_radius_if_needed = Mock()
    api._get_full_user_info_dict = Mock(return_value={"student_id": "10001"})
    api._ensure_account_refresh_thread = Mock()
    api.get_notifications = Mock(return_value={"success": False})
    api.stop_auto_refresh = threading.Event()
    api.server_attendance_radius_m = 30
    api.target_range_m = 30
    api.config_path = "unused"
    api.global_params = {}
    api.window = None
    return api


def patch_login_services(monkeypatch, api, response):
    client = SimpleNamespace(session=SimpleNamespace(close=Mock()), app=None)
    def factory(owner):
        client.app = owner
        def verify(*_args):
            assert owner.is_offline_mode is False
            assert api.is_offline_mode is True
            return response
        client.login = Mock(side_effect=verify)
        return client
    monkeypatch.setattr(main_module, "ApiClient", factory)
    monkeypatch.setattr(main_module, "background_task_manager", None, raising=False)
    monkeypatch.setattr(main_module, "_read_config_ini", lambda *_a: main_module._get_default_config())
    monkeypatch.setattr(main_module, "_build_public_map_provider_frontend_payload", lambda *_a, **_k: {
        "map_provider": "amap", "map_providers": {}, "map_provider_key_bundle": {},
    })
    return client


def test_failed_online_login_keeps_offline_identity_tasks_and_network_gate(monkeypatch):
    api = make_login_runtime()
    original = (api.user_data, api.all_run_data, api.api_client, api.device_ua)
    verification = patch_login_services(monkeypatch, api, {"success": False, "message": "denied"})
    response = api.login("10001", "not-a-real-password")
    assert response["success"] is False
    assert (api.user_data, api.all_run_data, api.api_client, api.device_ua) == original
    assert api.is_offline_mode is True
    verification.session.close.assert_called_once()
    api._save_config.assert_not_called()


def test_verified_online_login_commits_new_client_and_clears_offline_tasks(monkeypatch):
    api = make_login_runtime()
    old_client = api.api_client
    verification = patch_login_services(monkeypatch, api, {
        "success": True, "data": {"userInfo": {"id": "test-id"}, "deptInfo": {}},
    })
    response = api.login("10001", "not-a-real-password")
    assert response["success"] is True
    assert response["is_offline_mode"] is False
    assert api.is_offline_mode is False
    assert api.api_client is verification and verification.app is api
    assert api.all_run_data == [] and api.current_run_idx == -1
    old_client.session.close.assert_called_once()


@pytest.mark.parametrize("operation", ["login", "import", "multi", "single", "exit_multi"])
def test_running_task_refuses_mode_changes_without_stopping_it(monkeypatch, operation):
    api = make_login_runtime()
    api.stop_run_flag.clear()
    manager = SimpleNamespace(lock=threading.Lock(), tasks={
        api._web_session_id: {"status": "running"}, "another-session": {"status": "running"},
    }, stop_task=Mock())
    monkeypatch.setattr(main_module, "background_task_manager", manager, raising=False)
    before = (api.user_data, api.all_run_data, api.is_offline_mode)
    calls = {
        "login": lambda: api.login("10001", "not-a-real-password"),
        "import": lambda: api.import_task_data({"task_name": "offline-test"}),
        "multi": api.enter_multi_account_mode, "single": api.enter_single_account_mode,
        "exit_multi": api.exit_multi_account_mode,
    }
    result = calls[operation]()
    assert result["success"] is False
    assert (api.user_data, api.all_run_data, api.is_offline_mode) == before
    manager.stop_task.assert_not_called()
    assert not api.stop_run_flag.is_set()


@pytest.mark.parametrize("offline", [False, True])
def test_initial_data_error_does_not_change_execution_mode(tmp_path, offline):
    api = make_login_runtime()
    api.user_dir = str(tmp_path / "missing")
    api.is_offline_mode = offline
    response = api.get_initial_data()
    assert response["success"] is False
    assert api.is_offline_mode is offline
    assert response["is_offline_mode"] is offline


@pytest.mark.parametrize("offline", [False, True])
def test_initial_data_and_import_expose_execution_mode(tmp_path, monkeypatch, offline):
    api = make_login_runtime()
    api.user_dir = str(tmp_path)
    api.is_offline_mode = offline
    api.is_guest = True
    api.auth_group = "guest"
    api.auth_username = None
    api._load_global_config = Mock()
    monkeypatch.setattr(main_module, "_read_config_ini", lambda *_a: main_module._get_default_config())
    monkeypatch.setattr(main_module, "background_task_manager", None, raising=False)
    monkeypatch.setattr(main_module, "auth_system", SimpleNamespace(
        get_theme_config=lambda *_a, **_k: {}, get_available_theme_styles=lambda: [],
    ), raising=False)
    monkeypatch.setattr(main_module, "_apply_identity_bundle_to_theme_config", lambda theme, *_a: theme)
    monkeypatch.setattr(main_module, "_build_public_map_provider_frontend_payload", lambda *_a, **_k: {
        "map_provider": "amap", "map_providers": {}, "map_provider_key_bundle": {},
    })
    response = api.get_initial_data()
    assert response["success"] is True
    assert response["is_offline_mode"] is offline
    result = api.import_task_data({"task_name": "isolated-offline-test"})
    assert result["success"] is True
    assert result["is_offline_mode"] is True
    assert api.is_offline_mode is True


@pytest.mark.parametrize("response", [[], ["invalid"], {"success": True, "data": []}])
def test_invalid_login_response_preserves_offline_state(monkeypatch, response):
    api = make_login_runtime()
    original = (api.user_data, api.all_run_data, api.api_client)
    verification = patch_login_services(monkeypatch, api, response)
    assert api.login("10001", "not-a-real-password")["success"] is False
    assert (api.user_data, api.all_run_data, api.api_client) == original
    assert api.is_offline_mode is True
    verification.session.close.assert_called_once()


def test_invalid_offline_import_preserves_online_identity_and_tasks(monkeypatch):
    api = make_login_runtime()
    api.is_offline_mode = False
    original = (api.user_data, api.all_run_data, api.current_run_idx)
    monkeypatch.setattr(main_module, "background_task_manager", None, raising=False)
    result = api.import_task_data({"task_name": "invalid", "run_coords (gps)": [[1], [2]]})
    assert result["success"] is False
    assert api.is_offline_mode is False
    assert (api.user_data, api.all_run_data, api.current_run_idx) == original


def test_idle_offline_to_multi_discards_only_offline_single_account_state(monkeypatch):
    api = make_login_runtime()
    account = SimpleNamespace(username="10002", worker_thread=None,
                              user_data=SimpleNamespace(name="test", id=None), status_text="idle", summary="", params={})
    api.accounts = {"10002": account}
    api.user_info = {"student_id": "NULL"}
    api.login_success = True
    api.path_gen_callbacks = {}
    api._update_multi_global_buttons = Mock()
    api.stop_multi_auto_refresh = threading.Event()
    api.stop_account_monitor = threading.Event()
    api.account_monitor_thread = SimpleNamespace(is_alive=lambda: True)
    monkeypatch.setattr(main_module, "background_task_manager", None, raising=False)
    monkeypatch.setattr(main_module, "socketio", None, raising=False)
    monkeypatch.setattr(main_module, "save_session_state", Mock())
    result = api.enter_multi_account_mode()
    assert result["success"] is True
    assert result["is_offline_mode"] is False
    assert api.is_offline_mode is False and api.is_multi_account_mode is True
    assert api.all_run_data == [] and api.current_run_idx == -1
    assert not api.user_info and not api.login_success
    assert api.accounts == {"10002": account}


def test_background_work_in_other_session_does_not_block_login(monkeypatch):
    api = make_login_runtime()
    monkeypatch.setattr(main_module, "background_task_manager", SimpleNamespace(
        lock=threading.Lock(), tasks={"unrelated-session": {"status": "running"}},
    ), raising=False)
    assert api._execution_blocks_mode_change() is False


def test_login_started_during_verification_is_not_committed(monkeypatch):
    api = make_login_runtime()
    original = (api.user_data, api.all_run_data, api.api_client)
    client = patch_login_services(monkeypatch, api, {"success": True, "data": {}})
    def concurrent_execution(*_args):
        api.stop_run_flag.clear()
        return {"success": True, "data": {}}
    client_factory = main_module.ApiClient
    def factory(owner):
        created = client_factory(owner)
        created.login = Mock(side_effect=concurrent_execution)
        return created
    monkeypatch.setattr(main_module, "ApiClient", factory)
    assert api.login("10001", "not-a-real-password")["success"] is False
    assert (api.user_data, api.all_run_data, api.api_client) == original
    assert api.is_offline_mode is True
