"""Offline Chromium checks for profile-pinned workers, CSS and shared cookies.

Run with ``python tests/browser_map_proxy_profiles_smoke.py``. All provider
responses are local fixtures; direct internet requests fail the smoke check.
"""

from __future__ import annotations

import base64
import functools
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

from flask import Flask, g, request, send_file
from playwright.sync_api import sync_playwright
from werkzeug.serving import WSGIRequestHandler, make_server


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config_adapter import JsonConfigAdapter
from map_request_proxy import register_map_proxy_routes


ACTOR_A = "11111111-1111-4111-8111-111111111111"
ACTOR_B = "22222222-2222-4222-8222-222222222222"
AUTH_TOKEN = "offline-profile-fixture-auth"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5X8AAAAASUVORK5CYII=")


class QuietRequestHandler(WSGIRequestHandler):
    def log_request(self, *_args, **_kwargs):
        pass


def profiles():
    return {"Map": {
        "frontend_proxy_enabled": "true", "frontend_config_id": "front-one", "backend_config_id": "back-two",
        "configs": [
            {"id": "front-one", "name": "Front", "provider": "amap", "js_key": "front-fixture",
             "backend_page_origin": "https://front-one.test"},
            {"id": "back-two", "name": "Back", "provider": "amap", "js_key": "back-fixture",
             "backend_page_origin": "https://back-two.test"},
        ],
    }}


def fixture_response(path):
    scripts = {
        "/assets/entry.mjs": """import './dependency.mjs';
            import 'https://webapi.amap.com/assets/absolute.mjs';
            self.events.push('entry');
            const target='./dynamic.mjs'; await import(target);
            const methods={import(value){return value}};
            self.postMessage({events:self.events,methodResult:methods.import('unchanged')});""",
        "/assets/dependency.mjs": """self.events=['dependency'];
            await fetch('https://webapi.amap.com/assets/dependency-fetch.json');
            self.events.push('dependency-fetch');
            const base='https://webapi.amap.com';
            await fetch(base+'/assets/assembled-fetch.json');""",
        "/assets/absolute.mjs": "self.events.push('absolute');",
        "/assets/dynamic.mjs": """await fetch('https://webapi.amap.com/assets/dynamic-fetch.json');
            self.events.push('dynamic');""",
    }
    if path in scripts:
        return "application/javascript", scripts[path].encode()
    if path == "/assets/style.css":
        return "text/css", b"@import './nested.css';.fixture{background-image:url(./image.png)}"
    if path == "/assets/nested.css":
        return "text/css", b".fixture{border:2px solid transparent;border-image:url('https://webapi.amap.com/assets/nested.png') 1}"
    if path.endswith(".png"):
        return "image/png", PNG
    if path.endswith(".json"):
        return "application/json", b'{"fixture":true}'
    raise AssertionError("Unexpected upstream resource: " + path)


def initialize(page, actor, profile=None):
    return page.evaluate("""async ({actor,profile}) => {
        await ZXMapRequestProxy.initialize({enabled:true,provider:'amap',sessionId:actor,
            ...(profile ? {map_config_id:profile} : {})});
        return ZXMapRequestProxy.getConfig().contextToken;
    }""", {"actor": actor, "profile": profile})


def load_resources(page, label):
    result = page.evaluate("""async label => {
        const worker=new Worker(ZXMapRequestProxy.rewriteUrl('https://webapi.amap.com/assets/entry.mjs?case='+label),{type:'module'});
        const outcome=await new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>reject(Error('Worker deadline')),10000);
            worker.onmessage=event=>{clearTimeout(timer);resolve(event.data)};
            worker.onerror=event=>{clearTimeout(timer);reject(Error(event.message||'Worker error'))};
        }).finally(()=>worker.terminate());
        await new Promise((resolve,reject)=>{
            const style=document.createElement('link');style.rel='stylesheet';
            style.onload=resolve;style.onerror=()=>reject(Error('Stylesheet error'));
            style.href='https://webapi.amap.com/assets/style.css?case='+label;
            document.head.appendChild(style);
        });
        return outcome;
    }""", label)
    events = result["events"]
    assert sorted(events) == sorted(["dependency", "dependency-fetch", "absolute", "entry", "dynamic"]), result
    assert events.index("dependency") < events.index("dependency-fetch") < events.index("entry") < events.index("dynamic"), result
    assert result["methodResult"] == "unchanged", result
    page.wait_for_function("""() => performance.getEntriesByType('resource').some(entry=>entry.name.includes('/assets/nested.png'))
        && performance.getEntriesByType('resource').some(entry=>entry.name.includes('/assets/image.png'))""")


