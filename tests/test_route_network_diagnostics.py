"""Direct route-network diagnostics never block a planner or send HTTP data."""

import importlib
import importlib.util
import json
import socket
import ssl
import threading
import time
from types import SimpleNamespace

import pytest


def test_route_network_probe_has_an_importable_entry_point():
    assert importlib.util.find_spec("route_network_diagnostics") is not None, (
        "route timeout diagnostics need an independent, nonblocking probe module"
    )


@pytest.fixture
def runtime(monkeypatch):
    probe = importlib.import_module("route_network_diagnostics")
    threads = []
    original_thread = threading.Thread

    def create_thread(**kwargs):
        thread = original_thread(**kwargs)
        threads.append(thread)
        return thread

    def forbid_dns(*_args, **_kwargs):
        raise AssertionError("Tests must not access a real network")

    monkeypatch.setattr(probe, "Thread", create_thread)
    monkeypatch.setattr(probe, "_PROBE_SLOTS", threading.BoundedSemaphore(2))
    monkeypatch.setattr(probe.socket, "getaddrinfo", forbid_dns)
    value = SimpleNamespace(probe=probe, threads=threads, events=[])
    value.emit = lambda event, **fields: value.events.append({"event": event, **fields})
    yield value
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive(), "diagnostic worker did not release its resources"


def finish(runtime):
    for thread in runtime.threads:
        thread.join(timeout=2)
        assert not thread.is_alive()
    return runtime.events


def dns_row(family=socket.AF_INET, ip="203.0.113.5"):
    address = (ip, 443) if family == socket.AF_INET else (ip, 443, 0, 0)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", address)


class FakeSocket:
    def __init__(self, connect_error=None, handshake_error=None):
        self.connect_error = connect_error
        self.handshake_error = handshake_error
        self.closed = False
        self.timeouts = []
        self.address = None
        self.handshakes = 0

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def connect(self, address):
        self.address = address
        if self.connect_error:
            raise self.connect_error

    def do_handshake(self):
        self.handshakes += 1
        if self.handshake_error:
            raise self.handshake_error

    def close(self):
        self.closed = True

    def send(self, *_args):
        raise AssertionError("A network probe must never send application bytes")

    sendall = send


def transport(runtime, monkeypatch, *, connect_error=None, tls_error=None):
    raw, tls, wraps = [], [], []

    def new_socket(family, sock_type, proto=0):
        assert family in (socket.AF_INET, socket.AF_INET6)
        assert sock_type == socket.SOCK_STREAM
        assert proto in (0, socket.IPPROTO_TCP)
        value = FakeSocket(connect_error=connect_error)
        raw.append(value)
        return value

    def wrap(sock, *, server_hostname, do_handshake_on_connect):
        assert do_handshake_on_connect is False
        wraps.append((sock, server_hostname))
        value = FakeSocket(handshake_error=tls_error)
        tls.append(value)
        return value

    monkeypatch.setattr(runtime.probe.socket, "socket", new_socket)
    monkeypatch.setattr(runtime.probe.ssl, "create_default_context", lambda: SimpleNamespace(wrap_socket=wrap))
    return raw, tls, wraps


@pytest.mark.parametrize("provider,hosts", [
    ("amap", ["restapi.amap.com", "webapi.amap.com", "restapi.amap.com"]),
    ("amap", ["restapi.amap.com.attacker.test"]),
    ("amap", ["https://restapi.amap.com/path"]),
    ("amap", ["restapi.amap.com:8443"]),
    ("amap", ["127.0.0.1"]),
    ("baidu", ["restapi.amap.com"]),
    ("unknown", ["restapi.amap.com"]),
    ("amap", []),
    ("amap", "restapi.amap.com"),
])
def test_unapproved_destinations_and_more_than_two_hosts_are_rejected(runtime, provider, hosts):
    assert runtime.probe.schedule_route_network_probe(provider, hosts, runtime.emit) is False
    assert runtime.threads == []
    assert runtime.events == []


