from functools import wraps
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask, g
import pytest

import map_request_proxy as proxy_module


SESSION = "11111111-1111-4111-8111-111111111111"
SOURCE = "/map-proxy/amap/https/webapi.amap.com/maps/checkredirect?key=isolated"
TARGET = "https://mapplugin.amap.com/maps/checkredirectcdn?key=isolated&callback=isolated"


def upstream(status=200, body=b"const isolated = true;", headers=None):
    result = SimpleNamespace(status_code=status, content=body,
                             headers={"Content-Type": "application/javascript", **(headers or {})}, closed=False)

    def close():
        result.closed = True

    result.close = close
    return result


def make_proxy(tmp_path, transport, *, resolver=None):
    app = Flask(__name__)
    app.secret_key = "isolated-amap-redirect-tests"
    app.testing = True

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            g.user, g.session_id = "isolated-admin", SESSION
            return view(*args, **kwargs)
        return wrapped

    config = SimpleNamespace(get=lambda section, key, fallback=None: {
        "frontend_proxy_enabled": True, "backend_page_origin": "https://authorized.example",
    }.get(key, fallback))
    proxy_module.register_map_proxy_routes(
        app, login_required, lambda: config, lambda *_args: True,
        transport=transport, tile_cache_dir=tmp_path,
        dns_resolver=resolver or (lambda _host, port, **_kwargs: [(None, None, None, None, ("8.8.8.8", port))]),
    )
    client = app.test_client()
    client.set_cookie("auth_token", "isolated-auth-token")
    assert client.post("/api/map-proxy/context", headers={
        "Origin": "http://localhost", "X-Session-ID": SESSION,
    }).status_code == 200
    return client


def test_redirect_helper_accepts_only_observed_pair_and_cleans_control_query():
    helper = getattr(proxy_module, "_amap_sdk_redirect")
    result = helper("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 302,
                    TARGET + "&session_id=private&auth_token=private")
    assert result == TARGET


@pytest.mark.parametrize("provider,method,host,path,status", [
    ("tencent", "GET", "webapi.amap.com", "/maps/checkredirect", 302),
    ("amap", "POST", "webapi.amap.com", "/maps/checkredirect", 302),
    ("amap", "GET", "restapi.amap.com", "/maps/checkredirect", 302),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirect/", 302),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirectcdn", 302),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 301),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 303),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 307),
    ("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 308),
])
def test_redirect_helper_does_not_widen_source_or_status(provider, method, host, path, status):
    assert getattr(proxy_module, "_amap_sdk_redirect")(provider, method, host, path, status, TARGET) is None


@pytest.mark.parametrize("location", [
    "http://mapplugin.amap.com/maps/checkredirectcdn",
    "//mapplugin.amap.com/maps/checkredirectcdn",
    "/maps/checkredirectcdn",
    "https://127.0.0.1/maps/checkredirectcdn",
    "https://mapplugin.amap.com.evil.example/maps/checkredirectcdn",
    "https://webapi.amap.com/maps/checkredirectcdn",
    "https://mapplugin.amap.com:443/maps/checkredirectcdn",
    "https://mapplugin.amap.com:8443/maps/checkredirectcdn",
    "https://user:pass@mapplugin.amap.com/maps/checkredirectcdn",
    "https://mapplugin.amap.com/maps/checkredirectcdn#fragment",
    "https://mapplugin.amap.com/maps/checkredirectcdn/",
    "https://mapplugin.amap.com/maps/%63heckredirectcdn",
    "https://mapplugin.amap.com/other-script.js",
    "https://mapplugin.amap.com\\evil/maps/checkredirectcdn",
    "https://mapplugin.amap.com/maps/checkredirectcdn\r\nInjected: yes",
    "https://mapplugin.amap.com/maps/checkredirectcdn?key=invalid\x7fvalue",
    " https://mapplugin.amap.com/maps/checkredirectcdn",
    "https://mapplugin.amap.com/maps/checkredirectcdn?key=" + "x" * 4097,
    "", None,
])
def test_redirect_helper_rejects_unsafe_or_unobserved_targets(location):
    assert getattr(proxy_module, "_amap_sdk_redirect")("amap", "GET", "webapi.amap.com", "/maps/checkredirect", 302, location) is None


def test_allowed_redirect_is_followed_once_without_forwarding_secrets(tmp_path, caplog):
    initial = upstream(302, headers={"Location": TARGET, "Set-Cookie": "vendor=must-not-forward"})
    final = upstream()
    calls = []

    def transport(method, url, *, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        assert "Cookie" not in headers and "Authorization" not in headers
        assert headers["Referer"] == "https://authorized.example/"
        assert headers["Origin"] == "https://authorized.example"
        if len(calls) == 1:
            return initial
        assert initial.closed
        assert url == TARGET and method == "GET" and body is None
        return final

    client = make_proxy(tmp_path, transport)
    response = client.get(SOURCE, headers={"Authorization": "Bearer private", "Cookie": "private=must-not-forward"})
    assert response.status_code == 200
    assert response.data == final.content
    assert response.headers["Content-Type"].startswith("application/javascript")
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers and "Location" not in response.headers
    assert len(calls) == 2 and initial.closed and final.closed
    assert "key=isolated" not in caplog.text and "callback=isolated" not in caplog.text


def test_second_redirect_is_rejected_without_a_third_request(tmp_path):
    responses = [upstream(302, headers={"Location": TARGET}), upstream(302, headers={"Location": TARGET})]
    calls = []

    def transport(*args, **kwargs):
        calls.append(args[1])
        assert len(calls) <= 2
        return responses[len(calls) - 1]

    response = make_proxy(tmp_path, transport).get(SOURCE)
    assert response.status_code == 502 and len(calls) == 2
    assert all(item.closed for item in responses)


def test_redirect_target_is_revalidated_before_any_second_upstream_request(tmp_path):
    calls, resolutions = [], []
    initial = upstream(302, headers={"Location": TARGET})

    def resolver(host, port, **_kwargs):
        resolutions.append(host)
        address = "127.0.0.1" if host == "mapplugin.amap.com" else "8.8.8.8"
        return [(None, None, None, None, (address, port))]

    def transport(*args, **kwargs):
        calls.append(args[1])
        return initial

    response = make_proxy(tmp_path, transport, resolver=resolver).get(SOURCE)
    assert response.status_code in {400, 502}
    assert resolutions == ["webapi.amap.com", "mapplugin.amap.com"]
    assert len(calls) == 1 and initial.closed


@pytest.mark.parametrize("path,method", [
    ("/maps/checkredirectcdn/", "GET"),
    ("/other-script.js", "GET"),
    ("/maps/checkredirectcdn", "POST"),
])
def test_new_cdn_host_is_not_a_general_purpose_proxy(tmp_path, path, method):
    calls = []
    client = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    response = client.open("/map-proxy/amap/https/mapplugin.amap.com" + path, method=method)
    assert response.status_code == 400
    assert not calls


def test_exact_cdn_script_can_be_requested_without_redirect(tmp_path):
    calls = []
    client = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(urlsplit(args[1]).path) or upstream())
    response = client.get("/map-proxy/amap/https/mapplugin.amap.com/maps/checkredirectcdn?key=isolated")
    assert response.status_code == 200
    assert calls == ["/maps/checkredirectcdn"]
