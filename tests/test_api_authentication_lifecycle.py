"""Replacing a school session must also discard its App access token."""

from types import SimpleNamespace
from unittest.mock import Mock

import requests

import api_client
import api_runtime
from api_runtime import Api


def authenticated_client(monkeypatch):
    runtime = SimpleNamespace(
        requests=requests,
        _redact_sensitive_log_value=lambda value: value,
    )
    monkeypatch.setattr(api_client, "_main", lambda: runtime)
    client = api_client.ApiClient(SimpleNamespace(device_ua="test-agent"))
    client.set_access_token("old-access-token")
    client.session.cookies.set("shiroCookie", "old-cookie-token")
    return client


def test_logout_discards_access_token_when_replacing_network_session(monkeypatch):
    client = authenticated_client(monkeypatch)
    original_session = client.session
    runtime = SimpleNamespace(requests=requests)
    monkeypatch.setattr(api_runtime, "_main", lambda: runtime)
    api = SimpleNamespace(
        api_client=client,
        log_and_notify_frontend=lambda message: None,
        shutdown_session_runtime=lambda **kwargs: original_session.close(),
        _init_state_variables=lambda: None,
        _load_global_config=lambda: None,
    )

    result = Api.logout(api)

    assert result["success"] is True
    assert client.session is not original_session
    assert client.access_token is None
    assert "Authorization" not in client._get_headers()


def test_relogin_discards_access_token_before_refresh_thread_starts(monkeypatch):
    client = authenticated_client(monkeypatch)
    acc = SimpleNamespace(
        username="student-1", api_client=client,
        user_data=SimpleNamespace(id="user-1"), is_verifying=False,
    )
    started = []

    def start_refresh():
        started.append(True)
        assert client.access_token is None
        assert "Authorization" not in client._get_headers()

    thread = SimpleNamespace(start=start_refresh)
    monkeypatch.setattr(api_runtime.threading, "Thread", lambda **kwargs: thread)
    api = SimpleNamespace(_multi_refresh_worker=Mock())

    Api._reset_account_session_for_relogin(api, acc)

    assert started == [True]
    assert client.access_token is None
    assert len(client.session.cookies) == 0
    assert acc.user_data.id == ""
    assert acc.is_verifying is True