def test_environment_reports_presence_only_even_for_empty_proxy_value(runtime, monkeypatch):
    names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy")
    # A plain mapping tests each spelling independently on Windows as well.
    monkeypatch.setattr(runtime.probe.os, "environ", {
        "HTTPS_PROXY": "http://example-user:placeholder-password@proxy.test:8080",
        "http_proxy": "", "NO_PROXY": "private-placeholder.test",
    })
    env = runtime.probe.route_network_environment()
    assert env["probe_transport"] == "python_direct"
    assert env["browser_proxy_usage"] == "unknown"
    assert env["proxy_env_confirms_browser_proxy"] is False
    assert env["platform"] and env["python_version"]
    assert env["proxy_env_present"] == {name: name in {"HTTPS_PROXY", "http_proxy", "NO_PROXY"} for name in names}
    text = json.dumps(env)
    assert "placeholder-password" not in text and "proxy.test" not in text
    assert "private-placeholder.test" not in text


def test_optional_native_module_lookup_failure_cannot_break_application_import(runtime, monkeypatch):
    from eventlet import patcher
    def unavailable(_name):
        raise RuntimeError("optional runtime unavailable")
    monkeypatch.setattr(patcher, "original", unavailable)
    assert runtime.probe._native_module("socket") is socket


def test_host_selection_filters_untrusted_rows_and_takes_first_two_approved_hosts(runtime):
    hosts = [None, 123, "evil.test", "restapi.amap.com:443", "restapi.amap.com",
             "restapi.amap.com", "webapi.amap.com", "apis.map.qq.com"]
    assert runtime.probe.select_route_probe_hosts("amap", hosts) == ["restapi.amap.com", "webapi.amap.com"]
    assert runtime.probe.select_route_probe_hosts("unknown", hosts) == []
    assert runtime.probe.select_route_probe_hosts("amap", "restapi.amap.com") == []


def test_host_selection_does_not_examine_more_than_128_rows(runtime):
    seen = []
    def rows():
        for index in range(1000):
            seen.append(index)
            yield "restapi.amap.com" if index == 128 else "unapproved.test"
    assert runtime.probe.select_route_probe_hosts("amap", rows()) == []
    assert len(seen) == 128


def test_dns_failure_records_only_exception_type_and_numeric_errno(runtime, monkeypatch):
    def lookup(*_args, **_kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "private resolver details")
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lookup)
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
    events = finish(runtime)
    error = next(row for row in events if row["phase"] == "dns" and row["state"] == "error")
    assert error["state"] == "error"
    assert error["error_type"] == "gaierror" and error["errno"] == socket.EAI_NONAME
    assert "private resolver details" not in json.dumps(events)
    assert events[-1]["phase"] == "finished"


def test_tcp_timeout_never_enters_tls_and_closes_socket(runtime, monkeypatch):
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [dns_row()])
    raw, tls, _wraps = transport(runtime, monkeypatch, connect_error=TimeoutError("private endpoint"))
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
    events = finish(runtime)
    error = next(row for row in events if row["phase"] == "tcp")
    assert error["state"] == "error" and error["error_type"] == "TimeoutError"
    assert error["family"] == "ipv4" and error["ip"] == "203.0.113.5"
    assert raw[0].closed and not tls
    assert raw[0].address == ("203.0.113.5", 443)
    assert 0 < raw[0].timeouts[0] <= 1
    assert "private endpoint" not in json.dumps(events)


