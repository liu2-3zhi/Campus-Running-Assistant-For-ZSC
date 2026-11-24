"""Exercise the App contract at the real requests serialization boundary."""

import json
import sys
import urllib.parse
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from requests.adapters import BaseAdapter

import api_client


class AppTransport(BaseAdapter):
    def __init__(self):
        self.calls = []
        self.responses = []

    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        status, payload = self.responses.pop(0) if self.responses else (200, {"code": 200})
        response = requests.Response()
        response.status_code = status
        response.reason = "OK" if status == 200 else "Error"
        response.request = request
        response.url = request.url
        response.headers["Content-Type"] = "application/json"
        response.encoding = "utf-8"
        response._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return response

    def close(self):
        pass


@pytest.fixture
def app_client(monkeypatch):
    runtime = SimpleNamespace(
        requests=requests,
        urllib=urllib,
        _redact_sensitive_log_text=lambda value: str(value or ""),
        _redact_sensitive_log_value=lambda value: value,
    )
    monkeypatch.setattr(api_client, "_main", lambda: runtime)
    monkeypatch.setattr(api_client.ApiClient, "_APP_VERSION_CACHE", {})
    owner = SimpleNamespace(
        device_ua="Android test device", is_offline_mode=False,
        log_and_notify_frontend=lambda _message: None,
    )
    transport = AppTransport()
    clients = []

    def factory():
        client = api_client.ApiClient(owner)
        client.session.trust_env = False
        client.session.mount("https://", transport)
        clients.append(client)
        return client

    yield factory, transport
    for client in clients:
        client.session.close()


def test_check_version_uses_get_and_equal_version_cache_is_reused(app_client):
    factory, transport = app_client
    first = factory()
    transport.responses.append((200, {"code": 200, "data": {"version": "1.0.85"}}))
    assert first.sync_app_version() == "1.0.85"
    request, _ = transport.calls[0]
    assert request.method == "GET"
    assert request.url == "https://zslf.zsc.edu.cn/app/checkVersion"
    assert request.body is None
    assert factory().sync_app_version() == "1.0.85"
    assert len(transport.calls) == 1


def test_check_version_preserves_existing_android_app_ua_suffix(app_client):
    factory, transport = app_client
    client = factory()
    full_ua = ("Mozilla/5.0 (Linux; Android 16; fixture; wv) Chrome/159.0.0.0 Mobile Safari/537.36 "
               "uni-app (Immersed/29.09091) Html5Plus/1.0")
    client.app.device_ua = full_ua
    transport.responses.append((200, {"code": 200, "data": {"version": "1.0.85"}}))

    client.sync_app_version()

    assert transport.calls[0][0].headers["User-Agent"] == full_ua


@pytest.mark.parametrize("device_ua", [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) Mobile/15E148",
    "Mozilla/5.0 (iPad; CPU OS 18_5 like Mac OS X) Mobile/15E148",
    "mozilla/5.0 (ipod touch; cpu iphone os 15_8 like mac os x)",
    "CampusApp (iOS17.5; iPhone15,2)",
    "CampusApp (iPadOS 18.5)",
])
def test_apple_mobile_ua_is_rejected_without_rejecting_custom_nonapple_ua(device_ua):
    assert api_client.ApiClient.is_unsupported_device_ua(device_ua)
    assert api_client.ApiClient.normalize_device_ua(device_ua) == ""
    assert api_client.ApiClient.normalize_device_ua("Custom UA AppleWebKit/537.36") == (
        "Custom UA AppleWebKit/537.36"
    )


@pytest.mark.parametrize("optional_ua", [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) Mobile/15E148",
    "Mobile Safari/537.36",
    None,
])
def test_random_ua_falls_back_to_android_webview_for_bad_mobile_candidates(monkeypatch, optional_ua):
    monkeypatch.setitem(sys.modules, "fake_useragent", SimpleNamespace(
        UserAgent=lambda **_kwargs: SimpleNamespace(random=optional_ua),
    ))

    ua = api_client.ApiClient.generate_random_ua()

    assert "Android " in ua
    assert "; wv)" in ua
    assert not api_client.ApiClient.is_unsupported_device_ua(ua)


