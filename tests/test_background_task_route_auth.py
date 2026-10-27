import ast
import functools
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g, jsonify, request

import background_task_manager as background
import main
import route_failure_visibility as visibility
from guest_token_store import GuestTokenStore


ROOT = Path(__file__).resolve().parents[1]
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
C = "33333333-3333-4333-8333-333333333333"
ROUTES = (
    ("start_background_task", "start", "POST", "start_tasks"),
    ("get_background_task_status", "status", "GET", "view_tasks"),
    ("stop_background_task", "stop", "POST", "stop_tasks"),
)


def load_routes(runtime, manager, app):
    tree = ast.parse((ROOT / "web_server.py").read_text(encoding="utf-8"))
    server = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "start_web_server")
    functions = {node.name: node for node in server.body if isinstance(node, ast.FunctionDef)}
    namespace = {
        "_main": lambda: runtime, "web_sessions": runtime.web_sessions,
        "web_sessions_lock": runtime.web_sessions_lock,
        "background_task_manager": manager, "functools": functools,
        "logging": logging, "time": time,
    }
    for name in ("login_required", "_background_task_login_required", "_require_background_task_permission"):
        if name in functions:
            exec(compile(ast.Module(body=[functions[name]], type_ignores=[]),
                         str(ROOT / "web_server.py"), "exec"), namespace)
    for name, suffix, method, _permission in ROUTES:
        node = functions[name]
        # Keep the production authentication decorator and remove only registration.
        node.decorator_list = [decorator for decorator in node.decorator_list
                               if not (isinstance(decorator, ast.Call)
                                       and isinstance(decorator.func, ast.Attribute)
                                       and decorator.func.attr == "route")]
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     str(ROOT / "web_server.py"), "exec"), namespace)
        app.add_url_rule("/api/background_task/" + suffix, name, namespace[name], methods=[method])


@pytest.fixture
def harness(monkeypatch):
    def session(owner, group="user"):
        return SimpleNamespace(
            auth_username=owner, auth_group=group, is_authenticated=True, is_guest=False,
            is_multi_account_mode=False, is_offline_mode=True,
            stop_run_flag=threading.Event(), all_run_data=[],
        )

    sessions = {A: session("actor", "admin"), B: session("owner"), C: session("actor", "admin")}
    permissions = {}
    groups = {"actor": "admin", "owner": "user"}
    verify = Mock(side_effect=lambda _sid, owner, token: token == "token-" + owner)
    touch = Mock()
    runtime = SimpleNamespace(
        request=request, jsonify=jsonify, g=g, web_sessions=sessions,
        web_sessions_lock=threading.Lock(), normalize_session_uuid=main.normalize_session_uuid,
        ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
        _is_safe_auth_username=lambda username: bool(username),
        _verify_session_cookie_token=verify,
        resolve_admin_view_identity=Mock(return_value=None),
        token_manager=SimpleNamespace(
            verify_token=Mock(side_effect=lambda owner, sid, token: (verify(sid, owner, token), "valid")),
            create_token=Mock(), refresh_token=Mock(), invalidate_token=Mock(),
        ),
        auth_system=SimpleNamespace(
            check_permission=Mock(side_effect=lambda owner, permission: permissions.get((owner, permission), True)),
            get_user_group=Mock(side_effect=lambda owner: groups[owner]),
            get_account_cancellation_status=Mock(return_value=None),
        ),
        _read_config_ini=Mock(return_value=None),
    )
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    resolver = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "resolve_admin_origin_session_context")
    namespace = {
        "normalize_session_uuid": main.normalize_session_uuid,
        "web_sessions": sessions, "web_sessions_lock": runtime.web_sessions_lock,
        "token_manager": runtime.token_manager, "auth_system": runtime.auth_system,
        "touch_admin_view_origin_session": touch, "logging": logging,
    }
    exec(compile(ast.Module(body=[resolver], type_ignores=[]), str(ROOT / "main.py"), "exec"), namespace)
    runtime.resolve_admin_origin_session_context = Mock(wraps=namespace[resolver.name])
    manager = object.__new__(background.BackgroundTaskManager)
    manager.lock = threading.Lock()
    manager.tasks = {sid: {"status": "running", "error": "PRIVATE_REASON"} for sid in sessions}
    manager.route_failure_batches = {}
    for sid in sessions:
        batch = manager.begin_route_planning_batch(sid)
        manager.record_route_planning_failure(sid, {
            "diagnostic_id": "diagnostic-" + sid[0], "provider": "amap", "error": "PRIVATE_REASON",
        }, batch)
    manager.get_task_status = Mock(wraps=manager.get_task_status)
    manager.start_background_task = Mock(return_value={"success": True})
    manager.stop_task = Mock(return_value={"success": True})
    monkeypatch.setattr(background, "_main", lambda: runtime)
    monkeypatch.setattr(visibility, "_main", lambda: runtime)
    app = Flask(__name__)
    app.testing = True
    load_routes(runtime, manager, app)
    client = app.test_client()
    client.set_cookie("auth_token", "token-actor")
    return SimpleNamespace(runtime=runtime, manager=manager, client=client, sessions=sessions,
                           permissions=permissions, groups=groups, touch=touch)


