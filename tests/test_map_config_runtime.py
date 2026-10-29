import copy
import json
import shutil
import subprocess
import threading
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest
import requests
from flask import Flask, g

import api_runtime
import main
from config_adapter import JsonConfigAdapter
from map_request_proxy import register_map_proxy_routes


SESSION_ID = "11111111-1111-4111-8111-111111111111"
KEY_FIELDS = {"amap": "js_key", "tencent": "map_key", "tianditu": "token", "baidu": "ak"}


def make_config(front="amap", back="amap"):
    rows = []
    for config_id, provider in (("front-one", front), ("back-two", back)):
        rows.append({
            "id": config_id, "name": config_id, "provider": provider,
            KEY_FIELDS[provider]: config_id + "-secret",
            "backend_page_origin": "https://" + config_id + ".test",
            **({"security_js_code": config_id + "-security"} if provider == "amap" else {}),
        })
    config = JsonConfigAdapter.__new__(JsonConfigAdapter)
    config._data = {"Map": {
        "provider": front, "configs": rows, "frontend_config_id": "front-one",
        "backend_config_id": "back-two", "frontend_proxy_enabled": "true",
    }}
    return config


@pytest.fixture
def encryption_context(monkeypatch):
    context = main._generate_map_key_runtime_context()
    monkeypatch.setattr(main, "_get_map_key_runtime_session_identity", lambda _: (SESSION_ID, "alice", True))
    monkeypatch.setattr(main, "_get_map_key_runtime_context_for_session", lambda **_: context)
    return context


@pytest.mark.parametrize("front,back", [
    ("amap", "amap"), ("tencent", "amap"), ("tianditu", "baidu"), ("baidu", "tianditu"),
])
def test_public_bundle_decrypts_only_frontend_credentials_even_when_backend_provider_is_requested(
    front, back, encryption_context,
):
    config = make_config(front, back)
    payload = main._build_public_map_provider_frontend_payload(
        config, required_provider=back, session_id=SESSION_ID,
    )
    assert payload["map_provider"] == front
    assert payload["map_config_id"] == "front-one"
    assert payload["map_provider_key_bundle"]["available"] is True
    decrypted = main._decrypt_map_provider_key_bundle(payload["map_provider_key_bundle"], encryption_context)
    expected = {KEY_FIELDS[front]: "front-one-secret"}
    if front == "amap":
        expected["security_js_code"] = "front-one-security"
    assert decrypted == {front: expected}
    assert "back-two" not in json.dumps(payload)
    assert "back-two-secret" not in json.dumps(decrypted)
    assert "backend_page_origin" not in json.dumps(payload)
    assert "front-one-secret" not in json.dumps(payload)
    assert "security_js_code" not in json.dumps(payload["map_providers"])


@pytest.mark.parametrize("front,back", [("amap", "amap"), ("tencent", "amap"), ("baidu", "tianditu")])
def test_route_planning_uses_backend_profile_while_initialization_uses_frontend(front, back):
    config = make_config(front, back)
    plan = main._plan_route_with_map_provider([[113.39, 22.52], [113.40, 22.53]], runtime_config=config)
    assert main._get_active_map_provider(config) == back
    assert main._get_active_map_provider(config, scope="frontend") == front
    assert plan["provider"] == back
    assert plan["provider_config"][KEY_FIELDS[back]] == "back-two-secret"
    assert plan["provider_config"]["config_id"] == "back-two"
    frontend = main._get_map_provider_frontend_config(config)
    assert frontend["map_provider"] == front
    assert frontend["map_providers"][front][KEY_FIELDS[front]] == "front-one-secret"
    assert "back-two-secret" not in json.dumps(frontend)


def test_backend_dispatch_passes_backend_origin_and_key_to_browser_executor(monkeypatch):
    config = make_config()
    captured = {}

    def execute(session_id, page, waypoints, plan, python_params):
        captured.update(plan)
        return {"path": waypoints}

    monkeypatch.setattr(main, "chrome_pool", SimpleNamespace(), raising=False)
    monkeypatch.setattr(main, "_plan_route_path_with_amap_runtime", execute)
    result = main._plan_route_path_with_provider_runtime(
        SESSION_ID, [[113.39, 22.52], [113.40, 22.53]], runtime_config=config,
        app_base_url="https://fallback.test",
    )
    assert "error" not in result
    assert captured["provider_config"]["js_key"] == "back-two-secret"
    assert captured["_runtime_page_origin"] == "https://back-two.test"


