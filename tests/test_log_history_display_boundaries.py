import ast
import copy
from functools import wraps
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, g, jsonify, request
import pytest

import main


SERVER_PATH = Path(__file__).resolve().parents[1] / "web_server.py"
SERVER_FUNCTIONS = {
    node.name: node
    for node in ast.walk(ast.parse(SERVER_PATH.read_text(encoding="utf-8")))
    if isinstance(node, ast.FunctionDef)
}


def load_server_function(name, namespace):
    # Keep the route and authentication decorators around the actual handler.
    node = copy.deepcopy(SERVER_FUNCTIONS[name])
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(SERVER_PATH), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def history_app(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    app = Flask(__name__)
    app.config["TESTING"] = True
    auth = SimpleNamespace(
        check_permission=Mock(return_value=True),
        get_user_group=Mock(return_value="admin"),
        get_login_history=Mock(),
        get_audit_logs=Mock(),
    )
    runtime = SimpleNamespace(
        request=request,
        jsonify=jsonify,
        g=g,
        auth_system=auth,
        LOGIN_LOGS_DIR=str(tmp_path),
        _redact_sensitive_display_value=main._redact_sensitive_display_value,
    )

    def login_required(function):
        @wraps(function)
        def protected(*args, **kwargs):
            user = request.headers.get("X-Test-User")
            if not user:
                return jsonify({"success": False, "message": "authentication required"}), 401
            g.user = user
            return function(*args, **kwargs)

        return protected

    def admin_required(function):
        @login_required
        @wraps(function)
        def protected(*args, **kwargs):
            if auth.get_user_group(g.user) not in ("admin", "super_admin"):
                return jsonify({"success": False, "message": "administrator required"}), 403
            return function(*args, **kwargs)

        return protected

    namespace = {
        "_main": lambda: runtime,
        "app": app,
        "login_required": login_required,
        "admin_required": admin_required,
        "os": os,
        "json": json,
        "logging": logging,
        "BILLING_LOGS_DIR": str(tmp_path / "billing"),
    }
    return SimpleNamespace(
        app=app,
        auth=auth,
        namespace=namespace,
        root=tmp_path,
        headers={"X-Test-User": "test-admin"},
    )


AUTH_HISTORY_ROUTES = (
    ("auth_admin_login_logs", "/auth/admin/login_logs", "get_login_history", ("student", 2)),
    ("auth_admin_audit_logs", "/auth/admin/audit_logs", "get_audit_logs", ("student", "login", 2)),
    ("admin_logs_login_history", "/api/admin/logs/login_history", "get_login_history", ("student", 2)),
    ("admin_logs_audit", "/api/admin/logs/audit", "get_audit_logs", ("student", "login", 2)),
)


@pytest.mark.parametrize("name,path,getter,arguments", AUTH_HISTORY_ROUTES)
def test_auth_history_display_is_redacted_with_persistence_redaction_disabled(
    history_app, name, path, getter, arguments
):
    original = [{
        "username": "student",
        "action": "login",
        "message": "登录失败 token=history-token reason=凭证过期",
        "session_id": "history-session",
        "details": {"password": "history-password", "status": 401},
    }]
    snapshot = copy.deepcopy(original)
    getattr(history_app.auth, getter).return_value = original
    load_server_function(name, history_app.namespace)

    response = history_app.app.test_client().get(
        path + "?username=student&action=login&limit=2", headers=history_app.headers
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["logs"][0]["username"] == "student"
    assert payload["logs"][0]["details"]["status"] == 401
    assert "凭证过期" in payload["logs"][0]["message"]
    for credential in ("history-token", "history-session", "history-password"):
        assert credential not in response.get_data(as_text=True)
    history_app.auth.check_permission.assert_called_once_with("test-admin", "view_audit_logs")
    getattr(history_app.auth, getter).assert_called_once_with(*arguments)
    assert original == snapshot
    assert main._redact_sensitive_log_value(original) is original


@pytest.mark.parametrize("name,path,getter,arguments", AUTH_HISTORY_ROUTES)
def test_auth_history_display_keeps_permission_check(history_app, name, path, getter, arguments):
    history_app.auth.check_permission.return_value = False
    load_server_function(name, history_app.namespace)

    response = history_app.app.test_client().get(path, headers=history_app.headers)

    assert response.status_code == 403
    assert response.get_json()["success"] is False
    getattr(history_app.auth, getter).assert_not_called()


def test_sms_history_display_redacts_codes_and_keeps_original_file(history_app):
    original = [
        {"timestamp": 1, "phone": "15500001234", "content": "旧回执 token=old-sms-token"},
        {"timestamp": 2, "phone": "15500001234", "content": "管理员添加短信验证码: 123456 token=sms-token", "details": {"password": "sms-password"}},
        {"timestamp": 3, "phone": "15500005678", "content": "其他号码"},
    ]
    log_path = history_app.root / "sms_replies.json"
    stored = "\n".join(json.dumps(entry, ensure_ascii=False) for entry in original) + "\n"
    log_path.write_text(stored, encoding="utf-8")
    load_server_function("sms_reply_logs", history_app.namespace)

    response = history_app.app.test_client().get(
        "/api/sms/reply-logs?phone=15500001234&limit=1", headers=history_app.headers
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert (payload["total"], payload["limit"], len(payload["logs"])) == (2, 1, 1)
    assert payload["logs"][0]["timestamp"] == 2
    assert "管理员添加短信验证码" in payload["logs"][0]["content"]
    for credential in ("123456", "sms-token", "sms-password"):
        assert credential not in response.get_data(as_text=True)
    assert log_path.read_text(encoding="utf-8") == stored

    history_app.auth.get_user_group.return_value = "user"
    denied = history_app.app.test_client().get("/api/sms/reply-logs", headers=history_app.headers)
    assert denied.status_code == 403
    assert denied.get_json()["success"] is False


def test_billing_history_display_redacts_nested_values_and_keeps_original_files(history_app):
    billing_dir = Path(history_app.namespace["BILLING_LOGS_DIR"])
    billing_dir.mkdir()
    files = {}
    for index, event_type in enumerate(("billing_created", "billing_created", "other")):
        record = {
            "billing_id": f"billing-{index}",
            "created_at": f"2026-11-06 10:00:0{index}",
            "event_type": event_type,
            "reason": "匹配理由 token=billing-token",
            "details": {"password": "billing-password", "amount": 5},
            "after": {"session_id": "billing-session", "status": "pending"},
        }
        path = billing_dir / f"event-{index}.json"
        files[path] = json.dumps(record, ensure_ascii=False)
        path.write_text(files[path], encoding="utf-8")
    for name in ("_billing_log_matches_keyword", "_safe_billing_log_sort_key", "admin_billing_logs"):
        load_server_function(name, history_app.namespace)

    response = history_app.app.test_client().get(
        "/api/admin/billing/logs?event_type=billing_created&keyword=匹配理由&page_size=1",
        headers=history_app.headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert (payload["total"], payload["page"], payload["page_size"]) == (2, 1, 1)
    assert payload["logs"][0]["billing_id"] == "billing-1"
    assert payload["logs"][0]["details"]["amount"] == 5
    assert payload["logs"][0]["after"]["status"] == "pending"
    for credential in ("billing-token", "billing-password", "billing-session"):
        assert credential not in response.get_data(as_text=True)
    for path, stored in files.items():
        assert path.read_text(encoding="utf-8") == stored

    history_app.auth.get_user_group.return_value = "user"
    denied = history_app.app.test_client().get("/api/admin/billing/logs", headers=history_app.headers)
    assert denied.status_code == 403
    assert denied.get_json()["success"] is False
