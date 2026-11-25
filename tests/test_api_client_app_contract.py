"""Exercise the App contract at the real requests serialization boundary."""

from concurrent.futures import ThreadPoolExecutor
import json
import sys
from threading import Event
import time
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
        self.version_responses = []

    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        if urlsplit(request.url).path == "/app/checkVersion":
            status, payload = self.version_responses.pop(0) if self.version_responses else (
                200, {"code": 200, "data": {"version": "1.0.85"}},
            )
        else:
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

    @property
    def business_calls(self):
        return [call for call in self.calls if urlsplit(call[0].url).path != "/app/checkVersion"]

    @property
    def version_calls(self):
        return [call for call in self.calls if urlsplit(call[0].url).path == "/app/checkVersion"]


@pytest.fixture
def version_clock(monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(api_client, "time", SimpleNamespace(
        monotonic=lambda: clock.now,
        sleep=time.sleep,
    ))
    return clock


@pytest.fixture
def app_client(monkeypatch, version_clock):
    runtime = SimpleNamespace(
        requests=requests,
        urllib=urllib,
        _redact_sensitive_log_text=lambda value: str(value or ""),
        _redact_sensitive_log_value=lambda value: value,
    )
    monkeypatch.setattr(api_client, "_main", lambda: runtime)
    monkeypatch.setattr(api_client.ApiClient, "_APP_VERSION_CACHE", {})
    monkeypatch.setattr(api_client.ApiClient, "_APP_VERSION_REFRESH_IN_FLIGHT", {}, raising=False)
    owner = SimpleNamespace(
        device_ua="Mozilla/5.0 (Linux; Android 16; test device)", is_offline_mode=False,
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


_COMPATIBILITY_DETAILS = {
    "startTime": "请更新APP后再进行跑步",
    "endTime": "原因：APP版本过低/超时,请在我的-设置点击版本号更新后再跑步。",
    "geoCoorList": [],
    "walkPaths": [],
}


def _detail_response(details):
    return {"code": 200, "success": True, "data": {"errandDetail": details}}


def test_run_details_refreshes_version_with_retries_then_uses_new_header(app_client, monkeypatch):
    factory, transport = app_client
    client = factory()
    assert client.sync_app_version() == "1.0.85"
    retries = []
    monkeypatch.setattr(client, "_wait_for_retry_or_cancel", lambda delay: retries.append(delay) or False)
    transport.version_responses.extend([
        (503, {"code": 503}),
        (200, {"code": 200, "data": {"version": "invalid"}}),
        (200, {"code": 200, "data": {"version": "1.0.86"}}),
    ])
    recovered = _detail_response({"geoCoorList": [{"lon": 1, "lat": 2}]})
    transport.responses.extend([(200, _detail_response(_COMPATIBILITY_DETAILS)), (200, recovered)])

    assert client.get_run_details("e", "u", "s") == recovered
    assert len(retries) == 2
    assert len(transport.version_calls) == 4
    first, refreshed = [request for request, _ in transport.business_calls]
    assert first.url == refreshed.url
    assert [first.headers["appVersion"], refreshed.headers["appVersion"]] == ["1.0.85", "1.0.86"]


def test_run_details_returns_persistent_compatibility_response_after_one_recheck(app_client, monkeypatch):
    factory, transport = app_client
    client = factory()
    client.sync_app_version()
    monkeypatch.setattr(client, "_wait_for_retry_or_cancel", lambda _delay: False)
    transport.version_responses.extend([(503, {"code": 503})] * 3)
    incompatible = _detail_response(_COMPATIBILITY_DETAILS)
    transport.responses.extend([(200, incompatible)] * 3)

    assert client.get_run_details("e", "u", "s") == incompatible
    assert len(transport.version_calls) == 4
    assert len(transport.business_calls) == 2


def test_run_details_does_not_refresh_for_school_opening_hours_notice(app_client):
    factory, transport = app_client
    client = factory()
    client.sync_app_version()
    unavailable = _detail_response({"geoCoorList": [], "endTime": "原因：21:30后不开放任务/超时"})
    transport.responses.append((200, unavailable))

    assert client.get_run_details("e", "u", "s") == unavailable
    assert len(transport.version_calls) == len(transport.business_calls) == 1


def test_task_expiry_annotation_is_matched_without_leaking_the_date():
    payload = _detail_response({
        "name": "第十二次2公里跑步30分钟内完成",
        "geoCoorList": [],
        "endTime": "2026-11-24(当前任务已超时)",
    })

    assert api_client.classify_task_detail_notice(payload) == (
        "availability", ("当前任务已超时",),
    )


@pytest.mark.parametrize("details,message", [
    ({"startTime": "请将 ＡＰＰ 更新至最新版后再跑步", "geoCoorList": None}, "获取任务详情成功"),
    ({"endTime": "客户端版本号不匹配，请重新尝试"}, "获取任务详情成功"),
    ({"startTime": "请更新版本后再进行跑步", "geoCoorList": []}, "获取任务详情成功"),
    ({}, "当前 App 版本不对，请更新后再试"),
])
def test_task_version_recovery_accepts_explicit_wording_variants(app_client, details, message):
    factory, transport = app_client
    client = factory()
    client.sync_app_version()
    gated = _detail_response(details)
    if not details:
        gated = {"code": 400, "success": False}
    gated["message"] = message
    recovered = _detail_response({"geoCoorList": [{"lon": 1, "lat": 2}]})
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.86"}}))
    transport.responses.extend([(200, gated), (200, recovered)])

    assert client.get_run_details("e", "u", "s") == recovered
    assert len(transport.version_calls) == len(transport.business_calls) == 2


@pytest.mark.parametrize("details,message", [
    ({"startTime": "请更新 APP 后再进行跑步", "geoCoorList": [{"lon": 1, "lat": 2}]}, "成功"),
    ({"startTime": "请更新路线后再跑步", "geoCoorList": []}, "获取任务详情成功"),
    ({"startTime": "请登录", "geoCoorList": []}, "请求超时"),
    ({"startTime": "无需更新 APP，任务尚未开放", "geoCoorList": []}, "获取任务详情成功"),
    ({"startTime": "任务版本过低", "geoCoorList": []}, "获取任务详情成功"),
])
def test_task_version_recovery_ignores_unrelated_text(app_client, details, message):
    factory, transport = app_client
    client = factory()
    client.sync_app_version()
    response = {**_detail_response(details), "message": message}
    transport.responses.append((200, response))

    assert client.get_run_details("e", "u", "s") == response
    assert len(transport.version_calls) == len(transport.business_calls) == 1


def test_check_version_uses_get_and_equal_version_cache_is_reused(app_client):
    factory, transport = app_client
    first = factory()
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.85"}}))
    assert first.sync_app_version() == "1.0.85"
    request, _ = transport.calls[0]
    assert request.method == "GET"
    assert request.url == "https://zslf.zsc.edu.cn/app/checkVersion"
    assert request.body is None
    assert factory().sync_app_version() == "1.0.85"
    assert len(transport.calls) == 1


@pytest.mark.parametrize("blocked_by", ["offline", "cancelled"])
def test_inactive_request_does_not_probe_or_delay_next_online_request(app_client, blocked_by):
    factory, transport = app_client
    client = factory()
    cancel = Event()
    client._execution_cancel_event = cancel
    if blocked_by == "offline":
        client.app.is_offline_mode = True
    else:
        cancel.set()

    assert client._request("GET", "/appNotice/unreadNumber") is None
    assert client.sync_app_version() == client.NEW_APP_VERSION
    assert not transport.calls

    client.app.is_offline_mode = False
    cancel.clear()
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.104"}}))
    assert client._request("GET", "/appNotice/unreadNumber").status_code == 200
    assert len(transport.version_calls) == 1
    assert transport.business_calls[0][0].headers["appVersion"] == "1.0.104"


def test_version_refreshes_on_the_next_active_request_after_six_hours(app_client, version_clock):
    factory, transport = app_client
    client = factory()
    transport.version_responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"version": "1.0.101"}}),
    ])

    client.get_run_list("test-user")
    version_clock.now += 6 * 60 * 60 - 1
    factory().get_unread_notice_count()
    assert len(transport.version_calls) == 1
    assert [request.headers["appVersion"] for request, _ in transport.business_calls] == [
        "1.0.100", "1.0.100",
    ]

    version_clock.now += 1
    assert len(transport.version_calls) == 1
    client.get_run_list("test-user")
    assert [(urlsplit(request.url).path, request.headers["appVersion"]) for request, _ in transport.calls[-2:]] == [
        ("/app/checkVersion", "1.0.100"),
        ("/run/errand/getErrandList", "1.0.101"),
    ]
    factory().get_unread_notice_count()
    assert transport.business_calls[-1][0].headers["appVersion"] == "1.0.101"
    assert len(transport.version_calls) == 2


