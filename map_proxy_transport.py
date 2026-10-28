"""Bounded, exclusive keep-alive sessions for unauthenticated map upstreams."""

from __future__ import annotations

import atexit
import math
import queue
import socket
import threading
import time

import requests


_PRIVATE_HEADERS = frozenset({"cookie", "cookie2", "authorization", "proxy-authorization"})


class _DNSLookup:
    def __init__(self, host, port, deadline, resolver):
        self.host, self.port = host, port
        self.deadline, self.resolver = deadline, resolver
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.cancelled = False
        self.records = None
        self.error = None


class MapProxyDNSResolver:
    """Bound DNS callers without creating a thread or future for every timeout.

    Timed-out system lookups cannot be interrupted portably. They keep their
    admission slot until they finish, so both active and queued work stay bounded.
    """

    def __init__(self, *, max_workers=4, max_requests=8):
        if (type(max_workers) is not int or max_workers < 1
                or type(max_requests) is not int or max_requests < max_workers):
            raise ValueError("map DNS capacity must cover its positive worker count")
        self.max_workers = max_workers
        self._queue = queue.Queue(maxsize=max_requests)
        self._admission = threading.BoundedSemaphore(max_requests)
        self._state_lock = threading.Lock()
        self._workers = []
        self._closed = False

    def _start_workers(self):
        while len(self._workers) < self.max_workers:
            worker = threading.Thread(target=self._work, daemon=True,
                                      name="map-proxy-dns-" + str(id(self)) + "-" + str(len(self._workers)))
            worker.start()
            self._workers.append(worker)

    def _work(self):
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                with job.lock:
                    if self._closed or job.cancelled or time.monotonic() >= job.deadline:
                        job.error = requests.ConnectTimeout("map DNS deadline expired")
                        job.event.set()
                        continue
                try:
                    records = job.resolver(job.host, job.port, type=socket.SOCK_STREAM)
                    error = None if records else requests.ConnectionError("map DNS returned no addresses")
                except BaseException as exc:
                    records = None
                    error = (requests.ConnectTimeout("map DNS resolution timed out")
                             if isinstance(exc, (TimeoutError, requests.Timeout))
                             else requests.ConnectionError("map DNS resolution failed"))
                with job.lock:
                    if not job.cancelled:
                        job.records, job.error = records, error
                        job.event.set()
            finally:
                if job is not None:
                    self._admission.release()
                self._queue.task_done()

    def resolve(self, host, port, *, deadline, resolver=None):
        remaining = deadline - time.monotonic()
        if not math.isfinite(remaining) or remaining <= 0:
            raise requests.ConnectTimeout("map DNS deadline expired")
        job = _DNSLookup(host, port, deadline, resolver or socket.getaddrinfo)
        with self._state_lock:
            if self._closed:
                raise requests.ConnectionError("map DNS resolver is closed")
            if not self._admission.acquire(blocking=False):
                raise requests.ConnectTimeout("map DNS capacity exhausted")
            try:
                self._start_workers()
                self._queue.put_nowait(job)
            except BaseException:
                self._admission.release()
                raise requests.ConnectionError("map DNS worker unavailable") from None
        completed = job.event.wait(max(0, deadline - time.monotonic()))
        with job.lock:
            if not completed or time.monotonic() >= deadline:
                job.cancelled = True
                raise requests.ConnectTimeout("map DNS deadline expired")
            if job.error is not None:
                raise job.error from None
            return job.records

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            while True:
                try:
                    job = self._queue.get_nowait()
                except queue.Empty:
                    break
                with job.lock:
                    job.cancelled = True
                    job.error = requests.ConnectionError("map DNS resolver is closed")
                    job.event.set()
                self._admission.release()
                self._queue.task_done()
            for _worker in self._workers:
                self._queue.put_nowait(None)


_UPSTREAM_DNS = MapProxyDNSResolver()
atexit.register(_UPSTREAM_DNS.close)


def resolve_map_host(host, port, *, deadline, resolver=None):
    """Return full getaddrinfo records within an absolute monotonic deadline."""
    return _UPSTREAM_DNS.resolve(host, port, deadline=deadline, resolver=resolver)


