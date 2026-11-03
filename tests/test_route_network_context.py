"""Exercise useful, bounded network evidence through the production worker."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import background_task_manager
import main
import test_route_worker_telemetry as telemetry
from map_runtime_origin import MAP_RUNTIME_MARKER
from background_task_manager import ChromeBrowserPool


def request(url="https://restapi.amap.com/v3/direction/walking?key=fake-secret", **fields):
    return SimpleNamespace(
        url=url, method="GET", resource_type="script", timing={},
        headers={"referer": "https://origin.test/private-session/path?private=header-secret",
                 "origin": "https://origin.test:443", "cookie": "header-cookie",
                 "authorization": "Bearer header-authorization", "x-debug": "header-secret"},
        **fields,
    )


def response(req, *, broken_transport=False):
    def unavailable():
        raise RuntimeError("transport-secret")
    return SimpleNamespace(
        request=req, url=req.url, status=200,
        server_addr=unavailable if broken_transport else lambda: {"ipAddress": "203.0.113.17", "port": 443},
        security_details=unavailable if broken_transport else lambda: {
            "protocol": "TLS 1.3", "issuer": "certificate-private", "subjectName": "certificate-private"},
    )


class RouteNetworkContextTests(unittest.TestCase):
    def run_worker(self, exercise, *, context=None, scheduler=None):
        fixture = telemetry.RouteWorkerTelemetryTests()
        pool, page, listeners = fixture.pool()
        page.evaluate.side_effect = lambda script, args: exercise(listeners, pool, args)
        with patch.object(background_task_manager, "schedule_route_network_probe",
                          scheduler or (lambda *_args: False), create=True), self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js(
                "private-session", "script", [], diagnostic_context=context or fixture.context(),
                deadline_epoch_ms=time.time() * 1000 + 30000)
        events = [json.loads(record.getMessage().split("worker=", 1)[1])
                  for record in logs.records if " worker=" in record.getMessage()]
        return result, events, "\n".join(record.getMessage() for record in logs.records)

    def test_actual_request_origins_are_logged_without_header_or_referrer_secrets(self):
        def exercise(listeners, _pool, _args):
            req = request()
            listeners["request"](req)
            listeners["response"](response(req))
            listeners["requestfinished"](req)
            return {"path": [{"lng": 1, "lat": 2}, {"lng": 3, "lat": 4}]}

        result, events, text = self.run_worker(exercise)
        self.assertTrue(result["success"])
        started = next(item for item in events if item["event"] == "request_start")
        self.assertEqual(started["host"], "restapi.amap.com")
        self.assertEqual(started["request_origin"], {
            "referer_origin": "https://origin.test", "origin_header": "https://origin.test"})
        for secret in ("fake-secret", "private-session", "header-secret", "header-cookie", "header-authorization"):
            self.assertNotIn(secret, text)
        self.assertNotIn("/path", text)

    def test_response_transport_is_logged_and_retained_in_host_summary_without_certificate_data(self):
        def exercise(listeners, _pool, _args):
            req = request()
            listeners["request"](req)
            listeners["response"](response(req))
            listeners["requestfinished"](req)
            return {"path": []}

        result, events, text = self.run_worker(exercise)
        self.assertTrue(result["success"])
        transport = next(item for item in events if item["event"] == "response_transport")
        expected = {
            "remote_ip": "203.0.113.17", "remote_port": 443, "tls_protocol": "TLS 1.3"}
        self.assertEqual(transport["transport"], expected)
        hosts = result["result"]["diagnostic"]["worker"]["network"]["host_summaries"]
        self.assertEqual(hosts[0]["transport"], expected)
        self.assertNotIn("certificate-private", text)

    def test_transport_introspection_failure_preserves_success(self):
        def exercise(listeners, _pool, _args):
            req = request()
            listeners["request"](req)
            listeners["response"](response(req, broken_transport=True))
            listeners["requestfinished"](req)
            return {"path": []}

        result, _events, text = self.run_worker(exercise)
        self.assertTrue(result["success"])
        self.assertNotIn("transport-secret", text)

    def test_timeout_snapshot_collects_transport_from_responses_received_before_failure(self):
        def exercise(listeners, _pool, _args):
            req = request("https://restapi.amap.com/v3/log/init?key=fake-secret")
            listeners["request"](req)
            listeners["response"](response(req))
            raise RuntimeError("upstream timeout")

        result, events, text = self.run_worker(exercise)
        self.assertFalse(result["success"])
        network = result["diagnostic"]["network"]
        host = next(item for item in network["host_summaries"] if item["host"] == "restapi.amap.com")
        self.assertEqual(host["transport"]["remote_ip"], "203.0.113.17")
        self.assertEqual(host["transport"]["tls_protocol"], "TLS 1.3")
        self.assertTrue(any(item["event"] == "response_transport" for item in events))
        self.assertNotIn("fake-secret", text)

    def test_response_metadata_rpc_reentry_does_not_drop_status_or_endpoint(self):
        def exercise(listeners, _pool, _args):
            req = request()
            received = response(req)
            req.response = lambda: received
            finished = False

            def server_addr():
                nonlocal finished
                if not finished:
                    finished = True
                    listeners["requestfinished"](req)
                return {"ipAddress": "203.0.113.17", "port": 443}

            received.server_addr = server_addr
            listeners["request"](req)
            listeners["response"](received)
            if not finished:
                finished = True
                listeners["requestfinished"](req)
            return {"path": []}

        result, events, _text = self.run_worker(exercise)
        self.assertTrue(result["success"])
        completed = next(item for item in events if item["event"] == "request_finished")
        self.assertEqual(completed["http_status"], 200)
        transport = next(item for item in events if item["event"] == "response_transport")
        self.assertEqual(transport["transport"]["remote_ip"], "203.0.113.17")
        self.assertEqual(result["result"]["diagnostic"]["worker"]["network"]["finished"], 1)

    def test_failures_survive_success_event_cap_and_ignore_blob_traffic(self):
        def exercise(listeners, _pool, _args):
            for index in range(35):
                req = request(f"https://webapi.amap.com/loader-{index}.js")
                listeners["request"](req)
                listeners["response"](response(req))
                listeners["requestfinished"](req)
            for scheme in ("blob:https://origin.test/private-session", "data:text/plain,header-secret"):
                req = request(scheme)
                listeners["request"](req)
                listeners["requestfinished"](req)
            for index in range(16):
                req = request(f"https://restapi.amap.com/route-{index}?key=fake-secret", failure="net::ERR_TIMED_OUT")
                listeners["request"](req)
                listeners["requestfailed"](req)
            return {"error": "地图路线服务请求超时"}

        result, events, text = self.run_worker(exercise)
        snapshot = result["result"]["diagnostic"]["worker"]["network"]
        self.assertEqual(snapshot["started"], 51)
        self.assertEqual(snapshot["finished"], 35)
        self.assertEqual(snapshot["failed"], 16)
        self.assertEqual(len(snapshot["failed_requests"]), 12)
        self.assertGreater(snapshot["events_dropped"], 0)
        summaries = {item["host"]: item for item in snapshot["host_summaries"]}
        self.assertEqual(summaries["webapi.amap.com"]["finished"], 35)
        self.assertEqual(summaries["restapi.amap.com"]["failed"], 16)
        self.assertEqual(summaries["restapi.amap.com"]["pending"], 0)
        failures = [item for item in events if item["event"] == "request_failed"]
        self.assertGreater(len(failures), 0)
        self.assertLessEqual(len(failures), 12)
        self.assertNotIn("header-secret", text)
        self.assertNotIn("private-session", text)

    def test_delayed_probe_callback_keeps_original_diagnostic_id(self):
        callbacks = []
        def scheduler(_provider, _hosts, emit):
            callbacks.append(emit)
            return True

        fixture = telemetry.RouteWorkerTelemetryTests()
        pool, page, listeners = fixture.pool()
        attempts = 0
        def evaluate(_script, _args):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                req = request(failure="net::ERR_TIMED_OUT")
                listeners["request"](req)
                listeners["requestfailed"](req)
                return {"error": "地图路线服务请求超时"}
            return {"path": []}
        page.evaluate.side_effect = evaluate
        with patch.object(background_task_manager, "schedule_route_network_probe", scheduler, create=True), self.assertLogs(level="INFO") as logs:
            first = pool._do_execute_js("private-session", "script", [], diagnostic_context=fixture.context())
            second_context = {**fixture.context(), "diagnostic_id": "next-command"}
            second = pool._do_execute_js("private-session", "script", [], diagnostic_context=second_context)
            self.assertEqual(len(callbacks), 1)
            callbacks[0]("network_probe", phase="dns", state="ok", host="restapi.amap.com")
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        probe = next(record.getMessage() for record in logs.records
                     if '"event": "network_probe"' in record.getMessage())
        self.assertIn("id=telemetry-test ", probe)
        self.assertNotIn("next-command", probe)
        self.assertTrue(any("network_probe_scheduled" in record.getMessage() for record in logs.records))

    def test_http_errors_survive_network_and_browser_event_caps(self):
        for status in (429, 503):
            with self.subTest(status=status):
                scheduled = []
                def scheduler(*args):
                    scheduled.append(args)
                    return True
                def exercise(listeners, _pool, _args):
                    for index in range(35):
                        req = request(f"https://webapi.amap.com/loader-{index}.js")
                        listeners["request"](req)
                        listeners["response"](response(req))
                        listeners["requestfinished"](req)
                    for index in range(12):
                        listeners["console"](SimpleNamespace(type="warning", text=f"loader warning {index}"))
                    req = request()
                    failed_response = response(req)
                    failed_response.status = status
                    listeners["request"](req)
                    listeners["response"](failed_response)
                    listeners["requestfinished"](req)
                    return {"error": "provider returned an HTTP error"}

                result, events, text = self.run_worker(exercise, scheduler=scheduler)
                network = result["result"]["diagnostic"]["worker"]["network"]
                self.assertEqual(network["finished"], 36)
                self.assertEqual(network["failed"], 0)
                self.assertEqual(network["http_error_count"], 1)
                self.assertEqual(network["http_errors"][0]["http_status"], status)
                failed_host = next(item for item in network["host_summaries"] if item["host"] == "restapi.amap.com")
                self.assertEqual(failed_host["http_errors"], 1)
                self.assertEqual(failed_host["last_http_status"], status)
                self.assertTrue(any(item.get("http_status") == status for item in events))
                self.assertEqual(scheduled, [])
                self.assertNotIn("fake-secret", text)
                self.assertNotIn("header-secret", text)

    def test_host_summary_limit_does_not_hide_total_network_failure_count(self):
        def exercise(listeners, _pool, _args):
            for index in range(16):
                req = request(f"https://upstream-{index}.example/route", failure="net::ERR_TIMED_OUT")
                listeners["request"](req)
                listeners["requestfailed"](req)
            return {"error": "地图路线服务请求超时"}

        result, _events, _text = self.run_worker(exercise)
        network = result["result"]["diagnostic"]["worker"]["network"]
        self.assertEqual(network["started"], 16)
        self.assertEqual(network["failed"], 16)
        self.assertEqual(len(network["host_summaries"]), 8)
        self.assertTrue(all(item["failed"] == 1 for item in network["host_summaries"]))

    def test_runtime_page_ready_reports_verified_origin_and_referrer_policy(self):
        fixture = telemetry.RouteWorkerTelemetryTests()
        pool, page, _listeners = fixture.pool()
        page.url = "https://origin.test/map-runtime"
        page.goto.return_value = SimpleNamespace(headers={"referrer-policy": "strict-origin"})
        page.evaluate.side_effect = [
            {"origin": "https://origin.test", "url": "https://origin.test/map-runtime",
             "marker": MAP_RUNTIME_MARKER, "meta_referrer": "strict-origin"},
            {"path": []},
        ]
        with self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js("private-session", "script", [],
                diagnostic_context=fixture.context(), runtime_page_origin="https://origin.test/path")
        self.assertTrue(result["success"])
        ready = next(json.loads(record.getMessage().split("worker=", 1)[1]) for record in logs.records
                     if '"event": "runtime_page_ready"' in record.getMessage())
        actual = ready["runtime_page"]
        self.assertEqual(actual["origin"], "https://origin.test")
        self.assertEqual(actual["url"], "https://origin.test/map-runtime")
        self.assertEqual(actual["referrer_policy"], "strict-origin")
        self.assertEqual(actual["meta_referrer"], "strict-origin")

    def test_successful_planning_does_not_create_background_network_probes(self):
        scheduled = []
        def scheduler(*args):
            scheduled.append(args)
            return True
        def exercise(listeners, _pool, _args):
            req = request()
            listeners["request"](req)
            listeners["response"](response(req))
            listeners["requestfinished"](req)
            return {"path": [{"lng": 1, "lat": 2}, {"lng": 3, "lat": 4}]}

        result, _events, _text = self.run_worker(exercise, scheduler=scheduler)
        self.assertTrue(result["success"])
        self.assertEqual(scheduled, [])

    def test_pending_request_and_exception_timeout_still_schedule_probe(self):
        cases = (
            ("tianditu", "https://api.tianditu.gov.cn/drive", "exception", "AbortError: 地图路线服务请求超时"),
            ("tencent", "https://apis.map.qq.com/ws/direction/v1/walking/", "error", "JSONP request timeout"),
        )
        for provider, url, status, reason in cases:
            with self.subTest(provider=provider):
                scheduled = []
                def scheduler(selected_provider, hosts, _emit):
                    scheduled.append((selected_provider, hosts))
                    return True
                def exercise(listeners, _pool, args):
                    req = request(url)
                    listeners["request"](req)
                    listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps({
                        "event": "segment_callback", "segment": 1, "status": status, "reason": reason})))
                    return {"error": "Segment 1 failed: " + reason}
                fixture = telemetry.RouteWorkerTelemetryTests()
                context = {**fixture.context(), "provider": provider}
                result, events, _text = self.run_worker(exercise, scheduler=scheduler, context=context)
                self.assertTrue(result["success"])
                self.assertEqual(len(scheduled), 1)
                self.assertEqual(scheduled[0][0], provider)
                self.assertTrue(any(item["event"] == "network_probe_scheduled" for item in events))

    def test_main_entry_keeps_provider_domain_readable_while_redacting_real_credentials(self):
        plan = {"provider": "amap", "actual_mode": "walking", "plugins": ["AMap.Walking"],
                "provider_config": {"provider": "amap", "display_name": "高德",
                                    "coordinate_system": "gcj02", "js_key": "fake-secret"}}
        pool = SimpleNamespace(execute_js=lambda *_args, **_kwargs: {
            "error": "net::ERR_TIMED_OUT https://restapi.amap.com/v3/direction/walking?key=fake-secret"})
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value=plan
        ), patch.object(main, "resolve_backend_page_origin", return_value=("https://origin.test", "global")), self.assertLogs(level="INFO") as logs:
            result = main._plan_route_path_with_provider_runtime("private-session", [[1, 2], [3, 4]])
        starts = [record.getMessage() for record in logs.records if "phase=start " in record.getMessage()]
        self.assertEqual(len(starts), 1)
        self.assertIn("provider=amap ", starts[0])
        self.assertIn("restapi.amap.com", result["error"])
        text = "\n".join(record.getMessage() for record in logs.records) + result["error"]
        self.assertNotIn("fake-secret", text)
        self.assertNotIn("private-session", text)

    def test_main_logs_origin_candidates_and_selected_source_without_url_paths(self):
        plan = {"provider": "amap", "actual_mode": "walking", "plugins": ["AMap.Walking"],
                "provider_config": {"backend_page_origin": "https://profile.test/provider?private=profile"}}
        class RuntimeConfig:
            def get(self, section, key, fallback=None):
                if (section, key) == ("Map", "backend_page_origin"):
                    return "https://global.test/config?private=global"
                if (section, key) == ("Map", "providers"):
                    return {"amap": {"backend_page_origin": "https://profile.test/provider?private=profile"}}
                return fallback
        pool = SimpleNamespace(execute_js=lambda *_args, **_kwargs: {"path": [{"lng": 1, "lat": 2}]})
        with patch.object(main, "chrome_pool", pool, create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value=plan
        ), patch.object(
            main, "resolve_backend_page_origin", return_value=("https://profile.test", "provider")
        ), self.assertLogs(level="INFO") as logs:
            result = main._plan_route_path_with_provider_runtime(
                "private-session", [[1, 2], [3, 4]], runtime_config=RuntimeConfig(),
                app_base_url="http://request.test/app?private=request",
            )
        entry = next(line for line in logs.output if "phase=origin_resolution" in line)
        trace = json.loads(entry.split("trace=", 1)[1])
        self.assertEqual(result["provider"], "amap")
        self.assertEqual(trace["selected_source"], "provider")
        self.assertEqual(trace["selected_origin"], "https://profile.test")
        self.assertEqual([row["source"] for row in trace["candidates"]], ["provider", "global", "request"])
        self.assertEqual([row["origin"] for row in trace["candidates"]], [
            "https://profile.test", "https://global.test", "http://request.test",
        ])
        for private in ("private-session", "private=", "profile?", "global?", "request?"):
            self.assertNotIn(private, entry)


class RealRouteNetworkContextTests(unittest.TestCase):
    def test_browser_emits_actual_referrer_and_remote_endpoint_without_private_query(self):
        from playwright.sync_api import sync_playwright

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *_args):
                pass

        playwright = self.enterContext(sync_playwright())
        if not Path(playwright.chromium.executable_path).exists():
            self.skipTest("Playwright Chromium is unavailable")
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        pool._browser = browser
        pool._contexts = {}
        with self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js("private-session", """async () => {
                await fetch('/route?key=fake-secret&private=header-secret').then(response => response.text());
                return {path: [{lng:1, lat:2}, {lng:3, lat:4}]};
            }""", [], diagnostic_context={"diagnostic_id": "real-network-context", "provider": "amap",
                   "sensitive_values": ["fake-secret", "private-session"]},
                runtime_page_origin=origin, deadline_epoch_ms=time.time() * 1000 + 5000)
        self.assertTrue(result["success"], result)
        events = [json.loads(record.getMessage().split("worker=", 1)[1])
                  for record in logs.records if " worker=" in record.getMessage()]
        started = next(item for item in events if item["event"] == "request_start")
        finished = next(item for item in events if item["event"] == "request_finished")
        transport = next(item for item in events if item["event"] == "response_transport")
        self.assertEqual(started["request_origin"]["referer_origin"], origin)
        self.assertEqual(transport["transport"]["remote_ip"], "127.0.0.1")
        self.assertEqual(transport["transport"]["remote_port"], server.server_port)
        self.assertEqual(finished["http_status"], 200)
        text = "\n".join(record.getMessage() for record in logs.records)
        self.assertNotIn("fake-secret", text)
        self.assertNotIn("header-secret", text)
        self.assertNotIn("private-session", text)
