"""Raw SDK callbacks have a log-only channel before public diagnostics shrink."""

import ast
import json
import logging
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import background_task_manager as background


def run_callback(provider, value_source, *, raw_enabled=True, raw_body=None):
    module = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
    helper = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                  and node.name == f"_plan_route_path_with_{provider}_runtime")
    execute = next(node for node in ast.walk(helper) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js")
    source = execute.args[1].value
    diagnostic_helpers = source[source.index("const diagnosticStarted"):source.index("function diagnosticResult")]
    script = "\n".join([
        "const events=[]; const sink=value=>events.push(value);",
        "sink.rawLogsEnabled=" + json.dumps(raw_enabled) + "; globalThis.__zxRouteProgress=sink;",
        "const arg=[[], 'example-secret']; const waypointsPy=[[1,2],[3,4]];",
        "function extractSegmentPath(){return [];}", diagnostic_helpers,
        "const value=" + value_source + ";",
        "recordResponse(0, 'example-status', value" + (", " + json.dumps(raw_body) if raw_body is not None else "") + ");",
        "console.log(JSON.stringify({events,diagnostic}));",
    ])
    result = subprocess.run(["node", "-e", script], capture_output=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("provider", ["amap", "tencent", "tianditu", "baidu"])
def test_sdk_log_channel_keeps_long_callback_and_original_fields(provider):
    callback = {"message": "example-secret " + "vendor detail " * 200 + "callback-tail",
                "token": "example-secret", "routes": [{"steps": [{"path": list(range(30))}]}],
                "vendor_only_field": {"raw": "complete vendor field"}}
    result = run_callback(provider, json.dumps(callback))
    original = next(event for event in result["events"] if event["event"] == "sdk_callback_raw")
    assert original["response"] == callback
    assert original["segment"] == 1 and original["status"] == "example-status"
    public = result["diagnostic"]["segments"][0]
    assert len(public["reason"]) <= 600
    assert len(public["callback_history"][0]["reason"]) <= 200
    assert "callback-tail" not in json.dumps(public)
    assert "example-secret" not in json.dumps(public)
    assert "vendor_only_field" not in public


def test_log_channel_handles_cyclic_sdk_object_and_bigints_without_changing_public_result():
    result = run_callback("amap", "(()=>{const value={message:'cycle reason', count:123n}; value.self=value; return value;})()")
    original = next(event for event in result["events"] if event["event"] == "sdk_callback_raw")
    assert original["response"]["count"] == "123"
    assert original["response"]["self"] == "<cycle>"
    assert result["diagnostic"]["segments"][0]["reason"] == "cycle reason"


def test_log_channel_keeps_sdk_error_message_and_stack():
    result = run_callback("tencent", "new Error('original SDK exception callback-tail')")
    original = next(event for event in result["events"] if event["event"] == "sdk_callback_raw")
    assert original["response"]["message"] == "original SDK exception callback-tail"
    assert "original SDK exception callback-tail" in original["response"]["stack"]


def test_existing_tianditu_body_can_be_logged_without_expanding_public_reason():
    body = "<original-response>" + "full XML body " * 200 + "body-tail</original-response>"
    result = run_callback("tianditu", json.dumps({"message": "short public reason"}), raw_body=body)
    original = next(event for event in result["events"] if event["event"] == "sdk_callback_raw")
    assert original["response"] == body
    assert result["diagnostic"]["segments"][0]["reason"] == "short public reason"
    assert body not in json.dumps(result["diagnostic"])


@pytest.mark.parametrize("provider", ["amap", "tencent", "tianditu", "baidu"])
def test_redaction_enabled_sink_skips_raw_callback_channel(provider):
    result = run_callback(provider, json.dumps({"message": "example-secret public reason"}), raw_enabled=False)
    assert not any(event["event"] == "sdk_callback_raw" for event in result["events"])
    assert any(event["event"] == "segment_callback" for event in result["events"])


@pytest.mark.parametrize("enabled", [False, True])
def test_worker_raw_callback_event_is_logged_only_and_never_saved_to_public_state(monkeypatch, caplog, enabled):
    monkeypatch.setattr(background, "_main", lambda: SimpleNamespace(_log_redaction_enabled=enabled))
    active = {"diagnostic_id": "example-diagnostic", "provider": "amap", "worker_started": time.monotonic(),
              "progress_marker": "example-marker:", "last_progress": {"event": "segment_start"},
              "progress_segments": {}, "segment_states": {}, "attempt_started": {}, "events": []}
    callbacks = {}
    page = Mock()
    page.on.side_effect = lambda event, callback: callbacks.setdefault(event, callback)
    pool = background.ChromeBrowserPool.__new__(background.ChromeBrowserPool)
    pool._install_route_page_diagnostics({"page": page, "route_diagnostic_context": active})
    payload = {"event": "sdk_callback_raw", "segment": 1,
               "response": {"token": "example-secret", "message": "full raw callback-tail"}}
    with caplog.at_level(logging.INFO):
        callbacks["console"](SimpleNamespace(type="debug", text=active["progress_marker"] + json.dumps(payload)))
    assert ("full raw callback-tail" in caplog.text) is not enabled
    assert active["last_progress"] == {"event": "segment_start"}
    assert active["progress_segments"] == {} and active["events"] == []
    assert "sdk_callback_raw" not in json.dumps(active)
