import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g, request

from map_request_proxy import register_map_proxy_routes


ACTOR = "11111111-1111-4111-8111-111111111111"
TARGET = "22222222-2222-4222-8222-222222222222"


def production_context_callback(refresh_token):
    source = Path(__file__).resolve().parents[1] / "web_server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef)
                and item.name == "_refresh_map_proxy_context_actor")
    runtime = SimpleNamespace(token_manager=SimpleNamespace(refresh_token=refresh_token))
    namespace = {"_main": lambda: runtime}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[node.name]


@pytest.fixture
def proxy_runtime():
    app = Flask(__name__)
    app.secret_key = "context-lifecycle-test"
    config = {"Map": {"frontend_proxy_enabled": True}}
    refresh = Mock(return_value=True)
    authorize = Mock(return_value=True)
    transport = Mock(return_value=SimpleNamespace(
        status_code=200, headers={"Content-Type": "image/png"}, content=b"image", close=Mock(),
    ))

    def login_required(view):
        def authenticated_view():
            g.user = "administrator"
            g.session_id = ACTOR
            g.viewed_session_id = request.headers.get("X-Session-ID", "")
            return view()
        authenticated_view.__name__ = view.__name__
        return authenticated_view

    # Configuration lookup mirrors the production adapter interface.
    adapter = SimpleNamespace(get=lambda section, key, fallback=None: config.get(section, {}).get(key, fallback))
    register_map_proxy_routes(
        app, login_required, lambda: adapter, authorize, transport=transport,
        dns_resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
        on_context_authenticated=production_context_callback(refresh),
    )
    client = app.test_client()
    client.set_cookie("auth_token", "administrator-token")
    return client, refresh, authorize, config


def bootstrap(client, headers=None):
    return client.post("/api/map-proxy/context", json={}, headers=headers or {
        "Origin": "http://localhost", "X-Session-ID": TARGET,
        "X-Admin-Origin-Session-ID": ACTOR,
    })


def test_context_bootstrap_and_renewal_refresh_only_real_actor_token(proxy_runtime):
    client, refresh, authorize, _config = proxy_runtime
    for expected_count in (1, 2):
        response = bootstrap(client)
        assert response.status_code == 200
        assert refresh.call_count == expected_count
        refresh.assert_called_with("administrator", ACTOR)
        authorize.assert_called_with("administrator", "administrator-token", ACTOR, True)
        assert all("map_proxy_context=" in value for value in response.headers.getlist("Set-Cookie"))
        for _ in range(3):
            assert client.get("/map-proxy/amap/https/webapi.amap.com/tile").status_code == 200
        assert refresh.call_count == expected_count


@pytest.mark.parametrize("failure", ("origin", "disabled", "session", "token", "authorization", "authorization_exception"))
def test_failed_context_authentication_never_refreshes_token(proxy_runtime, failure):
    client, refresh, authorize, config = proxy_runtime
    headers = {"Origin": "http://localhost", "X-Session-ID": TARGET, "X-Admin-Origin-Session-ID": ACTOR}
    if failure == "origin":
        headers["Origin"] = "http://untrusted.invalid"
    elif failure == "disabled":
        config["Map"]["frontend_proxy_enabled"] = False
    elif failure == "session":
        headers["X-Session-ID"] = "invalid-session"
    elif failure == "token":
        client.delete_cookie("auth_token")
    elif failure == "authorization":
        authorize.return_value = False
    else:
        authorize.side_effect = RuntimeError("authorization unavailable")
    response = bootstrap(client, headers)
    assert response.status_code in (401, 403, 404)
    assert response.headers.getlist("Set-Cookie") == []
    refresh.assert_not_called()


@pytest.mark.parametrize("failure", (False, None, RuntimeError("token refresh failed")))
def test_context_refresh_failure_prevents_cookie_renewal(proxy_runtime, failure):
    client, refresh, _authorize, _config = proxy_runtime
    if isinstance(failure, Exception):
        refresh.side_effect = failure
    else:
        refresh.return_value = failure
    response = bootstrap(client)
    assert response.status_code == 403
    assert response.json["success"] is False
    assert response.headers.getlist("Set-Cookie") == []
    refresh.assert_called_once_with("administrator", ACTOR)
