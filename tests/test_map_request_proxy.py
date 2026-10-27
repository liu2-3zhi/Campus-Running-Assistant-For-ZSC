import json
import logging
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlencode, urlsplit

import urllib3
from flask import Flask, g, request

from map_request_proxy import (
    PROXY_HOSTS,
    MapProxyAccessLogFilter,
    _rewrite_vendor_urls,
    register_map_proxy_routes,
)


SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"


class Config:
    def __init__(self):
        self.data = {"frontend_proxy_enabled": True, "backend_page_origin": "https://global.example", "providers": {
            "amap": {"backend_page_origin": "https://authorized.example"},
        }}

    def get(self, section, key, fallback=None):
        return self.data.get(key, fallback) if section == "Map" else fallback


class MapRequestProxyTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        received = self.received
        self.upstream_responses = {}
        upstream_responses = self.upstream_responses

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                received.append({"path": self.path, "headers": dict(self.headers), "body": body, "method": self.command})
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", "https://127.0.0.1/private?key=never")
                    self.end_headers()
                    return
                payload = b'const a="https://webapi.amap.com/module.js?key=public"; const b="//restapi.amap.com/v3/path";'
                content_type = "application/javascript; charset=utf-8"
                if self.path.startswith("/large"):
                    payload = b"x" * 4096
                if urlsplit(self.path).path in upstream_responses:
                    content_type, payload = upstream_responses[urlsplit(self.path).path]
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Set-Cookie", "vendor_secret=forbidden")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.upstream.server_close)
        self.addCleanup(self.upstream.shutdown)
        self.config = Config()
        self.allowed = True
        api_a = SimpleNamespace(is_authenticated=True, is_guest=False, auth_username="admin")
        api_b = SimpleNamespace(is_authenticated=True, is_guest=False, auth_username="user")
        self.runtime = SimpleNamespace(
            normalize_session_uuid=lambda value: value if value in (SESSION_A, SESSION_B) else "",
            web_sessions={SESSION_A: api_a, SESSION_B: api_b}, web_sessions_lock=threading.Lock(),
            _verify_session_cookie_token=lambda sid, username, token: token == ("admin-token" if username == "admin" else "user-token"),
            resolve_admin_origin_session_context=lambda target, origin, token: {"session_id": SESSION_A, "username": "admin"}
                if self.allowed and origin == SESSION_A and token == "admin-token" else None,
            auth_system=SimpleNamespace(check_permission=lambda *_: self.allowed),
            CONFIG_FILE="unused", _read_config_ini=lambda _path: self.config,
        )
        self.app = Flask(__name__)
        self.app.testing = True
        self.app.secret_key = "test-proxy-only-secret"
        manager = urllib3.PoolManager()
        self.addCleanup(manager.clear)

        def transport(method, url, *, headers, body, timeout):
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            target = f"http://127.0.0.1:{self.upstream.server_port}{parsed.path}"
            if parsed.query:
                target += "?" + parsed.query
            from urllib3.util import Timeout
            return manager.request(method, target, headers=headers, body=body, redirect=False, preload_content=False,
                                   timeout=Timeout(connect=timeout[0], read=timeout[1]), retries=False)

        def login_required(view):
            def wrapped(*args, **kwargs):
                g.user = "admin"
                g.session_id = SESSION_A
                target = request.headers.get("X-Session-ID", "")
                origin = request.headers.get("X-Admin-Origin-Session-ID", "")
                g.viewed_session_id = target if origin and target != SESSION_A else SESSION_A
                return view(*args, **kwargs)
            wrapped.__name__ = view.__name__
            return wrapped

        def authorize_actor(username, token, actor_session_id, require_view_all):
            return self.allowed and actor_session_id == SESSION_A and token == ("admin-token" if username == "admin" else "user-token")

        register_map_proxy_routes(self.app, login_required, lambda: self.config, authorize_actor,
                                  transport=transport, max_response_bytes=2048,
                                  dns_resolver=lambda host, port, type: [(None, None, None, None, ("8.8.8.8", port))])
        @self.app.route("/")
        def test_page():
            return '<!doctype html><body><script src="/proxy-hooks.js"></script></body>'

        @self.app.route("/scripts/map-request-proxy.js")
        @self.app.route("/proxy-hooks.js")
        def proxy_hooks():
            source = Path(__file__).resolve().parents[1] / "scripts" / "map-request-proxy.js"
            return self.app.response_class(source.read_text(encoding="utf-8"), mimetype="application/javascript")

        self.client = self.app.test_client()
        self.client.set_cookie("auth_token", "admin-token")

    def bootstrap(self, target=SESSION_A, origin=""):
        headers = {"X-Session-ID": target, "Origin": "http://localhost"}
        if origin:
            headers["X-Admin-Origin-Session-ID"] = origin
        return self.client.post("/api/map-proxy/context", headers=headers, json={})

    def test_authenticated_http_proxy_filters_secrets_and_rewrites_vendor_scripts(self):
        bootstrap = self.bootstrap()
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(bootstrap.json, {"success": True, "expires_in": 1800})
        cookie = bootstrap.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Path=/map-proxy", cookie)
        response = self.client.get("/map-proxy/amap/https/webapi.amap.com/maps?key=public&session_id=never&auth_token=never", headers={"Authorization": "Bearer never", "Cookie": "app=never"})
        self.assertEqual(response.status_code, 200)
        upstream = self.received[-1]
        self.assertEqual(upstream["headers"]["Referer"], "https://authorized.example/")
        self.assertEqual(upstream["headers"]["Origin"], "https://authorized.example")
        self.assertNotIn("Cookie", upstream["headers"])
        self.assertNotIn("Authorization", upstream["headers"])
        self.assertEqual(upstream["path"], "/maps?key=public")
        self.assertIn(b"/map-proxy/amap/https/webapi.amap.com/module.js?key=public", response.data)
        self.assertIn(b"/map-proxy/amap/https/restapi.amap.com/v3/path", response.data)
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn(b"authorized.example", response.data)

    def test_runtime_resource_hosts_are_allowlisted_and_rewritten(self):
        self.assertEqual(self.bootstrap().status_code, 200)
        for provider, host in (
            ("amap", "jsapi-data1.amap.com"),
            ("amap", "o4.amap.com"),
            ("tencent", "confinfo.map.qq.com"),
            ("tencent", "mapstyle.qpic.cn"),
            ("tencent", "vectorsdk.map.qq.com"),
            ("baidu", "apimaponline0.bdimg.com"),
            ("baidu", "dlswbr.baidu.com"),
            ("baidu", "miao.baidu.com"),
            ("baidu", "webmap0.bdimg.com"),
            ("tianditu", "api.tianditu.gov.cn"),
        ):
            with self.subTest(provider=provider, host=host):
                self.assertIn(host, PROXY_HOSTS[provider])
                response = self.client.get(
                    f"/map-proxy/{provider}/https/{host}/runtime.js?key=redacted"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_provider_javascript_and_css_rewrite_only_exact_vendor_hosts(self):
        cases = {
            "amap": (
                'const a="https://jsapi-data1.amap.com/sdk.js";'
                'const b="//o4.amap.com/style.css";'
                'const c="https://jsapi-data6.amap.com/no.js";'
            ),
            "tencent": (
                'const a="https://confinfo.map.qq.com/sdk.js";'
                'const b="//vectorsdk.map.qq.com/worker.js";'
                'const c="https://mapstyle.qpic.cn/style.css";'
                'const d="https://fake.map.qq.com/no.js";'
            ),
            "baidu": (
                'const a="https://apimaponline0.bdimg.com/tile";'
                'const b="//dlswbr.baidu.com/sdk.js";'
                'const c="https://miao.baidu.com/data";'
                'const d="https://webmap0.bdimg.com/tile";'
                'const e="https://apimaponline4.bdimg.com/no.js";'
            ),
            "tianditu": (
                'const a="https://api.tianditu.gov.cn/api.js";'
                'const b="//t7.tianditu.com/DataServer";'
            ),
        }
        expected_hosts = {
            "amap": ("jsapi-data1.amap.com", "o4.amap.com"),
            "tencent": ("confinfo.map.qq.com", "vectorsdk.map.qq.com", "mapstyle.qpic.cn"),
            "baidu": ("apimaponline0.bdimg.com", "dlswbr.baidu.com", "miao.baidu.com", "webmap0.bdimg.com"),
            "tianditu": ("api.tianditu.gov.cn", "t7.tianditu.com"),
        }
        for provider, body in cases.items():
            with self.subTest(provider=provider):
                rewritten = _rewrite_vendor_urls(body, provider, "https://app.example", "https://origin.example")
                for host in expected_hosts[provider]:
                    self.assertIn(f"/map-proxy/{provider}/https/{host}", rewritten)
                self.assertNotIn("https://origin.example", rewritten)
        self.assertIn("https://jsapi-data6.amap.com/no.js", _rewrite_vendor_urls(
            cases["amap"], "amap", "https://app.example", "https://origin.example"
        ))

    def test_baidu_root_urls_preserve_sdk_concatenation_and_accept_root_queries(self):
        body = 'const root="https://api.map.baidu.com";const combined=protocol+"//api.map.baidu.com";'
        rewritten = _rewrite_vendor_urls(body, "baidu", "https://app.example", "https://origin.example")
        self.assertIn('root="https://app.example/map-proxy/baidu/https/api.map.baidu.com"', rewritten)
        self.assertIn('combined=protocol+"//api.map.baidu.com"', rewritten)
        self.assertEqual(self.bootstrap().status_code, 200)
        for suffix in ("", "/", "//"):
            with self.subTest(suffix=suffix):
                response = self.client.get(
                    f"/map-proxy/baidu/https/api.map.baidu.com{suffix}?qt=verify&callback=test"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.received[-1]["path"], "/?qt=verify&callback=test")

    def test_private_backend_origin_is_removed_from_plain_and_escaped_json(self):
        origin = "https://authorized.example:8443"
        for escaped in (origin, origin.replace("/", r"\/"), origin.replace("/", r"\\/")):
            with self.subTest(escape_count=escaped.count("\\")):
                body = f'const settings={{"private_origin":"{escaped}"}};'
                self.assertEqual(
                    _rewrite_vendor_urls(body, "amap", "https://app.example", origin),
                    'const settings={"private_origin":""};',
                )

    def test_amap_split_protocol_service_base_is_not_rewritten_mid_literal(self):
        body = 'var wi=(ji=config[16]||config[2].split(":")[0])+"://restapi.amap.com";var route=wi+"/v3/direction/walking";'
        self.assertEqual(
            _rewrite_vendor_urls(body, "amap", "http://127.0.0.1:27718", "https://authorized.example"),
            body,
        )

    def test_jsonp_mime_is_corrected_only_for_matching_safe_callback_and_valid_json(self):
        self.assertEqual(self.bootstrap().status_code, 200)
        cases = [
            ("json", "application/json", {"callback": "map_cb"}, b'map_cb({"status":"1","info":"OK"});', True),
            ("octet", "application/octet-stream", {"cb": "AMap._cb$1"}, b'AMap._cb$1({"status":0});', True),
            ("comment", "text/plain", {"callback": "map_cb"}, b'/**/map_cb({"items":[1,true,null]});\n', True),
            ("guarded", "text/plain", {"callback": "TMap._svcb.cb123"}, b'TMap._svcb.cb123&&TMap._svcb.cb123({"status":0});', True),
            ("guard-mismatch", "text/plain", {"callback": "map_cb"}, b'other_cb&&map_cb({"status":0});', False),
            ("guard-extra", "text/plain", {"callback": "map_cb"}, b'map_cb&&map_cb({"status":0});alert(1)', False),
            ("pure", "application/json", {"callback": "map_cb"}, b'{"status":0}', False),
            ("missing", "application/json", {}, b'map_cb({"status":0});', False),
            ("unsafe", "application/json", {"callback": "map_cb);alert(1)//"}, b'map_cb({"status":0});', False),
            ("reserved", "application/json", {"callback": "window.constructor"}, b'window.constructor({"status":0});', False),
            ("duplicate", "application/json", {"callback": ["map_cb", "other_cb"]}, b'map_cb({"status":0});', False),
            ("wrong", "application/json", {"callback": "map_cb"}, b'other_cb({"status":0});', False),
            ("broken", "application/json", {"callback": "map_cb"}, b'map_cb({"status":0}', False),
            ("extra", "application/octet-stream", {"callback": "map_cb"}, b'map_cb({"status":0});alert(1)', False),
            ("expression", "application/json", {"callback": "map_cb"}, b'map_cb({"value":window.secret});', False),
            ("nonjson", "application/json", {"callback": "map_cb"}, b'map_cb({"value":NaN});', False),
            ("html", "text/html", {"callback": "map_cb"}, b'map_cb({"status":0});', False),
        ]
        for name, content_type, params, body, corrected in cases:
            with self.subTest(case=name):
                path = f"/jsonp-{name}"
                self.upstream_responses[path] = (content_type, body)
                response = self.client.get(
                    "/map-proxy/amap/https/restapi.amap.com" + path,
                    query_string=params,
                    headers={"Sec-Fetch-Dest": "script"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "application/javascript" if corrected else content_type)
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.data, body)
        self.upstream_responses["/jsonp-fetch"] = ("application/json", b'map_cb({"status":0});')
        response = self.client.get(
            "/map-proxy/amap/https/restapi.amap.com/jsonp-fetch?callback=map_cb",
            headers={"Sec-Fetch-Dest": "empty"},
        )
        self.assertEqual(response.mimetype, "application/json")

    def test_classic_worker_bootstrap_contains_only_public_proxy_context(self):
        self.assertEqual(self.bootstrap().status_code, 200)
        response = self.client.get(
            "/map-proxy/baidu/https/api.map.baidu.com/worker.js",
            headers={"Sec-Fetch-Dest": "worker", "Sec-Fetch-Mode": "same-origin"},
        )
        self.assertTrue(response.data.startswith(b'importScripts("http://localhost/scripts/map-request-proxy.js");'))
        for secret in (b"admin-token", SESSION_A.encode(), b"authorized.example", b"global.example"):
            self.assertNotIn(secret, response.data)
        module = self.client.get(
            "/map-proxy/baidu/https/api.map.baidu.com/worker.js",
            headers={"Sec-Fetch-Dest": "worker", "Sec-Fetch-Mode": "cors"},
        )
        self.assertFalse(module.data.startswith(b"importScripts("))

    def test_access_is_rechecked_and_admin_tabs_share_actor_without_target_override(self):
        self.assertEqual(self.bootstrap(SESSION_B, SESSION_A).status_code, 200)
        self.assertEqual(self.bootstrap(SESSION_A).status_code, 200)
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/maps").status_code, 200)
        self.allowed = False
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/maps").status_code, 401)
        self.assertEqual(len(self.received), 1)

    def test_invalid_hosts_auth_and_redirects_are_rejected_before_external_requests(self):
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/maps").status_code, 401)
        self.assertEqual(self.bootstrap().status_code, 200)
        self.assertEqual(self.client.get("/map-proxy/amap/http/webapi.amap.com/maps").status_code, 400)
        for host in ("127.0.0.1", "webapi.amap.com.evil.test", "webapi.amap.com:443", "user@webapi.amap.com", "api.map.baidu.com"):
            with self.subTest(host=host):
                self.assertEqual(self.client.get(f"/map-proxy/amap/https/{host}/maps").status_code, 400)
        self.assertEqual(self.received, [])
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/redirect").status_code, 502)
        self.assertEqual(len(self.received), 1)
        self.client.set_cookie("auth_token", "changed")
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/maps").status_code, 401)

    def test_post_body_limits_response_limits_and_disabled_config(self):
        self.bootstrap()
        response = self.client.post("/map-proxy/amap/https/restapi.amap.com/route", data=b"payload", content_type="application/json", headers={"X-Session-ID": "never"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.received[-1]["body"], b"payload")
        self.assertEqual(self.received[-1]["method"], "POST")
        response = self.client.post("/map-proxy/amap/https/restapi.amap.com/route", data=b"x" * (1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        response = self.client.get("/map-proxy/amap/https/webapi.amap.com/large")
        self.assertEqual(response.status_code, 502)
        self.config.data["frontend_proxy_enabled"] = False
        self.assertEqual(self.client.get("/map-proxy/amap/https/webapi.amap.com/maps").status_code, 404)

    def test_query_values_are_absent_from_access_log_records(self):
        record = logging.LogRecord("werkzeug", logging.INFO, "", 0, '%s - "GET /map-proxy/amap/https/webapi.amap.com/maps?key=secret&jscode=secret HTTP/1.1" 200 -', ("127.0.0.1",), None)
        self.assertTrue(MapProxyAccessLogFilter().filter(record))
        self.assertNotIn("secret", record.getMessage())
        self.assertIn("webapi.amap.com", record.getMessage())

        nested = logging.LogRecord("werkzeug", logging.INFO, "", 0, "request=%s", ({
            "url": "/map-proxy/amap/https/webapi.amap.com/maps?key=secret",
            "nested": ["/map-proxy/amap/https/webapi.amap.com/module?jscode=secret"],
        },), None)
        self.assertTrue(MapProxyAccessLogFilter().filter(nested))
        self.assertNotIn("secret", nested.getMessage())

    def test_real_browser_rewrites_tianditu_dynamic_images_before_resource_requests(self):
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        self.assertEqual(self.bootstrap().status_code, 200)
        context_cookie = self.client.get_cookie("map_proxy_context", path="/map-proxy").value
        server = make_server("127.0.0.1", 0, self.app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"
        playwright = self.enterContext(sync_playwright())
        if not Path(playwright.chromium.executable_path).exists():
            self.skipTest("Playwright Chromium 未安装；真实 DOM 代理未验证")
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        context = browser.new_context()
        context.add_cookies([
            {"name": "auth_token", "value": "admin-token", "url": origin},
            {"name": "map_proxy_context", "value": context_cookie, "domain": "127.0.0.1", "path": "/map-proxy"},
        ])
        page = context.new_page()
        direct_requests = []
        page.on("request", lambda request: direct_requests.append(True)
                if request.url.startswith("http://api.tianditu.gov.cn/") else None)
        page.route("http://api.tianditu.gov.cn/**", lambda route: route.abort())
        page.goto(origin)
        with page.expect_response(lambda response: "/map-proxy/tianditu/https/api.tianditu.gov.cn/v4.0/image/logo.png?case=markup" in response.url) as proxied:
            result = page.evaluate("""() => {
                ZXMapRequestProxy.install({enabled: true, provider: 'tianditu'});
                const logo = 'http://api.tianditu.gov.cn/v4.0/image/logo.png';
                const container = document.createElement('div');
                container.innerHTML = '<img src="' + logo + '?case=markup" style="background-image:url(' + logo + '?case=css)">';
                document.body.appendChild(container);
                const background = document.createElement('div');
                background.style.backgroundImage = 'url(' + logo + '?case=setter)';
                document.body.appendChild(background);
                return {src: container.querySelector('img').getAttribute('src'),
                    background: background.style.backgroundImage};
            }""")
        self.assertEqual(proxied.value.status, 200)
        self.assertEqual(result["src"], "/map-proxy/tianditu/https/api.tianditu.gov.cn/v4.0/image/logo.png?case=markup")
        self.assertIn("/map-proxy/tianditu/https/api.tianditu.gov.cn/v4.0/image/logo.png?case=setter", result["background"])
        self.assertEqual(direct_requests, [])

    def test_real_browser_blob_and_remote_workers_keep_imports_fetch_and_xhr_behind_proxy(self):
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        worker_path = "/res/webgl/10/worker_wasm_test.js"
        self.upstream_responses[worker_path] = ("application/javascript", b'''
            self.onmessage = async () => {
                try {
                    const response = await fetch("https://apimaponline0.bdimg.com/pvd/?kind=fetch");
                    const fetched = await response.json();
                    const xhr = await new Promise((resolve, reject) => {
                        const request = new XMLHttpRequest();
                        request.open("GET", "https://apimaponline1.bdimg.com/pvd/?kind=xhr");
                        request.onload = () => resolve(JSON.parse(request.responseText));
                        request.onerror = reject; request.send();
                    });
                    self.postMessage({fetched, xhr, name: self.name});
                } catch (error) { self.postMessage({error: String(error)}); }
            };
        ''')
        self.upstream_responses["/pvd/"] = ("application/json", b'{"ok":true}')
        self.assertEqual(self.bootstrap().status_code, 200)
        signed_cookie = self.client.get_cookie("map_proxy_context", path="/map-proxy").value
        server = make_server("127.0.0.1", 0, self.app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"
        playwright = self.enterContext(sync_playwright())
        if not Path(playwright.chromium.executable_path).exists():
            self.skipTest("Playwright Chromium 未安装；Worker 代理未验证")
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        context = browser.new_context()
        context.add_cookies([
            {"name": "auth_token", "value": "admin-token", "url": origin},
            {"name": "map_proxy_context", "value": signed_cookie, "domain": "127.0.0.1", "path": "/map-proxy"},
        ])
        direct_requests = []
        context.on("request", lambda req: direct_requests.append(req.resource_type)
                   if urlsplit(req.url).hostname in PROXY_HOSTS["baidu"] else None)
        for host in PROXY_HOSTS["baidu"]:
            context.route(f"https://{host}/**", lambda route: route.abort())
        page = context.new_page()
        page.goto(origin)
        for blob in (True, False):
            with self.subTest(blob=blob):
                result = page.evaluate("""({blob, path}) => new Promise((resolve, reject) => {
                    ZXMapRequestProxy.install({enabled: true, provider: 'baidu'});
                    const source = 'https://api.map.baidu.com' + path;
                    const objectUrl = blob ? URL.createObjectURL(new Blob(['importScripts(' + JSON.stringify(source) + ');'], {type: 'text/javascript'})) : null;
                    const worker = new Worker(objectUrl || source, {name: 'map-worker'});
                    if (objectUrl) URL.revokeObjectURL(objectUrl);
                    const timer = setTimeout(() => { worker.terminate(); reject(new Error('worker timed out')); }, 5000);
                    worker.onmessage = ({data}) => { clearTimeout(timer); worker.terminate(); resolve(data); };
                    worker.onerror = () => { clearTimeout(timer); worker.terminate(); reject(new Error('worker failed')); };
                    worker.postMessage({});
                })""", {"blob": blob, "path": worker_path})
                self.assertEqual(result, {"fetched": {"ok": True}, "xhr": {"ok": True}, "name": "map-worker"})
        self.assertEqual(direct_requests, [])


if __name__ == "__main__":
    unittest.main()
