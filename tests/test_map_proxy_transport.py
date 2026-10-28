"""Real keep-alive and bounded lease checks for map-only upstream sessions."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
import requests

from map_proxy_transport import MapProxyTransport


@pytest.fixture
def map_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            received.append({"port": self.client_address[1],
                             "cookie": self.headers.get("Cookie"),
                             "authorization": self.headers.get("Authorization"),
                             "proxy_authorization": self.headers.get("Proxy-Authorization")})
            payload = b"isolated-map-resource"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Set-Cookie", "upstream-map=not-forwarded; Path=/")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/tile", received
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def fetch(pool, url, **options):
    return pool.request("GET", url, headers=options.pop("headers", {}),
                        body=None, timeout=(1, 1), **options)


def test_sequential_requests_reuse_tcp_without_carrying_vendor_or_application_cookies(map_server, monkeypatch):
    url, received = map_server
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    with MapProxyTransport(max_sessions=1) as pool:
        for _index in range(2):
            response = fetch(pool, url, headers={"Cookie": "app=private", "authorization": "private",
                                                "Proxy-Authorization": "private"})
            assert response.status_code == 200
            assert response.content == b"isolated-map-resource"
            response.close()
    assert len(received) == 2
    assert received[0]["port"] == received[1]["port"]
    assert all(not row[field] for row in received for field in ("cookie", "authorization", "proxy_authorization"))


def test_stream_lease_is_exclusive_bounded_and_released_only_on_close(map_server):
    url, received = map_server
    with MapProxyTransport(max_sessions=2, acquire_timeout=0) as pool:
        first, second = fetch(pool, url), fetch(pool, url)
        assert first.content and second.content
        with pytest.raises(requests.ConnectTimeout, match="capacity"):
            fetch(pool, url)
        assert len(received) == 2
        first.close()
        reused = fetch(pool, url)
        assert reused.content
        assert received[2]["port"] == received[0]["port"]
        first.close()
        with pytest.raises(requests.ConnectTimeout, match="capacity"):
            fetch(pool, url)
        second.close()
        reused.close()


def test_before_release_runs_after_response_close_and_before_session_becomes_available(map_server):
    url, _received = map_server
    called = []
    with MapProxyTransport(max_sessions=1, acquire_timeout=0) as pool:
        def detach(response):
            assert response.raw.closed
            with pytest.raises(requests.ConnectTimeout, match="capacity"):
                fetch(pool, url)
            called.append(True)

        response = fetch(pool, url, before_release=detach)
        assert response.content
        response.close()
        response.close()
        with fetch(pool, url) as next_response:
            assert next_response.content
    assert called == [True]


class TrackedSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


def test_shutdown_refuses_new_leases_and_closes_active_session_when_returned(map_server):
    url, _received = map_server
    sessions = []

    def factory():
        session = TrackedSession()
        sessions.append(session)
        return session

    pool = MapProxyTransport(max_sessions=1, session_factory=factory)
    response = fetch(pool, url)
    assert response.content
    pool.close()
    with pytest.raises(RuntimeError, match="closed"):
        fetch(pool, url)
    assert sessions[0].close_calls == 0
    response.close()
    pool.close()
    assert sessions[0].close_calls == 1


def test_request_failure_discards_session_and_releases_capacity(map_server):
    url, _received = map_server
    failed = TrackedSession()
    failed.request = lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.ReadTimeout("isolated"))
    candidates = iter([failed, requests.Session()])
    with MapProxyTransport(max_sessions=1, acquire_timeout=0, session_factory=lambda: next(candidates)) as pool:
        with pytest.raises(requests.ReadTimeout, match="isolated"):
            fetch(pool, url)
        assert failed.close_calls == 1
        with fetch(pool, url) as response:
            assert response.content


def test_callback_failure_discards_session_and_releases_capacity(map_server):
    url, _received = map_server
    failed = TrackedSession()
    candidates = iter([failed, requests.Session()])
    with MapProxyTransport(max_sessions=1, acquire_timeout=0, session_factory=lambda: next(candidates)) as pool:
        response = fetch(pool, url, before_release=lambda _response: (_ for _ in ()).throw(ValueError("isolated detach failure")))
        assert response.content
        with pytest.raises(ValueError, match="detach"):
            response.close()
        assert failed.close_calls == 1
        with fetch(pool, url) as next_response:
            assert next_response.content


def test_session_creation_failure_does_not_reserve_capacity_forever(map_server):
    url, _received = map_server
    attempts = []

    def factory():
        attempts.append(True)
        if len(attempts) == 1:
            raise ValueError("isolated creation failure")
        return requests.Session()

    with MapProxyTransport(max_sessions=1, acquire_timeout=0, session_factory=factory) as pool:
        with pytest.raises(ValueError, match="creation"):
            fetch(pool, url)
        with fetch(pool, url) as response:
            assert response.content


def test_injected_adapters_are_created_once_per_session_and_closed_on_shutdown(map_server):
    url, _received = map_server
    adapters = []

    def adapter_factory():
        adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=1, max_retries=0)
        adapters.append(adapter)
        return adapter

    with MapProxyTransport(max_sessions=1, adapter_factory=adapter_factory) as pool:
        for _index in range(2):
            with fetch(pool, url) as response:
                assert response.content
    assert len(adapters) == 2


def test_parallel_streams_wait_for_bounded_exclusive_session_leases(map_server):
    url, received = map_server
    condition = threading.Condition()
    release = threading.Event()
    entered = []
    sessions = []

    def factory():
        session = TrackedSession()
        sessions.append(session)
        return session

    with MapProxyTransport(max_sessions=3, acquire_timeout=2, session_factory=factory) as pool:
        def worker():
            with fetch(pool, url) as response:
                assert response.content
                with condition:
                    entered.append(True)
                    condition.notify_all()
                assert release.wait(3)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(worker) for _index in range(6)]
            try:
                with condition:
                    assert condition.wait_for(lambda: len(entered) == 3, timeout=2)
                assert len(received) == len(sessions) == 3
                release.set()
                for future in futures:
                    future.result(timeout=3)
            finally:
                release.set()
    assert len(received) == 6
    assert len({row["port"] for row in received}) == 3
    assert all(session.close_calls == 1 for session in sessions)


def test_response_close_failure_discards_session_and_releases_capacity(map_server):
    url, _received = map_server
    failed = TrackedSession()

    class BrokenResponse:
        def close(self):
            raise ValueError("isolated response close failure")

    failed.request = lambda *_args, **_kwargs: BrokenResponse()
    candidates = iter([failed, requests.Session()])
    callbacks = []
    with MapProxyTransport(max_sessions=1, acquire_timeout=0, session_factory=lambda: next(candidates)) as pool:
        response = fetch(pool, url, before_release=lambda _response: callbacks.append(True))
        with pytest.raises(ValueError, match="response close"):
            response.close()
        response.close()
        assert failed.close_calls == 1
        with fetch(pool, url) as next_response:
            assert next_response.content
    assert callbacks == [True]


def test_request_deadline_shortens_capacity_wait_without_releasing_another_lease(map_server):
    url, received = map_server
    with MapProxyTransport(max_sessions=1, acquire_timeout=1) as pool:
        first = fetch(pool, url)
        try:
            started = time.monotonic()
            with pytest.raises(requests.ConnectTimeout):
                fetch(pool, url, acquire_timeout=.05)
            assert time.monotonic() - started < .30
            assert len(received) == 1
        finally:
            first.close()
        with fetch(pool, url, acquire_timeout=.5) as next_response:
            assert next_response.content


@pytest.mark.parametrize("remaining", [0, -1])
def test_expired_request_never_borrows_an_idle_session(map_server, remaining):
    url, received = map_server
    with MapProxyTransport(max_sessions=1) as pool:
        with fetch(pool, url) as first:
            assert first.content
        with pytest.raises(requests.ConnectTimeout):
            fetch(pool, url, acquire_timeout=remaining)
        assert len(received) == 1


def test_expired_budget_during_session_creation_discards_it_without_network_request():
    sessions = []

    class SlowSession(TrackedSession):
        def request(self, *_args, **_kwargs):
            raise AssertionError("expired request must not reach the network")

    def factory():
        session = SlowSession()
        sessions.append(session)
        time.sleep(.04)
        return session

    with MapProxyTransport(session_factory=factory) as pool:
        with pytest.raises(requests.ConnectTimeout):
            fetch(pool, "http://isolated.invalid/", acquire_timeout=.01)
        assert sessions[0].close_calls == 1
        assert pool._allocated == 0