def test_legacy_key_edit_updates_only_frontend_profile(monkeypatch, encryption_context):
    config = make_config()
    writer = Mock()
    monkeypatch.setattr(main, "_read_config_ini", lambda _: config)
    monkeypatch.setattr(main, "_write_config_with_comments", writer)
    api = SimpleNamespace(
        config_path="unused-test-config", global_params={}, log_and_notify_frontend=Mock(),
        _web_session_id=SESSION_ID, auth_username="alice",
    )
    result = api_runtime.Api.save_map_provider_key(api, "amap", "edited-front-key")
    assert result["success"] is True
    front, back = config.get("Map", "configs")
    assert front["js_key"] == "edited-front-key"
    assert back["js_key"] == "back-two-secret"
    assert back["security_js_code"] == "back-two-security"
    assert config.get("Map", "backend_config_id") == "back-two"
    assert result["map_config_id"] == "front-one"
    assert main._decrypt_map_provider_key_bundle(result["map_provider_key_bundle"], encryption_context) == {
        "amap": {"js_key": "edited-front-key", "security_js_code": "front-one-security"},
    }
    writer.assert_called_once()


def test_stale_key_edit_for_previous_provider_does_not_touch_backend(monkeypatch):
    config = make_config("tencent", "amap")
    before = copy.deepcopy(config._data)
    writer = Mock()
    monkeypatch.setattr(main, "_read_config_ini", lambda _: config)
    monkeypatch.setattr(main, "_write_config_with_comments", writer)
    api = SimpleNamespace(config_path="unused-test-config", global_params={}, log_and_notify_frontend=Mock())
    result = api_runtime.Api.save_map_provider_key(api, "amap", "stale-key")
    assert result["success"] is False
    assert config._data == before
    writer.assert_not_called()


def test_stale_key_edit_for_same_provider_profile_is_rejected_without_writing(monkeypatch):
    config = make_config()
    config.set("Map", "frontend_config_id", "back-two")
    before = copy.deepcopy(config._data)
    writer = Mock()
    monkeypatch.setattr(main, "_read_config_ini", lambda _: config)
    monkeypatch.setattr(main, "_write_config_with_comments", writer)
    api = SimpleNamespace(config_path="unused-test-config", global_params={}, log_and_notify_frontend=Mock())
    result = api_runtime.Api.save_map_provider_key(api, "amap", "stale-front-key", config_id="front-one")
    assert result["success"] is False
    assert config._data == before
    assert api.global_params == {}
    writer.assert_not_called()


@pytest.fixture
def detour_runtime(monkeypatch):
    config = make_config()
    monkeypatch.setattr(api_runtime, "_DETOUR_LEG_CACHE", api_runtime.collections.OrderedDict())
    monkeypatch.setattr(main, "_read_config_ini", lambda _: config)
    planner = Mock(return_value={"path": [[113.39, 22.52], [113.40, 22.53]], "provider": "amap"})
    monkeypatch.setattr(main, "_plan_route_path_with_provider_runtime", planner)
    api = SimpleNamespace(_calculate_distance_m=lambda *_: 100.0, _route_leg_is_rate_limited=lambda _: False)

    def plan():
        return api_runtime.Api._plan_detour_leg(api, [113.39, 22.52], [113.40, 22.53], session_id=SESSION_ID)

    return config, planner, plan


@pytest.mark.parametrize("field", ["js_key", "security_js_code", "backend_page_origin", "backend_config_id"])
def test_detour_cache_isolated_when_backend_configuration_changes(detour_runtime, field):
    config, planner, plan = detour_runtime
    assert plan()["cached"] is False
    assert plan()["cached"] is True
    assert planner.call_count == 1
    if field == "backend_config_id":
        config.set("Map", field, "front-one")
    else:
        config.get("Map", "configs")[1][field] = "https://changed.test" if field == "backend_page_origin" else "changed-secret"
    assert plan()["cached"] is False
    assert planner.call_count == 2


def test_detour_cache_reuses_backend_routes_after_name_order_or_frontend_key_changes(detour_runtime):
    config, planner, plan = detour_runtime
    assert plan()["cached"] is False
    rows = config.get("Map", "configs")
    rows[1]["name"] = "Renamed backend"
    rows[0]["js_key"] = "edited-front-key"
    rows.reverse()
    assert plan()["cached"] is True
    assert planner.call_count == 1


