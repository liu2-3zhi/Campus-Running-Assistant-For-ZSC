from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from tests.test_map_proxy_concurrency import MapProxyConcurrencyTests as _ConcurrencyHarness


TILE = '/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts?tk=secret'


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
    assert all(sum(timeout) <= 6 for timeout in calls)
    assert 'stage=tile' in caplog.text
    assert 'ReadTimeout' in caplog.text and 'secret' not in caplog.text


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

    def transport(*args, **kwargs):
        calls.append(True)
        raise requests.ReadTimeout()

    fetch = make_fetch(transport)
    assert fetch(TILE)[0] == 502
    assert len(calls) == 2
    with patch('map_request_proxy.time.monotonic', side_effect=[0, 0, 13, 13, 13, 13]):
        assert fetch(TILE)[0] == 502
    assert len(calls) == 3, 'expired budget must prevent a second attempt'
    assert fetch('/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts')[0] == 502
    assert len(calls) == 5, 'failure must release admission and active permits'


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429])
def test_permanent_tile_status_is_not_retried(status):
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        return response(status)

    assert make_fetch(transport)(TILE)[0] == status
    assert len(calls) == 1
