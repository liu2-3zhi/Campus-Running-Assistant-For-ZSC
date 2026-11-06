import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from background_task_manager import ChromeBrowserPool


class RouteWorkerTelemetryTests(unittest.TestCase):
    def pool(self):
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        page = Mock()
        listeners = {}
        page.on.side_effect = lambda event, callback: listeners.setdefault(event, callback)
        pool._contexts = {"private-session": {"page": page}}
        return pool, page, listeners

    def context(self):
        return {"diagnostic_id": "telemetry-test", "provider": "amap", "sensitive_values": ["fake-secret", "private-session"]}

    @patch.object(main, "_log_redaction_enabled", True)
    def test_timeout_keeps_progress_pending_requests_and_budget_before_cleanup(self):
        pool, page, listeners = self.pool()
        request = SimpleNamespace(url="https://maps.test/route?key=fake-secret&origin=11.22,33.44", method="GET", resource_type="xhr")
        finished = SimpleNamespace(url="https://maps.test/sdk?key=fake-secret", method="GET", resource_type="script",
                                   timing={"domainLookupStart": 0, "domainLookupEnd": 2, "connectStart": 2, "connectEnd": 8,
                                           "requestStart": 9, "responseStart": 30, "responseEnd": 31})

        def evaluate(_script, args):
            self.assertFalse(args[4], "redacted worker must disable raw SDK callback logging")
            def progress(payload):
                listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps(payload)))
            # Filling the browser error ring must not stop progress or request telemetry.
            for _ in range(14):
                listeners["pageerror"](RuntimeError("fake-secret test error"))
            progress({"event": "route_start", "segment_count": 3, "max_retries": 2})
            progress({"event": "segment_start", "segment": 1, "attempts": 2, "wave": 2, "state": "running"})
            progress({"event": "segment_callback", "segment": 1, "status": "error", "reason": "fake-secret upstream"})
            progress({"event": "segment_result", "segment": 2, "state": "completed", "success": True, "path_count": 40})
            listeners["request"](finished)
            listeners["response"](SimpleNamespace(request=finished, url=finished.url, status=200))
            listeners["requestfinished"](finished)
            listeners["request"](request)
            listeners["response"](SimpleNamespace(request=request, url=request.url, status=200))
            raise RuntimeError("后端路径规划总时限已耗尽 fake-secret")

        page.evaluate.side_effect = evaluate
        def cleanup(*_args, **_kwargs):
            request.failure = "net::ERR_ABORTED"
            listeners["requestfailed"](request)
        page.goto.side_effect = cleanup
        with self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context(),
                                         deadline_epoch_ms=time.time() * 1000 + 30000, queued_at_monotonic=time.monotonic() - .2)
        self.assertFalse(result["success"])
        diagnostic = result["diagnostic"]
        self.assertEqual(diagnostic["stage"], "route")
        self.assertEqual(diagnostic["completed_count"], 1)
        self.assertEqual(diagnostic["unfinished_count"], 2)
        self.assertEqual(diagnostic["not_started_count"], 1)
        self.assertEqual(diagnostic["pending_segments"], [1])
        self.assertGreaterEqual(diagnostic["queue_wait_ms"], 190)
        self.assertEqual(diagnostic["network"]["pending_count"], 1)
        self.assertEqual(diagnostic["network"]["finished"], 1)
        self.assertEqual(diagnostic["network"]["failed"], 0)
        self.assertEqual(diagnostic["network"]["pending"][0]["http_status"], 200)
        self.assertEqual(diagnostic["browser_events_dropped"], 2)
        self.assertEqual(diagnostic["segments"][0]["state"], "running")
        text = "\n".join(logs.output) + json.dumps(result)
        for secret in ("fake-secret", "private-session", "11.22", "33.44", "ERR_ABORTED"):
            self.assertNotIn(secret, text)
        for field in ("remaining_ms", "deadline_exhausted", "segment_callback", "domainLookupEnd", "request_finished"):
            self.assertIn(field, text)
        page.goto.assert_called_once_with("about:blank", wait_until="commit", timeout=1000)
        self.assertIsNone(pool._contexts["private-session"]["route_diagnostic_context"])

    @patch.object(main, "_log_redaction_enabled", True)
    def test_progress_cap_keeps_latest_state_and_next_command_is_isolated(self):
        pool, page, listeners = self.pool()
        markers = []
        def evaluate(_script, args):
            self.assertFalse(args[4], "the legacy event cap applies to redacted logging")
            markers.append(args[3])
            if len(markers) == 1:
                for index in range(170):
                    payload = {"event": "segment_start", "segment": 1, "attempts": index, "state": "running", "cookie": "must-not-log"}
                    listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps(payload)))
                listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps({"event": "segment_result", "segment": 1, "state": "completed"})))
            else:
                listeners["console"](SimpleNamespace(type="debug", text=markers[0] + json.dumps({"event": "segment_start", "segment": 2})))
            return {"path": []}
        page.evaluate.side_effect = evaluate
        with self.assertLogs(level="INFO") as logs:
            first = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context())
            second = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context())
        one = first["result"]["diagnostic"]["worker"]
        two = second["result"]["diagnostic"]["worker"]
        self.assertEqual(one["progress_events_dropped"], 11)
        self.assertEqual(one["segments"][0]["state"], "completed")
        self.assertEqual(two["segments"], [])
        self.assertNotEqual(*markers)
        self.assertNotIn("must-not-log", "\n".join(logs.output))

    def test_expired_queue_emits_correlated_snapshot_without_browser_creation(self):
        pool, page, _listeners = self.pool()
        pool._do_get_context = Mock()
        with self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context(),
                                         deadline_epoch_ms=time.time() * 1000 - 1, queued_at_monotonic=time.monotonic() - 46)
        pool._do_get_context.assert_not_called()
        page.evaluate.assert_not_called()
        self.assertEqual(result["diagnostic"]["stage"], "queue")
        self.assertGreaterEqual(result["diagnostic"]["queue_wait_ms"], 46000)
        self.assertIn("queue_deadline_exhausted", "\n".join(logs.output))

    def test_large_route_counts_survive_detail_limit_and_pending_attempt_has_age(self):
        pool, page, listeners = self.pool()
        def evaluate(_script, args):
            def progress(payload):
                listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps(payload)))
            progress({"event": "route_start", "segment_count": 100})
            for segment in range(1, 100):
                progress({"event": "segment_start", "segment": segment, "state": "running"})
                progress({"event": "segment_result", "segment": segment, "state": "completed"})
            progress({"event": "segment_start", "segment": 100, "state": "running"})
            progress({"event": "segment_callback", "segment": 100, "attempt_elapsed_ms": 80})
            active = pool._contexts["private-session"]["route_diagnostic_context"]
            active["attempt_started"][100] -= .15
            raise RuntimeError("后端路径规划总时限已耗尽")
        page.evaluate.side_effect = evaluate
        with self.assertLogs(level="INFO"):
            result = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context())
        diagnostic = result["diagnostic"]
        self.assertEqual(diagnostic["completed_count"], 99)
        self.assertEqual(diagnostic["not_started_count"], 0)
        self.assertEqual(diagnostic["unfinished_count"], 1)
        self.assertEqual(diagnostic["segments"][0]["segment"], 100)
        self.assertGreaterEqual(diagnostic["segments"][0]["attempt_elapsed_ms"], 150)
        self.assertEqual(len(diagnostic["segments"]), 12)
        self.assertEqual(diagnostic["segments_omitted"], 88)

    def test_logging_failure_does_not_break_planning_or_plain_context_failure_contract(self):
        pool, page, _listeners = self.pool()
        page.evaluate.return_value = {"path": []}
        with patch("background_task_manager.logging.log", side_effect=RuntimeError("broken logger")):
            result = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context())
        self.assertTrue(result["success"])
        context_error = {"success": False, "error": "cannot initialize", "extra": "contract"}
        pool._do_get_context = Mock(return_value=context_error)
        self.assertEqual(pool._do_execute_js("private-session", "script", []), context_error)

    def test_queue_logging_keeps_request_when_queue_depth_is_unavailable(self):
        pool, _page, _listeners = self.pool()
        pool._native_threading = Mock()
        pool._native_threading.Event.return_value.wait.return_value = False
        pool._request_queue = Mock()
        pool._request_queue.qsize.side_effect = NotImplementedError("queue depth unavailable")
        with self.assertLogs(level="INFO") as logs:
            result = pool._send_request("execute_js", {"diagnostic_context": self.context()}, timeout=0)
        self.assertFalse(result["success"])
        request = pool._request_queue.put.call_args.args[0]
        self.assertIsInstance(request["queued_at_monotonic"], float)
        text = "\n".join(logs.output)
        self.assertIn("enqueued", text)
        self.assertIn("caller_wait_timeout", text)
        self.assertIn("telemetry-test", text)

    def test_counts_are_explicitly_partial_above_tracker_limit(self):
        pool, page, listeners = self.pool()
        def evaluate(_script, args):
            listeners["console"](SimpleNamespace(type="debug", text=args[3] + json.dumps({"event": "route_start", "segment_count": 5000})))
            return {"path": []}
        page.evaluate.side_effect = evaluate
        with self.assertLogs(level="INFO"):
            result = pool._do_execute_js("private-session", "script", [], diagnostic_context=self.context())
        snapshot = result["result"]["diagnostic"]["worker"]
        self.assertTrue(snapshot["counts_are_partial"])
        self.assertEqual(snapshot["segments_untracked"], 904)
        self.assertIsNone(snapshot["not_started_count"])
        self.assertIsNone(snapshot["unfinished_count"])


