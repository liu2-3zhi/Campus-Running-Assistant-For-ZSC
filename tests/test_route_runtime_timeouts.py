"""Execute extracted production planners with a deterministic clock and SDK responses."""

import ast
import functools
import json
import subprocess
from pathlib import Path

import pytest

from map_error_catalog import map_error_retry_policy


PROVIDERS = ("amap", "tencent", "tianditu", "baidu")
ROOT = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def provider_sources():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    sources = {}
    for provider in PROVIDERS:
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == f"_plan_route_path_with_{provider}_runtime")
        execute = next(node for node in ast.walk(helper) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js")
        sources[provider] = execute.args[1].value
    return sources


HARNESS = r"""
globalThis.window = globalThis;
let now = 100000;
let sequence = 0;
const timers = new Map();
const firedTimers = [];
globalThis.setTimeout = (callback, delay = 0, ...args) => {
    const id = ++sequence;
    timers.set(id, {id, at: now + Math.max(0, Number(delay) || 0), delay, callback: () => callback(...args)});
    return id;
};
globalThis.clearTimeout = id => timers.delete(id);
Date.now = () => now;
async function flushPromises() {
    for (let index = 0; index < 40; index++) { await Promise.resolve(); }
}
async function fireNextTimer() {
    await flushPromises();
    const timer = [...timers.values()].sort((a, b) => a.at - b.at || a.id - b.id)[0];
    if (!timer) { throw new Error('Planner stalled without a pending timer'); }
    timers.delete(timer.id);
    now = timer.at;
    firedTimers.push({delay: timer.delay, at: now});
    timer.callback();
    await flushPromises();
}
async function pumpUntil(predicate) {
    for (let step = 0; step < 100; step++) {
        await flushPromises();
        if (predicate()) { return; }
        await fireNextTimer();
    }
    throw new Error('Virtual timer budget exceeded');
}

const attempts = [];
const lateDeliveries = [];
const aborts = [];
const scripts = new Set();
function responseKind(attempt) {
    if (scenario.terminal) { return 'timeout'; }
    return attempt === 1 ? scenario.first : 'success';
}
function scheduleReply(deliver, attempt) {
    const kind = responseKind(attempt);
    if (kind === 'timeout') {
        setTimeout(() => {
            lateDeliveries.push({attempt, activeAttempts: attempts.length, at: now});
            deliver(scenario.late);
        }, 15150);
    } else if (kind === 'failure') {
        setTimeout(() => deliver('failure'), 10);
        setTimeout(() => {
            lateDeliveries.push({attempt, activeAttempts: attempts.length, at: now});
            deliver(scenario.late);
        }, 160);
    } else {
        setTimeout(() => deliver('success'), 100);
    }
}
function beginRequest(kind) {
    const attempt = attempts.length + 1;
    attempts.push({attempt, kind, at: now});
    return attempt;
}

globalThis.document = {
    getElementById: () => null,
    createElement: () => ({style: {}, dataset: {}}),
    body: {appendChild() {}},
    head: {
        appendChild(script) {
            scripts.add(script);
            script.parentNode = {removeChild: child => scripts.delete(child)};
            const name = new URL(script.src).searchParams.get('callback');
            const callback = globalThis[name];
            const attempt = beginRequest('jsonp');
            scheduleReply(kind => callback(kind === 'failure'
                ? {status: 510, message: 'RETRY_FAILURE'}
                : {status: 0, result: {routes: [{polyline: kind === 'poison'
                    ? [70, 80, 20000, 20000] : [2, 1, 2000000, 2000000]}]}}), attempt);
        }
    }
};
globalThis.AMapLoader = {load: async () => {}};
class AmapSearch {
    search(start, end, callback) {
        const attempt = beginRequest('amap');
        scheduleReply(kind => callback(kind === 'failure' ? 'error' : 'complete',
            kind === 'failure' ? {info: 'SERVICE_NOT_AVAILABLE'} : {routes: [{steps: [{path:
                kind === 'poison' ? [{lng: 80, lat: 70}, {lng: 81, lat: 71}] : [start, end]
            }]}]}), attempt);
    }
}
globalThis.AMap = {
    LngLat: class {constructor(lng, lat) { this.lng = lng; this.lat = lat; }},
    Walking: AmapSearch, Driving: AmapSearch
};

globalThis.BMAP_STATUS_SUCCESS = 0;
class BaiduSearch {
    constructor(map, options) { this.options = options; this.status = 0; }
    getStatus() { return this.status; }
    search(start, end) {
        const attempt = beginRequest('baidu');
        scheduleReply(kind => {
            this.status = kind === 'failure' ? 7 : 0;
            const path = kind === 'poison' ? [{lng: 80, lat: 70}, {lng: 81, lat: 71}] : [start, end];
            this.options.onSearchComplete({getPlan: () => kind === 'failure' ? null : {
                getNumRoutes: () => 1, getRoute: () => ({getPath: () => path})
            }});
        }, attempt);
    }
}
globalThis.BMap = {
    Point: class {constructor(lng, lat) { this.lng = lng; this.lat = lat; }},
    Map: class {centerAndZoom() {}}, WalkingRoute: BaiduSearch, DrivingRoute: BaiduSearch
};

// The fake XML document exposes only the elements read by the production parser.
globalThis.DOMParser = class {
    parseFromString(text) {
        const match = text.match(/<routelatlon>(.*?)<\/routelatlon>/);
        return {querySelector: selector => selector === 'result' ? {
            querySelector: child => child === 'routelatlon' && match ? {textContent: match[1]} : null
        } : null};
    }
};
globalThis.fetch = (url, {signal}) => {
    const attempt = beginRequest('fetch');
    const kind = responseKind(attempt);
    const points = JSON.parse(new URL(url).searchParams.get('postStr'));
    const body = reply => reply === 'failure' ? 'RETRY_FAILURE'
        : `<result><routelatlon>${reply === 'poison' ? '80,70;81,71' : points.orig + ';' + points.dest}</routelatlon></result>`;
    const response = reply => ({ok: reply !== 'failure', status: reply === 'failure' ? 503 : 200,
                               text: async () => body(reply)});
    function pendingReply(resolve, reject, bodyOnly) {
        signal.addEventListener('abort', () => {
            aborts.push({attempt, at: now});
            reject(new DOMException('Fetch aborted by request timer', 'AbortError'));
        }, {once: true});
        scheduleReply(reply => resolve(bodyOnly ? body(reply) : response(reply)), attempt);
    }
    if (scenario.bodyTimeout && kind === 'timeout') {
        return Promise.resolve({ok: true, status: 200,
            text: () => new Promise((resolve, reject) => pendingReply(resolve, reject, true))});
    }
    return new Promise((resolve, reject) => pendingReply(resolve, reject, false));
};
"""


def run_scenario(provider, mode, *, first="timeout", late="poison", terminal=False,
                 retries=1, body_timeout=False):
    params = {"api_retries": retries, "api_retry_delay_s": 0.1,
              "api_queue_interval_s": 0, "api_fallback_line": False,
              "_map_error_retry_policy": map_error_retry_policy(provider)}
    args = [[[1, 2], [3, 4]], "fake-key", params]
    args += [[], mode] if provider == "amap" else [mode]
    scenario = {"first": first, "late": late, "terminal": terminal, "bodyTimeout": body_timeout}
    code = "const scenario = " + json.dumps(scenario) + ";\n" + HARNESS
    code += "\nconst planner = " + provider_sources()[provider] + ";\n"
    code += "const args = " + json.dumps(args) + ";\n"
    code += r"""
let result;
let failure;
const planning = planner(args).then(value => { result = value; }, error => { failure = String(error); });
await pumpUntil(() => result !== undefined || failure !== undefined);
if (failure) { throw new Error(failure); }
const resultBeforeLateCallbacks = JSON.stringify(result);
while (timers.size) { await fireNextTimer(); }
await planning;
console.log(JSON.stringify({result, resultBeforeLateCallbacks, attempts, lateDeliveries, aborts, firedTimers,
    remainingScripts: scripts.size, remainingJsonpCallbacks: Object.keys(globalThis).filter(key => key.startsWith('__qqRouteCallback_'))}));
"""
    process = subprocess.run(["node", "--input-type=module"], input=code, capture_output=True,
                             encoding="utf-8", timeout=10, cwd=ROOT)
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def assert_diagnostics(payload, statuses):
    result = payload["result"]
    assert result == json.loads(payload["resultBeforeLateCallbacks"])
    diagnostic = result["diagnostic"]
    assert diagnostic["waves"] == len(statuses)
    segment = diagnostic["segments"][0]
    assert segment["attempts"] == len(statuses) == len(payload["attempts"])
    history = segment["callback_history"]
    assert [row["attempt"] for row in history] == list(range(1, len(statuses) + 1))
    assert [row["wave"] for row in history] == list(range(1, len(statuses) + 1))
    assert [row["status"] for row in history] == statuses
    assert payload["remainingScripts"] == 0
    assert payload["remainingJsonpCallbacks"] == []


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("mode", ("walking", "driving"))
@pytest.mark.parametrize("late", ("poison", "failure"))
def test_timeout_then_success_ignores_prior_attempt_callback(provider, mode, late):
    payload = run_scenario(provider, mode, late=late)
    result = payload["result"]
    assert "error" not in result
    assert len(result["path"]) == 2
    for actual, expected in zip(result["path"], ((1, 2), (3, 4))):
        assert actual["lng"] == pytest.approx(expected[0], abs=0.00001)
        assert actual["lat"] == pytest.approx(expected[1], abs=0.00001)
    first = {"amap": "timeout", "tencent": "exception", "tianditu": "AbortError", "baidu": "timeout"}[provider]
    second = {"amap": "complete", "tencent": "0", "tianditu": "response", "baidu": "0"}[provider]
    assert_diagnostics(payload, [first, second])
    assert payload["lateDeliveries"] == [{"attempt": 1, "activeAttempts": 2, "at": 115150}]
    assert len([timer for timer in payload["firedTimers"] if timer["delay"] == 15000]) == 1
    assert result["diagnostic"]["elapsed_ms"] == 15200
    if provider == "tianditu":
        assert payload["aborts"] == [{"attempt": 1, "at": 115000}]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("mode", ("walking", "driving"))
def test_transient_vendor_failure_then_success_records_both_waves(provider, mode):
    payload = run_scenario(provider, mode, first="failure")
    assert "error" not in payload["result"]
    first = {"amap": "error", "tencent": "510", "tianditu": "response", "baidu": "7"}[provider]
    second = {"amap": "complete", "tencent": "0", "tianditu": "response", "baidu": "0"}[provider]
    assert_diagnostics(payload, [first, second])
    assert payload["lateDeliveries"][0]["activeAttempts"] == 2
    assert all(timer["delay"] != 15000 for timer in payload["firedTimers"])
    assert payload["result"]["diagnostic"]["elapsed_ms"] == 210


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("retries", (0, 1, 99))
def test_exhausted_timeout_budget_cannot_be_overwritten_by_late_success(provider, retries):
    payload = run_scenario(provider, "walking", terminal=True, retries=retries)
    attempts = 1 if retries == 0 else 2
    status = {"amap": "timeout", "tencent": "exception", "tianditu": "AbortError", "baidu": "timeout"}[provider]
    assert_diagnostics(payload, [status] * attempts)
    assert "path" not in payload["result"]
    assert "超时" in payload["result"]["error"]
    assert f"{attempts} waves ({attempts} attempts)" in payload["result"]["error"]
    assert len([timer for timer in payload["firedTimers"] if timer["delay"] == 15000]) == attempts
    assert len(payload["lateDeliveries"]) == attempts


@pytest.mark.parametrize("mode", ("walking", "driving"))
def test_tianditu_timeout_while_reading_response_body_retries_cleanly(mode):
    payload = run_scenario("tianditu", mode, body_timeout=True)
    assert "error" not in payload["result"]
    assert_diagnostics(payload, ["AbortError", "response"])
    assert payload["aborts"] == [{"attempt": 1, "at": 115000}]
    assert payload["lateDeliveries"][0]["activeAttempts"] == 2
