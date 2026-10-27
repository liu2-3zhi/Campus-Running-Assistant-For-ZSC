"""Opt-in live SDK/planner checks through the production backend proxy.

Pass MAP_SMOKE_CREDENTIALS as a JSON object keyed by provider. Each value has
key, origin and optional securityJsCode. No credentials or raw responses are
written to disk. Run explicitly; this is not an offline unit test.
"""

from __future__ import annotations

import ast
import functools
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask, g, request, send_file
from playwright.sync_api import sync_playwright
from werkzeug.serving import WSGIRequestHandler, make_server


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_request_proxy import PROXY_HOSTS, _MapProxy, register_map_proxy_routes


class QuietRequestHandler(WSGIRequestHandler):
    def log_request(self, *_args, **_kwargs):
        pass

    def log_error(self, *_args, **_kwargs):
        pass


def production_planner(provider):
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    name = f"_plan_route_path_with_{provider}_runtime"
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js":
            return ast.literal_eval(node.args[1])
    raise AssertionError(f"{provider}: production planner not found")


def safe_error(error, credentials):
    message = str(error)
    for credential in credentials.values():
        for name in ("key", "securityJsCode"):
            if credential.get(name):
                message = message.replace(credential[name], "<redacted>")
    return re.sub(r"https?://[^\s]+", "<url>", message)[:400]


def browser_step(page, source, args=None, timeout_ms=30000):
    return page.evaluate("""async ({source,args,timeoutMs}) => {
        let timer;
        try { return await Promise.race([
            Promise.resolve().then(() => (0,eval)('('+source+')')(args)),
            new Promise((_,reject) => {timer=setTimeout(() => reject(Error('browser step deadline')),timeoutMs)})
        ]); } finally {clearTimeout(timer)}
    }""", {"source": source, "args": args, "timeoutMs": timeout_ms})


MAP_CHECK = """async ({provider,key}) => {
    if(provider==='tencent' && !window.TMap) await new Promise((resolve,reject)=>{
        const script=document.createElement('script');script.onload=resolve;script.onerror=()=>reject(Error('SDK load failed'));
        script.src='https://map.qq.com/api/gljs?v=1.exp&key='+encodeURIComponent(key);document.head.appendChild(script);
    });
    if(provider==='tianditu' && !window.T) await new Promise((resolve,reject)=>{
        const script=document.createElement('script');script.onload=resolve;script.onerror=()=>reject(Error('SDK load failed'));
        script.src='https://api.tianditu.gov.cn/api?v=4.0&tk='+encodeURIComponent(key);document.head.appendChild(script);
    });
    if(provider==='amap') {
        window.__smokeMap=new AMap.Map('map',{zoom:16,center:[116.397128,39.916527]});
        const line=new AMap.Polyline({path:[[116.397128,39.916527],[116.398128,39.916527]]});
        const marker=new AMap.Marker({position:[116.397128,39.916527]});
        window.__smokeMap.add([line,marker]);line.setPath([[116.398128,39.916527],[116.397128,39.916527]]);marker.setPosition([116.398128,39.916527]);
    } else if(provider==='tencent') {
        window.__smokeMap=new TMap.Map('map',{zoom:16,center:new TMap.LatLng(39.916527,116.397128)});
    } else if(provider==='tianditu') {
        window.__smokeMap=new T.Map('map');window.__smokeMap.centerAndZoom(new T.LngLat(116.397128,39.916527),16);
        const line=new T.Polyline([new T.LngLat(116.397128,39.916527),new T.LngLat(116.398128,39.916527)]);
        const marker=new T.Marker(new T.LngLat(116.397128,39.916527));
        window.__smokeMap.addOverLay(line);window.__smokeMap.addOverLay(marker);
        line.setLngLats([new T.LngLat(116.398128,39.916527),new T.LngLat(116.397128,39.916527)]);line.setColor('#0088ff');marker.setLngLat(new T.LngLat(116.398128,39.916527));
    } else if(provider==='baidu') {
        window.__smokeMap=new BMap.Map('map');window.__smokeMap.centerAndZoom(new BMap.Point(116.4035,39.9225),16);
        const line=new BMap.Polyline([new BMap.Point(116.4035,39.9225),new BMap.Point(116.4045,39.9225)]);
        const marker=new BMap.Marker(new BMap.Point(116.4035,39.9225));
        window.__smokeMap.addOverlay(line);window.__smokeMap.addOverlay(marker);
        line.setPath([new BMap.Point(116.4045,39.9225),new BMap.Point(116.4035,39.9225)]);marker.setPosition(new BMap.Point(116.4045,39.9225));
    }
    return !!window.__smokeMap;
}"""


