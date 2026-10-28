from types import SimpleNamespace
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest
import requests

from tests.test_map_proxy_concurrency import MapProxyConcurrencyTests as _ConcurrencyHarness
from map_request_proxy import _MapProxy


TILE = '/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts?REQUEST=GetTile&TILECOL=1&TILEROW=2&TILEMATRIX=3&tk=secret'


def response(status=200, content=b'tile', close=None):
    return SimpleNamespace(status_code=status, content=content,
                           headers={'Content-Type': 'image/png'}, close=close or (lambda: None))


def make_fetch(transport):
    return _ConcurrencyHarness().make_proxy(transport)[1]


def test_tianditu_tile_retries_one_timeout_with_redacted_stage_logging(caplog):
    calls = []

    def transport(*args, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls) == 1:
            raise requests.ReadTimeout('tk=secret')
        return response()

    fetch = make_fetch(transport)
    assert fetch(TILE)[:2] == (200, b'tile')
    assert len(calls) == 2
    assert all(timeout.total <= 6 for timeout in calls)
    assert 'stage=tile' in caplog.text
    assert 'ReadTimeout' in caplog.text and 'secret' not in caplog.text


@pytest.mark.parametrize('resource', [
    '/map-proxy/amap/https/jsapi-data1.amap.com/tile/v1/pbf/0/1_2_3?auth_key=secret',
    '/map-proxy/tencent/https/rt0.map.gtimg.com/tile?tiles=1_2_3&version=1',
    '/map-proxy/baidu/https/apimaponline0.bdimg.com/starpic/?u=1&qt=sate&fm=1&ak=secret',
])
def test_confirmed_provider_tiles_get_one_bounded_retry(resource):
    calls = []

    def transport(*args, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls) == 1:
            raise requests.ReadTimeout()
        return response()

    assert make_fetch(transport)(resource)[0] == 200
    assert len(calls) == 2
    assert all(timeout.total <= 6 for timeout in calls)


@pytest.mark.parametrize('status', [502, 503, 504])
def test_retryable_tile_status_closes_first_response(status):
    closed = []
    values = iter([response(status, close=lambda: closed.append(True)), response()])
    fetch = make_fetch(lambda *args, **kwargs: next(values))
    assert fetch(TILE)[0] == 200
    assert closed == [True]


@pytest.mark.parametrize('resource', [
    '/map-proxy/tianditu/https/api.tianditu.gov.cn/api?v=4.0',
    '/map-proxy/tianditu/https/api.tianditu.gov.cn/drive',
    '/map-proxy/tianditu/https/t0.tianditu.gov.cn/auth',
    '/map-proxy/tencent/https/rt0.map.gtimg.com/tile.png',
    '/map-proxy/tianditu/https/t0.tianditu.gov.cn/auth_w/wmts',
    '/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts?REQUEST=GetCapabilities',
])
def test_scripts_auth_routes_and_other_providers_are_not_retried(resource):
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        raise requests.ReadTimeout()

    assert make_fetch(transport)(resource)[0] == 502
    assert len(calls) == 1


@pytest.mark.parametrize('error_type', [requests.ConnectionError, requests.exceptions.ChunkedEncodingError])
def test_tile_stream_timeout_closes_failed_response_and_retries(error_type):
    closed, calls = [], []

    def stream(**kwargs):
        yield b'partial'
        raise error_type('upstream reset')

    def transport(*args, **kwargs):
        calls.append(True)
        return SimpleNamespace(status_code=200, headers={'Content-Type': 'image/png'},
                               iter_content=stream, close=lambda: closed.append(True)) if len(calls) == 1 else response()

    assert make_fetch(transport)(TILE)[:2] == (200, b'tile')
    assert closed == [True]


def test_tile_attempts_and_deadline_are_bounded_and_permits_are_released():
    calls = []
    clock = None

    def transport(*args, **kwargs):
        calls.append(True)
        if clock is not None:
            clock[0] = 13
        raise requests.ReadTimeout()

    fetch = make_fetch(transport)
    assert fetch(TILE)[0] == 502
    assert len(calls) == 2
    clock = [0]
    with patch('map_request_proxy.time.monotonic', side_effect=lambda: clock[0]):
        assert fetch(TILE)[0] == 502
    clock = None
    assert len(calls) == 3, 'expired budget must prevent a second attempt'
    assert fetch('/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts')[0] == 502
    assert len(calls) == 4, 'failure must release permits; metadata must not be retried'


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429])
def test_permanent_tile_status_is_not_retried(status):
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        return response(status)

    assert make_fetch(transport)(TILE)[0] == status
    assert len(calls) == 1


@pytest.mark.parametrize('phase', ['headers', 'body'])
def test_real_trickling_response_is_interrupted_at_total_deadline_and_socket_closes(phase):
    disconnected = threading.Event()
    completed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if phase == 'headers':
                    self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Trickle: ')
                    self.wfile.flush()
                else:
                    self.send_response(200)
                    self.send_header('Content-Length', '100')
                    self.end_headers()
                for _ in range(100):
                    self.wfile.write(b'x')
                    self.wfile.flush()
                    time.sleep(.01)
                if phase == 'headers':
                    self.wfile.write(b'\r\nContent-Length: 0\r\n\r\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                disconnected.set()
            finally:
                completed.set()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    proxy = _MapProxy.__new__(_MapProxy)
    proxy.transport = proxy._request_upstream
    proxy.max_response_bytes = 1024
    try:
        started = time.monotonic()
        with patch('map_request_proxy.TILE_DEADLINE_SECONDS', .20), patch('map_request_proxy.TILE_ATTEMPT_SECONDS', .15):
            with pytest.raises(requests.Timeout):
                proxy._request_tile('GET', f'http://127.0.0.1:{server.server_port}/tile', {}, None, 'test-host', provider='tianditu')
        elapsed = time.monotonic() - started
        assert elapsed < .60, f'continuous upstream data bypassed the total deadline: {elapsed:.3f}s'
        assert disconnected.wait(.25), 'deadline must close the actual upstream socket'
        assert completed.wait(.25), 'upstream request must not continue after the caller returns'
        assert not any(thread.name.startswith('map-tile-deadline-') for thread in threading.enumerate())
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()