def test_tls_failure_keeps_tcp_success_and_closes_all_sockets(runtime, monkeypatch):
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [dns_row()])
    raw, tls, wraps = transport(runtime, monkeypatch, tls_error=ssl.SSLCertVerificationError(1, "private certificate data"))
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
    events = finish(runtime)
    assert next(row for row in events if row["phase"] == "tcp")["state"] == "ok"
    failure = next(row for row in events if row["phase"] == "tls")
    assert failure["state"] == "error" and failure["error_type"] == "SSLCertVerificationError"
    assert wraps[0][1] == "restapi.amap.com"
    assert raw[0].closed and tls[0].closed and tls[0].handshakes == 1
    assert all(0 < value <= 1 for value in raw[0].timeouts + tls[0].timeouts)
    assert "private certificate data" not in json.dumps(events)


@pytest.mark.parametrize("provider,host", [
    ("amap", "restapi.amap.com"), ("tencent", "apis.map.qq.com"),
    ("tianditu", "api.tianditu.gov.cn"), ("baidu", "api.map.baidu.com"),
])
def test_success_probes_only_first_address_of_each_family(runtime, monkeypatch, provider, host):
    rows = [dns_row(), dns_row(ip="203.0.113.6"),
            dns_row(socket.AF_INET6, "2001:db8::5"), dns_row(socket.AF_INET6, "2001:db8::6")]
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: rows)
    raw, tls, wraps = transport(runtime, monkeypatch)
    assert runtime.probe.schedule_route_network_probe(provider, [host], runtime.emit)
    events = finish(runtime)
    dns = next(row for row in events if row["phase"] == "dns" and row["state"] == "ok")
    assert dns["addresses"] == [{"family": "ipv4", "ip": "203.0.113.5"}, {"family": "ipv6", "ip": "2001:db8::5"}]
    assert len(raw) == len(tls) == 2
    assert all(row["state"] == "ok" for row in events if row["phase"] in {"tcp", "tls"})
    assert {row["family"] for row in events if row["phase"] == "tls"} == {"ipv4", "ipv6"}
    assert all(value.closed for value in raw + tls)
    assert all(value[1] == host for value in wraps)
    assert runtime.threads[0].daemon is True
    assert events[-1]["dns_cancellable"] is False


def test_blocked_dns_returns_immediately_and_holds_global_concurrency_slots(runtime, monkeypatch):
    gate = threading.Event()
    entered = threading.Event()
    def blocked(*_args, **_kwargs):
        entered.set()
        gate.wait(timeout=2)
        raise socket.gaierror(socket.EAI_NONAME, "test")
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", blocked)
    try:
        start = time.perf_counter()
        assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
        assert time.perf_counter() - start < 0.5
        assert entered.wait(timeout=1)
        assert runtime.events[0]["phase"] == "start"
        assert any(row["phase"] == "dns" and row["state"] == "started" and row["dns_timeout_control"] == "system" for row in runtime.events)
        assert runtime.probe.schedule_route_network_probe("amap", ["webapi.amap.com"], runtime.emit)
        assert runtime.probe.schedule_route_network_probe("baidu", ["api.map.baidu.com"], runtime.emit) is False
    finally:
        gate.set()
        finish(runtime)
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
    finish(runtime)


def test_slow_uncancellable_dns_exhausts_budget_before_any_connect(runtime, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runtime.probe, "monotonic", lambda: clock[0])
    def lookup(*_args, **_kwargs):
        clock[0] += 4.1
        return [dns_row()]
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lookup)
    raw, _tls, _wraps = transport(runtime, monkeypatch)
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com", "webapi.amap.com"], runtime.emit)
    events = finish(runtime)
    assert not raw
    assert next(row for row in events if row["phase"] == "dns" and row["state"] == "ok")["duration_ms"] == 4100
    assert events[-1]["budget_exhausted"] is True
    assert events[-1]["dns_cancellable"] is False