def invoke(harness, route, *, target=B, origin=A, payload=None):
    _name, suffix, method, _permission = route
    headers = {"X-Session-ID": target}
    if origin is not None:
        headers["X-Admin-Origin-Session-ID"] = origin
    return harness.client.open("/api/background_task/" + suffix, method=method, headers=headers,
                               json=payload if payload is not None else {"task_indices": [0]})


def assert_no_business_or_token_changes(harness):
    harness.manager.get_task_status.assert_not_called()
    harness.manager.start_background_task.assert_not_called()
    harness.manager.stop_task.assert_not_called()
    assert all(not api.stop_run_flag.is_set() for api in harness.sessions.values())
    for name in ("create_token", "refresh_token", "invalidate_token"):
        getattr(harness.runtime.token_manager, name).assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("failure", ("missing_token", "invalid_token", "malformed_origin", "revoked_origin"))
def test_unverified_or_revoked_actor_cannot_read_start_or_stop(harness, route, failure):
    origin = A
    if failure == "missing_token":
        harness.client.delete_cookie("auth_token")
    elif failure == "invalid_token":
        harness.client.set_cookie("auth_token", "invalid")
    elif failure == "malformed_origin":
        origin = "invalid"
    else:
        harness.permissions[("actor", "view_all_sessions")] = False
    response = invoke(harness, route, origin=origin)
    assert response.status_code == 401
    assert response.json["need_login"] is True
    assert response.headers.getlist("Set-Cookie") == []
    assert_no_business_or_token_changes(harness)
    harness.runtime.resolve_admin_view_identity.assert_not_called()
    harness.touch.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_owner_cookie_cannot_bypass_invalid_explicit_source(harness, route):
    harness.runtime.token_manager.verify_token.side_effect = lambda _owner, sid, _token: (sid != A, "token_expired")
    response = invoke(harness, route, target=C)
    assert response.status_code == 401
    assert_no_business_or_token_changes(harness)
    harness.runtime.resolve_admin_view_identity.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("lookup_error", (False, True))
def test_permissions_use_actual_actor_and_fail_closed(harness, route, lookup_error):
    harness.sessions[B].auth_group = "super_admin"
    harness.groups["owner"] = "super_admin"
    permission = route[3]
    if lookup_error:
        def check(owner, name):
            if name == permission:
                raise RuntimeError("permission store unavailable")
            return True
        harness.runtime.auth_system.check_permission.side_effect = check
    else:
        harness.permissions[("actor", permission)] = False
    response = invoke(harness, route)
    assert response.status_code == 403
    assert_no_business_or_token_changes(harness)
    assert ("actor", permission) in [call.args for call in harness.runtime.auth_system.check_permission.call_args_list]
    assert all(call.args[0] == "actor" for call in harness.runtime.auth_system.check_permission.call_args_list)


@pytest.mark.parametrize("route", ROUTES)
def test_verified_chain_targets_c_without_rotating_tokens_or_touching_b(harness, route):
    response = invoke(harness, route, target=C)
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.headers.getlist("Set-Cookie") == []
    assert not harness.sessions[A].stop_run_flag.is_set()
    assert not harness.sessions[B].stop_run_flag.is_set()
    assert all(call.args[0] == "actor" for call in harness.runtime.auth_system.check_permission.call_args_list)
    assert harness.touch.call_args.args == (A,)
    if route[1] == "start":
        harness.manager.start_background_task.assert_called_once_with(
            C, harness.sessions[C], [0], False, bypass_overdue=False, waive_charge=False)
    elif route[1] == "status":
        harness.manager.get_task_status.assert_called_once_with(C, include_route_failures=True)
        assert not harness.sessions[C].stop_run_flag.is_set()
    else:
        harness.manager.stop_task.assert_called_once_with(C)
        assert harness.sessions[C].stop_run_flag.is_set()
    for name in ("create_token", "refresh_token", "invalidate_token"):
        getattr(harness.runtime.token_manager, name).assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_owner_request_without_view_source_still_works(harness, route):
    harness.client.set_cookie("auth_token", "token-owner")
    response = invoke(harness, route, origin=None)
    assert response.status_code == 200
    assert response.json["success"] is True
    assert all(call.args[0] == "owner" for call in harness.runtime.auth_system.check_permission.call_args_list)