class _LeasedResponse:
    def __init__(self, response, session, pool, before_release):
        self._response = response
        self._session = session
        self._pool = pool
        self._before_release = before_release
        self._close_lock = threading.Lock()
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._response, name)

    def __bool__(self):
        return bool(self._response)

    def __iter__(self):
        return iter(self._response)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        discard = False
        try:
            try:
                self._response.close()
            except BaseException:
                discard = True
                raise
        finally:
            try:
                if self._before_release is not None:
                    self._before_release(self)
            except BaseException:
                discard = True
                raise
            finally:
                self._pool._release(self._session, discard=discard)


class MapProxyTransport:
    """Hold each Session exclusively until its streaming response is closed.

    before_release(response) detaches request-scoped cancellation before another
    request can reuse the socket. A failed detach discards that Session.
    """

    def __init__(self, *, max_sessions=12, acquire_timeout=3.0,
                 session_factory=None, adapter_factory=None):
        if type(max_sessions) is not int or max_sessions < 1:
            raise ValueError("map transport capacity must be a positive integer")
        self.max_sessions = max_sessions
        self.acquire_timeout = max(0.0, float(acquire_timeout))
        self.session_factory = session_factory or requests.Session
        self.adapter_factory = adapter_factory or self._default_adapter
        self._condition = threading.Condition()
        self._idle = []
        self._allocated = 0
        self._closed = False

    @staticmethod
    def _default_adapter():
        return requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=1,
                                             pool_block=True, max_retries=0)

    @staticmethod
    def _reset_session(session):
        session.trust_env = False
        session.auth = None
        session.cookies.clear()
        for name in list(session.headers):
            if name.lower() in _PRIVATE_HEADERS:
                del session.headers[name]

    @staticmethod
    def _close_session(session):
        try:
            session.close()
        except Exception:
            pass

    def _discard(self, session):
        self._close_session(session)
        with self._condition:
            self._allocated -= 1
            self._condition.notify_all()

    def _acquire(self, acquire_timeout=None):
        started = time.monotonic()
        request_deadline = None
        wait_timeout = self.acquire_timeout
        if acquire_timeout is not None:
            remaining = float(acquire_timeout)
            if not math.isfinite(remaining) or remaining <= 0:
                raise requests.ConnectTimeout("map transport request deadline expired")
            request_deadline = started + remaining
            wait_timeout = min(wait_timeout, remaining)
        deadline = started + wait_timeout
        with self._condition:
            while True:
                if self._closed:
                    raise RuntimeError("map transport is closed")
                if request_deadline is not None and time.monotonic() >= request_deadline:
                    raise requests.ConnectTimeout("map transport request deadline expired")
                if self._idle:
                    return self._idle.pop()
                if self._allocated < self.max_sessions:
                    self._allocated += 1
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise requests.ConnectTimeout("map transport capacity wait expired")
                self._condition.wait(remaining)
        session = None
        try:
            session = self.session_factory()
            self._reset_session(session)
            for prefix in ("http://", "https://"):
                previous = session.adapters.get(prefix)
                if previous is not None:
                    previous.close()
                session.mount(prefix, self.adapter_factory())
        except BaseException:
            if session is not None:
                self._close_session(session)
            with self._condition:
                self._allocated -= 1
                self._condition.notify_all()
            raise
        with self._condition:
            closed = self._closed
        if closed:
            self._discard(session)
            raise RuntimeError("map transport is closed")
        if request_deadline is not None and time.monotonic() >= request_deadline:
            self._discard(session)
            raise requests.ConnectTimeout("map transport request deadline expired")
        return session

    def _release(self, session, *, discard=False):
        try:
            self._reset_session(session)
        except Exception:
            discard = True
        with self._condition:
            if not discard and not self._closed:
                self._idle.append(session)
                self._condition.notify()
                return
        self._discard(session)

    def request(self, method, url, *, headers, body, timeout, before_release=None, acquire_timeout=None):
        session = self._acquire(acquire_timeout=acquire_timeout)
        try:
            self._reset_session(session)
            upstream_headers = {name: value for name, value in (headers or {}).items()
                                if str(name).lower() not in _PRIVATE_HEADERS}
            response = session.request(method, url, headers=upstream_headers, data=body,
                                       timeout=timeout, allow_redirects=False, stream=True)
            return _LeasedResponse(response, session, self, before_release)
        except BaseException:
            self._release(session, discard=True)
            raise

    def close(self):
        with self._condition:
            if self._closed:
                return
            self._closed = True
            idle, self._idle = self._idle, []
            self._condition.notify_all()
        for session in idle:
            self._discard(session)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
