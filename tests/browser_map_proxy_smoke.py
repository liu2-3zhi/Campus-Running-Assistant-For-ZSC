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


def run(credentials):
    assert credentials and set(credentials) <= PROXY_HOSTS.keys(), "explicit provider credentials required"
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
        return '<!doctype html><html><head></head><body><div id="map" style="width:800px;height:600px"></div></body></html>'

    @app.get("/proxy.js")
    def proxy_script():
        return send_file(ROOT / "scripts" / "map-request-proxy.js", mimetype="application/javascript")

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
                        page.on("request", record_request)
                        page.on("response", record_response)
                        page.on("pageerror", lambda error: runtime_errors.append(safe_error(error, credentials)))
                        page.on("console", lambda message: console_errors.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                        page.on("dialog", lambda dialog: dialog.dismiss())
                        page.goto(app_origin, wait_until="domcontentloaded")
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
                            map_ready = page.evaluate(MAP_CHECK, {"provider": provider, "key": credential["key"]})
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
                        if route.get("error"):
                            result["error"] = safe_error(route["error"], credentials)
                        if route.get("map_error"):
                            result["map_error"] = route["map_error"]
                        results.append(result)
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
        results = run(credentials)
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(results, ensure_ascii=True, indent=2))
    raise SystemExit(0 if all(row["route_success"] and row["route_points"] >= 2 and row["map_ready"] and not row["direct_requests"] and not row["proxy_failures"] for row in results) else 1)
