from copy import deepcopy

import pytest
from types import SimpleNamespace

from tests import browser_map_proxy_smoke as smoke


def evaluate_acceptance(row):
    method = getattr(smoke, "evaluate_acceptance", None)
    assert callable(method), "the smoke runner must expose strict acceptance evaluation"
    return method(row)


def smoke_results_passed(rows):
    method = getattr(smoke, "smoke_results_passed", None)
    assert callable(method), "the smoke runner must reject failed or empty result sets"
    return method(rows)


def successful_result():
    return {
        "route_success": True, "route_points": 5, "map_ready": True,
        "ui_verified": True, "proxy_enabled": True,
        "proxy_failures": [], "upstream_failures": [], "direct_requests": [],
        "script_errors": 0, "unhandled_rejections": 0, "console_error_messages": [],
    }


def test_retried_upstream_attempts_are_retained_but_only_same_request_can_recover():
    summarize = getattr(smoke, 'summarize_upstream_attempts', None)
    assert callable(summarize)
    rows = [
        {'provider': 'tianditu', 'request_id': 'one', 'error_type': 'ReadTimeout'},
        {'provider': 'tianditu', 'request_id': 'one', 'status': 200},
        {'provider': 'tianditu', 'request_id': 'two', 'status': 502},
        {'provider': 'tianditu', 'request_id': 'three', 'status': 200},
    ]
    result = summarize(rows, 'tianditu')
    assert result['upstream_attempt_failures'] == [rows[0], rows[2]]
    assert result['upstream_failures'] == [rows[2]]
    assert result['recovered_upstream_requests'] == 1


def test_network_probe_distinguishes_queued_context_headers_and_finished_body_without_urls():
    probe_type = getattr(smoke, "MapNetworkProbe", None)
    assert callable(probe_type), "native network phases must be observable without wrapping fetch"
    probe = probe_type()
    context = SimpleNamespace(url="http://localhost/api/map-proxy/context?token=must-not-appear", resource_type="fetch",
                              timing={"requestStart": -1, "responseStart": -1, "responseEnd": -1})
    tile = SimpleNamespace(url="http://localhost/map-proxy/tianditu/https/t0.tianditu.gov.cn/tile?key=must-not-appear", resource_type="image")
    probe.request_started(context)
    probe.request_started(tile)
    first = probe.snapshot()
    assert first["context_started"] == first["context_pending"] == 1
    assert first["context_headers"] == 0 and first["proxy_pending_types"] == {"image": 1}
    assert first["context_pending_timing"][0]["requestStart"] == -1
    probe.response_received(SimpleNamespace(request=context, status=200))
    assert probe.snapshot()["context_headers"] == 1
    assert probe.snapshot()["context_pending"] == 1
    probe.request_finished(context)
    probe.request_failed(tile)
    last = probe.snapshot()
    assert last["context_finished"] == 1 and last["context_pending"] == 0
    assert last["proxy_pending"] == 0 and "must-not-appear" not in str(last)


def test_smoke_success_requires_both_function_and_lifecycle_and_keeps_original():
    row = successful_result()
    before = deepcopy(row)
    result = evaluate_acceptance(row)
    assert result["functional_pass"] is True
    assert result["lifecycle_pass"] is True
    assert result["passed"] is True
    assert row == before
    assert smoke_results_passed([row]) is True
    assert smoke_results_passed([]) is False


@pytest.mark.parametrize("field,value", [
    ("script_errors", 1), ("unhandled_rejections", 1),
    ("console_error_messages", ["native SDK asynchronous error"]),
])
def test_smoke_runtime_errors_must_fail_even_with_a_valid_route(field, value):
    row = successful_result()
    row[field] = value
    result = evaluate_acceptance(row)
    assert result["functional_pass"] is True
    assert result["lifecycle_pass"] is False
    assert result["passed"] is False
    assert smoke_results_passed([row]) is False


@pytest.mark.parametrize("field,value", [
    ("proxy_failures", [{"status": 502}]), ("upstream_failures", [{"status": 500}]),
    ("direct_requests", [{"host": "maps.example.test"}]),
    ("map_error", "wrong JavaScript MIME"), ("ui_verified", False),
    ("route_points", 0),
])
def test_smoke_transport_and_render_failures_cannot_be_hidden_by_sdk_load(field, value):
    row = successful_result()
    row[field] = value
    assert evaluate_acceptance(row)["functional_pass"] is False
    assert smoke_results_passed([row]) is False


def test_direct_control_allows_expected_vendor_requests_and_preserves_failed_rounds():
    row = successful_result()
    row["proxy_enabled"] = False
    row["direct_requests"] = [{"host": "maps.example.test"}]
    row["rounds"] = [{"functional_pass": True, "lifecycle_pass": False},
                     {"functional_pass": True, "lifecycle_pass": True}]
    result = evaluate_acceptance(row)
    assert result["functional_pass"] is True
    assert result["lifecycle_pass"] is False
    assert result["passed"] is False


@pytest.mark.parametrize("provider", ["tencent", "baidu"])
def test_pressure_matrix_runs_three_rounds_with_ten_updates_and_retains_failures(monkeypatch, provider):
    class Page:
        def set_viewport_size(self, viewport):
            pass

        def wait_for_function(self, source, timeout):
            pass

        def wait_for_timeout(self, timeout):
            pass

    coordinates = [[116.397128, 39.916527], [116.397428, 39.916527],
                   [116.397728, 39.916527], [116.398128, 39.916527],
                   [116.398528, 39.916527]]
    progress_calls = []
    failed_once = False

    def step(page, source, args=None, **kwargs):
        nonlocal failed_once
        if ".debugState" in source:
            return {"map_ready": False, "active_provider": provider,
                    "placeholder_text": "SDK timeout key=ephemeral-test", "native_map": {"secret": "not-safe"}}
        if ".progress(" in source:
            progress_calls.append(args)
            if not failed_once:
                failed_once = True
                raise AssertionError("first round vendor error")
            position = coordinates[args - 1]
            return {"lines": [1], "points": [position], "expectedRunner": position,
                    "businessPoint": position, "cameraWrites": 0}
        if ".seed(" in source:
            return {"lines": [1], "cameraWrites": 0}
        if ".destroy(" in source:
            return {"instrumentation_restored": True}

    monkeypatch.setattr(smoke, "browser_step", step)
    rows = smoke.exercise_map_lifecycle(Page(), provider, {"key": "ephemeral-test"},
                                        session_id="fixture", render_ui=True,
                                        errors=[], rejections=[], console=[])
    assert len(rows) == 6
    assert rows[0]["functional_pass"] is False
    assert rows[0]["error"] == "first round vendor error"
    assert rows[0]["debug_state"]["map_ready"] is False
    assert rows[0]["debug_state"]["active_provider"] == provider
    assert "ephemeral-test" not in rows[0]["debug_state"]["placeholder_text"]
    assert "native_map" not in rows[0]["debug_state"]
    assert all(row["functional_pass"] and row["progress_updates"] == 10 for row in rows[1:])
    assert len(progress_calls) == 51
    assert [row["viewport"] for row in rows] == ["desktop"] * 3 + ["mobile"] * 3
