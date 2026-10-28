import copy
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import api_runtime
import main
import map_error_catalog
import route_failure_visibility
from background_task_manager import ChromeBrowserPool
from route_diagnostics import build_route_failure_summary
from runtime_models import AccountSession


AUTH_MESSAGE = "百度地图 API 认证失败，错误码：220，Referer 校验失败"


def extract(message, provider="baidu", kind="dialog"):
    parser = getattr(map_error_catalog, "extract_baidu_sdk_auth_error", None)
    assert callable(parser), "Baidu SDK authentication events need an explicit parser"
    return parser({"kind": kind, "detail": message}, provider=provider)


@pytest.mark.parametrize("message", [AUTH_MESSAGE, "Baidu Map API authentication failed, error_code=220"])
def test_explicit_baidu_auth_code_is_namespaced_and_explained(message):
    result = extract(message)
    assert result["api_type"] == "baidu_jsapi_auth"
    assert result["stage"] == "sdk_auth"
    assert result["error_code"] == 220
    assert result["error_explanation"] == "Referer 校验失败"
    assert result["retryable"] is False


@pytest.mark.parametrize("message", [
    "百度地图 API 认证失败，HTTP status=220，耗时301毫秒",
    "百度未授权使用地图api，可能是因为您提供的密钥不是有效的百度LBS开放平台密钥",
])
def test_auth_message_without_explicit_vendor_code_remains_unknown(message):
    result = extract(message)
    assert result["message"] == message
    assert result["api_type"] == "baidu_jsapi_auth"
    assert "error_code" not in result
    assert "error_explanation" not in result


def test_unknown_explicit_code_is_retained_without_a_guessed_explanation():
    result = extract("百度地图 API 认证失败，错误码：999999")
    assert result["error_code"] == 999999
    assert "error_explanation" not in result


@pytest.mark.parametrize("suffix", ["220ms", "220.5", "220abc"])
def test_partial_numeric_tokens_are_not_vendor_error_codes(suffix):
    result = extract("Baidu Map API authentication failed, error_code=" + suffix)
    assert "error_code" not in result


@pytest.mark.parametrize("message,provider,kind", [
    (AUTH_MESSAGE, "tencent", "dialog"),
    ("request 220 failed", "baidu", "dialog"),
    ("百度地图路段2失败，坐标220", "baidu", "dialog"),
    (AUTH_MESSAGE, "baidu", "http_error"),
])
def test_unrelated_events_cannot_be_classified_as_baidu_authentication(message, provider, kind):
    assert extract(message, provider, kind) is None


def worker():
    listeners = {}
    page = Mock()
    page.on.side_effect = lambda name, callback: listeners.setdefault(name, callback)
    pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
    pool._initialized = True
    pool._contexts = {"test-session": {"page": page, "context": Mock()}}
    return pool, page, listeners


def dialog(listeners, message=AUTH_MESSAGE):
    event = SimpleNamespace(message=message, dismiss=Mock())
    listeners["dialog"](event)
    event.dismiss.assert_called_once()


def run_worker(pool, **kwargs):
    return pool._do_execute_js("test-session", "script", [], diagnostic_context={
        "provider": "baidu", "diagnostic_id": "test-diagnostic", "sensitive_values": ["known-secret"],
    }, **kwargs)


def test_auth_event_survives_full_event_buffer_and_worker_exception():
    pool, page, listeners = worker()

    def evaluate(*_args):
        for _ in range(15):
            listeners["pageerror"](RuntimeError("unrelated script error"))
        dialog(listeners, AUTH_MESSAGE + " ak=known-secret")
        raise RuntimeError("Baidu SDK load timeout")

    page.evaluate.side_effect = evaluate
    result = run_worker(pool)
    auth = result["diagnostic"]["sdk_auth_error"]
    assert auth["error_code"] == 220
    assert "known-secret" not in json.dumps(result)
    assert len(result["diagnostic"]["browser_events"]) == 12
    assert pool._contexts["test-session"]["route_diagnostic_context"] is None
    dialog(listeners, "百度地图 API 认证失败，错误码：301")
    page.evaluate.side_effect = lambda *_args: {"path": []}
    assert "sdk_auth_error" not in run_worker(pool)["result"]["diagnostic"]