def test_detour_planning_passes_the_same_configuration_snapshot_used_for_cache(monkeypatch):
    first = make_config()
    later = make_config("tencent", "tencent")
    reader = Mock(side_effect=[first, later])
    monkeypatch.setattr(main, "_read_config_ini", reader)
    monkeypatch.setattr(api_runtime, "_DETOUR_LEG_CACHE", api_runtime.collections.OrderedDict())
    planner = Mock(return_value={"path": [[113.39, 22.52], [113.40, 22.53]], "provider": "amap"})
    monkeypatch.setattr(main, "_plan_route_path_with_provider_runtime", planner)
    api = SimpleNamespace(_calculate_distance_m=lambda *_: 100.0, _route_leg_is_rate_limited=lambda _: False)
    result = api_runtime.Api._plan_detour_leg(api, [113.39, 22.52], [113.40, 22.53], session_id=SESSION_ID)
    assert result["cached"] is False
    reader.assert_called_once()
    assert planner.call_args.kwargs["runtime_config"] is first


def test_authenticated_http_proxy_uses_frontend_profile_origin_not_backend(tmp_path):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            payload = b"window.localMapFixture = true;"
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False
    config = make_config()
    app = Flask(__name__)
    app.testing = True
    app.secret_key = "map-profile-http-test-only"

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            g.user = "alice"
            g.session_id = SESSION_ID
            return view(*args, **kwargs)
        return wrapped

    def transport(method, url, *, headers, body, timeout):
        target = urlsplit(url)
        local_url = f"http://127.0.0.1:{server.server_port}{target.path}"
        if target.query:
            local_url += "?" + target.query
        return session.request(method, local_url, headers=headers, data=body,
                               timeout=timeout, stream=True, allow_redirects=False)

    register_map_proxy_routes(
        app, login_required, lambda: config,
        lambda username, token, actor, view_all: (username, token, actor, view_all) == ("alice", "test-token", SESSION_ID, False),
        transport=transport, tile_cache_dir=tmp_path,
        dns_resolver=lambda host, port, type: [(None, None, None, None, ("8.8.8.8", port))],
    )
    try:
        client = app.test_client()
        client.set_cookie("auth_token", "test-token")
        bootstrap = client.post("/api/map-proxy/context", json={}, headers={
            "X-Session-ID": SESSION_ID, "Origin": "http://localhost",
        })
        assert bootstrap.status_code == 200
        token = bootstrap.json["context_token"]
        response = client.get("/map-proxy/amap/https/webapi.amap.com/maps?key=front-one-secret&__map_context=" + token)
        assert response.status_code == 200
        assert len(received) == 1
        assert received[0]["Referer"] == "https://front-one.test/"
        assert received[0]["Origin"] == "https://front-one.test"
        assert "back-two" not in json.dumps(received)
    finally:
        session.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_legacy_loaded_sdk_reloads_before_reusing_changed_keys_or_security_codes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const legacy = fs.readFileSync('scripts/legacy-map-runtime.js', 'utf8');
const main = fs.readFileSync('scripts/main.js', 'utf8');
const begin = main.indexOf('function loadAMapOnce()');
const end = main.indexOf('\nasync function ensureSingleMap()', begin);
assert.ok(begin >= 0 && end > begin);
for (const provider of ['amap', 'tencent', 'tianditu']) {
  let reloads = 0;
  const sdk = {Map() {}, LatLng() {}, ControlBar() {}};
  const state = {
    AMAP_API_KEY: 'first-key', AMapReady: true, AMapInstance: sdk,
    window: {APP_CONFIG: {map_provider: provider, map_providers: {amap: {security_js_code: 'first-code'}}},
      AMap: sdk, TMap: sdk, T: sdk, location: {reload() { reloads += 1; }}},
  };
  vm.createContext(state);
  vm.runInContext(legacy + '\n' + main.slice(begin, end), state);
  const call = provider === 'amap' ? () => state.loadAMapOnce() :
    provider === 'tencent' ? key => state.loadTencentMapOnce(key) : key => state.loadTianDiTuMapOnce(key);
  call('first-key');
  call('first-key');
  assert.equal(reloads, 0);
  if (provider === 'amap') state.AMAP_API_KEY = 'second-key';
  assert.throws(() => call('second-key'));
  assert.equal(reloads, 1);
}
let reloads = 0;
const state = {AMAP_API_KEY: 'unchanged-key', AMapReady: true, AMapInstance: {},
  window: {APP_CONFIG: {map_provider: 'amap', map_providers: {amap: {security_js_code: 'first-code'}}},
    location: {reload() { reloads += 1; }}}};
vm.createContext(state);
vm.runInContext(legacy + '\n' + main.slice(begin, end), state);
state.loadAMapOnce();
state.window.APP_CONFIG.map_providers.amap.security_js_code = 'second-code';
assert.throws(() => state.loadAMapOnce());
assert.equal(reloads, 1);
"""
    result = subprocess.run([node, "-e", script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