class RealRouteWorkerTelemetryTests(unittest.TestCase):
    @patch.object(main, "_log_redaction_enabled", True)
    def test_browser_timeout_logs_live_progress_and_pending_http_request(self):
        from playwright.sync_api import sync_playwright

        release = threading.Event()
        received = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.set()
                release.wait(3)
                try:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *_args):
                pass

        playwright = self.enterContext(sync_playwright())
        if not Path(playwright.chromium.executable_path).exists():
            self.skipTest("Playwright Chromium 未安装；真实进度与网络事件未验证")
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(release.set)
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        pool._browser = browser
        pool._contexts = {}
        script = """async () => {
            __zxRouteProgress({event:'sdk_load_ready'});
            __zxRouteProgress({event:'route_start', segment_count:2});
            __zxRouteProgress({event:'segment_start', segment:1, attempts:1, state:'running'});
            fetch('/slow?key=fake-secret&origin=11.22,33.44').catch(() => {});
            await new Promise(() => {});
        }"""
        with self.assertLogs(level="INFO") as logs:
            result = pool._do_execute_js("private-session", script, [],
                diagnostic_context={"diagnostic_id": "real-telemetry", "provider": "amap", "sensitive_values": ["fake-secret"]},
                runtime_page_origin=f"http://127.0.0.1:{server.server_port}", deadline_epoch_ms=time.time() * 1000 + 800)
        self.assertFalse(result["success"], result)
        self.assertTrue(received.is_set())
        self.assertEqual(result["diagnostic"]["segments"][0]["state"], "running")
        self.assertEqual(result["diagnostic"]["not_started_count"], 1)
        self.assertEqual(result["diagnostic"]["network"]["pending_count"], 1)
        self.assertEqual(pool._contexts["private-session"]["page"].url, "about:blank")
        text = "\n".join(logs.output)
        self.assertIn("sdk_load_ready", text)
        self.assertIn("deadline_exhausted", text)
        self.assertIn("/slow?", text)
        self.assertNotIn("fake-secret", text)
        self.assertNotIn("11.22", text)


if __name__ == "__main__":
    unittest.main()