def test_random_ua_accepts_android_candidate_and_limits_optional_library_to_android(monkeypatch):
    captured = {}
    android = "Mozilla/5.0 (Linux; Android 14; Test Device) Mobile Safari/537.36"

    def user_agent_catalog(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(random=android)

    monkeypatch.setitem(sys.modules, "fake_useragent", SimpleNamespace(UserAgent=user_agent_catalog))

    assert api_client.ApiClient.generate_random_ua() == android
    assert captured == {"platforms": ["mobile"], "os": ["Android"]}


def test_login_replaces_apple_ua_on_version_probe_and_login_request(app_client, monkeypatch):
    factory, transport = app_client
    client = factory()
    client.app.device_ua = client._device_ua = "iPod account UA"
    client.app.platform = "ios"
    android = "Android selected-device"
    monkeypatch.setattr(client, "generate_random_ua", lambda: android)
    transport.responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"accessToken": "test-access-token"}}),
    ])

    assert client.login("test-user", "test-password")["code"] == 200

    assert [urlsplit(request.url).path for request, _ in transport.calls] == [
        "/app/checkVersion", "/app/login",
    ]
    for request, _ in transport.calls:
        assert request.headers["User-Agent"] == android + client.UA_SUFFIX
        assert request.headers["platform"] == "android"
    assert client.app.device_ua == client._device_ua == android


def test_version_cache_hit_repairs_apple_ua_without_rechecking_version(app_client, monkeypatch):
    factory, transport = app_client
    client = factory()
    api_client.ApiClient._APP_VERSION_CACHE[client.BASE_URL] = "1.0.100"
    client.app.device_ua = "iPhone stale saved UA"
    client.app.platform = "iOS"
    client._device_ua = "Android previous UA for same account"
    monkeypatch.setattr(client, "generate_random_ua", pytest.fail)

    assert client.sync_app_version() == "1.0.100"
    assert not transport.calls
    assert client.app.device_ua == "Android previous UA for same account"
    assert client._get_headers()["platform"] == "android"


def test_repair_notifies_the_owner_once_without_holding_the_client_ua_lock(
    app_client, monkeypatch, caplog,
):
    factory, _transport = app_client
    client = factory()
    client.app.device_ua = "iPhone stored-UA"
    client._device_ua = "iPhone cached-UA"
    android = "Android account-specific UA"
    repaired = []
    monkeypatch.setattr(client, "generate_random_ua", lambda: android)

    def repair(old_ua, replacement):
        assert client._device_ua_lock.acquire(blocking=False)
        client._device_ua_lock.release()
        repaired.append((old_ua, replacement))
        raise RuntimeError("private repair details")

    client.app._repair_unsupported_device_ua = repair
    with caplog.at_level("WARNING"):
        assert client.ensure_device_ua() == client.ensure_device_ua() == android

    assert repaired == [("iPhone stored-UA", android)]
    assert "RuntimeError" in caplog.text
    assert "private repair details" not in caplog.text


@pytest.mark.parametrize("data", [[], "unavailable", None, {}, {"version": "invalid"}])
def test_bad_version_reply_does_not_block_login_or_cache_failure(app_client, data):
    factory, transport = app_client
    client = factory()
    transport.responses.extend([
        (200, {"code": 200, "data": data}),
        (200, {"code": 200, "data": {"accessToken": "new-test-token"}}),
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
    ])
    assert client.login("test-user", "test-password")["code"] == 200
    assert client.access_token == "new-test-token"
    assert client.sync_app_version() == "1.0.100"
    assert len(transport.calls) == 3


def test_forced_version_refresh_does_not_downgrade_client(app_client):
    factory, transport = app_client
    client = factory()
    transport.responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"version": "1.0.9"}}),
    ])
    assert client.sync_app_version() == "1.0.100"
    assert client.sync_app_version(force=True) == "1.0.100"
    assert factory().sync_app_version() == "1.0.100"
    assert len(transport.calls) == 2


def test_login_drops_previous_tokens_and_uses_query_credentials(app_client):
    factory, transport = app_client
    client = factory()
    client._app_version_synced = True
    client.set_access_token("old-test-token")
    client._refresh_token = "old-test-refresh-token"
    client.session.cookies.set("shiroCookie", "old-test-cookie")
    transport.responses.append((401, {"code": 401, "message": "invalid credentials"}))

    assert client.login("test-user", "p+ &密")["code"] == 401
    request, _ = transport.calls[0]
    assert request.method == "POST"
    assert urlsplit(request.url).path == "/app/login"
    assert parse_qs(urlsplit(request.url).query) == {"username": ["test-user"], "password": ["p+ &密"]}
    assert request.body in (None, b"")
    assert "Authorization" not in request.headers
    assert client.access_token is None
    assert not client._refresh_token
    assert "Authorization" not in client._get_headers()
    assert len(transport.calls) == 1


