import ast
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g, jsonify, request

from api_client import ApiClient
from tests.backend_source_utils import PROJECT_ROOT


@pytest.mark.parametrize("action", ["save", "update"])
@pytest.mark.parametrize(
    ("submitted_ua", "expected_ua"),
    [
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X)", "Android fixture UA"),
        ("Campus App (iPadOS 18.5)", "Android fixture UA"),
        ("  Custom Browser AppleWebKit/537.36  ", "Custom Browser AppleWebKit/537.36"),
        ("", "Android fixture UA"),
    ],
)
def test_admin_account_write_normalizes_device_ua(monkeypatch, action, submitted_ua, expected_ua):
    generate_ua = Mock(return_value="Android fixture UA")
    monkeypatch.setattr(ApiClient, "generate_random_ua", generate_ua)
    api = SimpleNamespace(
        _load_user_school_accounts=lambda owner: {"10001": {"password": "previous"}},
        _save_user_school_accounts=Mock(),
    )
    runtime = SimpleNamespace(
        g=g, jsonify=jsonify, request=request, ApiClient=ApiClient,
        auth_system=SimpleNamespace(
            check_permission=lambda owner, permission: owner == "admin" and permission == "manage_users",
            get_user_group=lambda owner: "admin",
        ),
        is_valid_school_username=lambda value: value == "10001",
        is_valid_school_password=lambda value: value == "fixture-password",
    )
    app = Flask(__name__)

    @app.before_request
    def set_test_user():
        g.user = "admin"

    source = PROJECT_ROOT / "web_server.py"
    route_name = f"api_admin_school_account_{action}"
    node = next(
        node for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == route_name
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), {
        "app": app, "login_required": lambda route: route, "_main": lambda: runtime,
        "web_sessions": {"fixture-session": api}, "logging": logging,
    })

    with app.test_client() as client:
        result = client.post(f"/api/admin/school_account/{action}", json={
            "auth_username": "owner", "school_username": "10001",
            "password": "fixture-password", "ua": submitted_ua,
        }, headers={"X-Session-ID": "fixture-session"})

    assert result.status_code == 200
    assert result.json["success"] is True
    api._save_user_school_accounts.assert_called_once_with(
        "owner", {"10001": {"password": "fixture-password", "ua": expected_ua}},
    )
    assert generate_ua.call_count == int(expected_ua == "Android fixture UA")
