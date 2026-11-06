import json
import logging
import urllib.parse
from types import SimpleNamespace
from unittest import mock

import pytest
import requests

import api_client
import ip_verifier


def runtime_for_network_logs():
    return SimpleNamespace(
        requests=requests,
        urllib=urllib,
        _redact_sensitive_log_text=lambda value: str(value or ""),
        _redact_sensitive_log_value=lambda value: value,
        _create_payment_verify_probe=lambda **kwargs: ("probe-token", "probe-challenge"),
        _build_payment_verify_probe_url=ip_verifier._build_payment_verify_probe_url,
        _is_payment_verify_probe_consumed=lambda token: True,
    )


def response_with_text(text, status=200, reason="OK"):
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response.url = "https://api.example.test/result"
    response.headers = {"Content-Type": "application/json", "X-Upstream": "detail-response"}
    response._content = text.encode("utf-8")
    response.encoding = "utf-8"
    return response


def client_with_session(session):
    client = api_client.ApiClient.__new__(api_client.ApiClient)
    client.session = session
    client.app = SimpleNamespace(
        is_offline_mode=False,
        device_ua="test-agent",
        log_and_notify_frontend=mock.Mock(),
    )
    return client


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_network_request_logs_actual_parameters_headers_and_response(method, caplog):
    runtime = runtime_for_network_logs()
    response = response_with_text('{"code":13,"msg":"upstream-specific-reason"}')
    session = mock.Mock()
    getattr(session, method.lower()).return_value = response
    client = client_with_session(session)
    headers = {"Authorization": "authorization-value", "X-Diagnostic": "header-value"}

    with mock.patch.object(api_client, "_main", return_value=runtime), \
         mock.patch.object(client, "_get_headers", return_value=headers), \
         caplog.at_level(logging.DEBUG):
        result = client._request(
            method, "https://api.example.test/login?token=url-value",
            data={"username": "request-user", "password": "request-password"},
            params={"page": "query-value"},
        )

    assert result is response
    for detail in (
        "request-user", "request-password", "query-value", "authorization-value",
        "header-value", "detail-response", "upstream-specific-reason",
    ):
        assert detail in caplog.text


def test_network_headers_log_actual_cookie_values(caplog):
    runtime = runtime_for_network_logs()
    session = requests.Session()
    session.cookies.set("shiroCookie", "cookie-auth-value")
    client = client_with_session(session)

    with mock.patch.object(api_client, "_main", return_value=runtime), caplog.at_level(logging.DEBUG):
        headers = client._get_headers()

    assert headers["Authorization"] == "cookie-auth-value"
    assert "cookie-auth-value" in caplog.text


@pytest.mark.parametrize("error_class", [requests.Timeout, requests.RequestException])
def test_network_error_logs_actual_exception_message(error_class, caplog):
    runtime = runtime_for_network_logs()
    session = mock.Mock()
    session.get.side_effect = error_class("upstream refused diagnostic-connection-detail")
    client = client_with_session(session)

    with mock.patch.object(api_client, "_main", return_value=runtime), \
         mock.patch.object(client, "_get_headers", return_value={}), \
         mock.patch.object(client, "_wait_for_retry_or_cancel", return_value=True), \
         caplog.at_level(logging.ERROR):
        assert client._request("GET", "https://api.example.test/query") is None

    assert "diagnostic-connection-detail" in caplog.text


@pytest.mark.parametrize("valid_json", [True, False])
def test_json_parser_logs_actual_response_content(valid_json, caplog):
    runtime = runtime_for_network_logs()
    body = json.dumps({"msg": "parsed-response-detail"}) if valid_json else "broken-response-detail"
    response = response_with_text(body)
    client = client_with_session(mock.Mock())

    with mock.patch.object(api_client, "_main", return_value=runtime), caplog.at_level(logging.DEBUG):
        result = client._json(response)

    assert result == ({"msg": "parsed-response-detail"} if valid_json else None)
    assert body in caplog.text


def test_app_host_probe_logs_failed_response_body_headers_and_request(caplog):
    runtime = runtime_for_network_logs()
    runtime.requests = SimpleNamespace(
        post=mock.Mock(return_value=response_with_text("route-not-found-detail", 404, "Not Found")),
        exceptions=requests.exceptions,
    )

    with mock.patch.object(ip_verifier, "_main", return_value=runtime), \
         mock.patch.object(ip_verifier, "_cleanup_expired_payment_verify_probes"), \
         caplog.at_level(logging.DEBUG):
        assert not ip_verifier.IPVerifier().check_app_host("https://merchant.example.test")

    assert "probe-challenge" in caplog.text
    assert "probe-token" in caplog.text
    assert "detail-response" in caplog.text
    assert "route-not-found-detail" in caplog.text


def test_app_host_probe_failure_details_are_visible_at_warning_level(caplog):
    runtime = runtime_for_network_logs()
    runtime.requests = SimpleNamespace(
        post=mock.Mock(return_value=response_with_text("probe-warning-detail", 404, "Not Found")),
        exceptions=requests.exceptions,
    )

    with mock.patch.object(ip_verifier, "_main", return_value=runtime), \
         mock.patch.object(ip_verifier, "_cleanup_expired_payment_verify_probes"), \
         caplog.at_level(logging.WARNING):
        assert not ip_verifier.IPVerifier().check_app_host("https://merchant.example.test")

    for detail in ("probe-warning-detail", "detail-response", "probe-token"):
        assert detail in caplog.text


@pytest.mark.parametrize("version", ["4", "6"])
def test_public_ip_failure_logs_response_details_at_warning_level(version, caplog):
    runtime = runtime_for_network_logs()
    failed_response = response_with_text(f"ipv{version}-upstream-detail", 503, "Service Unavailable")

    def get_response(url, **kwargs):
        if url == f"http://{version}.ipw.cn":
            return failed_response
        return response_with_text("2001:db8::1" if version == "4" else "203.0.113.1")

    runtime.requests = SimpleNamespace(get=mock.Mock(side_effect=get_response))

    with mock.patch.object(ip_verifier, "_main", return_value=runtime), caplog.at_level(logging.WARNING):
        result = ip_verifier.IPVerifier().get_public_ip_addresses()

    assert result[f"ipv{version}"] is None
    for detail in (f"ipv{version}-upstream-detail", "detail-response", "503"):
        assert detail in caplog.text


@pytest.mark.parametrize("error_class", [requests.Timeout, requests.ConnectionError, RuntimeError])
def test_app_host_probe_logs_actual_exception_message(error_class, caplog):
    runtime = runtime_for_network_logs()
    runtime.requests = SimpleNamespace(
        post=mock.Mock(side_effect=error_class("probe-specific-failure-detail")),
        exceptions=requests.exceptions,
    )

    with mock.patch.object(ip_verifier, "_main", return_value=runtime), \
         mock.patch.object(ip_verifier, "_cleanup_expired_payment_verify_probes"), \
         caplog.at_level(logging.WARNING):
        assert not ip_verifier.IPVerifier().check_app_host("https://merchant.example.test")

    assert "probe-specific-failure-detail" in caplog.text