@pytest.mark.parametrize("as_string", [True, False])
def test_run_track_posts_json_with_app_upload_timeout(app_client, as_string):
    factory, transport = app_client
    client = factory()
    payload = {"trid": "test-track", "coordinate": "[]", "userName": "测试用户"}
    argument = json.dumps(payload, ensure_ascii=False) if as_string else payload
    assert client.submit_run_track(argument)["code"] == 200
    request, options = transport.calls[0]
    assert request.method == "POST"
    assert request.url == "https://zslf.zsc.edu.cn/run/errand/addErrandTrackByData"
    assert json.loads(request.body) == payload
    assert request.headers["Content-Type"] == "application/json;charset=UTF-8"
    assert options["timeout"] == (5, 30)


def test_object_data_is_json_and_explicit_form_encoding_remains_available(app_client):
    factory, transport = app_client
    client = factory()
    client._request("POST", "/mobileLogReport/addLog", data={"message": "测试"})
    request, _ = transport.calls[0]
    assert json.loads(request.body) == {"message": "测试"}
    assert request.headers["Content-Type"] == "application/json;charset=UTF-8"

    client._request("POST", "/form-test", data={"value": "a+b"}, force_content_type=client.FORM_CONTENT_TYPE)
    request, _ = transport.calls[1]
    assert parse_qs(request.body.decode()) == {"value": ["a+b"]}
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"


@pytest.mark.parametrize("method,args,path,query", [
    ("get_run_list", ("u",), "/run/errand/getErrandList", {"userId": ["u"], "offset": ["0"], "limit": ["10"]}),
    ("get_run_details", ("e", "u", "s"), "/run/errand/getErrandDetail", {"errandId": ["e"], "userId": ["u"], "errandScheduleId": ["s"]}),
    ("get_run_history_list", ("u", "s"), "/run/errand/getUserErrandTrackRecord", {"userId": ["u"], "errandScheduleId": ["s"], "offset": ["0"], "limit": ["10"]}),
    ("get_history_track_by_trid", ("t",), "/run/errand/getTrackByTrid", {"trid": ["t"]}),
    ("get_run_info_by_trid", ("t",), "/run/errand/getTrackRecordByTrid", {"trid": ["t"]}),
    ("get_unread_notice_count", (), "/app/appNotice/unreadNumber", {}),
    ("get_notice_list", (), "/app/appNotice/noticeListByType", {"offset": ["0"], "limit": ["10"], "typeId": ["0"]}),
    ("mark_notice_as_read", ("n",), "/app/appNotice/updateNoticeIsRead", {"noticeId": ["n"]}),
    ("get_roll_call_info", ("r", "u"), "/run/attendanceRecord/getAttendanceByRollCallId", {"id": ["r"], "userId": ["u"]}),
    ("get_attendance_radius", (), "/app/appFind/getDictTips", {"code": ["attendanceRadius"], "num": ["1"]}),
])
def test_query_endpoints_preserve_app_contract(app_client, method, args, path, query):
    factory, transport = app_client
    client = factory()
    client.set_access_token("test-access-token")
    assert getattr(client, method)(*args)["code"] == 200
    request, _ = transport.calls[0]
    assert request.method == "POST"
    assert urlsplit(request.url).path == path
    assert parse_qs(urlsplit(request.url).query) == query
    assert request.body in (None, b"")
    assert request.headers["Authorization"] == "test-access-token"
    assert request.headers["Accept"] == "*/*"
    assert request.headers["platform"] == "android"
    assert request.headers["appVersion"] == "1.0.85"


def test_attendance_keeps_distinct_ids_and_does_not_invent_missing_id(app_client):
    factory, transport = app_client
    client = factory()
    payload = {"id": "attendance-record", "rollCallId": "roll-call", "coordinate": "22.5,113.5", "userId": "u", "name": "测试用户"}
    client.submit_attendance(payload)
    query = parse_qs(urlsplit(transport.calls[0][0].url).query)
    assert query == {key: [value] for key, value in payload.items()}
    assert payload["id"] == "attendance-record"

    missing_id = {"rollCallId": "another-roll-call", "userId": "u"}
    client.submit_attendance(missing_id)
    assert "id" not in parse_qs(urlsplit(transport.calls[1][0].url).query)
    assert missing_id == {"rollCallId": "another-roll-call", "userId": "u"}


def test_http_auth_error_envelope_is_returned_without_retry(app_client):
    factory, transport = app_client
    transport.responses.append((401, {"code": 401, "message": "expired"}))
    assert factory().get_unread_notice_count() == {"code": 401, "message": "expired"}
    assert len(transport.calls) == 1