def test_idle_client_waits_for_a_new_request_to_refresh_an_expired_version(
    app_client, version_clock, monkeypatch,
):
    factory, transport = app_client
    def unexpected_background_worker(_thread):
        pytest.fail("version refresh must only run on demand")

    monkeypatch.setattr(api_client.threading.Thread, "start", unexpected_background_worker)
    client = factory()
    transport.version_responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"version": "1.0.102"}}),
    ])
    client.get_unread_notice_count()

    version_clock.now += 18 * 60 * 60
    assert len(transport.version_calls) == 1
    factory().get_unread_notice_count()
    assert len(transport.version_calls) == 2
    assert transport.business_calls[-1][0].headers["appVersion"] == "1.0.102"


def test_failed_expired_refresh_keeps_stale_version_until_retry(app_client, version_clock):
    factory, transport = app_client
    client = factory()
    transport.version_responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"version": "invalid"}}),
        (200, {"code": 200, "data": {"version": "1.0.102"}}),
    ])
    assert client.sync_app_version() == "1.0.100"
    version_clock.now += 6 * 60 * 60

    client.get_unread_notice_count()
    version_clock.now += 59
    factory().get_run_list("test-user")
    assert len(transport.version_calls) == 2
    assert [request.headers["appVersion"] for request, _ in transport.business_calls] == [
        "1.0.100", "1.0.100",
    ]

    version_clock.now += 1
    factory().get_unread_notice_count()
    assert len(transport.version_calls) == 3
    assert transport.business_calls[-1][0].headers["appVersion"] == "1.0.102"


