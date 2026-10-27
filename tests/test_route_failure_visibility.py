from types import SimpleNamespace
from unittest.mock import Mock
import threading

import route_failure_visibility as visibility


def setup_runtime(monkeypatch, group="admin", valid=True, origin=None):
    headers = {"X-Session-ID": "target"}
    if origin:
        headers["X-Admin-Origin-Session-ID"] = origin
    runtime = SimpleNamespace(
        request=SimpleNamespace(headers=headers, cookies={"auth_token": "token"}),
        web_sessions={"target": SimpleNamespace(auth_username="owner", is_authenticated=True, is_guest=False)},
        web_sessions_lock=threading.Lock(),
        ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
        _verify_session_cookie_token=Mock(return_value=valid),
        resolve_admin_origin_session_context=Mock(return_value=None),
        resolve_admin_view_identity=Mock(return_value=None),
        auth_system=SimpleNamespace(get_user_group=Mock(return_value=group)),
    )
    monkeypatch.setattr(visibility, "_main", lambda: runtime)
    return runtime


def test_unverified_uuid_does_not_disclose_admin_details(monkeypatch):
    setup_runtime(monkeypatch, valid=False)
    assert not visibility.can_view_route_failure_details("target")


def test_admin_view_uses_verified_actor_and_not_target_owner(monkeypatch):
    runtime = setup_runtime(monkeypatch, origin="origin")
    runtime.resolve_admin_origin_session_context.return_value = {"username": "actor"}
    assert visibility.can_view_route_failure_details("target")
    runtime.auth_system.get_user_group.assert_called_once_with("actor")


def test_public_response_drops_private_reason_from_all_fields(monkeypatch):
    setup_runtime(monkeypatch, group="user")
    result = visibility.project_route_failure_response({
        "success": False, "error": "SENSITIVE", "notices": ["SENSITIVE"],
        "_route_failure": {"diagnostic_id": "d1", "provider": "amap", "message": "SENSITIVE"},
    }, "target")
    assert "SENSITIVE" not in str(result)
    assert result["diagnostic_id"] == "d1"


def test_admin_receives_reason_and_role_lookup_fails_closed(monkeypatch):
    runtime = setup_runtime(monkeypatch)
    raw = {"success": False, "_route_failure": {"diagnostic_id": "d2", "provider": "amap", "message": "INVALID_USER_KEY", "segment": 2, "error_code": "10001"}}
    message = visibility.project_route_failure_response(raw, "target")["message"]
    assert "INVALID_USER_KEY" in message
    assert "路段：2；错误码：10001" in message
    runtime.auth_system.get_user_group.side_effect = RuntimeError("unavailable")
    assert "INVALID_USER_KEY" not in visibility.project_route_failure_response(raw, "target")["message"]
    assert "_route_failure" in raw


def test_multi_account_projection_still_uses_target_owner_role(monkeypatch):
    runtime = setup_runtime(monkeypatch, origin="origin")
    runtime.web_sessions["target"].is_multi_account_mode = True
    runtime.resolve_admin_origin_session_context.return_value = {"username": "actor"}
    runtime.auth_system.get_user_group.side_effect = lambda username: "admin" if username == "actor" else "user"
    assert not visibility.can_view_route_failure_details("target")