def test_navigation_late_auth_event_is_not_assigned_to_the_next_command():
    pool, page, listeners = worker()

    def prepare(*_args):
        dialog(listeners, "百度地图 API 认证失败，错误码：301")

    page.evaluate.return_value = {"error": "SDK load timeout"}
    with patch.object(pool, "_prepare_map_runtime_page", side_effect=prepare):
        result = run_worker(pool, runtime_page_origin="https://runtime.test")
    assert "sdk_auth_error" not in result["result"]["diagnostic"]
    assert result["result"]["diagnostic"]["browser_events"] == []


def test_javascript_cannot_inject_an_auth_event_from_another_command():
    pool, page, _listeners = worker()
    page.evaluate.return_value = {"error": "current timeout", "diagnostic": {"sdk_auth_error": auth_error()}}
    assert "sdk_auth_error" not in run_worker(pool)["result"]["diagnostic"]


def planned(payload):
    with patch.object(main, "chrome_pool", SimpleNamespace(), create=True), patch.object(
        main, "_plan_route_with_map_provider", return_value={"provider": "baidu"}
    ), patch.object(main, "resolve_backend_page_origin", return_value=("https://runtime.test", "request")), patch.object(
        main, "_plan_route_path_with_baidu_runtime", return_value=copy.deepcopy(payload)
    ):
        return main._plan_route_path_with_provider_runtime("test-session", [[113.39, 22.52], [113.40, 22.53]])


def auth_error(message=AUTH_MESSAGE):
    return {"provider": "baidu", "api_type": "baidu_jsapi_auth", "stage": "sdk_auth",
            "error_code": 220, "message": message, "source": "dialog"}


def test_production_entry_promotes_explicit_sdk_authentication_before_generic_timeout():
    result = planned({"error": "SDK load timeout", "diagnostic": {"sdk_auth_error": auth_error()}})
    summary = build_route_failure_summary(result)
    assert summary["api_type"] == "baidu_jsapi_auth"
    assert summary["stage"] == "sdk_auth"
    assert summary["error_code"] == 220
    assert summary["error_explanation"] == "Referer 校验失败"
    assert "220" in summary["message"]
    assert "SDK load timeout" in json.dumps(result["diagnostic"])


def test_unknown_authentication_message_is_preserved_without_inventing_an_error_code():
    candidate = auth_error("百度未授权使用地图api")
    candidate.pop("error_code")
    result = planned({"error": "SDK load timeout", "diagnostic": {"sdk_auth_error": candidate}})
    assert result["api_type"] == "baidu_jsapi_auth"
    assert result["error"] == candidate["message"]
    assert "error_code" not in result
    assert "error_explanation" not in result


@pytest.mark.parametrize("code", [4, 7, 8, 99999])
def test_explicit_route_error_takes_priority_over_browser_authentication(code):
    result = planned({"error": "route failure", "diagnostic": {"segment": 1,
        "segments": [{"segment": 1, "error_code": code}], "sdk_auth_error": auth_error()}})
    assert result["api_type"] == "baidu_jsapi_route"
    assert result["error_code"] == code
    assert result["error"] == "route failure"


def test_top_level_route_error_also_takes_priority_and_keeps_its_explanation():
    result = planned({"error": "route failure", "error_code": 4,
                      "diagnostic": {"sdk_auth_error": auth_error()}})
    assert result["api_type"] == "baidu_jsapi_route"
    assert result["error_code"] == 4
    assert result["error_explanation"] == "路线 SDK 密钥无效"


def test_successful_route_is_not_replaced_by_an_auxiliary_authentication_event():
    result = planned({"path": [{"lng": 113.39, "lat": 22.52}], "diagnostic": {"sdk_auth_error": auth_error()}})
    assert result["path"]
    assert "error" not in result
    assert "error_explanation" not in result
    assert result["diagnostic"]["sdk_auth_error"]["error_code"] == 220


def test_sdk_auth_structure_is_allowlisted_redacted_and_bounded_in_large_diagnostics():
    candidate = auth_error(AUTH_MESSAGE + " ak=known-secret " + "详情" * 5000)
    candidate.update({"token": "known-secret", "routes": [[113.39, 22.52]] * 5000})
    with patch.object(main, "_read_config_ini", return_value=Mock()):
        result = planned({"error": "SDK load timeout", "diagnostic": {
            "sdk_auth_error": candidate, "browser_events": [{"detail": "事件" * 5000}] * 12}})
    detail = result["diagnostic"]
    assert detail["sdk_auth_error"]["error_code"] == 220
    assert "token" not in detail["sdk_auth_error"]
    assert "routes" not in detail["sdk_auth_error"]
    assert "known-secret" not in json.dumps(result)
    summary = build_route_failure_summary(result)
    for ascii_only in (False, True):
        assert len(json.dumps(detail, ensure_ascii=ascii_only).encode()) <= 4096
        assert len(json.dumps(summary, ensure_ascii=ascii_only).encode()) <= 2048