def run(credentials, *, render_ui=False, render_legacy=False):
    assert credentials and set(credentials) <= PROXY_HOSTS.keys(), "explicit provider credentials required"
    assert not (render_ui and render_legacy), "run Vue and legacy rendering checks separately"
    session_id = "11111111-1111-4111-8111-111111111111"
    auth_token = secrets.token_urlsafe(32)
    app = Flask(__name__)
    app.secret_key = secrets.token_urlsafe(32)
    config = {"Map": {"frontend_proxy_enabled": True, "providers": {}}}
    for provider, credential in credentials.items():
        parsed = urlsplit(credential["origin"])
        assert parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username
        config["Map"]["providers"][provider] = {"backend_page_origin": f"{parsed.scheme}://{parsed.netloc}"}
    outbound = []
    ui_bundle = None
    if render_ui:
        bundle_env = {key: value for key, value in os.environ.items() if key != "MAP_SMOKE_CREDENTIALS"}
        compiled = subprocess.run(["node", str(ROOT / "tests" / "map_ui_browser_fixture.mjs")],
                                  cwd=ROOT, env=bundle_env, capture_output=True, text=True, encoding="utf-8", timeout=90)
        if compiled.returncode:
            raise RuntimeError("Vue acceptance fixture build failed: " + compiled.stderr[-1500:])
        ui_bundle = json.loads(compiled.stdout)

    def login_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if request.cookies.get("auth_token") != auth_token or request.headers.get("X-Session-ID") != session_id:
                return "", 401
            g.user = "proxy-smoke"
            g.session_id = session_id
            return view(*args, **kwargs)
        return wrapped

    def transport(method, url, *, headers, body, timeout):
        parsed = urlsplit(url)
        assert "Cookie" not in headers and "Authorization" not in headers
        provider = next(name for name, hosts in PROXY_HOSTS.items() if parsed.hostname in hosts)
        expected = config["Map"]["providers"][provider]["backend_page_origin"]
        assert headers["Origin"] == expected and headers["Referer"] == expected + "/"
        row = {"provider": provider, "host": parsed.hostname, "path": safe_error(parsed.path, credentials)}
        outbound.append(row)
        try:
            response = _MapProxy._request_upstream(method, url, headers=headers, body=body, timeout=timeout)
            row["status"] = response.status_code
            row["content_type"] = response.headers.get("Content-Type", "")
            return response
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise

    runtime_config = SimpleNamespace(get=lambda section, key, fallback=None: config.get(section, {}).get(key, fallback))
    register_map_proxy_routes(app, login_required, lambda: runtime_config,
                              lambda user, token, sid, _view: user == "proxy-smoke" and token == auth_token and sid == session_id,
                              transport=transport)

    @app.get("/")
    def page():
        if render_ui:
            return '<!doctype html><html><head><link rel="stylesheet" href="/map-ui.css"></head><body><div id="map-ui"></div><script src="/proxy.js"></script><script type="module" src="/map-ui.js"></script></body></html>'
        return '<!doctype html><html><head></head><body><div id="map" style="width:800px;height:600px"></div></body></html>'

    @app.get("/map-ui.js")
    def ui_script():
        return app.response_class(ui_bundle["files"]["map-ui.js"], mimetype="application/javascript")

    @app.get("/fixture/<path:name>")
    def ui_chunk(name):
        content = ui_bundle["files"].get("fixture/" + name)
        return app.response_class(content or "", status=200 if content else 404, mimetype="application/javascript")

    @app.get("/map-ui.css")
    def ui_style():
        return app.response_class('html,body,#map-ui{margin:0;width:100%;height:100%}.h-full{height:100%}.w-full{width:100%}.relative{position:relative}' + ui_bundle["css"], mimetype="text/css")

    @app.get("/proxy.js")
    def proxy_script():
        return send_file(ROOT / "scripts" / "map-request-proxy.js", mimetype="application/javascript")

    @app.get("/legacy-fixture.js")
    def legacy_fixture():
        return send_file(ROOT / "tests" / "legacy_map_browser_fixture.js", mimetype="application/javascript")

    @app.get("/legacy-scripts/<name>")
    def legacy_script(name):
        if name not in {"legacy-map-runtime.js", "legacy-map-render.js"}:
            return "", 404
        return send_file(ROOT / "scripts" / name, mimetype="application/javascript")

    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=QuietRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    app_origin = f"http://127.0.0.1:{server.server_port}"
    results = []
    try:
        with sync_playwright() as playwright:
            browser_path = os.environ.get("MAP_SMOKE_BROWSER_PATH")
            browser = playwright.chromium.launch(headless=True, **({"executable_path": browser_path} if browser_path else {}))
            try:
                for provider, credential in credentials.items():
                    context = browser.new_context(service_workers="block")
                    try:
                        context.add_cookies([{"name": "auth_token", "value": auth_token, "url": app_origin}])
                        page = context.new_page()
                        page.set_default_timeout(65000)
                        direct = []
                        failures = []
                        runtime_errors = []
                        console_errors = []
                        def record_request(req):
                            parsed = urlsplit(req.url)
                            if parsed.hostname and parsed.hostname != "127.0.0.1":
                                direct.append({"host": parsed.hostname, "path": safe_error(parsed.path, credentials), "type": req.resource_type})
                        def record_response(response):
                            parsed = urlsplit(response.url)
                            if parsed.path.startswith("/map-proxy/") and response.status >= 400:
                                failures.append({"status": response.status, "path": safe_error(parsed.path, credentials)})
                            if parsed.path.startswith("/map-proxy/") and response.request.resource_type == "script" and "javascript" not in response.headers.get("content-type", ""):
                                failures.append({"status": response.status, "path": safe_error(parsed.path, credentials), "script_mime": response.headers.get("content-type", "")})
                        page.on("request", record_request)
                        page.on("response", record_response)
                        page.on("pageerror", lambda error: runtime_errors.append(safe_error(getattr(error, "stack", None) or error, credentials)))
                        page.on("console", lambda message: console_errors.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                        page.on("dialog", lambda dialog: dialog.dismiss())
                        page.goto(app_origin, wait_until="domcontentloaded")
                        if not render_ui:
                            page.add_script_tag(url=app_origin + "/proxy.js")
                        page.evaluate("""async ({provider, sessionId}) => {
                            await ZXMapRequestProxy.initialize({enabled:true,provider,sessionId});
                        }""", {"provider": provider, "sessionId": session_id})
                        points = [[116.397128, 39.916527], [116.398128, 39.916527]]
                        params = {"api_retries": 0, "api_fallback_line": False, "api_retry_delay_s": 0, "api_queue_interval_s": 0}
                        args = [points, credential["key"], params]
                        if provider == "amap":
                            args += [["AMap.Walking"], "walking", credential.get("securityJsCode", "")]
                        else:
                            args += ["walking"]
                        started = time.monotonic()
                        map_ready = False
                        route = {}
                        try:
                            route = page.evaluate("""async ({source,args}) => {
                                let timer;
                                try { return await Promise.race([(0,eval)('('+source+')')(args),
                                    new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('planner deadline')),60000)})]); }
                                finally { clearTimeout(timer); }
                            }""", {"source": production_planner(provider), "args": args})
                            if render_ui:
                                # A backend planner has its own page in production. Do not mix its
                                # direct SDK loader with the frontend component's SDK loader.
                                page.goto(app_origin, wait_until="domcontentloaded")
                                browser_step(page, "args => mountMapAcceptance(args)", {"provider": provider, "key": credential["key"], "securityJsCode": credential.get("securityJsCode", ""), "sessionId": session_id})
                                page.wait_for_function("window.mapAcceptance?.ready()", timeout=30000)
                                initial = page.evaluate("mapAcceptance.seed()")
                                progress = page.evaluate("mapAcceptance.progress(2)")
                                assert initial["lines"] and progress["lines"], "route disappeared on progress"
                                expected = progress["expectedRunner"]
                                assert any(point and point[0] is not None and point[1] is not None and abs(point[0] - expected[0]) < 1e-6 and abs(point[1] - expected[1]) < 1e-6 for point in progress["points"]), f"runner SDK coordinate mismatch: expected {expected}, actual {progress['points']}"
                                assert progress["businessPoint"] == [116.397428, 39.916527], "business coordinates mutated"
                                assert initial["cameraWrites"] == progress["cameraWrites"], "progress reset viewport"
                                page.evaluate("mapAcceptance.progress(4)")
                                page.evaluate("mapAcceptance.finish()")
                                switched = page.evaluate("mapAcceptance.seed(1, 1)")
                                assert switched["lines"], "task switch lost route"
                                page.evaluate("mapAcceptance.destroy()")
                                page.evaluate("args => mountMapAcceptance(args)", {"provider": provider, "key": credential["key"], "securityJsCode": credential.get("securityJsCode", ""), "sessionId": session_id})
                                page.wait_for_function("window.mapAcceptance?.ready()", timeout=30000)
                                restored = page.evaluate("mapAcceptance.seed(1, 2)")
                                assert restored["lines"], "remount lost restored route"
                                page.set_viewport_size({"width": 390, "height": 844})
                                page.wait_for_timeout(400)
                                map_ready = page.evaluate("mapAcceptance.ready()")
                                route["ui_verified"] = True
                            elif not render_legacy:
                                map_ready = page.evaluate(MAP_CHECK, {"provider": provider, "key": credential["key"]})
                            if render_legacy:
                                page.goto(app_origin, wait_until="domcontentloaded")
                                if not render_ui:
                                    page.add_script_tag(url=app_origin + "/proxy.js")
                                page.evaluate("async ({provider,sessionId}) => ZXMapRequestProxy.initialize({enabled:true,provider,sessionId})", {"provider": provider, "sessionId": session_id})
                                browser_step(page, "async ({source,args}) => (0,eval)('('+source+')')(args)", {"source": production_planner(provider), "args": args}, timeout_ms=60000)
                                page.evaluate("() => document.getElementById('map')?.remove()")
                                page.add_script_tag(url=app_origin + "/legacy-fixture.js")
                                for mobile in (False, True):
                                    page.set_viewport_size({"width": 390 if mobile else 1280, "height": 844 if mobile else 800})
                                    browser_step(page, "args => mountLegacyMapAcceptance(args)", {"provider": provider, "key": credential["key"], "securityJsCode": credential.get("securityJsCode", ""), "sessionId": session_id, "mobile": mobile})
                                    page.wait_for_function("window.legacyMapAcceptance?.ready()")
                                    initial = browser_step(page, "() => legacyMapAcceptance.seed()")
                                    progress = browser_step(page, "() => legacyMapAcceptance.progress(2)")
                                    assert initial["lines"] and progress["lines"] and not progress["renderErrors"], "legacy route rendering failed"
                                    expected = progress["expectedRunner"]
                                    assert progress["runner"] and max(abs(a - b) for a, b in zip(progress["runner"], expected)) < 1e-7, "legacy runner SDK coordinate mismatch"
                                    moved = browser_step(page, "() => legacyMapAcceptance.moveView()")
                                    continued = browser_step(page, "() => legacyMapAcceptance.progress(4)")
                                    assert moved["cameraWrites"] == continued["cameraWrites"], "legacy progress reset viewport"
                                    browser_step(page, "() => legacyMapAcceptance.finish()")
                                    switched = browser_step(page, "() => legacyMapAcceptance.seed(1,1)")
                                    assert switched["lines"] and switched["taskIndex"] == 1, "legacy task switch lost route"
                                    page.evaluate("legacyMapAcceptance.destroy()")
                                route["legacy_ui_verified"] = True
                                map_ready = True
                        except Exception as error:
                            route["error" if not route else "map_error"] = safe_error(error, credentials)
                        page.wait_for_timeout(2000)
                        result = {"provider": provider, "origin": config["Map"]["providers"][provider]["backend_page_origin"],
                                  "route_points": len(route.get("path", [])), "route_success": not bool(route.get("error")),
                                  "map_ready": map_ready,
                                  "elapsed_ms": round((time.monotonic() - started) * 1000),
                                  "proxy_requests": sum(item["provider"] == provider for item in outbound),
                                  "upstream_failures": [item for item in outbound if item["provider"] == provider and (item.get("status", 0) >= 300 or item.get("error_type"))],
                                  "direct_requests": direct, "proxy_failures": failures, "script_errors": len(runtime_errors),
                                  "script_error_messages": list(dict.fromkeys(runtime_errors))[:5]}
                        result["console_error_messages"] = list(dict.fromkeys(console_errors))[:8]
                        if render_ui:
                            result["ui_verified"] = route.get("ui_verified", False)
                        if render_legacy:
                            result["legacy_ui_verified"] = route.get("legacy_ui_verified", False)
                        if route.get("error"):
                            result["error"] = safe_error(route["error"], credentials)
                        if route.get("map_error"):
                            result["map_error"] = route["map_error"]
                        results.append(result)
                        if os.environ.get("MAP_SMOKE_PROGRESS") == "1":
                            print(json.dumps(result, ensure_ascii=True), file=sys.stderr, flush=True)
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    return results


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    credentials = json.loads(os.environ.get("MAP_SMOKE_CREDENTIALS", "{}"))
    try:
        results = run(credentials, render_ui=os.environ.get("MAP_SMOKE_RENDER_UI") == "1", render_legacy=os.environ.get("MAP_SMOKE_RENDER_LEGACY") == "1")
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(results, ensure_ascii=True, indent=2))
    raise SystemExit(0 if all(row["route_success"] and row["route_points"] >= 2 and row["map_ready"]
                             and not row.get("map_error") and row.get("ui_verified", True)
                             and row.get("legacy_ui_verified", True)
                             and not row["direct_requests"] and not row["proxy_failures"] for row in results) else 1)
