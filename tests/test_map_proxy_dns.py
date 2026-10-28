"""Map DNS deadlines must bound callers, worker count, and pending lookups."""

from concurrent.futures import ThreadPoolExecutor
import socket
import threading
import time

import pytest
import requests

import map_proxy_transport


def resolver_pool(**kwargs):
    factory = getattr(map_proxy_transport, "MapProxyDNSResolver", None)
    assert callable(factory), "map DNS resolution needs a bounded worker pool"
    return factory(**kwargs)


def stop_pool(pool):
    pool.close()
    for worker in pool._workers:
        worker.join(timeout=1)
        assert not worker.is_alive()


def test_dns_preserves_complete_ipv4_and_ipv6_records():
    records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
               (socket.AF_INET6, socket.SOCK_STREAM, 6, "alias", ("::1", 443, 0, 4))]
    pool = resolver_pool(max_workers=1, max_requests=2)
    try:
        assert pool.resolve("isolated.invalid", 443, deadline=time.monotonic() + 1,
                            resolver=lambda *_a, **_k: records) == records
    finally:
        stop_pool(pool)


@pytest.mark.parametrize("error,expected", [
    (socket.gaierror("private-host-value"), requests.ConnectionError),
    (socket.timeout("private-host-value"), requests.ConnectTimeout),
])
def test_dns_errors_are_request_exceptions_without_raw_hosts(error, expected):
    pool = resolver_pool(max_workers=1, max_requests=2)

    def failing(*_args, **_kwargs):
        raise error

    try:
        with pytest.raises(expected) as caught:
            pool.resolve("isolated.invalid", 443, deadline=time.monotonic() + 1, resolver=failing)
        assert "private-host-value" not in str(caught.value)
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        assert pool.resolve("isolated.invalid", 443, deadline=time.monotonic() + 1,
                            resolver=lambda *_a, **_k: records) == records
    finally:
        stop_pool(pool)


def test_expired_dns_request_does_not_start_a_worker_or_call_resolver():
    pool = resolver_pool(max_workers=1, max_requests=2)
    called = []
    try:
        with pytest.raises(requests.ConnectTimeout):
            pool.resolve("isolated.invalid", 443, deadline=time.monotonic() - 1,
                         resolver=lambda *_a, **_k: called.append(True))
        assert called == []
        assert pool._workers == []
    finally:
        stop_pool(pool)


def test_timed_out_dns_work_stays_bounded_and_expired_queued_jobs_are_not_started():
    pool = resolver_pool(max_workers=1, max_requests=2)
    entered, release = threading.Event(), threading.Event()
    calls = []
    records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    def blocked(*_args, **_kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return records

    def lookup():
        with pytest.raises(requests.ConnectTimeout):
            pool.resolve("isolated.invalid", 443, deadline=time.monotonic() + .06, resolver=blocked)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(lookup)
            assert entered.wait(1)
            second = executor.submit(lookup)
            first.result(timeout=1)
            second.result(timeout=1)
        for _ in range(20):
            started = time.monotonic()
            lookup()
            assert time.monotonic() - started < .15
        assert len(calls) == 1
        assert len(pool._workers) == 1
        assert pool._queue.qsize() == 1
        release.set()
        pool._queue.join()
        assert len(calls) == 1, "expired queued DNS must not start after its caller returned"
        assert pool.resolve("isolated.invalid", 443, deadline=time.monotonic() + 1,
                            resolver=lambda *_a, **_k: records) == records
    finally:
        release.set()
        stop_pool(pool)
