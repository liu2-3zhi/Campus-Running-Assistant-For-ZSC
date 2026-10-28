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


def evaluate_acceptance(row):
    """Keep transport/rendering and teardown outcomes separate, and require both."""
    rounds = row.get("rounds", [])
    functional = bool(row.get("route_success") and row.get("route_points", 0) >= 2
                      and row.get("map_ready") and not row.get("map_error")
                      and row.get("ui_verified", True) and row.get("legacy_ui_verified", True)
                      and not row.get("proxy_failures") and not row.get("upstream_failures")
                      and not (row.get("proxy_enabled", True) and row.get("direct_requests"))
                      and all(item.get("functional_pass", False) for item in rounds))
    lifecycle = not bool(row.get("script_errors") or row.get("unhandled_rejections")
                         or row.get("console_error_messages")) and all(
                             item.get("lifecycle_pass", False) for item in rounds)
    return {**row, "functional_pass": functional, "lifecycle_pass": lifecycle,
            "passed": functional and lifecycle}


def smoke_results_passed(rows):
    return bool(rows) and all(evaluate_acceptance(row)["passed"] for row in rows)


def summarize_upstream_attempts(rows, provider):
    attempts = [row for row in rows if row['provider'] == provider]
    failed = lambda row: row.get('status', 0) >= 300 or bool(row.get('error_type'))
    grouped = {}
    for index, row in enumerate(attempts):
        grouped.setdefault(row.get('request_id', ('untracked', index)), []).append(row)
    return {
        'upstream_attempt_failures': [row for row in attempts if failed(row)],
        'upstream_failures': [group[-1] for group in grouped.values() if failed(group[-1])],
        'recovered_upstream_requests': sum(len(group) > 1 and any(failed(row) for row in group[:-1])
                                           and not failed(group[-1]) for group in grouped.values()),
    }


class MapNetworkProbe:
    """Observe browser network phases without replacing SDK/proxy fetch hooks."""

    def __init__(self):
        self.contexts = {}
        self.proxies = {}
        self.counts = {"context_started": 0, "context_headers": 0, "context_finished": 0,
                       "context_failed": 0, "context_last_status": 0}

    def request_started(self, request):
        path = urlsplit(request.url).path
        if path == "/api/map-proxy/context":
            self.contexts[id(request)] = request
            self.counts["context_started"] += 1
        elif path.startswith("/map-proxy/"):
            self.proxies[id(request)] = request

    def response_received(self, response):
        if id(response.request) in self.contexts:
            self.counts["context_headers"] += 1
            self.counts["context_last_status"] = response.status

    def request_finished(self, request):
        if self.contexts.pop(id(request), None) is not None:
            self.counts["context_finished"] += 1
        self.proxies.pop(id(request), None)

    def request_failed(self, request):
        if self.contexts.pop(id(request), None) is not None:
            self.counts["context_failed"] += 1
        self.proxies.pop(id(request), None)

    def snapshot(self):
        timing = []
        for request in list(self.contexts.values())[:5]:
            try:
                timing.append({field: request.timing.get(field, -1) for field in ("requestStart", "responseStart", "responseEnd")})
            except Exception:
                timing.append({"unavailable": True})
        types = {}
        for request in self.proxies.values():
            types[request.resource_type] = types.get(request.resource_type, 0) + 1
        return {**self.counts, "context_pending": len(self.contexts),
                "context_pending_timing": timing, "proxy_pending": len(self.proxies), "proxy_pending_types": types}

    def attach(self, page):
        if not hasattr(page, "on"):
            return
        for event, callback in self.bindings():
            page.on(event, callback)

    def detach(self, page):
        if not hasattr(page, "remove_listener"):
            return
        for event, callback in self.bindings():
            page.remove_listener(event, callback)

    def bindings(self):
        return (("request", self.request_started), ("response", self.response_received),
                ("requestfinished", self.request_finished), ("requestfailed", self.request_failed))