def test_expired_version_refresh_is_shared_between_clients(app_client, version_clock, monkeypatch):
    factory, transport = app_client
    first, second = factory(), factory()
    transport.version_responses.extend([
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
        (200, {"code": 200, "data": {"version": "1.0.103"}}),
    ])
    assert first.sync_app_version() == second.sync_app_version() == "1.0.100"
    version_clock.now += 6 * 60 * 60
    entered = Event()
    release = Event()
    send = transport.send

    def send_while_refreshing(request, **kwargs):
        if urlsplit(request.url).path == "/app/checkVersion":
            entered.set()
            assert release.wait(5)
        return send(request, **kwargs)

    monkeypatch.setattr(transport, "send", send_while_refreshing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        refreshing = pool.submit(first.sync_app_version)
        try:
            assert entered.wait(5)
            competing = pool.submit(second.sync_app_version)
            assert competing.result(timeout=2) == "1.0.100"
        finally:
            release.set()
        assert refreshing.result(timeout=5) == "1.0.103"

    assert len(transport.version_calls) == 2
    assert first.sync_app_version() == second.sync_app_version() == "1.0.103"


def test_check_version_reuses_existing_android_ua_with_app_suffix(app_client, monkeypatch):
    factory, transport = app_client
    client = factory()
    full_ua = ("Mozilla/5.0 (Linux; Android 16; fixture; wv) Chrome/159.0.0.0 Mobile Safari/537.36 "
               "uni-app (Immersed/29.09091) Html5Plus/1.0")
    client.app.device_ua = full_ua
    monkeypatch.setattr(client, "generate_random_ua", pytest.fail)
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.85"}}))

    client.sync_app_version()

    assert transport.calls[0][0].headers["User-Agent"] == full_ua
    assert client.app.device_ua == full_ua


@pytest.mark.parametrize("configured_ua", [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "custom-legacy-UA",
    "Mozilla/5.0 (Windows NT 10.0) Android Browser",
])
def test_all_campus_requests_send_stable_android_headers(app_client, monkeypatch, configured_ua):
    factory, transport = app_client
    client = factory()
    client.app.device_ua = client._device_ua = configured_ua
    client.app.platform = "windows"
    client.session.headers["user-agent"] = "session-default-UA"
    client.session.headers["Platform"] = "desktop"
    android = "Mozilla/5.0 (Linux; Android 16; fixture; wv)"
    generated = []
    repaired = []

    def repair(previous, replacement):
        repaired.append((previous, replacement))

    def generate():
        generated.append(android)
        return android

    client.app._repair_unsupported_device_ua = repair
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(generate))
    monkeypatch.setattr(client, "_wait_for_retry_or_cancel", lambda _seconds: False)
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.85"}}))

    client.sync_app_version()
    client._request("GET", "/appNotice/getAppNoticeList")
    transport.responses.extend([(503, {"code": 503}), (200, {"code": 200})])
    client._request("POST", "/run/attendanceRecord/getAttendanceByRollCallId")

    assert [urlsplit(request.url).path for request, _ in transport.calls] == [
        "/app/checkVersion", "/app/appNotice/getAppNoticeList",
        "/run/attendanceRecord/getAttendanceByRollCallId", "/run/attendanceRecord/getAttendanceByRollCallId",
    ]
    for request, _ in transport.calls:
        assert request.headers["User-Agent"] == android + client.UA_SUFFIX
        assert request.headers["platform"] == "android"
    assert generated == [android]
    assert repaired == [(configured_ua, android)]
    assert client.app.device_ua == client._device_ua == android


