"""Opt-in real multi-account SDK/proxy acceptance; credentials only from env.

MAP_SMOKE_CREDENTIALS has the same provider/key/origin contract as the single
account runner. MAP_SMOKE_MULTI_FRONTENDS accepts vue,legacy (both by default).
MAP_SMOKE_MULTI_PROXY=0 selects direct SDK requests on a locally fulfilled
authorized origin; no application request is sent to that domain.
"""

from __future__ import annotations

import functools
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask, g, request
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from map_request_proxy import PROXY_HOSTS, _MapProxy, register_map_proxy_routes
from browser_map_proxy_smoke import (
    QuietRequestHandler, browser_step, production_planner, safe_error,
    summarize_upstream_attempts,
)

SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_C = "33333333-3333-4333-8333-333333333333"


def assert_markers(snapshot, positions, expected, identities=None):
    """Check the native SDK state, not only the application position store."""
    assert snapshot["markerIds"] == sorted(positions), "multi-account marker membership mismatch"
    for username, position in positions.items():
        actual = snapshot["markers"][username]
        point = actual["point"]
        assert point and len(point) == 2, "SDK marker exposes no position"
        assert all(abs(float(point[i]) - float(expected[username][i])) < 2e-7 for i in range(2)), f"multi-account SDK coordinate mismatch for {username}: {point} != {expected[username]}"
        business = snapshot["businessPositions"][username]
        assert business["lon"] == position["lon"] and business["lat"] == position["lat"], "display conversion mutated business coordinates"
        if identities is not None:
            assert actual["identity"] == identities[username], "position update rebuilt an existing account marker"


def evaluate_multi_result(row):
    rounds = row.get('rounds') or []
    functional = bool(rounds) and bool(row.get('route_success')) and row.get('route_points', 0) >= 2 and not row.get('map_error') and all(item.get('functional_pass') for item in rounds)
    lifecycle = not any(row.get(name) for name in ('script_errors', 'unhandled_rejections', 'console_error_messages', 'proxy_failures', 'upstream_failures')) and all(item.get('lifecycle_pass') for item in rounds)
    return {**row, 'functional_pass': functional, 'lifecycle_pass': lifecycle,
            'passed': functional and lifecycle and not (row.get('proxy_enabled') and row.get('direct_requests'))}


