import ast
import configparser
import datetime
import json
import logging
import os
import re
from pathlib import Path
import socket
import time
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, g, jsonify, request, session
import pytest
import requests

import main


def load_server_function(name, namespace):
    source = (Path(__file__).resolve().parents[1] / "web_server.py").read_text(encoding="utf-8")
    matches = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1
    node = matches[0]
    node.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, "web_server.py", "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("enabled", [False, True])
def test_payment_log_file_and_admin_detail_follow_logging_switch(tmp_path, monkeypatch, enabled):
    monkeypatch.setattr(main, "_log_redaction_enabled", enabled)
    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    module = SimpleNamespace(
        _redact_sensitive_log_value=main._redact_sensitive_log_value,
        _redact_sensitive_display_value=main._redact_sensitive_display_value,
        request=request, session=session, jsonify=jsonify, g=g,
        auth_system=SimpleNamespace(check_permission=lambda *args: True),
    )
    namespace = {
        "_main": lambda: module, "os": os, "time": time, "datetime": datetime,
        "json": json, "logging": logging, "socket": socket,
        "PAYMENT_LOGS_DIR": str(tmp_path), "g": g,
        "auth_system": SimpleNamespace(check_permission=lambda *args: True),
    }
    writer = load_server_function("_write_payment_log", namespace)
    reader = load_server_function("admin_get_payment_log_detail", namespace)
    payload = {"error": "original reason " + "细节" * 600 + " end-marker", "api_response": {"token": "original-token", "code": 1002}}
    with app.test_request_context("/payments?token=request-token"):
        session["session_id"] = "original-session"
        writer("create_order", "test-admin", "ORDER1", payload)
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    stored = json.loads(paths[0].read_text(encoding="utf-8"))
    with app.test_request_context("/api/admin/payment_log_detail", method="POST", json={"log_id": paths[0].stem}):
        g.user = "test-admin"
        response = reader()
    detail = response.get_json()["log_detail"]
    assert detail == main._redact_sensitive_display_value(stored)
    assert detail["error"] == payload["error"]
    assert detail["api_response"] == "<redacted>"
    assert detail["session_id"] == "<redacted>"
    if enabled:
        assert stored["api_response"] == "<redacted>"
    else:
        assert stored["api_response"] == payload["api_response"]
        assert stored["session_id"] == "original-session"
        assert "token=request-token" in stored["request_url"]


def test_route_log_keeps_raw_error_and_full_diagnostic_before_public_sanitizer(monkeypatch, caplog):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    monkeypatch.setattr(main, "chrome_pool", object(), raising=False)
    monkeypatch.setattr(main, "resolve_backend_page_origin", lambda *args: ("https://merchant.example", "test"))
    monkeypatch.setattr(main, "describe_backend_page_origin_candidates", lambda *args: [])
    monkeypatch.setattr(main, "_plan_route_with_map_provider", lambda *args, **kwargs: {
        "provider": "amap", "actual_mode": "walking", "provider_config": {"js_key": "original-secret"},
    })
    reason = "vendor rejected key=original-secret " + "detail " * 800 + " error-tail"
    diagnostic = {"response": {"token": "original-secret", "message": "detail " * 900 + " diagnostic-tail"}}
    monkeypatch.setattr(main, "_plan_route_path_with_amap_runtime", lambda *args, **kwargs: {"error": reason, "diagnostic": diagnostic})
    with caplog.at_level(logging.DEBUG):
        result = main._plan_route_path_with_provider_runtime("session-1", [[1, 2], [3, 4]])
    assert reason in caplog.text
    assert "diagnostic-tail" in caplog.text
    assert "original-secret" not in result["error"]
    assert "original-secret" not in json.dumps(result["diagnostic"])


def test_request_entry_log_keeps_complete_query_by_default(monkeypatch, caplog):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    app = Flask(__name__)
    module = SimpleNamespace(g=g, request=request, _redact_sensitive_log_text=main._redact_sensitive_log_text)
    namespace = {"_main": lambda: module, "request": request, "time": time, "logging": logging}
    hook = load_server_function("inject_request_context_and_log_start", namespace)
    query = "key=original-secret&detail=" + "x" * 700 + "query-tail"
    with app.test_request_context("/map-proxy/amap/https/example.com/maps?" + query, headers={"X-Request-ID": "test-request"}), caplog.at_level(logging.INFO):
        hook()
    assert query in caplog.text


@pytest.mark.parametrize("function_name, kwargs", [("_query_yipay_order", {"order_id": "ORDER1"}), ("_fetch_yipay_orders", {})])
@pytest.mark.parametrize("failure", ["timeout", "connection", "invalid_json", "business"])
def test_payment_queries_log_complete_failure_details(monkeypatch, caplog, function_name, kwargs, failure):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    config = configparser.ConfigParser()
    config["Rainbow_YiPay"] = {"host": "https://pay.example.test", "pid": "merchant-1", "key": "test-only-key"}
    detail = "original-reason token=test-token " + "detail " * 150 + "reason-tail"
    response = requests.Response()
    response.status_code = 200
    response.encoding = "utf-8"
    response._content = (json.dumps({"code": 1002, "msg": detail}) if failure == "business" else detail).encode("utf-8")
    post = Mock(return_value=response)
    if failure in {"timeout", "connection"}:
        post.side_effect = (requests.Timeout if failure == "timeout" else requests.ConnectionError)(detail)
    module = SimpleNamespace(
        _read_config_ini=lambda *args: config, CONFIG_JSON_FILE="unused-test-config",
        requests=SimpleNamespace(post=post, exceptions=requests.exceptions),
        RsaSigner=lambda **kwargs: SimpleNamespace(generate_sign=lambda data: data),
        _redact_sensitive_log_text=main._redact_sensitive_log_text,
        _redact_sensitive_log_value=main._redact_sensitive_log_value,
    )
    function = load_server_function(function_name, {"_main": lambda: module, "configparser": configparser, "time": time, "logging": logging, "traceback": traceback, "json": json})
    with caplog.at_level(logging.INFO):
        result = function(**kwargs)
    assert result["success"] is False
    assert detail in caplog.text
    assert "test-token" not in result["message"]