@pytest.mark.parametrize("multi", (False, True))
def test_http_status_filters_complete_payload_using_mode_specific_role(harness, multi):
    harness.sessions[B].is_multi_account_mode = multi
    response = invoke(harness, ROUTES[1])
    assert response.status_code == 200
    assert ("PRIVATE_REASON" in response.get_data(as_text=True)) is not multi
    assert ("route_planning_failures" in response.json["task_status"]) is not multi
    assert harness.manager.tasks[B]["error"] == "PRIVATE_REASON"


@pytest.mark.parametrize("flag", ("bypass_overdue", "waive_charge"))
def test_billing_override_cannot_borrow_target_administrator_privileges(harness, flag):
    harness.groups["owner"] = "super_admin"
    harness.sessions[B].auth_group = "super_admin"
    harness.groups["actor"] = "user"
    harness.permissions[("actor", "bypass_overdue")] = False
    response = invoke(harness, ROUTES[0], payload={"task_indices": [0], flag: True})
    assert response.status_code == 403
    assert_no_business_or_token_changes(harness)


def test_read_only_a_b_c_a_chain_preserves_authentication_and_all_tasks(harness):
    for target in (A, B, C, A):
        response = invoke(harness, ROUTES[1], target=target, origin=None if target == A else A)
        assert response.status_code == 200
        assert response.headers.getlist("Set-Cookie") == []
    assert [call.args[0] for call in harness.manager.get_task_status.call_args_list] == [A, B, C, A]
    harness.manager.start_background_task.assert_not_called()
    harness.manager.stop_task.assert_not_called()
    assert all(not api.stop_run_flag.is_set() for api in harness.sessions.values())
    for name in ("create_token", "refresh_token", "invalidate_token"):
        getattr(harness.runtime.token_manager, name).assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("valid", (True, False))
def test_guest_token_is_bound_to_target_without_polling_writes(harness, route, valid, tmp_path):
    api = harness.sessions[B]
    api.auth_username = "guest"
    api.is_guest = True
    harness.groups["guest"] = "guest"
    guest_store = GuestTokenStore(str(tmp_path / "guests"))
    harness.runtime.token_manager.guest_store = guest_store
    token = guest_store.create(B if valid else C)
    harness.client.set_cookie("auth_token", token)
    harness.runtime._load_guest_session_record = Mock(return_value={"last_accessed": time.time()})
    harness.runtime._get_default_config = Mock(return_value={})
    harness.runtime._get_guest_config = Mock(return_value={"guest_session_inactivity_timeout": 300})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    response = invoke(harness, route, origin=None)
    assert response.status_code == (200 if valid else 401)
    assert {path: path.read_bytes() for path in before} == before
    if valid:
        assert all(call.args[0] == "guest" for call in harness.runtime.auth_system.check_permission.call_args_list)
        assert "PRIVATE_REASON" not in response.get_data(as_text=True)
    else:
        assert_no_business_or_token_changes(harness)


@pytest.mark.parametrize("route", ROUTES)
def test_expired_guest_session_cannot_read_start_or_stop(harness, route, tmp_path):
    api = harness.sessions[B]
    api.auth_username = "guest"
    api.is_guest = True
    guest_store = GuestTokenStore(str(tmp_path / "guests"))
    harness.runtime.token_manager.guest_store = guest_store
    harness.client.set_cookie("auth_token", guest_store.create(B))
    harness.runtime._load_guest_session_record = Mock(return_value={"last_accessed": 1})
    harness.runtime._get_default_config = Mock(return_value={})
    harness.runtime._get_guest_config = Mock(return_value={"guest_session_inactivity_timeout": 300})
    response = invoke(harness, route, origin=None)
    assert response.status_code == 401
    assert_no_business_or_token_changes(harness)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("record_state", ("missing", "corrupt", "mismatch"))
def test_guest_index_cannot_replace_missing_or_invalid_token_record(harness, route, record_state, tmp_path):
    api = harness.sessions[B]
    api.auth_username = "guest"
    api.is_guest = True
    guest_store = GuestTokenStore(str(tmp_path / "guests"))
    harness.runtime.token_manager.guest_store = guest_store
    token = guest_store.create(B)
    harness.client.set_cookie("auth_token", token)
    harness.runtime._load_guest_session_record = Mock(return_value={"last_accessed": time.time()})
    harness.runtime._get_default_config = Mock(return_value={})
    harness.runtime._get_guest_config = Mock(return_value={"guest_session_inactivity_timeout": 300})
    record_path = Path(guest_store._token_path(B))
    if record_state == "missing":
        record_path.unlink()
    elif record_state == "corrupt":
        record_path.write_text("{", encoding="utf-8")
    else:
        record_path.write_text('{"token":"another-token"}', encoding="utf-8")
    assert guest_store.find_session_id(token) == B
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    response = invoke(harness, route, origin=None)
    assert response.status_code == 401
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before
    assert_no_business_or_token_changes(harness)