def test_sdk_auth_fields_cannot_exceed_snapshot_limit_through_escaped_text():
    candidate = {field: "\0" * 1000 for field in
                 ("api_type", "stage", "error_code", "message", "source", "error_explanation", "error_hint", "retryable")}
    detail = main._bounded_route_runtime_diagnostic({"sdk_auth_error": candidate}, ())
    for ascii_only in (False, True):
        assert len(json.dumps(detail, ensure_ascii=ascii_only).encode()) <= 4096
    assert detail["sdk_auth_error"]


def test_auth_detail_is_removed_from_complete_public_http_and_websocket_payloads():
    result = planned({"error": "SDK load timeout", "diagnostic": {"sdk_auth_error": auth_error()}})
    summary = build_route_failure_summary(result)
    failure = {"success": False, "_route_failure": summary, "diagnostic": result["diagnostic"]}
    with patch.object(route_failure_visibility, "can_view_route_failure_details", return_value=False):
        public = route_failure_visibility.project_route_failure_response(failure, "test-session")
    with patch.object(route_failure_visibility, "can_view_route_failure_details", return_value=True):
        private = route_failure_visibility.project_route_failure_response(failure, "test-session")
    assert "Referer" in private["message"]
    assert "Referer" not in json.dumps(public)
    assert "sdk_auth_error" not in json.dumps(public)
    api = api_runtime.Api.__new__(api_runtime.Api)
    api._web_session_id = "test-session"
    socket = Mock()
    runtime = SimpleNamespace(socketio=socket, _redact_sensitive_log_value=lambda value: value)
    with patch.object(api_runtime, "_main", return_value=runtime):
        api._notify_route_planning_failure(result)
    public_ws = socket.emit.call_args.args[1]
    assert set(public_ws) == {"msg", "diagnostic_id"}
    assert "Referer" not in json.dumps(public_ws)
    assert public_ws["diagnostic_id"] == summary["diagnostic_id"]


@pytest.mark.parametrize("owner_role", ["user", "admin", "role_lookup_failed"])
def test_multi_http_and_websocket_details_follow_target_owner_not_admin_viewer(owner_role):
    result = planned({"error": "SDK load timeout", "diagnostic": {"sdk_auth_error": auth_error()}})
    summary = build_route_failure_summary(result)
    api = api_runtime.Api.__new__(api_runtime.Api)
    api._web_session_id, api.auth_username = "test-session", "target-owner"
    api.is_multi_account_mode, api.is_authenticated, api.is_guest = True, True, False
    account = AccountSession.__new__(AccountSession)
    account.username, account.api_bridge = "school-account", api
    socket = Mock()

    def role(username):
        if username == "viewer":
            return "admin"
        if owner_role == "role_lookup_failed":
            raise RuntimeError("lookup unavailable")
        return owner_role

    runtime = SimpleNamespace(
        socketio=socket, _redact_sensitive_log_value=lambda value: value,
        request=SimpleNamespace(headers={"X-Admin-Origin-Session-ID": "admin-origin"}, cookies={"auth_token": "test-token"}),
        ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID", web_sessions={"test-session": api},
        web_sessions_lock=threading.Lock(), auth_system=SimpleNamespace(get_user_group=role),
        resolve_admin_origin_session_context=lambda *_args: {"username": "viewer"},
    )
    failure = {"success": False, "_route_failure": summary, "diagnostic": result["diagnostic"]}
    with patch.object(api_runtime, "_main", return_value=runtime), patch.object(route_failure_visibility, "_main", return_value=runtime):
        response = route_failure_visibility.project_route_failure_response(failure, "test-session")
        api._notify_route_planning_failure(result, account=account)
    payload = socket.emit.call_args.args[1]
    assert ("Referer" in json.dumps(response)) is (owner_role == "admin")
    assert ("Referer" in json.dumps(payload)) is (owner_role == "admin")
    assert "sdk_auth_error" not in json.dumps(response)
    assert set(payload) == {"msg", "diagnostic_id"}