def check_blob_module_boundary(page, foreign_requests):
    start = len(foreign_requests)
    result = page.evaluate("""async () => {
        const source="import 'https://webapi.amap.com/assets/blob-import.mjs'; self.postMessage('loaded');";
        const url=URL.createObjectURL(new Blob([source],{type:'application/javascript'}));
        let worker;
        try {
            worker=new Worker(url,{type:'module'});
            const outcome=await new Promise(resolve=>{
                const timer=setTimeout(()=>resolve('deadline'),5000);
                worker.onmessage=()=>{clearTimeout(timer);resolve('loaded')};
                worker.onerror=event=>{event.preventDefault();clearTimeout(timer);resolve('worker-error')};
            });
            return {rejected:false,outcome};
        } catch(error) { return {rejected:true,message:error.message}; }
        finally { worker?.terminate();URL.revokeObjectURL(url); }
    }""")
    assert result.get("rejected"), {"blob_module": result, "direct_requests": foreign_requests[start:]}
    assert "blob" in result["message"].lower() and ("module" in result["message"].lower() or "模块" in result["message"]), result
    assert len(foreign_requests) == start, "Unsupported Blob modules must fail before any vendor request"


def run():
    config = JsonConfigAdapter.__new__(JsonConfigAdapter)
    config._data = profiles()
    valid_actors = {ACTOR_A, ACTOR_B}
    outbound = []
    app = Flask(__name__)
    app.secret_key = "offline-profile-fixture-cookie-signing"

    def login_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            actor = request.headers.get("X-Session-ID")
            if request.cookies.get("auth_token") != AUTH_TOKEN or actor not in valid_actors:
                return "", 401
            g.user, g.session_id = "fixture-user", actor
            return view(*args, **kwargs)
        return wrapped

    def authorize(user, token, actor, _view_all):
        return user == "fixture-user" and token == AUTH_TOKEN and actor in valid_actors

    def transport(_method, url, *, headers, **_kwargs):
        parsed = urlsplit(url)
        assert not ({"__map_context", "__map_module"} & dict(parse_qsl(parsed.query)).keys())
        assert "Cookie" not in headers and "Authorization" not in headers
        content_type, content = fixture_response(parsed.path)
        outbound.append({"path": parsed.path, "origin": headers["Origin"], "referer": headers["Referer"],
                         "mode": request.headers.get("Sec-Fetch-Mode"), "destination": request.headers.get("Sec-Fetch-Dest")})
        return SimpleNamespace(status_code=200, headers={"Content-Type": content_type}, content=content, close=lambda: None)

    @app.get("/")
    def index():
        return ('<!doctype html><html><head><script src="/scripts/map-request-proxy.js"></script></head>'
                '<body><div class="fixture" style="width:100px;height:100px"></div></body></html>')

    @app.get("/scripts/map-request-proxy.js")
    def proxy_script():
        return send_file(ROOT / "scripts/map-request-proxy.js", mimetype="application/javascript")

    with tempfile.TemporaryDirectory(prefix="map-proxy-profiles-browser-") as cache_dir:
        register_map_proxy_routes(app, login_required, lambda: config, authorize, transport=transport,
                                  tile_cache_dir=cache_dir,
                                  dns_resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))])
        server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=QuietRequestHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        app_origin = f"http://127.0.0.1:{server.server_port}"
        foreign_requests, browser_errors, worker_requests = [], [], []
        try:
            with sync_playwright() as playwright:
                browser_path = os.environ.get("MAP_SMOKE_BROWSER_PATH")
                browser = playwright.chromium.launch(headless=True, **({"executable_path": browser_path} if browser_path else {}))
                try:
                    context = browser.new_context(service_workers="block")
                    try:
                        context.add_cookies([{"name": "auth_token", "value": AUTH_TOKEN, "url": app_origin}])

                        def only_local(route):
                            if urlsplit(route.request.url).netloc == urlsplit(app_origin).netloc:
                                if urlsplit(route.request.url).path.endswith("/entry.mjs"):
                                    headers = route.request.all_headers()
                                    worker_requests.append({"mode": headers.get("sec-fetch-mode"), "destination": headers.get("sec-fetch-dest")})
                                route.continue_()
                            else:
                                foreign_requests.append(route.request.url)
                                route.abort()

                        context.route("**/*", only_local)
                        first, second = context.new_page(), context.new_page()
                        for page in (first, second):
                            page.set_default_timeout(15000)
                            page.on("pageerror", lambda error: browser_errors.append(str(error)))
                            page.goto(app_origin)
                        token_a = initialize(first, ACTOR_A, "front-one")
                        config.set("Map", "frontend_config_id", "back-two")
                        token_b = initialize(second, ACTOR_B, "back-two")
                        assert token_a and token_b and token_a != token_b
                        for page, label, expected_origin in ((first, "old-tab", "https://front-one.test"),
                                                             (second, "new-tab", "https://back-two.test")):
                            start = len(outbound)
                            try:
                                load_resources(page, label)
                            except Exception:
                                print(json.dumps({"worker_requests": worker_requests, "upstream": outbound, "browser_errors": browser_errors}))
                                raise
                            rows = outbound[start:]
                            assert len(rows) >= 10, rows
                            assert {row["origin"] for row in rows} == {expected_origin}, rows
                            assert {row["referer"] for row in rows} == {expected_origin + "/"}, rows
                        check_blob_module_boundary(first, foreign_requests)
                        assert initialize(first, ACTOR_A, "front-one") == token_a
                        assert initialize(second, ACTOR_B, "back-two") == token_b
                        valid_actors.remove(ACTOR_B)
                        check = """async token => (await fetch('/map-proxy/amap/https/webapi.amap.com/assets/alive.json?__map_context='+token)).status"""
                        assert first.evaluate(check, token_a) == 200, "A valid tab cannot depend on another tab's actor"
                        assert second.evaluate(check, token_b) == 401, "Revoked actor must not borrow another tab's authorization"
                    finally:
                        context.close()

                    valid_actors.add(ACTOR_B)
                    config._data = {"Map": {"provider": "amap", "frontend_proxy_enabled": "true",
                                            "providers": {"amap": {"js_key": "legacy-fixture",
                                                                   "backend_page_origin": "https://legacy-front.test"}}}}
                    legacy_context = browser.new_context(service_workers="block")
                    try:
                        legacy_context.add_cookies([{"name": "auth_token", "value": AUTH_TOKEN, "url": app_origin}])
                        legacy_context.route("**/*", only_local)
                        page = legacy_context.new_page()
                        page.on("pageerror", lambda error: browser_errors.append(str(error)))
                        page.goto(app_origin)
                        assert initialize(page, ACTOR_A), "Pre-migration pages also need an origin snapshot"
                        config._data = profiles()
                        config.set("Map", "frontend_config_id", "back-two")
                        start = len(outbound)
                        load_resources(page, "legacy-migration")
                        assert {row["origin"] for row in outbound[start:]} == {"https://legacy-front.test"}
                    finally:
                        legacy_context.close()
                    assert not foreign_requests, foreign_requests
                    assert not browser_errors, browser_errors
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive(), "Fixture server thread leaked"
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", server.server_port)) != 0, "Fixture listener leaked"
    print(json.dumps({"passed": True, "scenarios": ["profile-switch-workers-css", "shared-cookie-actor-isolation",
                                                    "blob-module-fail-closed", "legacy-migration-snapshot"], "upstream_requests": len(outbound),
                      "foreign_requests": len(foreign_requests), "services_closed": True}))


if __name__ == "__main__":
    run()
