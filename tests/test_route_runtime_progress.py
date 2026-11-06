"""Check live planner telemetry with the same virtual SDKs as timeout regressions."""

import json
import subprocess

import pytest

from map_error_catalog import map_error_retry_policy
from test_route_runtime_timeouts import HARNESS, PROVIDERS, ROOT, provider_sources


def run_progress(provider, *, first="timeout", terminal=False, hook="capture", stop_pending=False,
                 waypoint_count=2):
    params = {
        "api_retries": 1,
        "api_retry_delay_s": 0.1,
        "api_queue_interval_s": 0,
        "api_fallback_line": False,
        "_map_error_retry_policy": map_error_retry_policy(provider),
    }
    waypoints = [[1 + index * 2, 2 + index * 2] for index in range(waypoint_count)]
    args = [waypoints, "fake-progress-credential", params]
    args += [[], "walking"] if provider == "amap" else ["walking"]
    scenario = {"first": first, "late": "poison", "terminal": terminal, "bodyTimeout": False}
    code = "const scenario = " + json.dumps(scenario) + ";\n" + HARNESS
    code += "\nconst progress = [];\n"
    if hook == "capture":
        # Snapshot at emission time: later callbacks must not mutate earlier events.
        code += "globalThis.__zxRouteProgress = item => progress.push(JSON.parse(JSON.stringify(item)));\n"
        # This suite verifies compact redacted progress; raw log-only SDK callbacks
        # have a separate channel contract in test_sdk_callback_log_channel.py.
        code += "globalThis.__zxRouteProgress.rawLogsEnabled = false;\n"
    elif hook == "raise":
        code += "globalThis.__zxRouteProgress = () => { throw new Error('diagnostic sink unavailable'); };\n"
    code += "const planner = " + provider_sources()[provider] + ";\n"
    code += "const args = " + json.dumps(args) + ";\n"
    code += r"""
let result;
let failure;
planner(args).then(value => { result = value; }, error => { failure = String(error); });
"""
    if stop_pending:
        code += f"await pumpUntil(() => attempts.length === {waypoint_count - 1} || failure !== undefined);\n"
    else:
        code += "await pumpUntil(() => result !== undefined || failure !== undefined);\n"
    code += r"""
if (failure) { throw new Error(failure); }
const progressBeforeLateCallbacks = JSON.stringify(progress);
"""
    if not stop_pending:
        code += "while (timers.size) { await fireNextTimer(); }\n"
    code += "console.log(JSON.stringify({result, pending: result === undefined, progress, progressBeforeLateCallbacks, attempts}));\n"
    proc = subprocess.run(["node", "--input-type=module"], input=code, capture_output=True,
                          encoding="utf-8", timeout=10, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def events(payload, event):
    return [row for row in payload["progress"] if row["event"] == event]


def assert_safe_progress(progress):
    # Progress is a compact sequence of scalar metadata, never SDK objects/geometry.
    forbidden = {"key", "token", "security_js_code", "session_id", "path", "routes", "steps",
                 "lng", "lat", "waypoints", "provider_config", "callback_detail"}
    for row in progress:
        assert not (set(row) & forbidden)
        assert all(isinstance(value, (str, int, float, bool)) or value is None
                   for value in row.values())
        assert row["elapsed_ms"] >= 0
    assert "fake-progress-credential" not in json.dumps(progress)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_progress_is_visible_while_first_segment_is_still_pending(provider):
    payload = run_progress(provider, stop_pending=True)
    assert payload["pending"]
    assert len(payload["attempts"]) == 1
    assert not events(payload, "segment_result")
    assert not events(payload, "route_result")
    start = events(payload, "segment_start")
    assert len(start) == 1
    assert {field: start[0][field] for field in ("segment", "attempts", "wave", "state")} == {
        "segment": 1, "attempts": 1, "wave": 1, "state": "running",
    }
    route = events(payload, "route_start")
    assert len(route) == 1
    assert route[0]["segment_count"] == 1
    assert route[0]["segment_timeout_ms"] == 15000
    assert events(payload, "wave_start")[0]["wave"] == 1
    if provider in ("amap", "baidu"):
        names = [row["event"] for row in payload["progress"]]
        assert names.index("sdk_load_start") < names.index("sdk_load_ready") < names.index("segment_start")
    if provider == "amap":
        names = [row["event"] for row in payload["progress"]]
        assert names.index("loader_start") < names.index("loader_ready") < names.index("sdk_load_start")
    assert_safe_progress(payload["progress"])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_completed_segment_is_reported_before_entire_wave_returns(provider):
    payload = run_progress(provider, first="success", stop_pending=True, waypoint_count=3)
    assert payload["pending"]
    assert len(payload["attempts"]) == 2
    assert [row["segment"] for row in events(payload, "segment_start")] == [1, 2]
    finished = events(payload, "segment_result")
    assert len(finished) == 1
    assert finished[0]["segment"] == 1
    assert finished[0]["success"] is True
    assert finished[0]["state"] == "completed"
    assert not events(payload, "route_result")
    assert_safe_progress(payload["progress"])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_timeout_retry_logs_each_attempt_and_final_success(provider):
    payload = run_progress(provider)
    assert "error" not in payload["result"]
    assert payload["progress"] == json.loads(payload["progressBeforeLateCallbacks"])
    starts = events(payload, "segment_start")
    results = events(payload, "segment_result")
    callbacks = events(payload, "segment_callback")
    assert [row["attempts"] for row in starts] == [1, 2]
    assert [row["wave"] for row in starts] == [1, 2]
    assert [row["success"] for row in results] == [False, True]
    assert [row["state"] for row in results] == ["failed", "completed"]
    assert [row["attempts"] for row in results] == [1, 2]
    assert [row["wave"] for row in results] == [1, 2]
    assert len(callbacks) == 2
    assert callbacks[0]["elapsed_ms"] >= 15000
    assert starts[1]["elapsed_ms"] >= callbacks[0]["elapsed_ms"]
    assert [row["wave"] for row in events(payload, "wave_start")] == [1, 2]
    assert any(row["scope"] == "wave_retry" and row["delay_ms"] == 100
               for row in events(payload, "retry_wait"))
    assert events(payload, "route_result")[-1]["success"] is True
    assert_safe_progress(payload["progress"])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_exhausted_timeout_keeps_failure_progress_after_late_callbacks(provider):
    payload = run_progress(provider, terminal=True)
    assert "error" in payload["result"]
    assert payload["progress"] == json.loads(payload["progressBeforeLateCallbacks"])
    assert [row["success"] for row in events(payload, "segment_result")] == [False, False]
    assert [row["attempts"] for row in events(payload, "segment_result")] == [1, 2]
    assert events(payload, "route_result")[-1]["success"] is False
    assert_safe_progress(payload["progress"])


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("first", ("success", "timeout"))
def test_missing_or_failing_progress_sink_preserves_planning_result(provider, first):
    captured = run_progress(provider, first=first)
    missing = run_progress(provider, first=first, hook="missing")
    broken = run_progress(provider, first=first, hook="raise")
    assert captured["result"] == missing["result"] == broken["result"]
    assert captured["attempts"] == missing["attempts"] == broken["attempts"]
    assert missing["progress"] == broken["progress"] == []
