"""Log persistence and browser notification redaction use separate policies."""

import copy
import json
import logging
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import api_runtime
import main


def runtime_for_notifications():
    return SimpleNamespace(
        socketio=Mock(), _redact_sensitive_log_value=main._redact_sensitive_log_value,
        _redact_sensitive_display_value=main._redact_sensitive_display_value,
        _redact_sensitive_display_text=main._redact_sensitive_display_text,
    )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("explicit_frontend", [False, True])
def test_web_log_messages_are_always_redacted_even_when_file_logs_keep_original(monkeypatch, caplog, enabled, explicit_frontend):
    monkeypatch.setattr(main, "_log_redaction_enabled", enabled)
    runtime = runtime_for_notifications()
    monkeypatch.setattr(api_runtime, "_main", lambda: runtime)
    api = object.__new__(api_runtime.Api)
    api._web_session_id = "example-session"
    server_message = "upstream rejected token=example-server-token " + "detail " * 300 + "server-tail"
    frontend_message = "safe to explain password=example-browser-password browser-tail" if explicit_frontend else None
    with caplog.at_level(logging.INFO):
        api.log_and_notify_frontend(server_message, frontend_message=frontend_message, diagnostic_id="example-diagnostic")
    assert ("example-server-token" in caplog.text) is not enabled
    assert "server-tail" in caplog.text
    event, payload = runtime.socketio.emit.call_args.args
    assert event == "log_message" and payload["diagnostic_id"] == "example-diagnostic"
    public = json.dumps(payload)
    assert "example-server-token" not in public and "example-browser-password" not in public
    assert "<redacted>" in public
    assert ("browser-tail" in public) is explicit_frontend


def test_structured_notification_is_redacted_without_mutating_log_input(monkeypatch, caplog):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    runtime = runtime_for_notifications()
    monkeypatch.setattr(api_runtime, "_main", lambda: runtime)
    api = object.__new__(api_runtime.Api)
    api._web_session_id = "example-session"
    original = {"password": "example-password", "nested": {"token": "example-token"}, "reason": "vendor reason"}
    expected = copy.deepcopy(original)
    with caplog.at_level(logging.INFO):
        api.log_and_notify_frontend(original, diagnostic_id="token=example-diagnostic-token")
    assert "example-password" in caplog.text and "example-token" in caplog.text
    public = json.dumps(runtime.socketio.emit.call_args.args[1])
    assert "example-password" not in public and "example-token" not in public
    assert "example-diagnostic-token" not in public
    assert "vendor reason" in public
    assert original == expected


def test_frontend_ingestion_preserves_original_file_log_and_never_echoes_it(monkeypatch, caplog, tmp_path):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    runtime = runtime_for_notifications()
    runtime.browsing_activity_lock = threading.Lock()
    runtime.browsing_activity = {}
    monkeypatch.setattr(api_runtime, "_main", lambda: runtime)
    api = object.__new__(api_runtime.Api)
    api._web_session_id = "example-session"
    api.user_dir = str(tmp_path / "absent-user-data")
    api.auth_username = "example-user"
    api.is_guest = False
    message = "browser upstream error key=example-ingested-key " + "details " * 300 + "ingest-tail"
    logs = [{"message": message, "level": "ERROR", "timestamp": "12:00:00", "source": "example-source"}]
    expected = copy.deepcopy(logs)
    with caplog.at_level(logging.INFO):
        result = api.get_initial_data(frontend_logs=logs)
    assert message in caplog.text
    assert "example-ingested-key" not in json.dumps(result)
    runtime.socketio.emit.assert_not_called()
    assert logs == expected


def test_javascript_log_ingestion_is_persisted_without_a_browser_echo(monkeypatch, caplog):
    monkeypatch.setattr(main, "_log_redaction_enabled", False)
    runtime = runtime_for_notifications()
    monkeypatch.setattr(api_runtime, "_main", lambda: runtime)
    api = object.__new__(api_runtime.Api)
    message = "browser failure token=example-js-token " + "details " * 300 + "js-log-tail"
    with caplog.at_level(logging.INFO):
        api.js_log("ERROR", message)
    assert message in caplog.text
    runtime.socketio.emit.assert_not_called()