def test_two_hosts_expose_at_most_four_selected_addresses(runtime, monkeypatch):
    def lookup(host, port, family, kind):
        assert port == 443 and family == socket.AF_UNSPEC and kind == socket.SOCK_STREAM
        suffix = "5" if host == "restapi.amap.com" else "6"
        return [dns_row(ip="203.0.113." + suffix), dns_row(ip="203.0.113.99"),
                dns_row(socket.AF_INET6, "2001:db8::" + suffix)]
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lookup)
    raw, tls, _wraps = transport(runtime, monkeypatch)
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com", "webapi.amap.com"], runtime.emit)
    events = finish(runtime)
    addresses = [item for row in events if row["phase"] == "dns" for item in row.get("addresses", [])]
    assert len(addresses) == len({item["ip"] for item in addresses}) == 4
    assert len(raw) == len(tls) == 4
    assert all(value.closed for value in raw + tls)


def test_tcp_and_tls_share_four_second_budget_across_addresses_and_hosts(runtime, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runtime.probe, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [dns_row(), dns_row(socket.AF_INET6, "2001:db8::5")])
    raw, tls, _wraps = transport(runtime, monkeypatch)
    def spend(sock):
        timeout = sock.timeouts[-1]
        clock[0] += min(0.75, timeout)
        if timeout < 0.75:
            raise TimeoutError()
    def connect(sock, address):
        sock.address = address
        spend(sock)
    monkeypatch.setattr(FakeSocket, "connect", connect)
    monkeypatch.setattr(FakeSocket, "do_handshake", spend)
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com", "webapi.amap.com"], runtime.emit)
    events = finish(runtime)
    assert clock[0] == 4.0
    assert events[-1]["budget_exhausted"] is True
    assert len(raw) == 3 and len(tls) == 3
    assert all(0 < value <= 1 for sock in raw + tls for value in sock.timeouts)
    assert tls[-1].timeouts[-1] == 0.25
    assert all(value.closed for value in raw + tls)


def test_slow_emit_runs_only_in_daemon_and_cannot_delay_caller(runtime, monkeypatch):
    gate, entered = threading.Event(), threading.Event()
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [])
    def emit(*_args, **_kwargs):
        entered.set()
        gate.wait(timeout=2)
    try:
        started = time.perf_counter()
        assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], emit)
        assert time.perf_counter() - started < 0.5
        assert entered.wait(timeout=1)
    finally:
        gate.set()
        finish(runtime)


def test_tls_wrap_failure_closes_connected_raw_socket(runtime, monkeypatch):
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [dns_row()])
    raw, tls, _wraps = transport(runtime, monkeypatch)
    def wrap(*_args, **_kwargs):
        raise ssl.SSLError(1, "private handshake detail")
    monkeypatch.setattr(runtime.probe.ssl, "create_default_context", lambda: SimpleNamespace(wrap_socket=wrap))
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit)
    events = finish(runtime)
    assert raw[0].closed and not tls
    assert next(row for row in events if row["phase"] == "tls")["state"] == "error"
    assert "private handshake detail" not in json.dumps(events)


def test_failing_emit_and_thread_start_do_not_leak_capacity(runtime, monkeypatch):
    monkeypatch.setattr(runtime.probe.socket, "getaddrinfo", lambda *_args, **_kwargs: [dns_row()])
    raw, tls, _wraps = transport(runtime, monkeypatch)
    def broken_emit(*_args, **_kwargs):
        raise RuntimeError("diagnostic receiver unavailable")
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], broken_emit)
    finish(runtime)
    assert all(value.closed for value in raw + tls)
    factory = runtime.probe.Thread
    monkeypatch.setattr(runtime.probe, "Thread", lambda **_kwargs: SimpleNamespace(start=lambda: (_ for _ in ()).throw(RuntimeError("cannot start"))))
    assert runtime.probe.schedule_route_network_probe("amap", ["restapi.amap.com"], runtime.emit) is False
    monkeypatch.setattr(runtime.probe, "Thread", factory)
    assert runtime.probe._PROBE_SLOTS.acquire(blocking=False)
    assert runtime.probe._PROBE_SLOTS.acquire(blocking=False)
    runtime.probe._PROBE_SLOTS.release()
    runtime.probe._PROBE_SLOTS.release()
