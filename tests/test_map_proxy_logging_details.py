import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

import main
from map_request_proxy import MapProxyAccessLogFilter
from tests import test_map_proxy_concurrency as proxy_harness


TILE = "/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts?REQUEST=GetTile&TILECOL=1&TILEROW=2&TILEMATRIX=3&tk=secret"


@pytest.mark.parametrize("redaction_enabled", (False, True))
def test_tile_retry_logs_error_type_and_complete_detail(caplog, redaction_enabled):
    error_text = "tile provider timeout token=tile-secret " + "详情" * 300 + " diagnostic-tail"
    calls = []

    def transport(*_args, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            raise requests.ReadTimeout(error_text)
        return SimpleNamespace(status_code=200, content=b"tile", headers={"Content-Type": "image/png"}, close=lambda: None)

    with patch.object(main, "_log_redaction_enabled", redaction_enabled, create=True):
        _proxy, fetch = proxy_harness.MapProxyConcurrencyTests().make_proxy(transport)
        assert fetch(TILE)[:2] == (200, b"tile")

    retry = next(record.getMessage() for record in caplog.records if "stage=tile attempt=1 error=" in record.getMessage())
    assert "error=ReadTimeout" in retry
    assert "detail=tile provider timeout" in retry
    assert "diagnostic-tail" in retry
    assert ("tile-secret" not in retry) if redaction_enabled else (error_text in retry)


@pytest.mark.parametrize("error_type", (ValueError, RuntimeError))
def test_upstream_failure_logs_full_error_without_changing_public_response(caplog, error_type):
    error_text = "unexpected provider response token=resource-secret with diagnostic-tail"

    def transport(*_args, **_kwargs):
        raise error_type(error_text)

    with patch.object(main, "_log_redaction_enabled", False, create=True):
        _proxy, fetch = proxy_harness.MapProxyConcurrencyTests().make_proxy(transport)
        status, body, _headers = fetch()

    assert (status, body) == (502, b"")
    failure = next(record.getMessage() for record in caplog.records if "upstream failure" in record.getMessage())
    assert f"error={error_type.__name__}" in failure
    assert f"detail={error_text}" in failure


@pytest.mark.parametrize("redaction_enabled", (False, True))
def test_map_proxy_access_log_query_redaction_follows_logging_switch(redaction_enabled):
    record = logging.LogRecord(
        "werkzeug", logging.INFO, __file__, 1, "request=%s",
        ({"url": "/map-proxy/amap/https/webapi.amap.com/maps?key=map-secret&status=OK"},), None,
    )

    with patch.object(main, "_log_redaction_enabled", redaction_enabled, create=True):
        assert MapProxyAccessLogFilter().filter(record)

    message = record.getMessage()
    assert "webapi.amap.com/maps" in message
    assert ("map-secret" not in message) if redaction_enabled else ("key=map-secret&status=OK" in message)
