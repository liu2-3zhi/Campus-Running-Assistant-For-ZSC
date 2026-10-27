import time
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

from background_task_manager import ChromeBrowserPool
from map_runtime_origin import MAP_RUNTIME_MARKER


class RuntimeOriginBrowserTests(unittest.TestCase):
    def pool(self):
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        page = Mock()
        page.url = "https://maps.test/map-runtime"
        page.evaluate.side_effect = [{"origin": "https://maps.test", "marker": MAP_RUNTIME_MARKER}, {"path": [[1, 2]]}]
        pool._contexts = {"secret-session": {"page": page}}
        pool._do_get_context = Mock(return_value={"success": True})
        return pool, page

    def test_origin_is_fulfilled_locally_and_verified_before_planning(self):
        pool, page = self.pool()
        result = pool._do_execute_js("secret-session", "() => 7", [], runtime_page_origin="https://maps.test/path")
        self.assertTrue(result["success"])
        self.assertEqual(page.goto.call_args.args[0], "https://maps.test/map-runtime")
        self.assertNotIn("secret-session", str(page.goto.call_args))
        handler = page.route.call_args.args[1]
        route = Mock()
        handler(route)
        self.assertEqual(route.fulfill.call_args.kwargs["headers"]["Referrer-Policy"], "strict-origin")
        self.assertIn(MAP_RUNTIME_MARKER, route.fulfill.call_args.kwargs["body"])
        route.continue_.assert_not_called()
        self.assertEqual(page.unroute.call_count, 2)
        self.assertEqual(page.evaluate.call_count, 2)

    def test_origin_verification_failure_stops_before_script(self):
        pool, page = self.pool()
        page.evaluate.side_effect = [{"origin": "https://wrong.test", "marker": MAP_RUNTIME_MARKER}]
        result = pool._do_execute_js("secret-session", "() => 7", [], runtime_page_origin="https://maps.test")
        self.assertFalse(result["success"])
        self.assertEqual(page.evaluate.call_count, 1)
        self.assertEqual(page.unroute.call_count, 2)

    def test_expired_queue_task_does_not_create_context(self):
        pool, page = self.pool()
        result = pool._do_execute_js("secret-session", "() => 7", [], runtime_page_origin="https://maps.test",
                                     deadline_epoch_ms=time.time() * 1000 - 10)
        self.assertFalse(result["success"])
        pool._do_get_context.assert_not_called()
        page.goto.assert_not_called()

    def test_ordinary_call_keeps_existing_evaluate_contract(self):
        pool, page = self.pool()
        page.evaluate.side_effect = None
        page.evaluate.return_value = 7
        result = pool._do_execute_js("secret-session", "() => 7", [1])
        self.assertEqual(result, {"success": True, "result": 7})
        page.evaluate.assert_called_once_with("() => 7", [1])
        page.goto.assert_not_called()

    def test_origin_and_deadline_travel_in_one_queue_request(self):
        pool, _ = self.pool()
        pool._send_request = Mock(return_value={"success": True, "result": 7})
        deadline = time.time() * 1000 + 40000
        self.assertEqual(pool.execute_js("secret-session", "() => 7", runtime_page_origin="https://maps.test", deadline_epoch_ms=deadline), 7)
        args = pool._send_request.call_args.args
        self.assertEqual(args[0], "execute_js")
        self.assertEqual(args[1]["runtime_page_origin"], "https://maps.test")
        self.assertEqual(args[1]["deadline_epoch_ms"], deadline)


class RealRuntimeOriginBrowserTests(unittest.TestCase):
    def test_real_browser_origin_changes_without_contacting_document_servers(self):
        from playwright.sync_api import sync_playwright

        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(500)
                self.end_headers()

            def log_message(self, *_args):
                pass

        playwright = self.enterContext(sync_playwright())
        if not Path(playwright.chromium.executable_path).exists():
            self.skipTest("Playwright Chromium 未安装；真实来源拦截未验证")
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
        pool._initialized = True
        pool._browser = browser
        pool._contexts = {}
        servers = [ThreadingHTTPServer(("127.0.0.1", 0), Handler) for _ in range(2)]
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        for server in servers:
            origin = f"http://127.0.0.1:{server.server_port}"
            result = pool._do_execute_js("private-session-id", "([value]) => ({origin: location.origin, value, cookie: document.cookie})", [7],
                runtime_page_origin=origin, deadline_epoch_ms=time.time() * 1000 + 5000)
            self.assertTrue(result["success"], result)
            self.assertEqual(result["result"], {"origin": origin, "value": 7, "cookie": ""})
        self.assertEqual(received, [], "来源站点不应收到真实页面请求")
        self.assertEqual(pool._contexts["private-session-id"]["context"].cookies(), [])
        timed_out = pool._do_execute_js("private-session-id", "() => new Promise(() => {})", [],
            diagnostic_context={"diagnostic_id": "timeout-test"}, runtime_page_origin=origin,
            deadline_epoch_ms=time.time() * 1000 + 500)
        self.assertFalse(timed_out["success"], timed_out)
        self.assertIn("总时限", timed_out["error"])
        self.assertEqual(pool._contexts["private-session-id"]["page"].url, "about:blank")
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