@pytest.mark.parametrize("apple_ua", [
    "Mozilla/5.0 (iPhone)",
    "Mozilla/5.0 (iPad; CPU OS 18_1 like Mac OS X)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "CampusApp (macOS 15.6)",
])
def test_apple_repair_cannot_reuse_cached_desktop_ua(app_client, monkeypatch, apple_ua):
    factory, transport = app_client
    client = factory()
    client._device_ua = "custom-desktop-UA"
    client.app.device_ua = apple_ua
    repaired = []
    client.app._repair_unsupported_device_ua = lambda previous, replacement: repaired.append((previous, replacement))
    android = "Mozilla/5.0 (Linux; Android 16; fixture; wv) AppleWebKit/537.36"
    monkeypatch.setattr(api_client.ApiClient, "generate_random_ua", staticmethod(lambda: android))

    client.sync_app_version()
    client._request("POST", "/run/attendanceRecord/getAttendanceByRollCallId")

    assert repaired == [(apple_ua, android)]
    assert [request.headers["User-Agent"] for request, _ in transport.calls] == [android + client.UA_SUFFIX] * 2


@pytest.mark.parametrize("device_ua", [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) Mobile/15E148",
    "Mozilla/5.0 (iPad; CPU OS 18_5 like Mac OS X) Mobile/15E148",
    "mozilla/5.0 (ipod touch; cpu iphone os 15_8 like mac os x)",
    "CampusApp (iOS17.5; iPhone15,2)",
    "CampusApp (iPadOS 18.5)",
])
def test_apple_mobile_ua_is_rejected(device_ua):
    assert api_client.ApiClient.is_unsupported_device_ua(device_ua)
    assert api_client.ApiClient.normalize_device_ua(device_ua) == ""


def test_android_ua_with_applewebkit_is_reused():
    android = "Mozilla/5.0 (Linux; Android 16; fixture; wv) AppleWebKit/537.36"
    assert not api_client.ApiClient.is_unsupported_device_ua(android)
    assert api_client.ApiClient.normalize_device_ua(android) == android


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
    android = "Mozilla/5.0 (Linux; Android 16; selected-device)"
    monkeypatch.setattr(client, "generate_random_ua", lambda: android)
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.100"}}))
    transport.responses.append((200, {"code": 200, "data": {"accessToken": "test-access-token"}}))

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
    transport.version_responses.append((200, {"code": 200, "data": {"version": "1.0.100"}}))
    assert client.sync_app_version() == "1.0.100"
    client.app.device_ua = "iPhone stale saved UA"
    client.app.platform = "iOS"
    android = "Mozilla/5.0 (Linux; Android 16; same-account device)"
    client._device_ua = android
    monkeypatch.setattr(client, "generate_random_ua", pytest.fail)

    assert client.sync_app_version() == "1.0.100"
    assert len(transport.calls) == 1
    assert client.app.device_ua == android
    assert client._get_headers()["platform"] == "android"