def exercise_multi_map(page, provider, credential, frontend, *, proxy_enabled, errors, rejections, console):
    rows = []
    rounds = 3 if provider in {"tencent", "baidu"} else 1
    for mobile in (False, True):
        page.set_viewport_size({"width": 390 if mobile else 1280, "height": 844 if mobile else 800})
        for index in range(rounds):
            baseline = len(errors), len(rejections), len(console)
            row = {"viewport": "mobile" if mobile else "desktop", "round": index + 1,
                   "functional_pass": False, "lifecycle_pass": False}
            options = {"provider": provider, "key": credential["key"],
                       "securityJsCode": credential.get("securityJsCode", ""),
                       "sessionId": SESSION_A, "mobile": mobile, "frontendProxyEnabled": proxy_enabled}
            try:
                row['stage'] = 'mount'
                browser_step(page, "async options => window.mountMultiMapAcceptance(options)", options, timeout_ms=65000)
                page.wait_for_function("window.multiMapAcceptance?.ready()", timeout=65000)
                positions = {"first": {"lon": 116.397128, "lat": 39.916527, "name": "Runner A"},
                             "second": {"lon": 116.398128, "lat": 39.916827, "name": "Runner B"}}
                row['stage'] = 'seed'
                snapshot = browser_step(page, "async positions => window.multiMapAcceptance.seed(positions)", positions)
                expected = lambda values: page.evaluate("positions => Object.fromEntries(Object.entries(positions).map(([name,pos]) => [name,multiMapAcceptance.expectedPoint([pos.lon,pos.lat])]))", values)
                assert_markers(snapshot, positions, expected(positions))
                identities = {name: value["identity"] for name, value in snapshot["markers"].items()}
                for step in range(10):
                    row['stage'] = f'progress_{step + 1}'
                    positions["first"] = {"lon": 116.397128 + step * .00002, "lat": 39.916527, "name": "Runner A"}
                    snapshot = browser_step(page, "async ({name,pos}) => window.multiMapAcceptance.update(name,pos)", {"name": "first", "pos": positions["first"]})
                    assert_markers(snapshot, positions, expected(positions), identities)
                row['stage'] = 'remove_account'
                snapshot = browser_step(page, "async () => window.multiMapAcceptance.remove('second')")
                del positions["second"]
                assert_markers(snapshot, positions, expected(positions), {"first": identities["first"]})
                row['stage'] = 'switch_session'
                switched = browser_step(page, "async session => window.multiMapAcceptance.switchSession(session)", SESSION_C)
                if frontend == 'vue':
                    assert switched["acceptedOldSnapshot"] is False, "old-session snapshot was accepted"
                else:
                    assert switched["oldMarkersCleared"] is True, "departed legacy session retained markers"
                if switched.get("remountRequired"):
                    options["sessionId"] = SESSION_C
                    browser_step(page, "async options => window.mountMultiMapAcceptance(options)", options, timeout_ms=65000)
                page.wait_for_function("window.multiMapAcceptance?.ready()", timeout=65000)
                snapshot = page.evaluate("window.multiMapAcceptance.snapshot()")
                assert snapshot["sessionId"] == SESSION_C and not snapshot["markerIds"], "departed session markers survived navigation"
                positions = {"current": {"lon": 116.397728, "lat": 39.916627, "name": "Runner C"}}
                row['stage'] = 'current_session_seed'
                snapshot = browser_step(page, "async positions => window.multiMapAcceptance.seed(positions)", positions)
                assert_markers(snapshot, positions, expected(positions))
                row['stage'] = 'destroy'
                disposed = browser_step(page, "async () => window.multiMapAcceptance.destroy()")
                assert disposed["rootEmpty"] and disposed["markersCleared"], "multi-account teardown retained application resources"
                options["sessionId"] = SESSION_C
                row['stage'] = 'immediate_remount'
                browser_step(page, "async options => window.mountMultiMapAcceptance(options)", options, timeout_ms=65000)
                page.wait_for_function("window.multiMapAcceptance?.ready()", timeout=65000)
                snapshot = browser_step(page, "async positions => window.multiMapAcceptance.seed(positions)", positions)
                assert_markers(snapshot, positions, expected(positions))
                disposed = browser_step(page, "async () => window.multiMapAcceptance.destroy()")
                assert disposed["rootEmpty"] and disposed["markersCleared"]
                row.update({"functional_pass": True, "progress_updates": 10, "account_removal": True,
                            "session_switch": True, "immediate_remount": True})
            except Exception as error:
                row["error"] = safe_error(error, {provider: credential})
                try:
                    browser_step(page, "async () => window.multiMapAcceptance?.destroy()")
                except Exception:
                    pass
            page.wait_for_timeout(500)
            row.update({"script_errors": len(errors) - baseline[0], "unhandled_rejections": len(rejections) - baseline[1],
                        "console_errors": len(console) - baseline[2]})
            row["lifecycle_pass"] = not row.get("error") and not any(row[name] for name in ("script_errors", "unhandled_rejections", "console_errors"))
            rows.append(row)
    return rows


