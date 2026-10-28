import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from types import SimpleNamespace

from flask import Flask, g

from map_request_proxy import PROXY_COOKIE_NAME, PROXY_COOKIE_PATH, register_map_proxy_routes


SESSION_ID = "11111111-1111-4111-8111-111111111111"
RESOURCE = "/map-proxy/tencent/https/rt0.map.gtimg.com/tile.png"


class ObservedSemaphore:
    def __init__(self, semaphore):
        self.semaphore = semaphore
        self.condition = threading.Condition()
        self.calls = []

    def acquire(self, *args, **kwargs):
        with self.condition:
            self.calls.append((args, kwargs))
            self.condition.notify_all()
        return self.semaphore.acquire(*args, **kwargs)

    def release(self):
        return self.semaphore.release()

    def wait_for_calls(self, count):
        with self.condition:
            return self.condition.wait_for(lambda: len(self.calls) >= count, timeout=2)


class MapProxyConcurrencyTests(unittest.TestCase):
    def make_proxy(self, transport, concurrency=2, **options):
        app = Flask(__name__)
        app.testing = True
        app.secret_key = "isolated-concurrency-test"

        def login_required(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                g.user = "admin"
                g.session_id = SESSION_ID
                return view(*args, **kwargs)
            return wrapped

        proxy = register_map_proxy_routes(
            app, login_required,
            lambda: SimpleNamespace(get=lambda section, key, fallback=None:
                                    {"frontend_proxy_enabled": True}.get(key, fallback) if section == "Map" else fallback),
            lambda *_args: True,
            transport=transport,
            dns_resolver=lambda _host, port, **_kwargs: [(None, None, None, None, ("8.8.8.8", port))],
            max_concurrent_requests=concurrency,
            **options,
        )
        proxy.semaphore = ObservedSemaphore(proxy.semaphore)
        with app.test_client() as client:
            client.set_cookie("auth_token", "isolated-token")
            response = client.post("/api/map-proxy/context", headers={
                "Origin": "http://localhost", "X-Session-ID": SESSION_ID,
            })
            self.assertEqual(response.status_code, 200)
            context = client.get_cookie(PROXY_COOKIE_NAME, path=PROXY_COOKIE_PATH).value

        def fetch(path=RESOURCE):
            with app.test_client() as client:
                client.set_cookie("auth_token", "isolated-token")
                client.set_cookie(PROXY_COOKIE_NAME, context, path=PROXY_COOKIE_PATH)
                response = client.get(path)
                return response.status_code, response.data, dict(response.headers)

        return proxy, fetch

    @staticmethod
    def response(close=None):
        return SimpleNamespace(
            status_code=200, content=b"isolated-tile", headers={"Content-Type": "image/png"},
            close=close or (lambda: None),
        )

    def test_short_burst_waits_without_increasing_active_upstream_limit(self):
        release = threading.Event()
        saturated = threading.Event()
        lock = threading.Lock()
        active = 0
        peak = 0
        entered = 0

        def transport(*_args, **_kwargs):
            nonlocal active, peak, entered
            with lock:
                active += 1
                peak = max(peak, active)
                entered += 1
                if active == 2:
                    saturated.set()
            try:
                self.assertTrue(release.wait(timeout=5))
                return self.response()
            finally:
                with lock:
                    active -= 1

        proxy, fetch = self.make_proxy(transport)
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch) for _ in range(6)]
            try:
                self.assertTrue(proxy.semaphore.wait_for_calls(6))
                self.assertTrue(saturated.wait(timeout=2))
                with lock:
                    self.assertEqual(active, 2)
                release.set()
                responses = [future.result(timeout=3) for future in futures]
            finally:
                release.set()
        self.assertEqual([status for status, _body, _headers in responses], [200] * 6)
        self.assertEqual(entered, 6)
        self.assertEqual(peak, 2)
        for _status, body, headers in responses:
            self.assertEqual(body, b"isolated-tile")
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertEqual(headers["Cache-Control"], "no-store")

    def test_queue_admission_rejects_only_above_twice_the_active_limit(self):
        release = threading.Event()

        def transport(*_args, **_kwargs):
            self.assertTrue(release.wait(timeout=5))
            return self.response()

        proxy, fetch = self.make_proxy(transport)
        with ThreadPoolExecutor(max_workers=7) as executor:
            accepted = [executor.submit(fetch) for _ in range(6)]
            try:
                self.assertTrue(proxy.semaphore.wait_for_calls(6))
                overflow = executor.submit(fetch).result(timeout=1)
                self.assertEqual(overflow[:2], (429, b""))
                release.set()
                self.assertEqual([future.result(timeout=3)[0] for future in accepted], [200] * 6)
            finally:
                release.set()
        self.assertEqual(fetch()[0], 200)

    def test_queued_request_times_out_after_three_seconds_and_releases_admission(self):
        release = threading.Event()
        started = threading.Event()

        def transport(*_args, **_kwargs):
            started.set()
            self.assertTrue(release.wait(timeout=6))
            return self.response()

        proxy, fetch = self.make_proxy(transport, concurrency=1)
        with ThreadPoolExecutor(max_workers=2) as executor:
            active = executor.submit(fetch)
            try:
                self.assertTrue(proxy.semaphore.wait_for_calls(1))
                self.assertTrue(started.wait(timeout=2))
                started_at = time.monotonic()
                queued = executor.submit(fetch).result(timeout=4)
                elapsed = time.monotonic() - started_at
                self.assertEqual(queued[:2], (429, b""))
                self.assertGreaterEqual(elapsed, 2.8)
                self.assertLess(elapsed, 3.8)
                release.set()
                self.assertEqual(active.result(timeout=2)[0], 200)
            finally:
                release.set()
        self.assertEqual(fetch()[0], 200)

    def test_upstream_and_close_exceptions_release_active_and_admission_permits(self):
        mode = {"value": "transport"}

        def close():
            if mode["value"] == "close":
                raise RuntimeError("isolated close failure")

        def transport(*_args, **_kwargs):
            if mode["value"] == "transport":
                raise RuntimeError("isolated transport failure")
            if mode["value"] == "oversized":
                response = self.response(close)
                response.content = b"x" * 65
                return response
            return self.response(close)

        proxy, fetch = self.make_proxy(transport, concurrency=1, max_response_bytes=64)
        self.assertEqual(fetch()[0], 502)
        mode["value"] = "close"
        with self.assertRaisesRegex(RuntimeError, "isolated close failure"):
            fetch()
        mode["value"] = "oversized"
        self.assertEqual(fetch()[0], 502)
        mode["value"] = "ok"
        self.assertEqual(fetch()[0], 200)
        self.assert_all_permits_available(proxy)

    def assert_all_permits_available(self, proxy, concurrency=1):
        active = []
        admitted = []
        try:
            for _ in range(concurrency):
                self.assertTrue(proxy.semaphore.acquire(blocking=False))
                active.append(True)
            self.assertFalse(proxy.semaphore.acquire(blocking=False))
            for _ in range(concurrency * 3):
                self.assertTrue(proxy.admission_semaphore.acquire(blocking=False))
                admitted.append(True)
            self.assertFalse(proxy.admission_semaphore.acquire(blocking=False))
        finally:
            for _ in active:
                proxy.semaphore.release()
            for _ in admitted:
                proxy.admission_semaphore.release()

    def test_active_acquire_exception_releases_admission_without_over_releasing_active(self):
        proxy, fetch = self.make_proxy(lambda *_args, **_kwargs: self.response(), concurrency=1)
        original = proxy.semaphore.acquire

        def fail_acquire(*_args, **_kwargs):
            raise RuntimeError("isolated slot acquisition failure")

        proxy.semaphore.acquire = fail_acquire
        self.assertEqual(fetch()[:2], (502, b""))
        proxy.semaphore.acquire = original
        self.assert_all_permits_available(proxy)
        self.assertEqual(fetch()[0], 200)

    def test_validation_and_upstream_early_returns_release_both_limits(self):
        current_response = {"value": self.response()}
        proxy, fetch = self.make_proxy(lambda *_args, **_kwargs: current_response["value"], concurrency=1)
        public_resolver = proxy.dns_resolver
        cases = [
            ("query", RESOURCE + "?" + "&".join(f"p{index}=x" for index in range(257)), 400),
            ("dns", RESOURCE, 400),
            ("redirect", RESOURCE, 502),
            ("not_modified", RESOURCE, 304),
            ("declared_length", RESOURCE, 502),
        ]
        for name, path, status in cases:
            with self.subTest(name=name):
                proxy.dns_resolver = public_resolver
                response = self.response()
                if name == "dns":
                    proxy.dns_resolver = lambda *_args, **_kwargs: []
                elif name == "redirect":
                    response.status_code = 302
                elif name == "not_modified":
                    response.status_code = 304
                elif name == "declared_length":
                    response.headers["Content-Length"] = str(proxy.max_response_bytes + 1)
                current_response["value"] = response
                self.assertEqual(fetch(path)[:2], (status, b""))
                self.assert_all_permits_available(proxy)


if __name__ == "__main__":
    unittest.main()
