"""Full server diagnostics stay separate from bounded public route details."""

import json
import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import background_task_manager as background
import route_network_diagnostics as network


def active_context():
    return {
        "diagnostic_id": "diagnostic-example", "provider": "amap",
        "worker_started": time.monotonic(), "sensitive_values": ["example-secret"],
        "events": [], "sdk_auth_capture_enabled": True, "network_capture_enabled": True,
        "network_pending": {}, "network_counts": {"started": 0, "finished": 0, "failed": 0},
        "progress_marker": "example-progress:", "progress_segments": {},
        "segment_states": {}, "attempt_started": {},
    }


def listeners_for(active):
    callbacks = {}
    page = Mock()
    page.on.side_effect = lambda event, callback: callbacks.setdefault(event, callback)
    entry = {"page": page, "route_diagnostic_context": active}
    pool = background.ChromeBrowserPool.__new__(background.ChromeBrowserPool)
    pool._install_route_page_diagnostics(entry)
    return pool, entry, callbacks


def test_worker_log_keeps_full_original_fields_when_redaction_is_disabled(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=False))
    detail = {"token": "example-secret", "path": list(range(25)), "reason": "R" * 17000 + "complete-tail"}
    with caplog.at_level(logging.INFO):
        background.ChromeBrowserPool._log_route_worker_event(active_context(), "failure", detail=detail)
    assert "example-secret" in caplog.text
    assert "complete-tail" in caplog.text
    assert '"path": [0, 1, 2' in caplog.text and "24]" in caplog.text


def test_worker_log_uses_existing_sanitizer_when_redaction_is_enabled(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=True))
    with caplog.at_level(logging.INFO):
        background.ChromeBrowserPool._log_route_worker_event(
            active_context(), "failure", detail={"token": "example-secret", "path": [1, 2]})
    assert "example-secret" not in caplog.text
    assert "<redacted>" in caplog.text and "<omitted>" in caplog.text


def test_browser_logs_keep_event_after_public_capture_limit(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=False))
    active = active_context()
    _pool, _entry, callbacks = listeners_for(active)
    with caplog.at_level(logging.DEBUG):
        for index in range(13):
            callbacks["pageerror"](RuntimeError("example-secret detail-" + str(index) + "-tail" + "x" * 900))
    assert "detail-12-tail" in caplog.text and "example-secret" in caplog.text
    assert len(active["events"]) == 12
    assert active["events_dropped"] == 1
    assert "example-secret" not in json.dumps(active["events"])
    assert len(active["events"][0]["detail"].encode("utf-8")) <= 800


def test_network_logs_keep_original_url_and_headers_but_snapshot_stays_safe(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=False))
    active = active_context()
    _pool, _entry, callbacks = listeners_for(active)
    request = SimpleNamespace(
        url="https://restapi.amap.com/route?key=example-secret&mode=walking",
        headers={"Authorization": "Bearer example-secret", "Referer": "https://app.test/private?mode=walking"},
        resource_type="fetch", method="POST", post_data="complete request body",
    )
    with caplog.at_level(logging.INFO):
        callbacks["request"](request)
    assert request.url in caplog.text
    assert "Bearer example-secret" in caplog.text
    assert "complete request body" in caplog.text
    assert "private?mode=walking" in caplog.text
    stored = json.dumps(active["network_pending"][id(request)]["detail"])
    assert "example-secret" not in stored
    assert "complete request body" not in stored
    assert "private?mode=walking" not in stored


def test_progress_logs_keep_full_payload_but_public_progress_is_bounded(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=False))
    active = active_context()
    active["progress_events_logged"] = 160
    _pool, _entry, callbacks = listeners_for(active)
    payload = {"event": "segment_callback", "segment": 1, "reason": "example-secret " + "x" * 300,
               "vendor_response": {"code": 501, "message": "original vendor reason"}}
    message = SimpleNamespace(type="debug", text=active["progress_marker"] + json.dumps(payload))
    with caplog.at_level(logging.INFO):
        callbacks["console"](message)
    assert "original vendor reason" in caplog.text and "example-secret" in caplog.text
    assert "vendor_response" not in active["last_progress"]
    assert "example-secret" not in active["last_progress"]["reason"]
    assert len(active["last_progress"]["reason"].encode("utf-8")) <= 240


def test_worker_exception_log_keeps_original_error_while_result_is_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=False))
    pool = background.ChromeBrowserPool.__new__(background.ChromeBrowserPool)
    page = Mock()
    page.evaluate.side_effect = RuntimeError("original browser exception example-secret")
    pool._initialized = True
    pool._contexts = {"example-session": {"page": page, "context": Mock()}}
    with caplog.at_level(logging.WARNING):
        result = pool._do_execute_js("example-session", "script", [], diagnostic_context=active_context())
    assert "original browser exception example-secret" in caplog.text
    assert "Traceback" in caplog.text
    assert not result["success"]
    assert "example-secret" not in result["error"]


def test_network_detail_opt_in_preserves_safe_default_environment(monkeypatch):
    monkeypatch.setattr(network.os, "environ", {"HTTPS_PROXY": "http://example-user:example-secret@proxy.test:8080"})
    assert "proxy_env" not in network.route_network_environment()
    assert network.route_network_environment(include_details=True)["proxy_env"]["HTTPS_PROXY"].endswith("@proxy.test:8080")


def test_network_probe_detail_opt_in_keeps_error_message(monkeypatch):
    def fail(*_args, **_kwargs):
        raise network.socket.gaierror(-2, "complete resolver failure example-secret")

    monkeypatch.setattr(network.socket, "getaddrinfo", fail)
    slots = threading.BoundedSemaphore(2)
    slots.acquire()
    events = []
    network._run_probe("amap", ["restapi.amap.com"], lambda event, **fields: events.append(fields), slots,
                       include_details=True)
    failure = next(row for row in events if row["phase"] == "dns" and row["state"] == "error")
    assert "complete resolver failure example-secret" in failure["error_message"]