def test_full_diagnostic_logging_handles_cycles_and_unprintable_values(monkeypatch):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    cyclic = {"token": "original-token"}
    cyclic["cycle"] = cyclic
    assert "original-token" in main._format_log_diagnostic(cyclic)

    class Broken:
        def __str__(self):
            raise ValueError("cannot stringify")

    assert main._format_log_diagnostic(Broken()) == "<unavailable diagnostic>"


def test_web_log_view_redacts_original_files_before_filtering(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    app = Flask(__name__)
    logfile = tmp_path / "application.log"
    original = "vendor rejected token=original-secret password=original-password reason=配置不完整\n"
    logfile.write_text(original, encoding="utf-8")
    module = SimpleNamespace(request=request, jsonify=jsonify, LOGIN_LOGS_DIR=str(tmp_path),
                             _redact_sensitive_display_text=main._redact_sensitive_display_text)
    view = load_server_function("view_logs", {"_main": lambda: module, "os": os, "re": re, "logging": logging,
                                             "web_sessions": {"test-session": SimpleNamespace(auth_group="admin")}})
    with app.test_request_context("/logs/view", headers={"X-Session-ID": "test-session"}):
        data = view().get_json()
    assert "配置不完整" in data["logs"][0]
    assert "original-secret" not in json.dumps(data)
    assert "original-password" not in json.dumps(data)
    assert logfile.read_text(encoding="utf-8") == original
    with app.test_request_context("/logs/view?keyword=original-secret", headers={"X-Session-ID": "test-session"}):
        assert view().get_json()["logs"] == []


def test_display_redaction_is_independent_and_preserves_server_log_input(monkeypatch, capsys):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    monkeypatch.setattr(main, "_log_buffer", [])
    message = "Authorization: Bearer original-auth https://user:original-password@example.test/ sign=original-sign token=original-token"
    main._buffer_log("INFO", message)
    displayed = capsys.readouterr().out
    for credential in ("original-auth", "original-password", "original-sign", "original-token"):
        assert credential not in displayed
    assert main._log_buffer == [("INFO", message)]
    assert main._redact_sensitive_log_text(message) == message


def test_sms_history_display_hides_codes_without_mutating_original_record(monkeypatch):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    record = {"content": "管理员添加短信验证码: 123456", "details": {"password": "original-password"}}
    displayed = main._redact_sensitive_display_value(record)
    assert "123456" not in displayed["content"]
    assert displayed["details"]["password"] == "<redacted>"
    assert "123456" in record["content"]


@pytest.mark.parametrize("message", ["{'sign': 'original-signature'}", "[RSA验签] 签名: original-signature"])
def test_console_hides_signatures_while_default_file_keeps_them(monkeypatch, message):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, (), None)
    assert "original-signature" not in main.SensitiveLogFormatter("%(message)s").format(record)
    assert main.NoColorFileFormatter("%(message)s").format(record) == message


@pytest.mark.parametrize("scheme", ["http", "https", "socks4", "socks4a", "socks5", "socks5h"])
def test_display_hides_proxy_userinfo_without_changing_persisted_text(monkeypatch, scheme):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    message = f"ALL_PROXY={scheme}://test-user:original-password@proxy.example.test:1080"
    assert "original-password" not in main._redact_sensitive_display_text(message)
    assert main._redact_sensitive_log_text(message) == message


def test_display_hides_signature_aliases_and_payment_payloads(monkeypatch):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    payload = {"sig": "signature-value", "sn": "signature-value", "pay_info": "original-pay-info"}
    assert set(main._redact_sensitive_display_value(payload).values()) == {"<redacted>"}
    assert "original-pay-info" not in main._redact_sensitive_display_text(repr(payload))
    assert main._redact_sensitive_log_value(payload) == payload


@pytest.mark.parametrize("message", [
    "[网络请求] Cookie内容: {'JSESSIONID': 'original-secret', 'rememberMe': 'second-secret'}",
    "Cookie: JSESSIONID=original-secret; rememberMe=second-secret",
    "Authorization: Basic original-secret",
    "[前端日志][Session:original-secret] reason=vendor-error",
    "[前端日志][Session Id:original-secret] reason=vendor-error",
    "probe=http://127.0.0.1/api/payment/verify_host/probe/original-secret challenge=second-secret",
])
def test_display_hides_complete_cookie_and_ephemeral_session_details(monkeypatch, message):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    rendered = main._redact_sensitive_display_text(message)
    assert "original-secret" not in rendered
    assert "second-secret" not in rendered
    assert main._redact_sensitive_log_text(message) == message
