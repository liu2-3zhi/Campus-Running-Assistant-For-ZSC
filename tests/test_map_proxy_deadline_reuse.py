"""Actual keep-alive sockets must belong to the current request deadline only."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import nullcontext
import socket
import threading
import time
from types import SimpleNamespace

import pytest
import requests
from urllib3.util import Timeout
from urllib3.exceptions import NewConnectionError

from map_proxy_transport import MapProxyDNSResolver, MapProxyTransport
import map_request_proxy
from map_request_proxy import _MapProxy, _TileDeadlineAdapter, _TileRequestDeadline
from tests.test_map_proxy_tile_retry import make_fetch, response, TILE


def test_fast_connect_keeps_the_unused_tile_read_budget():
    observed = []

    def transport(*args, **kwargs):
        observed.append(kwargs["timeout"])
        return response()

    assert make_fetch(transport)(TILE)[0] == 200
    timeout = observed[0]
    assert isinstance(timeout, Timeout)
    assert timeout.total <= 6
    timeout.start_connect()
    assert timeout.read_timeout > 5, "fast connections must not lose half the reading budget"


def test_reused_socket_uses_current_deadline_and_old_cancellation_is_detached():
    ports = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            ports.append(self.client_address[1])
            self.send_response(200)
            self.send_header("Content-Length", "100" if self.path == "/slow" else "2")
            self.end_headers()
            try:
                if self.path == "/slow":
                    for _ in range(100):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(.01)
                else:
                    self.wfile.write(b"ok")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    pool = MapProxyTransport(max_sessions=1, adapter_factory=_TileDeadlineAdapter)
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with _TileRequestDeadline(time.monotonic() + 1) as old:
            first = pool.request("GET", url, headers={}, body=None, timeout=(.2, .2), before_release=old.detach)
            assert first.content == b"ok"
            first.close()
        with _TileRequestDeadline(time.monotonic() + .12) as current:
            second = pool.request("GET", url + "/slow", headers={}, body=None, timeout=(.2, .2), before_release=current.detach)
            old._expire()
            assert old.current_socket is None
            started = time.monotonic()
            try:
                with pytest.raises((requests.RequestException, OSError)):
                    _ = second.content
                assert time.monotonic() - started < .4
                assert current.expired.is_set()
            finally:
                second.close()
        assert ports[0] == ports[1], "the second request must reuse the actual TCP connection"
    finally:
        pool.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def stop_dns(pool, release):
    release.set()
    pool.close()
    for worker in pool._workers:
        worker.join(timeout=1)
        assert not worker.is_alive()


def test_active_tile_dns_timeout_returns_before_lookup_and_never_creates_a_socket(monkeypatch):
    dns = MapProxyDNSResolver(max_workers=1, max_requests=2)
    entered, release = threading.Event(), threading.Event()
    created = []

    def blocked_resolver(*_args, **_kwargs):
        entered.set()
        assert release.wait(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]

    def resolve(host, port, *, deadline, resolver=None):
        return dns.resolve(host, port, deadline=deadline, resolver=blocked_resolver)

    def forbid_socket(*_args, **_kwargs):
        created.append(True)
        raise AssertionError('expired DNS must not start a connection')

    monkeypatch.setattr(map_request_proxy, 'resolve_map_host', resolve)
    monkeypatch.setattr(map_request_proxy.socket, 'socket', forbid_socket)
    pool = MapProxyTransport(max_sessions=1, adapter_factory=_TileDeadlineAdapter)
    try:
        started = time.monotonic()
        with _TileRequestDeadline(time.monotonic() + .12) as deadline:
            with pytest.raises(requests.ConnectTimeout):
                pool.request('GET', 'http://rt0.map.gtimg.com/tile', headers={}, body=None,
                             timeout=(.2, .2), before_release=deadline.detach)
        assert entered.is_set()
        assert time.monotonic() - started < .45
        assert created == []
        assert pool._allocated == 0
        assert len(dns._workers) == 1
    finally:
        pool.close()
        stop_dns(dns, release)


def test_public_host_preflight_has_its_own_bounded_dns_budget(monkeypatch):
    dns = MapProxyDNSResolver(max_workers=1, max_requests=2)
    release = threading.Event()

    def blocked_resolver(*_args, **_kwargs):
        assert release.wait(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]

    monkeypatch.setattr(map_request_proxy, 'REQUEST_TIMEOUT', (.05, .2))
    monkeypatch.setattr(map_request_proxy, 'resolve_map_host', lambda host, port, *, deadline, resolver=None:
                        dns.resolve(host, port, deadline=deadline, resolver=blocked_resolver))
    try:
        started = time.monotonic()
        assert map_request_proxy._resolve_public_host('rt0.map.gtimg.com') is False
        assert time.monotonic() - started < .30
    finally:
        stop_dns(dns, release)


@pytest.mark.parametrize('active_tile_deadline', [True, False])
@pytest.mark.parametrize('include_public_address', [True, False])
def test_public_preflight_cannot_be_rebound_to_private_connection(monkeypatch, active_tile_deadline, include_public_address):
    public = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
    rebound = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
    if include_public_address:
        rebound = public + rebound
    created = []

    def resolve(_host, _port, *, deadline, resolver=None):
        return public if resolver is not None else rebound

    class Socket:
        def __init__(self, *_args, **_kwargs):
            created.append(self)
        def settimeout(self, _value):
            pass
        def setsockopt(self, *_args):
            pass
        def connect(self, _address):
            pass
        def close(self):
            pass

    monkeypatch.setattr(map_request_proxy, 'resolve_map_host', resolve)
    monkeypatch.setattr(map_request_proxy.socket, 'getaddrinfo', lambda *_a, **_k: rebound)
    monkeypatch.setattr(map_request_proxy.socket, 'socket', Socket)
    assert map_request_proxy._resolve_public_host('rt0.map.gtimg.com') is True
    adapter = _TileDeadlineAdapter()
    connection = adapter.poolmanager.pool_classes_by_scheme['http'].ConnectionCls(
        host='rt0.map.gtimg.com', port=443, timeout=.2)
    try:
        context = _TileRequestDeadline(time.monotonic() + .2) if active_tile_deadline else nullcontext()
        with context:
            with pytest.raises(NewConnectionError):
                connection._new_conn()
        assert created == [], 'rebound private addresses must be rejected before opening a socket'
    finally:
        connection.close()
        adapter.close()


def test_proxy_transport_uses_remaining_active_tile_budget_for_pool_capacity(monkeypatch):
    requested = []

    class Session(requests.Session):
        def request(self, *_args, **_kwargs):
            requested.append(True)
            return SimpleNamespace(close=lambda: None)

    pool = MapProxyTransport(max_sessions=1, acquire_timeout=1, session_factory=Session)
    monkeypatch.setattr(map_request_proxy, '_UPSTREAM_TRANSPORT', pool)
    first = pool.request('GET', 'http://isolated.invalid/', headers={}, body=None, timeout=.2)
    try:
        started = time.monotonic()
        with _TileRequestDeadline(time.monotonic() + .05):
            with pytest.raises(requests.ConnectTimeout):
                _MapProxy._request_upstream('GET', 'http://isolated.invalid/', headers={}, body=None, timeout=.2)
        assert time.monotonic() - started < .30
        assert requested == [True]
        first.close()
        with _MapProxy._request_upstream('GET', 'http://isolated.invalid/', headers={}, body=None, timeout=.2):
            assert requested == [True, True]
    finally:
        first.close()
        pool.close()