def _safe_map_debug_state(value, credentials):
    if not isinstance(value, dict):
        return None
    fields = ("map_ready", "active_provider", "map_instance_present", "placeholder_visible",
              "placeholder_text", "container_width", "container_height", "sdk_t_present",
              "native_destroy_type", "native_remove_type", "native_clear_overlays_type", "destroyed",
              "proxy_initialize_started", "proxy_initialize_completed", "proxy_initialize_rejected",
              "proxy_initialize_pending", "proxy_initialize_last_error")
    return {field: value[field] if isinstance(value[field], (bool, int, float)) else safe_error(value[field], credentials)
            for field in fields if field in value and isinstance(value[field], (str, bool, int, float))}


def exercise_map_lifecycle(page, provider, credential, *, session_id, render_ui,
                           errors, rejections, console, proxy_enabled=True,
                           script_base="/legacy-scripts/", rounds=None):
    """Run the same production UI lifecycle in direct and proxy browser contexts."""
    rounds = rounds if rounds is not None else (3 if provider in {"tencent", "baidu"} else 1)
    assert 1 <= rounds <= 10
    fixture = "mapAcceptance" if render_ui else "legacyMapAcceptance"
    mount = "mountMapAcceptance" if render_ui else "mountLegacyMapAcceptance"
    rows = []
    network = MapNetworkProbe()
    network.attach(page)
    for mobile in (False, True):
        page.set_viewport_size({"width": 390 if mobile else 1280, "height": 844 if mobile else 800})
        args = {"provider": provider, "key": credential["key"],
                "securityJsCode": credential.get("securityJsCode", ""),
                "sessionId": session_id, "mobile": mobile,
                "frontendProxyEnabled": proxy_enabled, "scriptBase": script_base}
        for index in range(rounds):
            baseline = (len(errors), len(rejections), len(console))
            row = {"viewport": "mobile" if mobile else "desktop", "round": index + 1,
                   "progress_updates": 0, "functional_pass": False, "lifecycle_pass": False}
            try:
                browser_step(page, f"args => {mount}(args)", args)
                page.wait_for_function(f"window.{fixture}?.ready()", timeout=30000)
                initial = browser_step(page, f"() => {fixture}.seed(0,0)")
                row["initial_snapshot"] = _safe_map_debug_state(initial, {provider: credential}) if isinstance(initial, dict) else initial
                assert initial["lines"], "initial task route missing"
                for update in range(10):
                    point_index = update // 2 + 1
                    progress = browser_step(page, f"index => {fixture}.progress(index)", point_index)
                    assert progress["lines"] and not progress.get("renderErrors"), "route disappeared on progress"
                    expected = progress["expectedRunner"]
                    assert any(point and all(value is not None for value in point)
                               and max(abs(a - b) for a, b in zip(point, expected)) < 1e-6
                               for point in progress["points"]), "runner SDK coordinate mismatch"
                    expected_business = [[116.397128, 39.916527], [116.397428, 39.916527],
                                         [116.397728, 39.916527], [116.398128, 39.916527],
                                         [116.398528, 39.916527]][point_index - 1]
                    assert max(abs(a - b) for a, b in zip(progress["businessPoint"], expected_business)) < 1e-10, "business coordinates mutated"
                    assert initial["cameraWrites"] == progress["cameraWrites"], "progress reset viewport"
                    row["progress_updates"] += 1
                browser_step(page, f"() => {fixture}.finish()")
                switched = browser_step(page, f"() => {fixture}.seed(1,1)")
                assert switched["lines"], "task switch lost route"
                released = browser_step(page, f"() => {fixture}.destroy()")
                assert released and released["instrumentation_restored"], "fixture instrumentation was not restored"
                browser_step(page, f"args => {mount}(args)", args)
                page.wait_for_function(f"window.{fixture}?.ready()", timeout=30000)
                restored = browser_step(page, f"() => {fixture}.seed(1,2)")
                assert restored["lines"], "remount lost restored route"
                released = browser_step(page, f"() => {fixture}.destroy()")
                assert released and released["instrumentation_restored"]
                row["functional_pass"] = True
            except Exception as error:
                row["error"] = safe_error(error, {provider: credential})
                row["network_debug"] = network.snapshot()
                try:
                    debug = browser_step(page, f"() => window.{fixture}?.debugState?.() || null", timeout_ms=1000)
                    safe_debug = _safe_map_debug_state(debug, {provider: credential})
                    if safe_debug is not None:
                        row["debug_state"] = safe_debug
                except Exception as debug_error:
                    row["debug_error"] = safe_error(debug_error, {provider: credential})
                try:
                    browser_step(page, f"() => window.{fixture}?.destroy()")
                except Exception as cleanup_error:
                    row["cleanup_error"] = safe_error(cleanup_error, {provider: credential})
            # Observe queued SDK callbacks after teardown; this is not a delay before cleanup.
            page.wait_for_timeout(500)
            row["script_errors"] = len(errors) - baseline[0]
            row["unhandled_rejections"] = len(rejections) - baseline[1]
            row["console_errors"] = len(console) - baseline[2]
            row["lifecycle_pass"] = not any(row[name] for name in ("script_errors", "unhandled_rejections", "console_errors")) and not row.get("cleanup_error")
            rows.append(row)
    network.detach(page)
    return rows


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
        if not getattr(g, 'map_smoke_request_id', None):
            g.map_smoke_request_id = secrets.token_hex(6)
        row = {"provider": provider, "host": parsed.hostname, "path": safe_error(parsed.path, credentials),
               "request_id": g.map_smoke_request_id}
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
                        unhandled_rejections = []
                        page.expose_function("recordSmokeRejection", lambda value: unhandled_rejections.append(safe_error(value, credentials)))
                        page.add_init_script("addEventListener('unhandledrejection', event => { window.recordSmokeRejection(String(event.reason?.stack || event.reason || 'unhandled rejection')); });")
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
                        lifecycle_rounds = []
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
                                lifecycle_rounds = exercise_map_lifecycle(
                                    page, provider, credential, session_id=session_id, render_ui=True,
                                    errors=runtime_errors, rejections=unhandled_rejections, console=console_errors)
                                map_ready = all(row["functional_pass"] for row in lifecycle_rounds)
                                route["ui_verified"] = map_ready
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
                                lifecycle_rounds = exercise_map_lifecycle(
                                    page, provider, credential, session_id=session_id, render_ui=False,
                                    errors=runtime_errors, rejections=unhandled_rejections, console=console_errors)
                                map_ready = all(row["functional_pass"] for row in lifecycle_rounds)
                                route["legacy_ui_verified"] = map_ready
                        except Exception as error:
                            route["error" if not route else "map_error"] = safe_error(error, credentials)
                        page.wait_for_timeout(2000)
                        result = {"provider": provider, "origin": config["Map"]["providers"][provider]["backend_page_origin"],
                                  "proxy_enabled": True, "rounds": lifecycle_rounds,
                                  "route_points": len(route.get("path", [])), "route_success": not bool(route.get("error")),
                                  "map_ready": map_ready,
                                  "elapsed_ms": round((time.monotonic() - started) * 1000),
                                  "proxy_requests": sum(item["provider"] == provider for item in outbound),
                                  **summarize_upstream_attempts(outbound, provider),
                                  "direct_requests": direct, "proxy_failures": failures, "script_errors": len(runtime_errors),
                                  "unhandled_rejections": len(unhandled_rejections),
                                  "script_error_messages": list(dict.fromkeys(runtime_errors))[:5]}
                        result["unhandled_rejection_messages"] = list(dict.fromkeys(unhandled_rejections))[:5]
                        result["console_error_messages"] = list(dict.fromkeys(console_errors))[:8]
                        if render_ui:
                            result["ui_verified"] = route.get("ui_verified", False)
                        if render_legacy:
                            result["legacy_ui_verified"] = route.get("legacy_ui_verified", False)
                        if route.get("error"):
                            result["error"] = safe_error(route["error"], credentials)
                        if route.get("map_error"):
                            result["map_error"] = route["map_error"]
                        result = evaluate_acceptance(result)
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
    raise SystemExit(0 if smoke_results_passed(results) else 1)