def test_repair_notifies_the_owner_once_without_holding_the_client_ua_lock(
    app_client, monkeypatch, caplog,
):
    factory, _transport = app_client
    client = factory()
    client.app.device_ua = "iPhone stored-UA"
    client._device_ua = "iPhone cached-UA"
    android = "Mozilla/5.0 (Linux; Android 16; account-specific device)"
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
def test_bad_cold_version_reply_allows_login_and_retries_after_cooldown(app_client, version_clock, data):
    factory, transport = app_client
    client = factory()
    transport.version_responses.extend([
        (200, {"code": 200, "data": data}),
        (200, {"code": 200, "data": {"version": "1.0.100"}}),
    ])
    transport.responses.append((200, {"code": 200, "data": {"accessToken": "new-test-token"}}))
    assert client.login("test-user", "test-password")["code"] == 200
    assert client.access_token == "new-test-token"
    assert transport.business_calls[0][0].headers["appVersion"] == client.NEW_APP_VERSION
    assert factory().sync_app_version() == client.NEW_APP_VERSION
    assert len(transport.version_calls) == 1
    version_clock.now += 60
    assert client.sync_app_version() == "1.0.100"
    assert len(transport.calls) == 3


def test_forced_version_refresh_does_not_downgrade_client(app_client):
    factory, transport = app_client
    client = factory()
    transport.version_responses.extend([
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
    client.set_access_token("old-test-token")
    client._refresh_token = "old-test-refresh-token"
    client.session.cookies.set("shiroCookie", "old-test-cookie")
    transport.responses.append((401, {"code": 401, "message": "invalid credentials"}))

    assert client.login("test-user", "p+ &密")["code"] == 401
    request, _ = transport.business_calls[0]
    assert request.method == "POST"
    assert urlsplit(request.url).path == "/app/login"
    assert parse_qs(urlsplit(request.url).query) == {"username": ["test-user"], "password": ["p+ &密"]}
    assert request.body in (None, b"")
    assert "Authorization" not in request.headers
    assert client.access_token is None
    assert not client._refresh_token
    assert "Authorization" not in client._get_headers()
    assert len(transport.business_calls) == 1


@pytest.mark.parametrize("as_string", [True, False])
def test_run_track_posts_json_with_app_upload_timeout(app_client, as_string):
    factory, transport = app_client
    client = factory()
    payload = {"trid": "test-track", "coordinate": "[]", "userName": "测试用户"}
    argument = json.dumps(payload, ensure_ascii=False) if as_string else payload
    assert client.submit_run_track(argument)["code"] == 200
    request, options = transport.business_calls[0]
    assert request.method == "POST"
    assert request.url == "https://zslf.zsc.edu.cn/run/errand/addErrandTrackByData"
    assert json.loads(request.body) == payload
    assert request.headers["Content-Type"] == "application/json;charset=UTF-8"
    assert options["timeout"] == (5, 30)


def test_object_data_is_json_and_explicit_form_encoding_remains_available(app_client):
    factory, transport = app_client
    client = factory()
    client._request("POST", "/mobileLogReport/addLog", data={"message": "测试"})
    request, _ = transport.business_calls[0]
    assert json.loads(request.body) == {"message": "测试"}
    assert request.headers["Content-Type"] == "application/json;charset=UTF-8"

    client._request("POST", "/form-test", data={"value": "a+b"}, force_content_type=client.FORM_CONTENT_TYPE)
    request, _ = transport.business_calls[1]
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
    request, _ = transport.business_calls[0]
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
    query = parse_qs(urlsplit(transport.business_calls[0][0].url).query)
    assert query == {key: [value] for key, value in payload.items()}
    assert payload["id"] == "attendance-record"

    missing_id = {"rollCallId": "another-roll-call", "userId": "u"}
    client.submit_attendance(missing_id)
    assert "id" not in parse_qs(urlsplit(transport.business_calls[1][0].url).query)
    assert missing_id == {"rollCallId": "another-roll-call", "userId": "u"}


def test_http_auth_error_envelope_is_returned_without_retry(app_client):
    factory, transport = app_client
    transport.responses.append((401, {"code": 401, "message": "expired"}))
    assert factory().get_unread_notice_count() == {"code": 401, "message": "expired"}
    assert len(transport.business_calls) == 1
