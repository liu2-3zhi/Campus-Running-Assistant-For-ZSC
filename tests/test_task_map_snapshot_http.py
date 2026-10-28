"""Exercise the real generic HTTP gate, not only the snapshot method."""

import ast
import logging
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, jsonify, request

import main
from api_runtime import Api


SESSION = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def snapshot_http():
    api = object.__new__(Api)
    api.is_authenticated = True
    api.is_guest = False
    api.auth_username = "test-owner"
    api.current_run_idx = 9
    api.all_run_data = [SimpleNamespace(run_coords=[[113, 22, 100]], current_point_index=0)]
    api.save_state = Mock()
    permissions = {"view_map": True}
    runtime = SimpleNamespace(
        request=request, jsonify=jsonify, normalize_session_uuid=main.normalize_session_uuid,
        ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
        _is_api_method_allowed=main._is_api_method_allowed,
        _is_safe_auth_username=lambda username: username == "test-owner",
        token_manager=SimpleNamespace(verify_token=Mock(return_value=(True, "valid")), refresh_token=Mock()),
        auth_system=SimpleNamespace(check_permission=Mock(side_effect=lambda _user, permission: permissions.get(permission, False))),
        update_session_activity=Mock(), _redact_sensitive_log_value=lambda value: value,
        save_session_state=Mock(), resolve_admin_origin_session_context=Mock(return_value=None),
    )
    app = Flask(__name__)
    app.testing = True
    tree = ast.parse(Path("web_server.py").read_text(encoding="utf-8"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "api_call")
    function.decorator_list = []
    namespace = {
        "_main": lambda: runtime, "logging": logging, "API_BLACKLIST_PREFIXES": [],
        "web_sessions": {SESSION: api}, "web_sessions_lock": threading.Lock(),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "web_server.py", "exec"), namespace)
    app.add_url_rule("/api/<path:method>", view_func=namespace["api_call"], methods=["POST"])
    client = app.test_client()
    client.set_cookie("auth_token", "isolated-token")
    return SimpleNamespace(client=client, api=api, runtime=runtime, permissions=permissions)


def invoke(harness, method="get_task_map_snapshot"):
    return harness.client.post("/api/" + method, json=[0], headers={"X-Session-ID": SESSION})


def test_snapshot_http_passes_allowlist_and_preserves_read_only_contract(snapshot_http):
    response = invoke(snapshot_http)
    assert response.status_code == 200, response.json
    assert response.json["route_ready"] is True
    assert response.json["details"]["run_coords"] == [[113, 22, 100]]
    snapshot_http.runtime.auth_system.check_permission.assert_called_once_with("test-owner", "view_map")
    assert snapshot_http.api.current_run_idx == 9
    snapshot_http.api.save_state.assert_not_called()
    snapshot_http.runtime.save_session_state.assert_not_called()


def test_snapshot_http_still_requires_map_permission(snapshot_http):
    snapshot_http.permissions["view_map"] = False
    response = invoke(snapshot_http)
    assert response.status_code == 403
    assert "view_map" in response.json["message"]
    assert "details" not in response.json


def test_sensitive_method_is_still_blocked(snapshot_http):
    response = invoke(snapshot_http, "update_school_account_overdue_count")
    assert response.status_code == 403
    snapshot_http.runtime.auth_system.check_permission.assert_not_called()