def run(credentials, *, frontends=("vue", "legacy"), proxy_enabled=True):
    assert credentials and set(credentials) <= PROXY_HOSTS.keys(), "Explicit map credentials are required"
    assert frontends and set(frontends) <= {"vue", "legacy"}, "Unknown multi-account frontend"
    bundle = None
    if "vue" in frontends:
        env = {name: value for name, value in os.environ.items() if name != "MAP_SMOKE_CREDENTIALS"}
        compiled = subprocess.run(["node", str(ROOT / "tests/multi_map_ui_browser_fixture.mjs")], cwd=ROOT,
                                  env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=True)
        bundle = json.loads(compiled.stdout)
    app = Flask(__name__)
    app.secret_key = secrets.token_urlsafe(32)
    auth_token = secrets.token_urlsafe(32)
    config = {"Map": {"frontend_proxy_enabled": True, "providers": {}}}
    for provider, credential in credentials.items():
        origin = urlsplit(credential["origin"])
        assert origin.scheme in {"http", "https"} and origin.hostname and not origin.username
        config["Map"]["providers"][provider] = {"backend_page_origin": f"{origin.scheme}://{origin.netloc}"}
    outbound = []
    script_sources = {name: (ROOT / 'scripts' / name).read_text(encoding='utf-8') for name in (
        'legacy-map-runtime.js', 'legacy-map-render.js', 'legacy-multi-accounts.js', 'map-request-proxy.js')}
    legacy_fixture_source = (ROOT / 'tests/legacy_multi_map_browser_fixture.js').read_text(encoding='utf-8')
    planners = {provider: production_planner(provider) for provider in credentials}

    def login_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            sid = request.headers.get("X-Session-ID", "")
            if request.cookies.get("auth_token") != auth_token or sid not in {SESSION_A, SESSION_C}:
                return "", 401
            g.user, g.session_id = "multi-map-smoke", sid
            return view(*args, **kwargs)
        return wrapped

    def transport(method, url, *, headers, body, timeout):
        parsed = urlsplit(url)
        provider = next(name for name, hosts in PROXY_HOSTS.items() if parsed.hostname in hosts)
        expected = config["Map"]["providers"][provider]["backend_page_origin"]
        assert headers["Origin"] == expected and headers["Referer"] == expected + "/"
        assert not any(name.lower() in {"cookie", "authorization", "x-session-id", "x-admin-origin-session-id"} for name in headers)
        if not getattr(g, "multi_map_request_id", None):
            g.multi_map_request_id = secrets.token_hex(6)
        row = {"provider": provider, "host": parsed.hostname, "path": safe_error(parsed.path, credentials), "request_id": g.multi_map_request_id}
        outbound.append(row)
        try:
            response = _MapProxy._request_upstream(method, url, headers=headers, body=body, timeout=timeout)
            row["status"] = response.status_code
            return response
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise

    runtime_config = SimpleNamespace(get=lambda section, key, fallback=None: config.get(section, {}).get(key, fallback))
    register_map_proxy_routes(app, login_required, lambda: runtime_config,
        lambda user, token, sid, _view: user == "multi-map-smoke" and token == auth_token and sid in {SESSION_A, SESSION_C}, transport=transport)

    def asset(path):
        if path == "/map-multi-acceptance":
            return ('<!doctype html><link rel="stylesheet" href="/multi-map-ui.css"><div id="map-ui"></div>'
                    '<div id="map" style="width:2px;height:2px"></div><script src="/scripts/map-request-proxy.js"></script>'
                    + ('<script type="module" src="/multi-map-ui.js"></script>' if bundle else ''), "text/html", 200)
        if path == "/multi-map-ui.css":
            return ('html,body,#map-ui{margin:0;width:100%;height:100%}.h-full{height:100%}.w-full{width:100%}.relative{position:relative}' + (bundle["css"] if bundle else ''), "text/css", 200)
        if bundle and path.lstrip('/') in bundle["files"]:
            return bundle["files"][path.lstrip('/')], "application/javascript", 200
        if path == "/legacy-multi-fixture.js":
            return legacy_fixture_source, "application/javascript", 200
        for prefix in ("/legacy-scripts/", "/scripts/"):
            if path.startswith(prefix):
                filename = path[len(prefix):]
                if filename in script_sources:
                    return script_sources[filename], "application/javascript", 200
        return "Not found", "text/plain", 404

    @app.get("/map-multi-acceptance")
    @app.get("/multi-map-ui.js")
    @app.get("/multi-map-ui.css")
    @app.get("/legacy-multi-fixture.js")
    @app.get("/fixture/<path:filename>")
    @app.get("/scripts/<path:filename>")
    @app.get("/legacy-scripts/<path:filename>")
    def static_asset(filename=None):
        body, content_type, status = asset(request.path)
        return app.response_class(body, status=status, mimetype=content_type)

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
                for frontend in frontends:
                    for provider, credential in credentials.items():
                        context = browser.new_context(service_workers="block")
                        try:
                            current_origin = app_origin if proxy_enabled else config["Map"]["providers"][provider]["backend_page_origin"]
                            if proxy_enabled:
                                context.add_cookies([{"name": "auth_token", "value": auth_token, "url": app_origin}])
                            else:
                                def serve(route):
                                    body, content_type, status = asset(urlsplit(route.request.url).path)
                                    return route.fulfill(body=body, content_type=content_type, status=status)
                                context.route(current_origin + "/**", serve)
                            page = context.new_page()
                            errors, rejections, console, direct, failures = [], [], [], [], []
                            start_outbound = len(outbound)
                            page.expose_function("recordMultiMapRejection", lambda value: rejections.append(safe_error(value, credentials)))
                            page.add_init_script("addEventListener('unhandledrejection', event => window.recordMultiMapRejection(String(event.reason?.stack || event.reason || 'unhandled rejection')))")
                            page.on("pageerror", lambda error: errors.append(safe_error(getattr(error, "stack", None) or error, credentials)))
                            page.on("console", lambda message: console.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                            page.on("dialog", lambda dialog: dialog.dismiss())
                            def record_request(req):
                                parsed = urlsplit(req.url)
                                if parsed.hostname and parsed.hostname != urlsplit(current_origin).hostname:
                                    direct.append({"host": parsed.hostname, "type": req.resource_type})
                            def record_response(response):
                                parsed = urlsplit(response.url)
                                if response.status >= 400 or (response.request.resource_type == "script" and "javascript" not in response.headers.get("content-type", "")):
                                    failures.append({"status": response.status, "path": safe_error(parsed.path, credentials),
                                                     "content_type": response.headers.get("content-type", "")})
                            page.on("request", record_request)
                            page.on("response", record_response)
                            page.goto(current_origin + "/map-multi-acceptance", wait_until="domcontentloaded")
                            route, rounds = {}, []
                            try:
                                page.evaluate("async ({provider,enabled,sessionId}) => ZXMapRequestProxy.initialize({provider,enabled,sessionId})", {"provider": provider, "enabled": proxy_enabled, "sessionId": SESSION_A})
                                args = [[[116.397128, 39.916527], [116.398128, 39.916527]], credential["key"], {"api_retries": 0, "api_fallback_line": False}]
                                args += [["AMap.Walking"], "walking", credential.get("securityJsCode", "")] if provider == 'amap' else ['walking']
                                route = browser_step(page, "async ({source,args}) => (0,eval)('('+source+')')(args)", {"source": planners[provider], "args": args}, timeout_ms=65000)
                                if route.get('error'):
                                    raise RuntimeError(route['error'])
                                page.goto(current_origin + "/map-multi-acceptance", wait_until="domcontentloaded")
                                if frontend == 'legacy':
                                    page.add_script_tag(url=current_origin + "/legacy-multi-fixture.js")
                                else:
                                    page.wait_for_function("typeof window.mountMultiMapAcceptance === 'function'")
                                rounds = exercise_multi_map(page, provider, credential, frontend, proxy_enabled=proxy_enabled, errors=errors, rejections=rejections, console=console)
                            except Exception as error:
                                route['map_error'] = safe_error(error, credentials)
                            page.wait_for_timeout(2000)
                            relevant_outbound = outbound[start_outbound:]
                            row = {"frontend": frontend, "provider": provider, "multi_account": True, "proxy_enabled": proxy_enabled,
                                   "route_success": bool(route) and not route.get('error'), "route_points": len(route.get('path', [])),
                                   "rounds": rounds, "map_error": route.get('map_error'),
                                   "script_errors": len(errors), "script_error_messages": list(dict.fromkeys(errors))[:6],
                                   "unhandled_rejections": len(rejections), "unhandled_rejection_messages": list(dict.fromkeys(rejections))[:6],
                                   "console_error_messages": list(dict.fromkeys(console))[:6], "direct_requests": direct,
                                   "proxy_failures": failures, **summarize_upstream_attempts(relevant_outbound, provider)}
                            results.append(evaluate_multi_result(row))
                        finally:
                            context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    return results


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    credentials = json.loads(os.environ.get('MAP_SMOKE_CREDENTIALS', '{}'))
    try:
        results = run(credentials, frontends=tuple(filter(None, os.environ.get('MAP_SMOKE_MULTI_FRONTENDS', 'vue,legacy').split(','))), proxy_enabled=os.environ.get('MAP_SMOKE_MULTI_PROXY', '1') != '0')
    except Exception as error:
        print(json.dumps({'error': safe_error(error, credentials)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(results, ensure_ascii=True, indent=2))
    raise SystemExit(0 if results and all(row['passed'] for row in results) else 1)
