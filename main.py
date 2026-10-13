# 跑步助手
# 这是一个基于Flask的Web应用，用于模拟跑步任务的执行


from __future__ import annotations

import ast
import glob
import math
import tempfile
import threading

from flask import jsonify, make_response, request, send_from_directory

from payment_crypto import RsaSigner
from config_adapter import JsonConfigAdapter
from auto_attendance_config import (
    _disable_auto_attendance,
    _enable_auto_attendance,
    _get_auto_attendance_by_session,
    _get_auto_attendance_session,
    _is_auto_attendance_enabled,
    _load_auto_attendance_config,
    _migrate_auto_attendance_from_ini,
    _record_auto_attendance_success,
    _save_auto_attendance_config,
    expire_stale_auto_attendance_accounts,
)
from runtime_maintenance import (
    _append_daily_full_restart_log,
    _apply_daily_restart_config_updates,
    _build_daily_restart_helper_command,
    _get_daily_full_restart_log_path,
    _get_daily_full_restart_marker_path,
    _get_daily_restart_config_view_data,
    _get_daily_restart_schedule_config,
    _has_daily_full_restart_marker_for_date,
    _parse_daily_restart_time_string,
    _read_daily_full_restart_marker,
    _run_daily_restart_helper,
    _strip_daily_restart_helper_args,
    _trigger_daily_full_restart,
    _write_daily_full_restart_marker,
)
from trusted_ip import (
    _TrustedIpMatcher,
    _get_trusted_ip_networks,
    _is_builtin_trusted_proxy_ip,
    _load_trusted_ip_networks,
    _parse_trusted_ip_entry,
    _print_red_console_warning,
    _select_forwarded_client_ip,
)
from ip_verifier import (
    IPVerifier,
    _build_payment_verify_probe_url,
    _cleanup_expired_payment_verify_probes,
    _consume_payment_verify_probe,
    _create_payment_verify_probe,
    _is_payment_verify_probe_consumed,
)
from frontend_js_hardening import (
    _compact_javascript_whitespace,
    _copy_javascript_regex_literal,
    _copy_javascript_string_literal,
    _copy_javascript_template_expression,
    _copy_javascript_template_literal,
    _decode_frontend_javascript_content,
    _get_frontend_js_anti_debug_guard,
    _harden_frontend_javascript_for_response,
    _javascript_identifier_char,
    _javascript_previous_nonspace_and_identifier,
    _javascript_previous_token_allows_regex,
    _javascript_space_is_required,
    _strip_javascript_comments,
)
from map_key_runtime import (
    _build_obfuscated_map_key_runtime_script,
    _decrypt_map_provider_key_bundle,
    _encrypt_map_provider_payload_for_client,
    _encrypt_map_provider_secret,
    _ensure_map_key_runtime_cache,
    _generate_map_key_runtime_context,
    _get_crypto_primitives,
    _get_map_key_runtime_context_by_version,
    _get_map_key_runtime_context_for_request,
    _get_map_key_runtime_context_for_session,
    _get_map_key_runtime_script_url,
    _get_map_key_runtime_session_identity,
    _get_map_key_runtime_user_key,
    _initialize_map_key_runtime,
    _load_client_public_key,
    _obfuscate_runtime_javascript,
    _register_map_key_runtime_context,
    _release_map_key_runtime_session,
    _unregister_map_key_runtime_context_if_unused,
)
from session_state import (
    _load_session_index,
    _save_session_index,
    cleanup_expired_sessions,
    load_session_state,
    restore_session_to_api_instance,
    save_session_state,
)
from captcha_html import (
    get_captcha_dimensions,
    get_captcha_original_width,
    resize_captcha_html,
)
from brute_force_manager import BruteForceTaskManager
from health_status import (
    _aggregate_health_status,
    _build_health_comment_fields,
    _build_health_token_index_key,
    _check_payment_system_health,
    _check_running_core_health,
    _check_sms_system_health,
    _collect_auth_usernames_for_token_lookup,
    _get_health_token_index_path,
    _is_admin_health_view_from_token,
    _read_health_token_index,
    _resolve_username_by_token,
    _safe_get_config_for_health,
    _validate_cached_health_token_owner,
    _write_health_token_index,
)
from ssl_config import (
    get_ssl_certificate_info,
    load_ssl_config,
    save_ssl_config,
    validate_ssl_certificate,
)
from background_task_manager import (
    BackgroundTaskManager,
    ChromeBrowserPool,
    MicroPixelCaptcha,
    PlaywrightContextProxy,
    PlaywrightPageProxy,
)
from runtime_models import (
    AccountSession,
    RunData,
    TokenManager,
    UserData,
    _advance_order_status_by_timeout,
    _allow_random_background_feedback,
    _apply_payment_success_transition,
    _apply_refund_transition,
    _build_billing_qr_cache_key,
    _cleanup_random_background_cache,
    _cleanup_random_background_index,
    _get_reusable_billing_qr,
    _invalidate_billing_qr_cache_by_order,
    _is_order_terminal_for_repay,
    _load_qr_cache_index,
    _normalize_gender_value,
    _resolve_billing_payment_entry,
    _save_qr_cache_index,
)
from api_client import ApiClient
from auth_system import AuthSystem, GUEST_SESSION_CREATION_LOCK
from api_runtime import Api
from web_server import start_web_server
from theme_background_cache import (
    _build_theme_background_image_url,
    _ensure_random_background_cache_count,
    _fetch_random_background_image,
    _start_default_theme_background_cache_warmup,
)

from guest_token_store import GuestTokenStore
from theme_background_state import (
    BackgroundStateStore,
    empty_state as _empty_background_state,
)
from theme_background_legacy import (
    _extract_background_image_url_from_value,
    _get_random_background_index_entry,
    _get_session_theme_background_binding,
    _load_random_background_index,
    _mark_random_background_file_expired,
    _mark_random_background_file_state,
    _normalize_theme_background_session_uuid,
    _normalize_theme_background_target,
    _parse_random_background_file_name,
    _reset_random_background_file_expired,
    _resolve_bound_theme_background_images,
    _resolve_theme_background_binding_decision,
    _save_random_background_index,
    _set_session_theme_background_binding,
)

_import_failures = []
_log_buffer = []
_logging_exception_hooks_installed = False
_SINGLE_INSTANCE_LOCK_HANDLE = None

# 运行时在 main() 中从 product_name_generator.py 导入。
# 这里先定义占位全局变量，便于启动校验测试对其进行 mock。
LoMeiGenerator = None
PRODUCT_NAME_GENERATOR_MODE = None
validate_product_name_generator_mode = None


class _NoopLock:
    """模块级占位锁：在完整初始化前避免 NameError。"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


MAX_MEMORY_SESSIONS = 100
BACKGROUND_CACHE_TARGET_COUNT = 5
_BACKGROUND_SELECTION_STATE = {}
_BACKGROUND_SELECTION_LOCK = threading.Lock()
_THEME_BACKGROUND_REFRESH_LOCK = threading.Lock()
_THEME_BACKGROUND_REFRESH_IN_PROGRESS = False
_THEME_BACKGROUND_WARMUP_LOCK = threading.Lock()
_THEME_BACKGROUND_WARMUP_IN_PROGRESS = False

# 支付订单状态常量（模块级，便于测试与工具函数复用）
ORDER_STATUS_FAILED = "failed"
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_REFUNDED_PARTIAL = "refunded_partial"
ORDER_STATUS_REFUNDED_FULL = "refunded_full"
ORDER_STATUS_FROZEN = "frozen"
ORDER_STATUS_PREAUTH = "preauth"
ORDER_STATUS_TIMEOUT = "timeout"
ORDER_STATUS_CLOSED = "closed"

PAYMENT_ORDERS_DIR = "payment_orders"
QR_CACHE_INDEX_FILE = "payment_orders/qr_cache_index.json"
payment_verify_probes = {}
payment_verify_probes_lock = _NoopLock()

# 运行时全局状态的安全默认值。
# 这些对象会在启动流程中被重新初始化；这里提供兜底，避免在初始化前访问时报 NameError。
browsing_activity = {}
browsing_activity_lock = _NoopLock()
# 管理员查看态（上帝模式）来源会话保活表：origin_session_id -> 最近一次已验证的查看请求时间。
# 管理员强制进入他人会话后，自身会话不再收到 API 流量；没有这份记录时，
# 会话不活跃监控会回收来源会话并吊销该用户的 token 文件，查看态随即整体 401 掉线。
admin_view_origin_activity = {}
admin_view_origin_activity_lock = _NoopLock()
# 来源会话保活窗口（秒）。窗口内没有新的查看请求（例如浏览器已关闭）时，
# 来源会话重新回到普通的不活跃回收逻辑，避免会话永久驻留。
ADMIN_VIEW_ORIGIN_KEEPALIVE_SECONDS = 1800
CDN_FILES = {}
js_cache_storage = {}
js_cache_lock = _NoopLock()
js_cache_last_update = {}
font_cache_storage = {}
font_cache_lock = _NoopLock()
source_map_storage = {}
source_map_lock = _NoopLock()
_midnight_runtime_reload_hook = None
ENABLE_FRONTEND_JS_ANTI_DEBUG = False
# 自动签到功能配置
AUTO_ATTENDANCE_NOTICE_LIMIT = 5  # 自动签到时拉取的通知数量上限
AUTO_ATTENDANCE_MAX_MINUTES = 120  # 自动签到最长持续时间（分钟），超时后自动关闭
# 自动签到关闭后，刷新线程连续多少轮确认未启用即自行退出（每轮约 30 秒）。
# 需要大于 1 以避免配置读写的瞬时抖动导致线程误退。
AUTO_ATTENDANCE_DISABLED_ROUNDS_BEFORE_EXIT = 2

# 多账号 worker 单次运行最多尝试执行多少个任务。
# 新的调度逻辑会在每完成一个任务后重新拉取任务列表，因此需要上限兜底，
# 防止服务端持续返回同一批未完成任务时陷入死循环。
MULTI_WORKER_MAX_TASKS = 50

# 跑步 PID 参数（单账号/多账号共用）
PID_KP = 4.80
PID_KI = 0.16
PID_KD = 1.80
PID_DEADZONE = 0.010
PID_INTEGRAL_LIMIT = 0.50
PID_DEADZONE_BOOST_STEP = 0.08
PID_DEADZONE_BOOST_MAX = 2.50

# [安全配置] 输入验证常量
MAX_USERNAME_LENGTH = 200  # 用户名最大长度
MAX_PASSWORD_LENGTH = 1000  # 密码最大长度
MAX_TAG_LENGTH = 200  # 标签最大长度
MAX_UA_LENGTH = 2000  # User-Agent最大长度
MAX_PARAMS_COUNT = 100  # 参数字典最大键值对数量
# 用户名格式验证：只允许字母、数字、下划线、连字符、点和@符号
USERNAME_PATTERN = re.compile(
    r'^[a-zA-Z0-9_\-\.@]+$') if 're' in dir() else None


def _buffer_log(level, message):
    """
    暂存日志到缓冲区，同时打印到控制台。
    """
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            _sys = __import__("sys")
            output_encoding = getattr(getattr(_sys, "stdout", None), "encoding", None) or "utf-8"
            safe_message = str(message).encode(output_encoding, errors="replace").decode(
                output_encoding, errors="replace"
            )
            print(safe_message)
        except Exception:
            print(str(message).encode("ascii", errors="replace").decode("ascii"))
    _log_buffer.append((level, message))












def _apply_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _is_frontend_js_hardening_enabled():
    return bool(ENABLE_FRONTEND_JS_ANTI_DEBUG)


def _is_javascript_asset_name(filename):
    normalized = str(filename or "").split("?", 1)[0].lower()
    return normalized.endswith((".js", ".mjs", ".cjs"))


def _is_javascript_content_type(content_type):
    normalized = str(content_type or "").split(";", 1)[0].strip().lower()
    return normalized in {
        "application/javascript",
        "text/javascript",
        "application/x-javascript",
        "application/ecmascript",
        "text/ecmascript",
    } or normalized.endswith("+javascript")


def _make_frontend_javascript_response(
    content,
    status=200,
    cache_control=None,
    no_cache=False,
    headers=None,
):
    body = _harden_frontend_javascript_for_response(content)
    response = make_response(body, status)
    response.mimetype = "application/javascript"
    if _is_frontend_js_hardening_enabled():
        response.headers["X-JS-Hardened"] = "1"
        response.headers["X-SourceMap"] = "stripped"
    if cache_control:
        response.headers["Cache-Control"] = cache_control
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    if no_cache:
        return _apply_no_cache_headers(response)
    return response


def _harden_frontend_javascript_response_if_needed(response):
    if not _is_frontend_js_hardening_enabled():
        return response
    if response.headers.get("X-JS-Hardened") == "1":
        return response
    if not _is_javascript_content_type(response.headers.get("Content-Type", "")):
        return response
    try:
        response.direct_passthrough = False
        response.set_data(_harden_frontend_javascript_for_response(response.get_data()))
        response.headers["X-JS-Hardened"] = "1"
        response.headers["X-SourceMap"] = "stripped"
    except Exception as exc:
        logging.error(f"[JS加固] after_request 处理失败: {exc}")
    return response


def _resolve_frontend_static_file(root_dir, filename):
    root_path = os.path.abspath(root_dir)
    candidate_path = os.path.abspath(os.path.join(root_path, str(filename or "")))
    try:
        if os.path.commonpath([root_path, candidate_path]) != root_path:
            return None
    except ValueError:
        return None
    if not os.path.isfile(candidate_path):
        return None
    return candidate_path


def _send_frontend_static_file(
    root_dir,
    filename,
    cache_control=None,
    no_cache=False,
    headers=None,
):
    if _is_frontend_js_hardening_enabled() and _is_javascript_asset_name(filename):
        file_path = _resolve_frontend_static_file(root_dir, filename)
        if not file_path:
            return jsonify({"success": False, "message": "File not found"}), 404
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return _make_frontend_javascript_response(
                    file.read(),
                    cache_control=cache_control,
                    no_cache=no_cache,
                    headers=headers,
                )
        except Exception as exc:
            logging.error(f"[JS加固] 读取前端脚本失败: {exc}")
            return jsonify({"success": False, "message": "File not found"}), 404
    response = send_from_directory(root_dir, filename)
    if cache_control:
        response.headers["Cache-Control"] = cache_control
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    if no_cache:
        return _apply_no_cache_headers(response)
    return response


def _redact_sensitive_log_text(value):
    """移除文本中以键值形式出现的凭据、令牌和其他认证材料。"""
    text = str(value or "")
    if not text:
        return text
    text = re.sub(
        r"(?i)(['\"]?\b("
        r"api[_-]?key|map[_-]?key|js[_-]?key|amap[_-]?key|"
        r"tencent[_-]?map[_-]?key|tianditu[_-]?token|baidu[_-]?ak|"
        r"token|password|secret|private[_-]?key|access[_-]?key|"
        r"authorization|cookie|captcha(?:[_-]?id)?|sms[_-]?code|"
        r"two[_-]?fa[_-]?code|verification[_-]?code|auth[_-]?code|"
        r"refresh[_-]?token|csrf[_-]?token|session[_-]?(?:id|uuid)|"
        r"x-session-id|shiro[_-]?cookie|sub[_-]?openid|sub[_-]?appid|"
        r"signature|merchant[_-]?key|"
        r"app[_-]?secret|client[_-]?secret|pay[_-]?url|payment[_-]?url|"
        r"return[_-]?url|notify[_-]?url|request[_-]?url"
        r")['\"]?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^,\s;&}]+)",
        r"\1<redacted>",
        text,
    )
    return re.sub(
        r"(?i)([?&](?:api[_-]?key|key|token|password|secret|"
        r"authorization|cookie|captcha(?:[_-]?id)?|sms[_-]?code|"
        r"verification[_-]?code|auth[_-]?code|openid|signature|sign|p)="
        r")[^&#\s]+",
        r"\1<redacted>",
        text,
    )


def _redact_sensitive_log_value(value):
    """递归移除日志中的凭据、令牌和其他认证材料。"""
    sensitive_fragments = (
        "api_key",
        "apikey",
        "map_key",
        "js_key",
        "token",
        "password",
        "secret",
        "private_key",
        "access_key",
        "authorization",
        "cookie",
        "shirocookie",
        "captcha",
        "sms_code",
        "two_fa_code",
        "verification_code",
        "auth_code",
        "refresh_token",
        "csrf_token",
        "session_id",
        "session_uuid",
        "sub_openid",
        "sub_appid",
        "signature",
        "sign",
        "pay_url",
        "payment_url",
        "pay_info",
        "payment_info",
        "return_url",
        "request_url",
        "notify_url",
        "signed_params",
        "refund_result",
        "platform_data",
        "platform_order",
        "order_data",
        "api_response",
        "query_result",
        "notify_params",
        "openid",
        "appid",
    )

    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip().lower().replace("-", "_")
            if any(fragment in normalized_key for fragment in sensitive_fragments):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_sensitive_log_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_log_value(item) for item in value)
    if isinstance(value, str):
        return _redact_sensitive_log_text(value)
    return value


def _install_amap_dialog_guard(page, guard_label="AMap"):
    """在 AMap 相关加载阶段自动拦截原生对话框，避免浏览器执行被阻塞。"""
    try:
        def _handle_dialog(dialog):
            try:
                logging.warning(
                    f"[{guard_label}] 拦截原生弹窗 type={getattr(dialog, 'type', 'unknown')} message={getattr(dialog, 'message', '')}"
                )
                dialog.dismiss()
            except Exception as dialog_error:
                logging.debug(f"[{guard_label}] dismiss dialog failed: {dialog_error}")

        page.on("dialog", _handle_dialog)
    except Exception as e:
        logging.debug(f"[{guard_label}] install dialog guard failed: {e}")


MAP_PROVIDER_DISPLAY_NAMES = {
    "amap": "高德地图",
    "tencent": "腾讯地图",
    "tianditu": "天地图",
    "baidu": "百度地图",
}

MAP_PROVIDER_KEY_FIELDS = {
    "amap": "js_key",
    "tencent": "map_key",
    "tianditu": "token",
    "baidu": "ak",
}

MAP_KEY_RUNTIME_SCRIPT_NAME = "map_key_runtime.js"
MAP_KEY_RUNTIME_NAMESPACE = "__MAP_KEY_RUNTIME__"
MAP_KEY_RUNTIME_TEMPLATE = r"""
(function (globalScope) {
  "use strict";

  const runtimeVersion = __MAP_KEY_RUNTIME_VERSION__;
  const runtimeNamespace = "__MAP_KEY_RUNTIME_NAMESPACE__";
  const decryptEndpoint = "/api/map_provider_keys/decrypt";
  let clientKeyPairPromise = null;

  function getSessionId() {
    try {
      const sessionStorageValue = globalScope.sessionStorage
        ? globalScope.sessionStorage.getItem("session_uuid")
        : "";
      if (sessionStorageValue) return sessionStorageValue;
    } catch (error) {
      // Ignore restricted storage; path fallback below still binds ordinary UI sessions.
    }
    const pathname = globalScope.location && globalScope.location.pathname
      ? String(globalScope.location.pathname)
      : "";
    const match = pathname.match(/\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i);
    return match ? match[1] : "";
  }

  function base64ToBytes(base64Text) {
    const binaryText = atob(base64Text);
    const bytes = new Uint8Array(binaryText.length);
    for (let i = 0; i < binaryText.length; i += 1) {
      bytes[i] = binaryText.charCodeAt(i);
    }
    return bytes;
  }

  function assertDebugAllowed() {
    if (globalScope.__FRONTEND_JS_HOOK_BLOCKED__) {
      clientKeyPairPromise = null;
      throw new Error("地图密钥运行时已锁定");
    }
  }

  async function getClientKeyPair() {
    if (!clientKeyPairPromise) {
      clientKeyPairPromise = crypto.subtle.generateKey(
        {
          name: "RSA-OAEP",
          modulusLength: 2048,
          publicExponent: new Uint8Array([1, 0, 1]),
          hash: "SHA-256",
        },
        false,
        ["encrypt", "decrypt"]
      );
    }
    return clientKeyPairPromise;
  }

  async function decryptMapProviderKeys(bundle, explicitSessionId) {
    assertDebugAllowed();
    const clientKeyPair = await getClientKeyPair();
    const clientPublicKey = await crypto.subtle.exportKey(
      "jwk",
      clientKeyPair.publicKey
    );
    const headers = { "Content-Type": "application/json" };
    const sessionId = explicitSessionId || getSessionId();
    if (sessionId) headers["X-Session-ID"] = sessionId;
    const endpointUrl = runtimeVersion
      ? decryptEndpoint + "?v=" + encodeURIComponent(runtimeVersion)
      : decryptEndpoint;
    const response = await fetch(endpointUrl, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers,
      body: JSON.stringify({
        runtime_version: runtimeVersion,
        bundle: bundle || {},
        client_public_key: clientPublicKey,
      }),
    });
    if (!response.ok) {
      throw new Error("地图密钥解密请求失败");
    }
    const payload = await response.json();
    if (!payload || payload.success === false) {
      throw new Error((payload && payload.message) || "地图密钥解密失败");
    }
    assertDebugAllowed();
    const encryptedPayload = payload.encrypted_payload || {};
    const wrappedKeyBuffer = await crypto.subtle.decrypt(
      { name: "RSA-OAEP" },
      clientKeyPair.privateKey,
      base64ToBytes(encryptedPayload.encrypted_key || "")
    );
    const aesKey = await crypto.subtle.importKey(
      "raw",
      wrappedKeyBuffer,
      { name: "AES-GCM" },
      false,
      ["decrypt"]
    );
    const decryptedBuffer = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: base64ToBytes(encryptedPayload.iv || ""),
      },
      aesKey,
      base64ToBytes(encryptedPayload.ciphertext || "")
    );
    const decryptedPayload = JSON.parse(new TextDecoder().decode(decryptedBuffer));
    return decryptedPayload.providers || {};
  }

  globalScope[runtimeNamespace] = Object.freeze({
    version: runtimeVersion,
    decryptMapProviderKeys,
  });
})(window);
"""
map_key_runtime_lock = None
map_key_runtime_cache = {}
map_key_runtime_session_contexts = {}
map_key_runtime_session_users = {}
map_key_runtime_user_contexts = {}
map_key_runtime_contexts_by_version = {}



def _get_map_key_runtime_lock():
    global map_key_runtime_lock
    if map_key_runtime_lock is None:
        map_key_runtime_lock = threading.Lock()
    return map_key_runtime_lock


def _normalize_map_provider(provider):
    normalized = str(provider or "").strip().lower()
    if normalized in MAP_PROVIDER_DISPLAY_NAMES:
        return normalized
    return "amap"



def _get_active_map_provider(config=None):
    runtime_config = config or _read_config_ini(CONFIG_FILE)
    configured_provider = runtime_config.get("Map", "provider", fallback="amap")
    return _normalize_map_provider(configured_provider)



def _get_map_provider_runtime_config(config=None, provider=None):
    runtime_config = config or _read_config_ini(CONFIG_FILE)
    provider = _normalize_map_provider(provider or _get_active_map_provider(runtime_config))
    providers_config = runtime_config.get("Map", "providers", fallback=None)
    if isinstance(providers_config, dict):
        amap_provider = providers_config.get("amap") or {}
        tencent_provider = providers_config.get("tencent") or {}
        tianditu_provider = providers_config.get("tianditu") or {}
        baidu_provider = providers_config.get("baidu") or {}
    else:
        amap_provider = {}
        tencent_provider = {}
        tianditu_provider = {}
        baidu_provider = {}
    provider_configs = {
        "amap": {
            "provider": "amap",
            "display_name": MAP_PROVIDER_DISPLAY_NAMES["amap"],
            "js_key": str(
                amap_provider.get("js_key")
                or runtime_config.get("Map", "amap_js_key", fallback="")
            ).strip(),
            "coordinate_system": "gcj02",
            "business_coordinate_system": "gcj02",
        },
        "tencent": {
            "provider": "tencent",
            "display_name": MAP_PROVIDER_DISPLAY_NAMES["tencent"],
            "map_key": str(
                tencent_provider.get("map_key")
                or runtime_config.get("Map", "tencent_map_key", fallback="")
            ).strip(),
            "coordinate_system": "gcj02",
            "business_coordinate_system": "gcj02",
        },
        "tianditu": {
            "provider": "tianditu",
            "display_name": MAP_PROVIDER_DISPLAY_NAMES["tianditu"],
            "token": str(
                tianditu_provider.get("token")
                or runtime_config.get("Map", "tianditu_token", fallback="")
            ).strip(),
            "coordinate_system": "wgs84",
            "business_coordinate_system": "gcj02",
        },
        "baidu": {
            "provider": "baidu",
            "display_name": MAP_PROVIDER_DISPLAY_NAMES["baidu"],
            "ak": str(
                baidu_provider.get("ak")
                or runtime_config.get("Map", "baidu_map_ak", fallback="")
            ).strip(),
            "coordinate_system": "bd09",
            "business_coordinate_system": "gcj02",
        },
    }
    return provider_configs[provider]


def _get_map_provider_frontend_config(config=None):
    runtime_config = config or _read_config_ini(CONFIG_FILE)
    map_provider = _get_active_map_provider(runtime_config)
    map_providers = {
        "amap": _get_map_provider_runtime_config(runtime_config, provider="amap"),
        "tencent": _get_map_provider_runtime_config(runtime_config, provider="tencent"),
        "tianditu": _get_map_provider_runtime_config(runtime_config, provider="tianditu"),
        "baidu": _get_map_provider_runtime_config(runtime_config, provider="baidu"),
    }
    return {
        "map_provider": map_provider,
        "map_providers": map_providers,
    }


def _strip_map_provider_secret_fields(map_providers):
    sanitized = {}
    providers = map_providers if isinstance(map_providers, dict) else {}
    for provider, value in providers.items():
        entry = dict(value) if isinstance(value, dict) else {}
        secret_field = MAP_PROVIDER_KEY_FIELDS.get(provider)
        if secret_field:
            entry.pop(secret_field, None)
        sanitized[provider] = entry
    return sanitized


def _load_map_key_runtime_template():
    return MAP_KEY_RUNTIME_TEMPLATE


def _map_key_runtime_unavailable_response():
    response = jsonify({"success": False, "message": "Runtime unavailable"})
    response.status_code = 404
    return _apply_no_cache_headers(response)


def _decrypt_map_provider_keys_for_request():
    runtime_context = _get_map_key_runtime_context_for_request(
        require_session_header=True
    )
    if not runtime_context:
        return _map_key_runtime_unavailable_response()

    payload = request.get_json(silent=True) or {}
    runtime_version = str(
        payload.get("runtime_version") or request.args.get("v", "")
    ).strip()
    if (
        not runtime_version
        or runtime_version
        != str(runtime_context.get("runtime_version") or "").strip()
    ):
        return _map_key_runtime_unavailable_response()

    providers = _decrypt_map_provider_key_bundle(
        payload.get("bundle") or {},
        runtime_context,
    )
    client_public_key = _load_client_public_key(payload.get("client_public_key"))
    if client_public_key is None:
        response = jsonify({"success": False, "message": "Runtime unavailable"})
        response.status_code = 400
        return _apply_no_cache_headers(response)

    encrypted_payload = _encrypt_map_provider_payload_for_client(
        json.dumps({"providers": providers}, ensure_ascii=False),
        client_public_key,
    )
    if not encrypted_payload:
        response = jsonify({"success": False, "message": "地图密钥解密失败"})
        response.status_code = 500
        return _apply_no_cache_headers(response)

    response = jsonify({"success": True, "encrypted_payload": encrypted_payload})
    return _apply_no_cache_headers(response)


def _build_map_provider_key_bundle(
    map_providers,
    provider=None,
    runtime_context=None,
    allow_global_fallback=True,
):
    encrypted_providers = {}
    providers = map_providers if isinstance(map_providers, dict) else {}
    requested_provider = _normalize_map_provider(
        provider or _get_active_map_provider()
    )
    requested_key_field = MAP_PROVIDER_KEY_FIELDS[requested_provider]
    try:
        if runtime_context is None and allow_global_fallback:
            runtime_context = _ensure_map_key_runtime_cache()
        if not isinstance(runtime_context, dict) or not runtime_context.get(
            "public_key"
        ):
            return {
                "provider": requested_provider,
                "runtime_version": "",
                "runtime_script": "",
                "providers": {
                    requested_provider: {
                        "field": requested_key_field,
                        "ciphertext": "",
                    }
                },
                "available": False,
            }
        provider_config = (
            providers.get(requested_provider)
            if isinstance(providers.get(requested_provider), dict)
            else {}
        )
        encrypted_secret = _encrypt_map_provider_secret(
            provider_config.get(requested_key_field, ""),
            runtime_context=runtime_context,
        )
        encrypted_providers[requested_provider] = {
            "field": requested_key_field,
            "ciphertext": encrypted_secret,
        }
        return {
            "provider": requested_provider,
            "runtime_version": runtime_context.get("runtime_version", ""),
            "runtime_script": _get_map_key_runtime_script_url(
                runtime_context.get("runtime_version", "")
            ),
            "providers": encrypted_providers,
            "available": True,
        }
    except Exception as e:
        logging.error(f"[MapKeyRuntime] 生成地图密钥密文失败: {e}")
        encrypted_providers.setdefault(
            requested_provider,
            {"field": requested_key_field, "ciphertext": ""},
        )
        return {
            "provider": requested_provider,
            "runtime_version": "",
            "runtime_script": _get_map_key_runtime_script_url(""),
            "providers": encrypted_providers,
            "available": False,
        }


def _build_public_map_provider_frontend_payload(
    config=None,
    required_provider=None,
    session_id=None,
    username=None,
):
    frontend_config = _get_map_provider_frontend_config(config)
    map_providers = frontend_config.get("map_providers", {})
    provider = _normalize_map_provider(
        required_provider or frontend_config.get("map_provider", "amap")
    )
    runtime_context = None
    normalized_session_id, session_username, session_exists = (
        _get_map_key_runtime_session_identity(session_id)
    )
    if session_exists:
        runtime_context = _get_map_key_runtime_context_for_session(
            session_id=normalized_session_id,
            username=session_username,
        )
    return {
        "map_provider": frontend_config.get("map_provider", "amap"),
        "map_providers": _strip_map_provider_secret_fields(map_providers),
        "map_provider_key_bundle": _build_map_provider_key_bundle(
            map_providers,
            provider=provider,
            runtime_context=runtime_context,
            allow_global_fallback=False,
        ),
    }


def _resolve_amap_js_key(config=None):
    if isinstance(config, (str, bytes, os.PathLike)):
        runtime_config = _read_config_ini(config)
    else:
        runtime_config = config or _read_config_ini(CONFIG_FILE)
    if runtime_config is None:
        runtime_config = _get_default_config()
    providers_config = runtime_config.get("Map", "providers", fallback=None)
    if isinstance(providers_config, str):
        providers_config = JsonConfigAdapter._coerce_map_providers(providers_config)
    if isinstance(providers_config, dict):
        amap_provider = providers_config.get("amap") or {}
        amap_js_key = str(amap_provider.get("js_key", "")).strip()
        if amap_js_key:
            return amap_js_key
    return str(runtime_config.get("Map", "amap_js_key", fallback="")).strip()



def _get_map_provider_plugins(provider, route_mode="walking"):
    provider = _normalize_map_provider(provider)
    normalized_route_mode = str(route_mode or "walking").strip().lower() or "walking"
    if provider == "amap":
        if normalized_route_mode == "driving":
            return ["AMap.Driving"]
        return ["AMap.Walking"]
    return []



def _install_map_runtime_guard(page, provider="amap", guard_label="MapRuntime"):
    provider = _normalize_map_provider(provider)
    try:
        def _handle_page_error(error):
            logging.warning(f"[{guard_label}] pageerror: {error}")

        page.on("pageerror", _handle_page_error)
    except Exception as e:
        logging.debug(f"[{guard_label}] install generic runtime guard failed: {e}")

    if provider == "amap":
        _install_amap_dialog_guard(page, guard_label=guard_label)


MAP_RUNTIME_PATH = "/map-runtime"
MAP_RUNTIME_PAGE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Map Runtime</title>
</head>
<body></body>
</html>
"""


def _render_map_runtime_page():
    return MAP_RUNTIME_PAGE_HTML


def _is_map_runtime_request_authorized(session_id):
    normalized_session_id = normalize_session_uuid(session_id)
    if not normalized_session_id:
        return False

    sessions = globals().get("web_sessions")
    sessions_lock = globals().get("web_sessions_lock")
    if not isinstance(sessions, dict) or sessions_lock is None:
        return False

    with sessions_lock:
        return normalized_session_id in sessions


def _build_map_backend_session_url(app_base_url, session_id):
    normalized_base = str(app_base_url or "").strip()
    if not normalized_base:
        return None
    parsed = urllib.parse.urlparse(normalized_base)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return None
    query = urllib.parse.urlencode(
        {"session_id": str(session_id or "")}
    )
    return urllib.parse.urljoin(
        normalized_base.rstrip("/") + "/",
        f"{MAP_RUNTIME_PATH.lstrip('/')}?{query}",
    )


def _ensure_map_backend_page_origin(page, session_id, app_base_url, guard_label="MapRoutePlanning"):
    session_url = _build_map_backend_session_url(app_base_url, session_id)
    if not session_url:
        return False
    try:
        page.goto(session_url, wait_until="domcontentloaded", timeout=15000)
        return True
    except Exception as e:
        logging.warning(
            f"[{guard_label}] 后端地图页面来源初始化失败: {e}"
        )
        return False



def _plan_route_with_map_provider(waypoints, provider=None, route_mode="walking", runtime_config=None):
    runtime_config = runtime_config or _read_config_ini(CONFIG_FILE)
    provider = _normalize_map_provider(provider or _get_active_map_provider(runtime_config))
    provider_config = _get_map_provider_runtime_config(runtime_config, provider=provider)
    actual_mode = str(route_mode or "walking").strip().lower() or "walking"
    notices = []
    if provider == "tianditu" and route_mode == "walking":
        actual_mode = "driving"
        notices.append("当前地图供应商不支持步行规划，已自动使用驾车规划代替")
    plugins = _get_map_provider_plugins(provider, actual_mode)
    return {
        "provider": provider,
        "provider_config": provider_config,
        "route_mode": route_mode,
        "actual_mode": actual_mode,
        "plugins": plugins,
        "notices": notices,
        "waypoints": waypoints,
    }



def _plan_route_path_with_amap_runtime(session_id, page, waypoints, provider_plan, python_params=None):
    provider_config = provider_plan.get("provider_config") or {}
    api_key = str(provider_config.get("js_key", "")).strip()
    if not api_key:
        return {"error": "未配置高德地图 JS Key"}

    plugins = provider_plan.get("plugins") or ["AMap.Walking"]
    actual_mode = str(provider_plan.get("actual_mode") or "walking").strip().lower() or "walking"
    return chrome_pool.execute_js(
        session_id,
        """
        (async (arg) => {
            const waypointsPy = arg[0] || [];
            const apiKey = arg[1];
            const pythonParams = arg[2] || {};
            const plugins = arg[3] || ["AMap.Walking"];
            const actualMode = arg[4] || "walking";
            const useFallback = pythonParams.api_fallback_line ?? false;
            const maxRetries = pythonParams.api_retries ?? 2;
            const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
            const queueIntervalMs = (pythonParams.api_queue_interval_s ??0.1) * 1000;
            // 每秒请求上限（默认 4 次/秒）：与排队间隔共同决定段间最小间隔，
            // 避免一次性并发发出全部路段请求而触发地图服务限流
            const qpsLimit = Math.max(1, Number(pythonParams.api_qps_limit ?? 4) || 4);
            const qpsIntervalMs = Math.ceil(1000 / qpsLimit);
            const maxFailedWaves =2;
            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

            async function ensureAmapLoader() {
                if (typeof AMapLoader !== 'undefined') {
                    return;
                }
                await new Promise((resolve, reject) => {
                    const existingScript = document.querySelector('script[data-amap-loader="true"]');
                    if (existingScript) {
                        existingScript.remove();
                    }
                    const script = document.createElement('script');
                    script.src = 'https://webapi.amap.com/loader.js';
                    script.async = true;
                    script.defer = true;
                    script.dataset.amapLoader = 'true';
                    script.onload = () => resolve();
                    script.onerror = () => reject(new Error('高德地图加载器加载失败'));
                    document.head.appendChild(script);
                });
            }

            function buildLngLat(point) {
                return new AMap.LngLat(Number(point[0]), Number(point[1]));
            }

            function extractSegmentPath(result) {
                const routes = result && result.routes;
                const firstRoute = Array.isArray(routes) && routes.length > 0 ? routes[0] : null;
                const steps = firstRoute && Array.isArray(firstRoute.steps) ? firstRoute.steps : [];
                const path = [];
                steps.forEach(step => {
                    const stepPath = Array.isArray(step.path) ? step.path : [];
                    stepPath.forEach(pt => path.push({ lng: Number(pt.lng), lat: Number(pt.lat) }));
                });
                return path;
            }

            // 高德通过 result.info 反馈错误；限流时 info 会带「上限/限流/CUQPS」等字样
            function isRateLimited(result, status) {
                const info = String((result && (result.info || result.message)) || status || '');
                return info.indexOf('上限') >= 0
                    || info.indexOf('限流') >= 0
                    || info.indexOf('CUQPS') >= 0
                    || info.indexOf('超出') >= 0;
            }

            async function planPath() {
                if (!Array.isArray(waypointsPy) || waypointsPy.length < 2) {
                    return { error: 'Waypoints must be at least 2.' };
                }

                await ensureAmapLoader();
                try {
                    await AMapLoader.load({ key: apiKey, version: '2.0', plugins });
                } catch (error) {
                    return { error: 'AMapLoader.load failed: ' + (error ? error.message : 'Unknown error') };
                }

                const serviceName = actualMode === 'driving' ? 'Driving' : 'Walking';
                const ServiceCtor = actualMode === 'driving' ? AMap.Driving : AMap.Walking;
                if (typeof ServiceCtor === 'undefined') {
                    return { error: `AMap.${serviceName} plugin failed to load` };
                }

                const service = new ServiceCtor({ map: null, panel: '', hideMarkers: true });
                const waypoints = waypointsPy.map(buildLngLat);
                const allPath = [];

                const searchSegment = (start, end) => new Promise((resolve) => {
                    const attempts = { count: 0 };
                    const runOnce = () => {
                        attempts.count += 1;
                        let settled = false;
                        const timeoutId = window.setTimeout(() => {
                            if (settled) {
                                return;
                            }
                            settled = true;
                            resolve({ error: '地图路线服务请求超时' });
                        }, 15000);

                        service.search(start, end, (status, result) => {
                            if (settled) {
                                return;
                            }
                            settled = true;
                            window.clearTimeout(timeoutId);
                            if (status === 'complete') {
                                const segmentPath = extractSegmentPath(result);
                                if (segmentPath.length > 0) {
                                    resolve({ path: segmentPath });
                                    return;
                                }
                            }
                            const errorInfo = result && result.info ? result.info : status || 'Unknown error';
                            if (isRateLimited(result, status) && attempts.count <= 4) {
                                // 限流退避：标记 rateLimited，避免被当成「该段无路线」
                                const backoff = Math.min(5000, 400 * Math.pow(2, attempts.count));
                                window.setTimeout(runOnce, backoff + Math.random() * 200);
                                return;
                            }
                            resolve({
                                error: 'Path planning failed: ' + errorInfo,
                                rateLimited: isRateLimited(result, status),
                            });
                        });
                    };
                    runOnce();
                });

                const segmentCount = waypoints.length - 1;
                const segmentPaths = Array(segmentCount).fill(null);
                const segmentErrors = Array(segmentCount).fill(null);
                const pendingIndexes = Array.from({ length: segmentCount }, (_, index) => index);
                const segmentAttempts = Array(segmentCount).fill(0);
                let consecutiveFailedWaves =0;

                while (pendingIndexes.length >0) {
                    const waveIndexes = pendingIndexes.slice();
                    pendingIndexes.length = 0;
                    const waveResults = await Promise.all(waveIndexes.map(async (segmentIndex, order) => {
                        // 节流：同时受排队间隔与每秒请求上限约束，避免并发触发地图服务限流
                        await sleep(Math.max(queueIntervalMs * order, qpsIntervalMs * order));
                        const result = await searchSegment(waypoints[segmentIndex], waypoints[segmentIndex + 1]);
                        return { segmentIndex, result };
                    }));
                    let waveSuccessCount = 0;
                    let waveRateLimited = 0;
                    waveResults.forEach(({ segmentIndex, result }) => {
                        if (result && Array.isArray(result.path) && result.path.length > 0) {
                            segmentPaths[segmentIndex] = result.path;
                            waveSuccessCount += 1;
                            return;
                        }
                        segmentErrors[segmentIndex] = result && result.error ? result.error : 'Unknown error';
                        if (result && result.rateLimited) {
                            // 限流不代表「该段无路线」：不消耗重试预算，退避后重排
                            waveRateLimited += 1;
                        } else {
                            segmentAttempts[segmentIndex] += 1;
                        }
                        if (segmentAttempts[segmentIndex] < maxRetries + 1) {
                            pendingIndexes.push(segmentIndex);
                        }
                    });
                    if (waveSuccessCount ===0) {
                        if (waveRateLimited > 0) {
                            // 整波被限流：退避等待，不累计失败波次
                            await sleep(Math.min(5000, 600 * waveRateLimited));
                        } else {
                            consecutiveFailedWaves += 1;
                            if (consecutiveFailedWaves >= maxFailedWaves) {
                                break;
                            }
                        }
                    } else {
                        consecutiveFailedWaves =0;
                    }
                    if (pendingIndexes.length >0) {
                        await sleep(retryDelayMs);
                    }
                }
                for (let i = 0; i < segmentCount; i += 1) {
                    const segmentPath = segmentPaths[i];
                    const realStart = waypoints[i];
                    const realEnd = waypoints[i + 1];
                    if (!segmentPath) {
                        if (useFallback) {
                            const fallbackPath = [
                                { lng: Number(realStart.lng), lat: Number(realStart.lat) },
                                { lng: Number(realEnd.lng), lat: Number(realEnd.lat) },
                            ];
                            allPath.push(...(i > 0 ? fallbackPath.slice(1) : fallbackPath));
                            continue;
                        }
                        return { error: `Segment ${i + 1} failed after ${maxFailedWaves} failed waves: ${segmentErrors[i] || 'Unknown error'}` };
                    }
                    if (i > 0) {
                        allPath.push(...segmentPath.slice(1));
                    } else {
                        allPath.push(...segmentPath);
                    }
                }

                return { path: allPath };
            }

            return await planPath();
        })
        """,
        waypoints,
        api_key,
        python_params or {},
        plugins,
        actual_mode,
    )



def _plan_route_path_with_tencent_runtime(session_id, page, waypoints, provider_plan, python_params=None):
    provider_config = provider_plan.get("provider_config") or {}
    map_key = str(provider_config.get("map_key", "")).strip()
    if not map_key:
        return {"error": "未配置腾讯地图 Key"}

    actual_mode = str(provider_plan.get("actual_mode") or "walking").strip().lower() or "walking"
    return chrome_pool.execute_js(
        session_id,
        """
        (async (arg) => {
            const waypointsPy = arg[0] || [];
            const mapKey = arg[1];
            const pythonParams = arg[2] || {};
            const actualMode = arg[3] || 'walking';
            const routeType = actualMode === 'driving' ? 'driving' : 'walking';
            const useFallback = pythonParams.api_fallback_line ?? false;
            const maxRetries = pythonParams.api_retries ?? 2;
            const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
            const queueIntervalMs = (pythonParams.api_queue_interval_s ??0.1) * 1000;
            // 每秒请求上限（默认 4 次/秒）：与排队间隔共同决定段间最小间隔，
            // 避免一次性并发发出全部路段请求而触发地图服务限流
            const qpsLimit = Math.max(1, Number(pythonParams.api_qps_limit ?? 4) || 4);
            const qpsIntervalMs = Math.ceil(1000 / qpsLimit);
            const maxFailedWaves =2;
            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
            let jsonpRequestId = 0;

            function buildRouteUrl(startCoord, endCoord) {
                return `https://apis.map.qq.com/ws/direction/v1/${encodeURIComponent(routeType)}/?from=${encodeURIComponent(`${startCoord.lat},${startCoord.lng}`)}&to=${encodeURIComponent(`${endCoord.lat},${endCoord.lng}`)}&output=jsonp&key=${encodeURIComponent(mapKey)}`;
            }

            function requestJsonp(url) {
                return new Promise((resolve, reject) => {
                    const callbackName = `__qqRouteCallback_${Date.now()}_${++jsonpRequestId}`;
                    const requestUrl = url.includes('?') ? `${url}&callback=${encodeURIComponent(callbackName)}` : `${url}?callback=${encodeURIComponent(callbackName)}`;
                    const script = document.createElement('script');
                    let settled = false;
                    let timeoutId = null;

                    function cleanup() {
                        if (timeoutId) {
                            window.clearTimeout(timeoutId);
                        }
                        if (script.parentNode) {
                            script.parentNode.removeChild(script);
                        }
                        try {
                            delete window[callbackName];
                        } catch (error) {
                            window[callbackName] = undefined;
                        }
                    }

                    window[callbackName] = function (data) {
                        if (settled) {
                            return;
                        }
                        settled = true;
                        cleanup();
                        resolve(data);
                    };

                    script.src = requestUrl;
                    script.async = true;
                    script.onerror = () => {
                        if (settled) {
                            return;
                        }
                        settled = true;
                        cleanup();
                        reject(new Error('腾讯路线服务 JSONP 加载失败'));
                    };

                    timeoutId = window.setTimeout(() => {
                        if (settled) {
                            return;
                        }
                        settled = true;
                        cleanup();
                        reject(new Error('腾讯路线服务 JSONP 请求超时'));
                    }, 15000);

                    document.head.appendChild(script);
                });
            }

            function decodePolyline(polyline) {
                if (!Array.isArray(polyline) || polyline.length < 2) {
                    return [];
                }
                // 防御式校验：腾讯返回的是一维数组，长度必须为偶数，
                // 且每项都要能转成有限数值，否则直接判为无效（避免产生畸形点）
                if (polyline.length % 2 !== 0) {
                    return [];
                }
                const coors = polyline.slice();
                for (let i = 0; i < coors.length; i += 1) {
                    const value = Number(coors[i]);
                    if (!Number.isFinite(value)) {
                        return [];
                    }
                    coors[i] = value;
                }
                for (let i = 2; i < coors.length; i += 1) {
                    coors[i] = Number(coors[i - 2]) + Number(coors[i]) / 1000000;
                }
                const points = [];
                for (let i = 0; i < coors.length; i += 2) {
                    const lat = Number(coors[i]);
                    const lng = Number(coors[i + 1]);
                    if (Number.isFinite(lat) && Number.isFinite(lng)) {
                        points.push({ lng, lat });
                    }
                }
                return points;
            }

            function extractRoutePathPoints(routeResponse) {
                // 防御式解析：限流等异常响应不带 result 字段，
                // 直接取 routes[0] 会抛 TypeError 并让整段规划失败
                const result = routeResponse && routeResponse.result;
                const routes = result && result.routes;
                const firstRoute = Array.isArray(routes) && routes.length > 0 ? routes[0] : null;
                if (!firstRoute) {
                    return null;
                }
                const polyline = Array.isArray(firstRoute.polyline) ? firstRoute.polyline : null;
                return decodePolyline(polyline);
            }

            // 地图服务的限流响应（腾讯 status=120 每秒请求量已达上限）
            function isRateLimited(data) {
                if (!data || typeof data !== 'object') {
                    return false;
                }
                if (Number(data.status) === 120) {
                    return true;
                }
                const message = String(data.message || '');
                return message.indexOf('上限') >= 0 || message.indexOf('限流') >= 0;
            }

            async function searchSegment(startCoord, endCoord) {
                let rateLimitHits = 0;
                while (true) {
                    const data = await requestJsonp(buildRouteUrl(startCoord, endCoord));
                    if (!data || typeof data !== 'object') {
                        return { error: '路线服务未返回有效数据。' };
                    }
                    if (isRateLimited(data)) {
                        rateLimitHits += 1;
                        if (rateLimitHits > 4) {
                            return { error: data.message || '路线服务限流', rateLimited: true };
                        }
                        // 限流退避：指数增长并加入抖动，避免同步重试再次撞上限
                        await sleep(Math.min(5000, 400 * Math.pow(2, rateLimitHits)) + Math.random() * 200);
                        continue;
                    }
                    if (data.status !== 0) {
                        return { error: data.message || `路线服务返回状态异常：${data.status}` };
                    }
                    const pathPoints = extractRoutePathPoints(data);
                    if (pathPoints === null) {
                        return { error: '路线服务响应缺少 result.routes。' };
                    }
                    if (pathPoints.length < 2) {
                        return { error: '路线服务未返回可绘制的有效路径点。' };
                    }
                    return { path: pathPoints };
                }
            }

            if (!Array.isArray(waypointsPy) || waypointsPy.length < 2) {
                return { error: 'Waypoints must be at least 2.' };
            }

            const waypoints = waypointsPy.map(point => ({ lng: Number(point[0]), lat: Number(point[1]) }));
            const allPath = [];

            const segmentCount = waypoints.length - 1;
            const segmentPaths = Array(segmentCount).fill(null);
            const segmentErrors = Array(segmentCount).fill(null);
            const pendingIndexes = Array.from({ length: segmentCount }, (_, index) => index);
            const segmentAttempts = Array(segmentCount).fill(0);
            let consecutiveFailedWaves =0;

            while (pendingIndexes.length >0) {
                const waveIndexes = pendingIndexes.slice();
                pendingIndexes.length = 0;
                const waveResults = await Promise.all(waveIndexes.map(async (segmentIndex, order) => {
                    // 节流：同时受排队间隔与每秒请求上限约束，避免并发触发地图服务限流
                    await sleep(Math.max(queueIntervalMs * order, qpsIntervalMs * order));
                    const result = await searchSegment(waypoints[segmentIndex], waypoints[segmentIndex + 1]);
                    return { segmentIndex, result };
                }));
                let waveSuccessCount = 0;
                let waveRateLimited = 0;
                waveResults.forEach(({ segmentIndex, result }) => {
                    if (result && Array.isArray(result.path) && result.path.length > 0) {
                        segmentPaths[segmentIndex] = result.path;
                        waveSuccessCount += 1;
                        return;
                    }
                    segmentErrors[segmentIndex] = result && result.error ? result.error : 'Unknown error';
                    if (result && result.rateLimited) {
                        // 限流不代表「该段无路线」：不消耗重试预算，退避后重排
                        waveRateLimited += 1;
                    } else {
                        segmentAttempts[segmentIndex] += 1;
                    }
                    if (segmentAttempts[segmentIndex] < maxRetries + 1) {
                        pendingIndexes.push(segmentIndex);
                    }
                });
                if (waveSuccessCount ===0) {
                    if (waveRateLimited > 0) {
                        // 整波被限流：退避等待，不累计失败波次
                        await sleep(Math.min(5000, 600 * waveRateLimited));
                    } else {
                        consecutiveFailedWaves += 1;
                        if (consecutiveFailedWaves >= maxFailedWaves) {
                            break;
                        }
                    }
                } else {
                    consecutiveFailedWaves =0;
                }
                if (pendingIndexes.length >0) {
                    await sleep(retryDelayMs);
                }
            }
            for (let i = 0; i < segmentCount; i += 1) {
                const segmentPath = segmentPaths[i];
                const realStart = waypoints[i];
                const realEnd = waypoints[i + 1];
                if (!segmentPath) {
                    if (useFallback) {
                        const fallbackPath = [
                            { lng: realStart.lng, lat: realStart.lat },
                            { lng: realEnd.lng, lat: realEnd.lat },
                        ];
                        allPath.push(...(i > 0 ? fallbackPath.slice(1) : fallbackPath));
                        continue;
                    }
                    return { error: `Segment ${i + 1} failed after ${maxFailedWaves} failed waves: ${segmentErrors[i] || 'Unknown error'}` };
                }
                if (i > 0) {
                    allPath.push(...segmentPath.slice(1));
                } else {
                    allPath.push(...segmentPath);
                }
            }

            return { path: allPath };
        })
        """,
        waypoints,
        map_key,
        python_params or {},
        actual_mode,
    )



def _plan_route_path_with_tianditu_runtime(session_id, page, waypoints, provider_plan, python_params=None):
    provider_config = provider_plan.get("provider_config") or {}
    token = str(provider_config.get("token", "")).strip()
    if not token:
        return {"error": "未配置天地图 Token"}

    actual_mode = str(provider_plan.get("actual_mode") or "driving").strip().lower() or "driving"
    return chrome_pool.execute_js(
        session_id,
        r"""
        (async (arg) => {
            const waypointsPy = arg[0] || [];
            const token = arg[1];
            const pythonParams = arg[2] || {};
            const actualMode = arg[3] || 'driving';
            const useFallback = pythonParams.api_fallback_line ?? false;
            const maxRetries = pythonParams.api_retries ?? 2;
            const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
            const queueIntervalMs = (pythonParams.api_queue_interval_s ??0.1) * 1000;
            // 每秒请求上限（默认 4 次/秒）：与排队间隔共同决定段间最小间隔，
            // 避免一次性并发发出全部路段请求而触发地图服务限流
            const qpsLimit = Math.max(1, Number(pythonParams.api_qps_limit ?? 4) || 4);
            const qpsIntervalMs = Math.ceil(1000 / qpsLimit);
            const maxFailedWaves =2;
            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
            const GCJ_PI = Math.PI;
            const GCJ_A = 6378245.0;
            const GCJ_EE = 0.00669342162296594323;

            function isOutOfChina(lng, lat) {
                return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
            }

            function transformLat(x, y) {
                let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
                ret += (20.0 * Math.sin(6.0 * x * GCJ_PI) + 20.0 * Math.sin(2.0 * x * GCJ_PI)) * 2.0 / 3.0;
                ret += (20.0 * Math.sin(y * GCJ_PI) + 40.0 * Math.sin(y / 3.0 * GCJ_PI)) * 2.0 / 3.0;
                ret += (160.0 * Math.sin(y / 12.0 * GCJ_PI) + 320 * Math.sin(y * GCJ_PI / 30.0)) * 2.0 / 3.0;
                return ret;
            }

            function transformLng(x, y) {
                let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
                ret += (20.0 * Math.sin(6.0 * x * GCJ_PI) + 20.0 * Math.sin(2.0 * x * GCJ_PI)) * 2.0 / 3.0;
                ret += (20.0 * Math.sin(x * GCJ_PI) + 40.0 * Math.sin(x / 3.0 * GCJ_PI)) * 2.0 / 3.0;
                ret += (150.0 * Math.sin(x / 12.0 * GCJ_PI) + 300.0 * Math.sin(x / 30.0 * GCJ_PI)) * 2.0 / 3.0;
                return ret;
            }

            function tdtCoordinateToGcj02(coord) {
                const lng = Number(coord && coord.lng);
                const lat = Number(coord && coord.lat);
                if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                    throw new Error('地图工作坐标无效，无法转换为高德坐标。');
                }
                if (isOutOfChina(lng, lat)) {
                    return { lng, lat };
                }
                let dLat = transformLat(lng - 105.0, lat - 35.0);
                let dLng = transformLng(lng - 105.0, lat - 35.0);
                const radLat = lat / 180.0 * GCJ_PI;
                let magic = Math.sin(radLat);
                magic = 1 - GCJ_EE * magic * magic;
                const sqrtMagic = Math.sqrt(magic);
                dLat = (dLat * 180.0) / ((GCJ_A * (1 - GCJ_EE)) / (magic * sqrtMagic) * GCJ_PI);
                dLng = (dLng * 180.0) / (GCJ_A / sqrtMagic * Math.cos(radLat) * GCJ_PI);
                return { lng: lng + dLng, lat: lat + dLat };
            }

            function gcj02ToWgs84Exact(lng, lat) {
                lng = Number(lng);
                lat = Number(lat);
                if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                    throw new Error('高德坐标无效，无法转换为地图工作坐标。');
                }
                if (isOutOfChina(lng, lat)) {
                    return { lng, lat };
                }
                let minLng = lng - 0.02;
                let maxLng = lng + 0.02;
                let minLat = lat - 0.02;
                let maxLat = lat + 0.02;
                let resultLng = lng;
                let resultLat = lat;
                for (let i = 0; i < 32; i += 1) {
                    resultLng = (minLng + maxLng) / 2;
                    resultLat = (minLat + maxLat) / 2;
                    const converted = tdtCoordinateToGcj02({ lng: resultLng, lat: resultLat });
                    const diffLng = converted.lng - lng;
                    const diffLat = converted.lat - lat;
                    if (Math.abs(diffLng) < 1e-10 && Math.abs(diffLat) < 1e-10) {
                        break;
                    }
                    if (diffLng > 0) {
                        maxLng = resultLng;
                    } else {
                        minLng = resultLng;
                    }
                    if (diffLat > 0) {
                        maxLat = resultLat;
                    } else {
                        minLat = resultLat;
                    }
                }
                return { lng: resultLng, lat: resultLat };
            }

            function gcj02ToTdtCoordinate(coord) {
                const lng = Number(coord && coord.lng);
                const lat = Number(coord && coord.lat);
                if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                    throw new Error('高德坐标无效，无法转换为地图工作坐标。');
                }
                if (isOutOfChina(lng, lat)) {
                    return { lng, lat };
                }
                return gcj02ToWgs84Exact(lng, lat);
            }

            function buildDrivingRouteUrl(startCoord, endCoord) {
                const postStr = {
                    orig: `${startCoord.lng},${startCoord.lat}`,
                    dest: `${endCoord.lng},${endCoord.lat}`,
                    style: '0'
                };
                return `https://api.tianditu.gov.cn/drive?postStr=${encodeURIComponent(JSON.stringify(postStr))}&type=search&tk=${encodeURIComponent(token)}`;
            }

            function extractRoutePathPoints(routeXmlText) {
                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(routeXmlText, 'text/xml');
                const parserError = xmlDoc.querySelector('parsererror');
                if (parserError) {
                    throw new Error('路线服务返回了无法解析的 XML。');
                }
                const resultNode = xmlDoc.querySelector('result');
                if (!resultNode) {
                    throw new Error('路线服务未返回 result 节点。');
                }
                const routeLatLonNode = resultNode.querySelector('routelatlon');
                const rawRoute = routeLatLonNode ? routeLatLonNode.textContent.trim() : '';
                if (!rawRoute) {
                    throw new Error('路线服务未返回可绘制的路径点。');
                }
                const points = rawRoute
                    .split(';')
                    .map(pair => pair.trim())
                    .filter(Boolean)
                    .map(pair => {
                        const match = pair.match(/^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
                        if (!match) {
                            return null;
                        }
                        const lng = Number(match[1]);
                        const lat = Number(match[2]);
                        if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                            return null;
                        }
                        return tdtCoordinateToGcj02({ lng, lat });
                    })
                    .filter(Boolean);
                if (points.length < 2) {
                    throw new Error('路线服务未返回足够的有效路径点。');
                }
                return points;
            }

            // 天地图限流：HTTP 429 或响应体带「上限/限流/超出」等字样
            function isRateLimited(response, bodyText) {
                if (response && response.status === 429) {
                    return true;
                }
                const text = String(bodyText || '');
                return text.indexOf('上限') >= 0
                    || text.indexOf('限流') >= 0
                    || text.indexOf('超出') >= 0
                    || text.indexOf('too many') >= 0;
            }

            async function searchSegment(startCoord, endCoord) {
                const maxRateLimitRetries = 4;
                let rateLimitHits = 0;
                while (true) {
                    const controller = new AbortController();
                    const timeoutId = window.setTimeout(() => {
                        controller.abort();
                    }, 15000);
                    try {
                        const response = await fetch(buildDrivingRouteUrl(startCoord, endCoord), {
                            signal: controller.signal
                        });
                        const bodyText = await response.text();
                        if (!response.ok) {
                            const limited = isRateLimited(response, bodyText);
                            if (limited && rateLimitHits < maxRateLimitRetries) {
                                rateLimitHits += 1;
                                await sleep(Math.min(5000, 400 * Math.pow(2, rateLimitHits)) + Math.random() * 200);
                                continue;
                            }
                            return {
                                error: `路线服务请求失败：HTTP ${response.status}`,
                                rateLimited: limited
                            };
                        }
                        if (isRateLimited(response, bodyText) && rateLimitHits < maxRateLimitRetries) {
                            rateLimitHits += 1;
                            await sleep(Math.min(5000, 400 * Math.pow(2, rateLimitHits)) + Math.random() * 200);
                            continue;
                        }
                        try {
                            return { path: extractRoutePathPoints(bodyText) };
                        } catch (parseError) {
                            return { error: `路线服务返回无效数据：${parseError && parseError.message ? parseError.message : String(parseError)}` };
                        }
                    } catch (error) {
                        if (error && error.name === 'AbortError') {
                            return { error: '地图路线服务请求超时' };
                        }
                        return { error: `路线服务请求失败：${error && error.message ? error.message : String(error)}` };
                    } finally {
                        window.clearTimeout(timeoutId);
                    }
                }
            }

            if (actualMode !== 'driving') {
                return { error: '当前天地图执行器仅支持驾车规划。' };
            }
            if (!Array.isArray(waypointsPy) || waypointsPy.length < 2) {
                return { error: 'Waypoints must be at least 2.' };
            }

            const waypoints = waypointsPy.map(point => gcj02ToTdtCoordinate({ lng: Number(point[0]), lat: Number(point[1]) }));
            const allPath = [];

            const segmentCount = waypoints.length - 1;
            const segmentPaths = Array(segmentCount).fill(null);
            const segmentErrors = Array(segmentCount).fill(null);
            const pendingIndexes = Array.from({ length: segmentCount }, (_, index) => index);
            const segmentAttempts = Array(segmentCount).fill(0);
            let consecutiveFailedWaves =0;

            while (pendingIndexes.length >0) {
                const waveIndexes = pendingIndexes.slice();
                pendingIndexes.length = 0;
                const waveResults = await Promise.all(waveIndexes.map(async (segmentIndex, order) => {
                    // 节流：同时受排队间隔与每秒请求上限约束，避免并发触发地图服务限流
                    await sleep(Math.max(queueIntervalMs * order, qpsIntervalMs * order));
                    const result = await searchSegment(waypoints[segmentIndex], waypoints[segmentIndex + 1]);
                    return { segmentIndex, result };
                }));
                let waveSuccessCount = 0;
                let waveRateLimited = 0;
                waveResults.forEach(({ segmentIndex, result }) => {
                    if (result && Array.isArray(result.path) && result.path.length > 0) {
                        segmentPaths[segmentIndex] = result.path;
                        waveSuccessCount += 1;
                        return;
                    }
                    segmentErrors[segmentIndex] = result && result.error ? result.error : 'Unknown error';
                    if (result && result.rateLimited) {
                        // 限流不代表「该段无路线」：不消耗重试预算，退避后重排
                        waveRateLimited += 1;
                    } else {
                        segmentAttempts[segmentIndex] += 1;
                    }
                    if (segmentAttempts[segmentIndex] < maxRetries + 1) {
                        pendingIndexes.push(segmentIndex);
                    }
                });
                if (waveSuccessCount ===0) {
                    if (waveRateLimited > 0) {
                        // 整波被限流：退避等待，不累计失败波次
                        await sleep(Math.min(5000, 600 * waveRateLimited));
                    } else {
                        consecutiveFailedWaves += 1;
                        if (consecutiveFailedWaves >= maxFailedWaves) {
                            break;
                        }
                    }
                } else {
                    consecutiveFailedWaves =0;
                }
                if (pendingIndexes.length >0) {
                    await sleep(retryDelayMs);
                }
            }
            for (let i = 0; i < segmentCount; i += 1) {
                const segmentPath = segmentPaths[i];
                const realStart = waypoints[i];
                const realEnd = waypoints[i + 1];
                if (!segmentPath) {
                    if (useFallback) {
                        const fallbackPath = [
                            tdtCoordinateToGcj02(realStart),
                            tdtCoordinateToGcj02(realEnd),
                        ];
                        allPath.push(...(i > 0 ? fallbackPath.slice(1) : fallbackPath));
                        continue;
                    }
                    return { error: `Segment ${i + 1} failed after ${maxFailedWaves} failed waves: ${segmentErrors[i] || 'Unknown error'}` };
                }
                if (i > 0) {
                    allPath.push(...segmentPath.slice(1));
                } else {
                    allPath.push(...segmentPath);
                }
            }

            return { path: allPath };
        })
        """,
        waypoints,
        token,
        python_params or {},
        actual_mode,
    )



def _plan_route_path_with_baidu_runtime(session_id, page, waypoints, provider_plan, python_params=None):
    provider_config = provider_plan.get("provider_config") or {}
    ak = str(provider_config.get("ak", "")).strip()
    if not ak:
        return {"error": "未配置百度地图 AK"}

    actual_mode = str(provider_plan.get("actual_mode") or "walking").strip().lower() or "walking"
    return chrome_pool.execute_js(
        session_id,
        """
        (async (arg) => {
            const waypointsPy = arg[0] || [];
            const ak = arg[1];
            const pythonParams = arg[2] || {};
            const actualMode = arg[3] || 'walking';
            const useFallback = pythonParams.api_fallback_line ?? false;
            const maxRetries = pythonParams.api_retries ?? 2;
            const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
            const queueIntervalMs = (pythonParams.api_queue_interval_s ??0.1) * 1000;
            // 每秒请求上限（默认 4 次/秒）：与排队间隔共同决定段间最小间隔，
            // 避免一次性并发发出全部路段请求而触发地图服务限流
            const qpsLimit = Math.max(1, Number(pythonParams.api_qps_limit ?? 4) || 4);
            const qpsIntervalMs = Math.ceil(1000 / qpsLimit);
            const maxFailedWaves =2;
            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

            function gcj02ToBd09(lng, lat) {
                const xPi = Math.PI * 3000.0 / 180.0;
                const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * xPi);
                const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * xPi);
                return {
                    lng: z * Math.cos(theta) + 0.0065,
                    lat: z * Math.sin(theta) + 0.006
                };
            }

            function bd09ToGcj02(lng, lat) {
                const xPi = Math.PI * 3000.0 / 180.0;
                const x = lng - 0.0065;
                const y = lat - 0.006;
                const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * xPi);
                const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * xPi);
                return {
                    lng: z * Math.cos(theta),
                    lat: z * Math.sin(theta)
                };
            }

            async function ensureBaiduMapScript() {
                if (window.BMapGL && typeof window.BMapGL.Map === 'function') {
                    return;
                }
                await new Promise((resolve, reject) => {
                    const existingScript = document.querySelector('script[data-baidu-map-api="true"]');
                    if (existingScript) {
                        existingScript.remove();
                    }
                    const script = document.createElement('script');
                    const callbackName = '__backendBaiduMapApiLoaded';
                    script.src = `https://api.map.baidu.com/api?v=1.0&type=webgl&ak=${encodeURIComponent(ak)}&callback=${callbackName}`;
                    script.async = true;
                    script.defer = true;
                    script.dataset.baiduMapApi = 'true';
                    window[callbackName] = function () {
                        try {
                            delete window[callbackName];
                        } catch (error) {
                            window[callbackName] = undefined;
                        }
                        if (window.BMapGL && typeof window.BMapGL.Map === 'function') {
                            resolve();
                            return;
                        }
                        reject(new Error('百度地图脚本加载完成但运行时不可用，请检查 AK、域名白名单或网络连接。'));
                    };
                    script.onerror = () => reject(new Error('百度地图脚本加载失败，请检查 AK 或网络连接。'));
                    document.head.appendChild(script);
                });
            }

            function ensureMapInstance() {
                let container = document.getElementById('__backend_baidu_route_map__');
                if (!container) {
                    container = document.createElement('div');
                    container.id = '__backend_baidu_route_map__';
                    container.style.cssText = 'width:1px;height:1px;position:fixed;left:-9999px;top:-9999px;opacity:0;pointer-events:none;';
                    document.body.appendChild(container);
                }
                if (!window.__backendBaiduRouteMap) {
                    window.__backendBaiduRouteMap = new BMapGL.Map(container.id);
                    window.__backendBaiduRouteMap.centerAndZoom(new BMapGL.Point(116.404, 39.915), 12);
                }
                return window.__backendBaiduRouteMap;
            }

            function createRouteSearch(routeType, map, resolve) {
                let searchInstance = null;
                const commonOptions = {
                    renderOptions: {
                        map,
                        autoViewport: false,
                        enableDragging: false
                    },
                    onSearchComplete(results) {
                        const status = searchInstance && typeof searchInstance.getStatus === 'function'
                            ? searchInstance.getStatus()
                            : null;
                        try {
                            const firstPlan = results && typeof results.getPlan === 'function' ? results.getPlan(0) : null;
                            if (!firstPlan || typeof firstPlan.getNumRoutes !== 'function') {
                                throw new Error('路线结果中未找到有效方案。');
                            }
                            const routeCount = firstPlan.getNumRoutes();
                            const points = [];
                            for (let i = 0; i < routeCount; i += 1) {
                                const route = firstPlan.getRoute(i);
                                if (!route || typeof route.getPath !== 'function') {
                                    continue;
                                }
                                const path = route.getPath();
                                if (Array.isArray(path)) {
                                    path.forEach(point => {
                                        const converted = bd09ToGcj02(Number(point.lng), Number(point.lat));
                                        points.push({ lng: converted.lng, lat: converted.lat });
                                    });
                                }
                            }
                            if (points.length < 2) {
                                throw new Error('路线结果未返回可绘制的有效路径点。');
                            }
                            resolve({ path: points });
                        } catch (error) {
                            if (status !== null && typeof BMAP_STATUS_SUCCESS !== 'undefined' && status !== BMAP_STATUS_SUCCESS) {
                                resolve({ error: `路线规划失败，状态码：${status}` });
                                return;
                            }
                            resolve({ error: error.message || String(error) });
                        }
                    }
                };

                if (routeType === 'walking') {
                    searchInstance = new BMapGL.WalkingRoute(map, commonOptions);
                } else {
                    searchInstance = new BMapGL.DrivingRoute(map, commonOptions);
                }
                return searchInstance;
            }

            // 百度限流：状态码或错误文案带「上限/限流/超出」等字样
            function isRateLimited(status, message) {
                const text = String(message || '');
                if (text.indexOf('上限') >= 0
                    || text.indexOf('限流') >= 0
                    || text.indexOf('超出') >= 0
                    || text.indexOf('too many') >= 0) {
                    return true;
                }
                return false;
            }

            function searchSegment(startCoord, endCoord, routeType, map) {
                return new Promise((resolve) => {
                    const maxRateLimitRetries = 4;
                    let rateLimitHits = 0;
                    const runOnce = () => {
                        let settled = false;
                        const timeoutId = window.setTimeout(() => {
                            if (settled) {
                                return;
                            }
                            settled = true;
                            resolve({ error: '地图路线服务请求超时' });
                        }, 15000);
                        const searchInstance = createRouteSearch(routeType, map, (result) => {
                            if (settled) {
                                return;
                            }
                            settled = true;
                            window.clearTimeout(timeoutId);
                            if (result && result.error && isRateLimited(null, result.error)
                                && rateLimitHits < maxRateLimitRetries) {
                                // 限流退避：标记 rateLimited，避免被当成「该段无路线」
                                rateLimitHits += 1;
                                window.setTimeout(
                                    runOnce,
                                    Math.min(5000, 400 * Math.pow(2, rateLimitHits)) + Math.random() * 200
                                );
                                return;
                            }
                            if (result && result.error && isRateLimited(null, result.error)) {
                                resolve({ error: result.error, rateLimited: true });
                                return;
                            }
                            resolve(result);
                        });
                        searchInstance.search(startCoord, endCoord);
                    };
                    runOnce();
                });
            }

            if (!Array.isArray(waypointsPy) || waypointsPy.length < 2) {
                return { error: 'Waypoints must be at least 2.' };
            }

            await ensureBaiduMapScript();
            const map = ensureMapInstance();
            const routeType = actualMode === 'driving' ? 'driving' : 'walking';
            const waypoints = waypointsPy.map(point => {
                const converted = gcj02ToBd09(Number(point[0]), Number(point[1]));
                return new BMapGL.Point(converted.lng, converted.lat);
            });
            const allPath = [];

            const segmentCount = waypoints.length - 1;
            const segmentPaths = Array(segmentCount).fill(null);
            const segmentErrors = Array(segmentCount).fill(null);
            const pendingIndexes = Array.from({ length: segmentCount }, (_, index) => index);
            const segmentAttempts = Array(segmentCount).fill(0);
            let consecutiveFailedWaves =0;

            while (pendingIndexes.length >0) {
                const waveIndexes = pendingIndexes.slice();
                pendingIndexes.length = 0;
                const waveResults = await Promise.all(waveIndexes.map(async (segmentIndex, order) => {
                    // 节流：同时受排队间隔与每秒请求上限约束，避免并发触发地图服务限流
                    await sleep(Math.max(queueIntervalMs * order, qpsIntervalMs * order));
                    const result = await searchSegment(waypoints[segmentIndex], waypoints[segmentIndex + 1]);
                    return { segmentIndex, result };
                }));
                let waveSuccessCount = 0;
                let waveRateLimited = 0;
                waveResults.forEach(({ segmentIndex, result }) => {
                    if (result && Array.isArray(result.path) && result.path.length > 0) {
                        segmentPaths[segmentIndex] = result.path;
                        waveSuccessCount += 1;
                        return;
                    }
                    segmentErrors[segmentIndex] = result && result.error ? result.error : 'Unknown error';
                    if (result && result.rateLimited) {
                        // 限流不代表「该段无路线」：不消耗重试预算，退避后重排
                        waveRateLimited += 1;
                    } else {
                        segmentAttempts[segmentIndex] += 1;
                    }
                    if (segmentAttempts[segmentIndex] < maxRetries + 1) {
                        pendingIndexes.push(segmentIndex);
                    }
                });
                if (waveSuccessCount ===0) {
                    if (waveRateLimited > 0) {
                        // 整波被限流：退避等待，不累计失败波次
                        await sleep(Math.min(5000, 600 * waveRateLimited));
                    } else {
                        consecutiveFailedWaves += 1;
                        if (consecutiveFailedWaves >= maxFailedWaves) {
                            break;
                        }
                    }
                } else {
                    consecutiveFailedWaves =0;
                }
                if (pendingIndexes.length >0) {
                    await sleep(retryDelayMs);
                }
            }
            for (let i = 0; i < segmentCount; i += 1) {
                const segmentPath = segmentPaths[i];
                const realStart = waypoints[i];
                const realEnd = waypoints[i + 1];
                if (!segmentPath) {
                    if (useFallback) {
                        const fallbackPath = [
                            bd09ToGcj02(Number(realStart.lng), Number(realStart.lat)),
                            bd09ToGcj02(Number(realEnd.lng), Number(realEnd.lat)),
                        ];
                        allPath.push(...(i > 0 ? fallbackPath.slice(1) : fallbackPath));
                        continue;
                    }
                    return { error: `Segment ${i + 1} failed after ${maxFailedWaves} failed waves: ${segmentErrors[i] || 'Unknown error'}` };
                }
                if (i > 0) {
                    allPath.push(...segmentPath.slice(1));
                } else {
                    allPath.push(...segmentPath);
                }
            }

            return { path: allPath };
        })
        """,
        waypoints,
        ak,
        python_params or {},
        actual_mode,
    )


def _normalize_provider_route_point(point):
    try:
        if isinstance(point, dict):
            lng = float(point.get("lng"))
            lat = float(point.get("lat"))
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            lng = float(point[0])
            lat = float(point[1])
        else:
            return None
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lng) and math.isfinite(lat)):
        return None
    return {"lng": lng, "lat": lat}


def _route_points_are_close(left, right, tolerance=1e-6):
    if not left or not right:
        return False
    return (
        abs(float(left["lng"]) - float(right["lng"])) <= tolerance
        and abs(float(left["lat"]) - float(right["lat"])) <= tolerance
    )


def _route_point_distance_sq(left, right):
    if not left or not right:
        return float("inf")
    return (float(left["lng"]) - float(right["lng"])) ** 2 + (
        float(left["lat"]) - float(right["lat"])
    ) ** 2


def _align_waypoints_to_route(route_points, waypoints):
    """把打卡点按顺序单调对齐到路线点（动态规划，最小化总偏移）。

    返回与 ``waypoints`` 等长的路线索引列表（单调不减），无法对齐时返回 None。
    """
    n = len(route_points)
    m = len(waypoints)
    if n == 0 or m == 0 or m > n:
        return None

    # cost[j][i] = 打卡点 j 对齐到路线点 i 的代价（归一化坐标下的平方距离）
    costs = [
        [
            _route_point_distance_sq(route_points[i], waypoints[j])
            for i in range(n)
        ]
        for j in range(m)
    ]

    # prefix[j][i] = 第 j 个打卡点取路线点 i 时，前 j+1 个打卡点（含 i）的最小累计代价
    prefix = [[0.0] * n for _ in range(m)]
    parent = [[-1] * n for _ in range(m)]
    prefix[0] = list(costs[0])
    for j in range(1, m):
        best = float("inf")
        best_index = -1
        for i in range(n):
            if prefix[j - 1][i] < best:
                best = prefix[j - 1][i]
                best_index = i
            prefix[j][i] = best + costs[j][i]
            parent[j][i] = best_index

    end_index = min(range(n), key=lambda i: prefix[m - 1][i])
    aligned = [0] * m
    aligned[m - 1] = end_index
    for j in range(m - 1, 0, -1):
        aligned[j - 1] = parent[j][aligned[j]]
        if aligned[j - 1] < 0:
            return None
    return aligned


def _complete_route_path_with_waypoint_endpoints(path, waypoints):
    """把地图服务「吸附」后偏掉的打卡点补回规划路径。

    关键约束：**顺序保持的单调对齐**。历史实现在每一轮都从路径末尾做全局
    最近邻匹配，后面的打卡点被依次追加到路径尾部，等于用直线把打卡点串起来
    （实测 115 点主路线被补成 124 点，出现 285m/277m/214m 的直线段）。

    现在的做法：
    1. 先用动态规划把打卡点按顺序单调对齐到路线点（最小化总偏移）；
    2. 对齐误差超过阈值的打卡点，替换其对应的那一段路线点（原地替换，
       不会把打卡点搬到路径末尾，也不会产生跨段的直线）；
    3. 首尾打卡点按同样的阈值在两端补齐。
    """
    if not isinstance(path, list) or not isinstance(waypoints, list) or len(waypoints) < 2:
        return path
    normalized_waypoints = [
        _normalize_provider_route_point(point)
        for point in waypoints
    ]
    normalized_waypoints = [point for point in normalized_waypoints if point]
    if len(normalized_waypoints) < 2:
        return path

    route_points = [_normalize_provider_route_point(point) for point in path]
    route_points = [point for point in route_points if point]
    if not route_points:
        return normalized_waypoints

    # 吸附误差量级：超过该距离才认为打卡点不在规划路径上，需要替换
    snap_tolerance_m = 30.0
    tolerance_sq = snap_tolerance_m * snap_tolerance_m

    def _metric_distance_sq(left, right):
        """按米制换算的平方距离（经度需按纬度做 cos 缩放）。"""
        if not left or not right:
            return float("inf")
        avg_lat = math.radians((float(left["lat"]) + float(right["lat"])) / 2.0)
        dx = (float(left["lng"]) - float(right["lng"])) * math.cos(avg_lat) * 111320.0
        dy = (float(left["lat"]) - float(right["lat"])) * 110540.0
        return dx * dx + dy * dy

    aligned = _align_waypoints_to_route(route_points, normalized_waypoints)
    if aligned is None:
        completed_path = list(route_points)
        first = _normalize_provider_route_point(completed_path[0])
        if not _route_points_are_close(first, normalized_waypoints[0]):
            completed_path.insert(0, normalized_waypoints[0])
        last = _normalize_provider_route_point(completed_path[-1])
        if not _route_points_are_close(last, normalized_waypoints[-1]):
            completed_path.append(normalized_waypoints[-1])
        return completed_path

    replacements = {}
    for waypoint_index, route_index in enumerate(aligned):
        waypoint = normalized_waypoints[waypoint_index]
        if _route_points_are_close(route_points[route_index], waypoint):
            continue
        if _metric_distance_sq(route_points[route_index], waypoint) <= tolerance_sq:
            continue
        replacements.setdefault(route_index, []).append(waypoint)

    completed_path = []
    for index, point in enumerate(route_points):
        completed_path.append(point)
        # 打卡点只做「原地插入」，绝不删除或替换既有路线点，
        # 否则会把真实道路几何删掉、制造跳点
        for waypoint in replacements.get(index, []):
            if not _route_points_are_close(completed_path[-1], waypoint):
                completed_path.append(waypoint)

    start = normalized_waypoints[0]
    if not _route_points_are_close(completed_path[0], start):
        completed_path.insert(0, start)
    end = normalized_waypoints[-1]
    if not _route_points_are_close(completed_path[-1], end):
        completed_path.append(end)

    return completed_path


def _build_multi_account_completion_status(total_tasks, successful_tasks):
    """多账号单个账号的收尾状态文案。

    文案以「状态词 + (成功/总数)」的形式给出，既保留原来一眼可辨的状态词
    （`全部完成` / `全部失败` / `部分成功` / `无任务可执行`，前端按这些词
    着色，见 getMultiAccountStatusClass），又补上数量，避免"全部完成"
    到底是 1 个还是 10 个任务无从判断。
    """
    total_tasks = max(0, int(total_tasks or 0))
    successful_tasks = max(0, min(total_tasks, int(successful_tasks or 0)))
    if total_tasks == 0:
        return "无任务可执行"
    failed_tasks = total_tasks - successful_tasks
    if failed_tasks == 0:
        return f"全部完成 ({successful_tasks}/{total_tasks})"
    if successful_tasks == 0:
        return f"全部失败 (0/{total_tasks})"
    return f"部分成功 ({successful_tasks}/{total_tasks})，{failed_tasks}个任务失败"



def _plan_route_path_with_provider_runtime(
    session_id,
    waypoints,
    python_params=None,
    provider=None,
    runtime_config=None,
    guard_label="MapRoutePlanning",
    app_base_url=None,
):
    runtime_config = runtime_config or _read_config_ini(CONFIG_FILE)
    provider_plan = _plan_route_with_map_provider(
        waypoints,
        provider=provider,
        route_mode="walking",
        runtime_config=runtime_config,
    )
    provider = provider_plan["provider"]

    global chrome_pool
    if not chrome_pool:
        return {
            "error": "Chrome浏览器池不可用，无法进行路径规划。",
            "provider": provider,
            "notices": provider_plan.get("notices", []),
        }

    ctx = chrome_pool.get_context(session_id)
    page = ctx["page"]
    _install_map_runtime_guard(page, provider=provider, guard_label=guard_label)
    if app_base_url and not _ensure_map_backend_page_origin(
        page,
        session_id,
        app_base_url,
        guard_label=guard_label,
    ):
        return {
            "error": "后端地图页面来源初始化失败，无法执行地图路径规划。",
            "provider": provider,
            "provider_plan": provider_plan,
            "notices": provider_plan.get("notices", []),
        }

    if provider == "amap":
        result = _plan_route_path_with_amap_runtime(session_id, page, waypoints, provider_plan, python_params)
    elif provider == "tencent":
        result = _plan_route_path_with_tencent_runtime(session_id, page, waypoints, provider_plan, python_params)
    elif provider == "tianditu":
        result = _plan_route_path_with_tianditu_runtime(session_id, page, waypoints, provider_plan, python_params)
    elif provider == "baidu":
        result = _plan_route_path_with_baidu_runtime(session_id, page, waypoints, provider_plan, python_params)
    else:
        result = {"error": f"不支持的地图供应商: {provider}"}

    if not isinstance(result, dict):
        result = {"error": "路径规划执行器未返回有效结果。"}
    if provider in ("tencent", "tianditu", "baidu") and isinstance(result.get("path"), list):
        result["path"] = _complete_route_path_with_waypoint_endpoints(result["path"], waypoints)
    result["provider"] = provider
    result["provider_plan"] = provider_plan
    result["notices"] = provider_plan.get("notices", [])
    return result








def _should_run_midnight_runtime_maintenance(current_dt=None, config=None):
    now_dt = current_dt or datetime.datetime.now()
    schedule_config = _get_daily_restart_schedule_config(config)
    if not schedule_config["enabled"] or not schedule_config["valid"]:
        return False
    return (
        now_dt.hour == schedule_config["hour"]
        and now_dt.minute == schedule_config["minute"]
    )


























def _flush_all_log_handlers():
    root_logger = logging.getLogger()
    for handler in list(getattr(root_logger, "handlers", [])):
        try:
            handler.flush()
        except Exception:
            continue



def _is_process_running(pid):
    try:
        target_pid = int(pid)
    except (TypeError, ValueError):
        return False

    if target_pid <= 0:
        return False

    try:
        os.kill(target_pid, 0)
    except OSError:
        return False
    except Exception:
        return False
    return True



def _wait_for_process_exit(
    pid,
    timeout_seconds=60,
    poll_interval=0.5,
    is_running_func=None,
    sleep_func=None,
    monotonic_func=None,
):
    check_running = is_running_func or _is_process_running
    do_sleep = sleep_func or time.sleep
    now_monotonic = monotonic_func or time.monotonic
    deadline = now_monotonic() + max(float(timeout_seconds or 0), 0)

    while True:
        if not check_running(pid):
            return True
        if now_monotonic() >= deadline:
            return False
        do_sleep(poll_interval)









def _handle_midnight_runtime_maintenance_tick(last_run_date, now_dt=None, config=None):
    current_dt = now_dt or datetime.datetime.now()
    if not _should_run_midnight_runtime_maintenance(current_dt, config=config):
        return last_run_date, False

    current_date = current_dt.date()
    if current_date == last_run_date:
        return last_run_date, False

    _trigger_daily_full_restart(now_dt=current_dt)
    return current_date, True



def _run_midnight_runtime_maintenance():
    logging.info("[午夜维护] 已切换为每日完全重启编排模式")
    return _trigger_daily_full_restart()



def start_midnight_runtime_maintenance_worker():
    def midnight_runtime_maintenance_worker():
        current_thread = threading.current_thread()
        logging.info(
            f"[午夜维护 Worker] 已在线程中启动: Thread[{current_thread.name}, id={current_thread.ident}]"
        )
        last_run_date = None
        while True:
            try:
                now_dt = datetime.datetime.now()
                last_run_date, _ = _handle_midnight_runtime_maintenance_tick(
                    last_run_date,
                    now_dt=now_dt,
                )
                time.sleep(30)
            except Exception as e:
                logging.error(f"[午夜维护] 后台维护线程异常: {e}", exc_info=True)
                time.sleep(30)

    maintenance_thread = threading.Thread(
        target=midnight_runtime_maintenance_worker,
        daemon=True,
        name="Midnight_Runtime_Maintenance_Worker",
    )
    maintenance_thread.start()
    logging.info(f"[线程创建] 午夜维护线程已启动: {maintenance_thread.name} (id={maintenance_thread.ident})")
    return maintenance_thread


def _is_same_origin_url(candidate_url, base_url):
    try:
        candidate = urllib.parse.urlparse(str(candidate_url or "").strip())
        base = urllib.parse.urlparse(str(base_url or "").strip())
    except Exception:
        return False
    if not candidate.scheme or not candidate.netloc:
        return False
    candidate_port = candidate.port or (443 if candidate.scheme.lower() == "https" else 80)
    base_port = base.port or (443 if base.scheme.lower() == "https" else 80)
    return (
        candidate.scheme.lower(),
        candidate.hostname.lower() if candidate.hostname else "",
        candidate_port,
    ) == (
        base.scheme.lower(),
        base.hostname.lower() if base.hostname else "",
        base_port,
    )


def _normalize_payment_return_url(return_url, app_host, notify_url):
    normalized_return_url = str(return_url or "").strip()
    if not normalized_return_url or normalized_return_url in {
        "null",
        "NULL",
        "None",
        "none",
        "undefined",
        "undefind",
    }:
        return None
    if not _is_same_origin_url(normalized_return_url, app_host):
        logging.warning(
            f"[支付验证] 拒绝跨站 return_url: {normalized_return_url} (app_host={app_host})"
        )
        return None
    return normalized_return_url


def _normalize_sms_signature(signature):
    normalized_signature = str(signature or "").strip()
    if not normalized_signature:
        return ""
    while (
        normalized_signature.startswith("【")
        and normalized_signature.endswith("】")
        and len(normalized_signature) >= 2
    ):
        normalized_signature = normalized_signature[1:-1].strip()
    return f"【{normalized_signature}】" if normalized_signature else ""


def _build_sms_verification_content(signature, template, code, code_expire_minutes):
    normalized_signature = _normalize_sms_signature(signature)
    rendered_template = str(template or "")
    rendered_template = rendered_template.replace("{code}", str(code)).replace(
        "{minutes}", str(code_expire_minutes)
    )
    return f"{normalized_signature}{rendered_template}"


def _get_sms_config_view_data(config):
    return {
        "enable_sms_service": config.getboolean(
            "Features", "enable_sms_service", fallback=False
        ),
        "enable_phone_modification": config.getboolean(
            "Features", "enable_phone_modification", fallback=False
        ),
        "enable_phone_login": config.getboolean(
            "Features", "enable_phone_login", fallback=False
        ),
        "enable_phone_registration_verify": config.getboolean(
            "Features", "enable_phone_registration_verify", fallback=False
        ),
        "username": config.get("SMS_Service_SMSBao", "username", fallback=""),
        "api_key": config.get("SMS_Service_SMSBao", "api_key", fallback=""),
        "signature": _normalize_sms_signature(
            config.get("SMS_Service_SMSBao", "signature", fallback="")
        ),
        "template_register": config.get(
            "SMS_Service_SMSBao", "template_register", fallback=""
        ),
        "code_expire_minutes": config.getint(
            "SMS_Service_SMSBao", "code_expire_minutes", fallback=5
        ),
        "rate_limit_per_account_day": config.getint(
            "SMS_Service_SMSBao", "rate_limit_per_account_day", fallback=10
        ),
        "rate_limit_per_ip_day": config.getint(
            "SMS_Service_SMSBao", "rate_limit_per_ip_day", fallback=20
        ),
        "rate_limit_per_phone_day": config.getint(
            "SMS_Service_SMSBao", "rate_limit_per_phone_day", fallback=5
        ),
    }




def _apply_sms_config_updates(config, data):
    if not config.has_section("Features"):
        config.add_section("Features")
    config.set(
        "Features",
        "enable_sms_service",
        str(data.get("enable_sms_service", False)).lower(),
    )
    config.set(
        "Features",
        "enable_phone_modification",
        str(data.get("enable_phone_modification", False)).lower(),
    )
    config.set(
        "Features",
        "enable_phone_login",
        str(data.get("enable_phone_login", False)).lower(),
    )
    config.set(
        "Features",
        "enable_phone_registration_verify",
        str(data.get("enable_phone_registration_verify", False)).lower(),
    )
    if not config.has_section("SMS_Service_SMSBao"):
        config.add_section("SMS_Service_SMSBao")
    config.set("SMS_Service_SMSBao", "username", data.get("username", ""))
    config.set("SMS_Service_SMSBao", "api_key", data.get("api_key", ""))
    config.set(
        "SMS_Service_SMSBao",
        "signature",
        _normalize_sms_signature(data.get("signature", "")),
    )
    config.set(
        "SMS_Service_SMSBao",
        "template_register",
        data.get("template_register", ""),
    )
    config.set(
        "SMS_Service_SMSBao",
        "code_expire_minutes",
        str(data.get("code_expire_minutes", 5)),
    )
    config.set(
        "SMS_Service_SMSBao",
        "rate_limit_per_account_day",
        str(data.get("rate_limit_per_account_day", 10)),
    )
    config.set(
        "SMS_Service_SMSBao",
        "rate_limit_per_ip_day",
        str(data.get("rate_limit_per_ip_day", 20)),
    )
    config.set(
        "SMS_Service_SMSBao",
        "rate_limit_per_phone_day",
        str(data.get("rate_limit_per_phone_day", 5)),
    )
    return config




SMSBAO_ERROR_MESSAGES = {
    "30": "密码错误",
    "40": "账号不存在",
    "41": "余额不足",
    "42": "账户已过期",
    "43": "IP地址限制",
    "50": "内容含有敏感词",
    "51": "手机号码不正确",
}



def _get_smsbao_error_message(result_code):
    return SMSBAO_ERROR_MESSAGES.get(result_code, f"未知错误(错误码:{result_code})")



def _digits_only(value):
    return re.sub(r"\D", "", str(value or "").strip())



def _normalize_phone(value):
    return _digits_only(value)[:11]



def _normalize_sms_code(value):
    return _digits_only(value)



def get_captcha_provider_config():
    """
    读取验证码提供方配置（本地图片 / 本地行为验证码）。

    返回 dict：
    - provider: "image"（本地图片验证码，默认） | "behavior"
    - behavior_base_url: 本地行为验证码服务根地址（后端代理时使用，浏览器不直接访问）
    - behavior_api_key: X-Captcha-Key 值（可为空）
    - behavior_type: 验证码类型（SLIDER/ROTATE/... 默认 SLIDER）
    """
    provider = "image"
    base_url = ""
    api_key = ""
    ctype = "SLIDER"
    try:
        cfg = _read_config_ini(CONFIG_JSON_FILE)
        if cfg is not None:
            provider = (cfg.get("Captcha", "provider",
                        fallback="image") or "image").strip().lower()
            if provider not in ("image", "behavior"):
                provider = "image"
            base_url = (cfg.get("Captcha", "behavior_base_url",
                        fallback="") or "").strip().rstrip("/")
            api_key = (cfg.get("Captcha", "behavior_api_key", fallback="") or "").strip()
            ctype = (cfg.get("Captcha", "behavior_type",
                     fallback="SLIDER") or "SLIDER").strip() or "SLIDER"
    except Exception as e:
        logging.warning(f"[验证码] 读取验证码提供方配置失败，回退本地图片: {e}")
    return {
        "provider": provider,
        "behavior_base_url": base_url,
        "behavior_api_key": api_key,
        "behavior_type": ctype,
    }


def append_behavior_captcha_history(captcha_id, behavior_type="SLIDER", status="created"):
    """
    记录 captcha-local 生成历史。行为验证码答案和图片不可回溯，只记录 ID、类型和状态。
    """
    if not captcha_id:
        return
    try:
        now_ts = time.time()
        history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
        os.makedirs(history_dir, exist_ok=True)
        date_str = datetime.datetime.fromtimestamp(now_ts).strftime("%Y%m%d")
        history_file = os.path.join(history_dir, f"captcha_history_{date_str}.jsonl")
        try:
            client_ip = request.environ.get("REMOTE_ADDR") or request.remote_addr
            user_agent = request.headers.get("User-Agent", "unknown")
        except Exception:
            client_ip = "unknown"
            user_agent = "unknown"
        history_entry = {
            "captcha_id": str(captcha_id),
            "provider": "behavior",
            "captcha_provider": "behavior",
            "behavior_type": str(behavior_type or "SLIDER"),
            "display_text": "使用验证码服务器",
            "code": "",
            "html": "",
            "client_ip": client_ip,
            "user_agent": user_agent,
            "timestamp": now_ts,
            "timestamp_readable": datetime.datetime.fromtimestamp(now_ts).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "expires_at": now_ts + 120,
            "status": status,
            "verified_at": None,
            "verified_input": None,
        }
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
        logging.debug(
            f"[验证码历史-behavior] 已记录验证码服务器请求: ID={str(captcha_id)[:12]}..."
        )
    except Exception as e:
        logging.error(f"[验证码历史-behavior] 记录历史失败: {e}", exc_info=True)


def update_behavior_captcha_history(captcha_id, passed):
    """
    更新 captcha-local 二次校验结果。不可回溯答案，verified_input 固定显示服务器校验。
    """
    if not captcha_id:
        return
    try:
        history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
        if not os.path.exists(history_dir):
            return
        status = "verified_success" if passed else "verified_failed"
        now_ts = time.time()
        for filename in sorted(os.listdir(history_dir), reverse=True):
            if not filename.endswith(".jsonl"):
                continue
            history_file = os.path.join(history_dir, filename)
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                updated = False
                for index, line in enumerate(lines):
                    try:
                        record = json.loads(line.strip())
                    except Exception:
                        continue
                    if record.get("captcha_id") != captcha_id:
                        continue
                    record["provider"] = "behavior"
                    record["captcha_provider"] = "behavior"
                    record["display_text"] = "使用验证码服务器"
                    record["code"] = ""
                    record["html"] = ""
                    record["status"] = status
                    record["verified_at"] = now_ts
                    record["verified_at_readable"] = datetime.datetime.fromtimestamp(
                        now_ts
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    record["verified_input"] = "验证码服务器二次校验"
                    lines[index] = json.dumps(record, ensure_ascii=False) + "\n"
                    updated = True
                    break
                if updated:
                    with open(history_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return
            except Exception as e:
                logging.warning(f"[验证码历史-behavior] 更新文件 {filename} 失败: {e}")
    except Exception as e:
        logging.error(f"[验证码历史-behavior] 更新历史失败: {e}", exc_info=True)


def normalize_captcha_history_record(record):
    if not isinstance(record, dict):
        return record
    # 历史记录只用于审计状态，不应成为验证码答案或会话标识的备份。
    record["code"] = ""
    record["captcha_code"] = ""
    record["html"] = ""
    record.pop("session_id", None)
    provider = str(
        record.get("provider") or record.get("captcha_provider") or ""
    ).strip().lower()
    if provider == "behavior":
        record["provider"] = "behavior"
        record["captcha_provider"] = "behavior"
        record["display_text"] = "使用验证码服务器"
        if record.get("verified_input"):
            record["verified_input"] = "验证码服务器二次校验"
    return record


def _verify_behavior_captcha(captcha_id):
    """
    本地行为验证码二次校验：调用行为验证码服务 GET /check2?id=<captcha_id>。
    返回 (bool, error_msg)。校验通过后该 id 在 behavior 侧被消费，无法重放。
    """
    import requests as _requests

    conf = get_captcha_provider_config()
    base_url = conf.get("behavior_base_url") or ""
    if not base_url:
        logging.error("[验证码-behavior] 未配置 behavior_base_url")
        return False, "人机验证服务未配置"
    headers = {}
    if conf.get("behavior_api_key"):
        headers["X-Captcha-Key"] = conf["behavior_api_key"]
    try:
        resp = _requests.get(
            f"{base_url}/check2",
            params={"id": captcha_id},
            headers=headers,
            timeout=5,
        )
        passed = resp.status_code == 200 and resp.text.strip().lower() == "true"
        update_behavior_captcha_history(captcha_id, passed)
        if passed:
            logging.info(f"[验证码-behavior] 二验通过: ID={captcha_id[:12]}...")
            return True, ""
        logging.warning(
            f"[验证码-behavior] 二验未通过: ID={captcha_id[:8]}..., "
            f"status={resp.status_code}"
        )
        return False, "人机验证未通过，请重试"
    except Exception as e:
        logging.error(f"[验证码-behavior] 二验请求失败: {e}")
        return False, "人机验证服务异常，请稍后重试"


def verify_captcha(captcha_id, user_input):
    """
    验证验证码辅助函数（按提供方分支：本地图片 / behavior）
    """
    logging.debug(f"[验证码] 开始验证: ID={str(captcha_id)[:8]}...")

    # ========================================
    # 提供方分支：behavior 走 /check2 二次校验，不依赖文本输入
    # ========================================
    if get_captcha_provider_config().get("provider") == "behavior":
        if not captcha_id or not captcha_id.strip():
            return False, "请先完成人机验证"
        return _verify_behavior_captcha(captcha_id.strip())

    if not captcha_id or not captcha_id.strip():
        return False, "验证码ID不能为空"

    if not user_input or not user_input.strip():
        return False, "人机验证码不能为空"
    captchas_dir = os.path.join("logs", "captchas")
    captcha_file = os.path.join(captchas_dir, f"{captcha_id}.json")
    if not os.path.exists(captcha_file):
        logging.warning(f"[验证码] 验证码文件不存在: ID={str(captcha_id)[:8]}...")
        return False, "人机验证码不存在或已失效"

    try:
        with open(captcha_file, "r", encoding="utf-8") as f:
            captcha_data = json.load(f)
        current_time = time.time()
        if captcha_data.get("expires_at", 0) < current_time:
            try:
                os.remove(captcha_file)
            except Exception as e:
                logging.warning(f"[验证码] 删除过期验证码文件失败: {e}")
            return False, "人机验证码已过期"
        stored_code = captcha_data.get("code", "")
        user_input_upper = user_input.strip().upper()
        is_correct = user_input_upper == stored_code

        def update_captcha_history():
            try:
                history_dir = os.path.join("logs", "captcha_history")
                date_str = datetime.datetime.now().strftime("%Y%m%d")
                history_file = os.path.join(
                    history_dir, f"captcha_history_{date_str}.jsonl"
                )
                if os.path.exists(history_file):
                    lines = []
                    with open(history_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    updated = False
                    for i, line in enumerate(lines):
                        try:
                            record = json.loads(line.strip())
                            if record.get("captcha_id") == captcha_id:
                                record["status"] = (
                                    "verified_success"
                                    if is_correct
                                    else "verified_failed"
                                )
                                record["verified_at"] = time.time()
                                record["verified_at_readable"] = (
                                    datetime.datetime.fromtimestamp(
                                        time.time()
                                    ).strftime("%Y-%m-%d %H:%M:%S")
                                )
                                record["verified_input"] = "已提交（内容已隐藏）"
                                lines[i] = (
                                    json.dumps(
                                        record, ensure_ascii=False) + "\n"
                                )
                                updated = True
                                break
                        except:
                            pass

                    if updated:
                        with open(history_file, "w", encoding="utf-8") as f:
                            f.writelines(lines)

                        logging.debug(
                            f"[验证码历史] 已更新验证结果: ID={captcha_id[:8]}..., 结果={'成功' if is_correct else '失败'}"
                        )
            except Exception as e:
                logging.error(f"[验证码历史] 更新验证结果失败: {e}", exc_info=True)

        threading.Thread(target=update_captcha_history,
                         daemon=True).start()
        try:
            os.remove(captcha_file)
            logging.debug(f"[验证码] 已删除验证码文件: {str(captcha_id)[:8]}...")
        except Exception as e:
            logging.warning(f"[验证码] 删除验证码文件失败: {e}")
        if is_correct:
            logging.info(f"[验证码] 验证成功: ID={captcha_id[:8]}...")
            return True, ""
        else:
            logging.warning(f"[验证码] 验证失败: ID={captcha_id[:8]}...")
            return False, "人机验证码错误"

    except json.JSONDecodeError as e:
        logging.error(f"[验证码] JSON解析失败: {e}")
        try:
            os.remove(captcha_file)
        except:
            pass
        return False, "人机验证码数据损坏"

    except Exception as e:
        logging.error(f"[验证码] 验证过程出错: {e}", exc_info=True)
        return False, "人机验证码验证失败"



def _register_payment_verify_probe_route(app):
    @app.route("/api/payment/verify_probe/<token>", methods=["POST"])
    def payment_verify_probe(token):
        data = request.get_json(silent=True) or {}
        challenge = data.get("challenge", "")
        if not _consume_payment_verify_probe(token, challenge):
            response = jsonify({"success": False})
            return _apply_no_cache_headers(response), 404
        response = jsonify({"success": True})
        return _apply_no_cache_headers(response)


def _register_payment_verify_host_route_for_tests(app, login_required, verifier_factory=None):
    verifier_factory = verifier_factory or IPVerifier

    @app.route("/api/payment/verify_host", methods=["POST"])
    @login_required
    def payment_verify_host():
        data = request.get_json(silent=True) or {}
        app_host = str(data.get("app_host", "")).strip()
        if not app_host:
            return jsonify({
                "success": False,
                "message": "app_host参数不能为空",
                "verified": False,
            })
        if not (app_host.startswith("http://") or app_host.startswith("https://")):
            return jsonify({
                "success": False,
                "message": "app_host格式不正确，必须以http://或https://开头",
                "verified": False,
            })

        verified = verifier_factory().check_app_host(app_host.rstrip("/"))
        if verified:
            return jsonify({
                "success": True,
                "message": "验证通过，这是本服务器",
                "verified": True,
            })
        return jsonify({
            "success": False,
            "message": "验证失败：目标地址未命中本机随机探针",
            "verified": False,
        })


def _try_import_builtin(module_name, display_name=None, use_print=False):
    """
    尝试导入内置模块，失败时记录但不立即退出。
    """
    if display_name is None:
        display_name = module_name

    try:
        module = __import__(module_name)
        _buffer_log("INFO", f"[导入检查] ✓ {display_name} 导入成功")
        return module
    except ImportError as e:
        _import_failures.append(
            {"module": display_name, "type": "builtin", "error": str(e)}
        )
        _buffer_log("ERROR", f"[导入检查] ✗ {display_name} 导入失败: {e}")
        return None


_buffer_log("INFO", "[导入检查] 开始导入Python内置模块...")
logging = _try_import_builtin("logging", None, True)
sys = _try_import_builtin("sys")
os = _try_import_builtin("os")
re = _try_import_builtin("re")
time = _try_import_builtin("time")
threading = _try_import_builtin("threading")
hashlib = _try_import_builtin("hashlib")
json = _try_import_builtin("json")
configparser = _try_import_builtin("configparser")
datetime = _try_import_builtin("datetime")
urllib = _try_import_builtin("urllib")
traceback = _try_import_builtin("traceback")
zipfile = _try_import_builtin("zipfile")
random = _try_import_builtin("random")
secrets = _try_import_builtin("secrets")
string = _try_import_builtin("string")
argparse = _try_import_builtin("argparse")
subprocess = _try_import_builtin("subprocess")
gc = _try_import_builtin("gc")
heapq = _try_import_builtin("heapq")
ipaddress = _try_import_builtin("ipaddress")
shutil = _try_import_builtin("shutil")
codecs = _try_import_builtin("codecs")
mimetypes = _try_import_builtin("mimetypes")

if _import_failures:
    _buffer_log("ERROR", f"\n{'='*70}")
    _buffer_log("ERROR", f"[致命错误] 内置模块导入失败")
    _buffer_log("ERROR", f"{'='*70}")
    _buffer_log("ERROR", f"\n检测到 {len(_import_failures)} 个内置模块导入失败：\n")
    for i, failure in enumerate(_import_failures, 1):
        _buffer_log("ERROR", f"  {i}. {failure['module']}")
        _buffer_log("ERROR", f"     错误: {failure['error']}\n")
    _buffer_log("ERROR", "这通常表示您的 Python 环境已损坏。")
    _buffer_log("ERROR", "建议重新安装 Python 或修复当前安装。")
    _buffer_log(f"{'='*70}\n")
    _import_failures.clear()
    if sys:
        sys.exit(1)
    else:
        exit(1)

_buffer_log("INFO", "[导入检查] ✓ 所有内置模块导入成功\n")
_import_failures.clear()
payment_verify_probes_lock = threading.Lock()

# 安全辅助函数：依赖导入完成后才能创建真正的线程锁和 IP 网络对象。
two_fa_challenges = {}
two_fa_challenges_lock = threading.Lock()
TWO_FA_CHALLENGE_TTL_SECONDS = 5 * 60
TWO_FA_CHALLENGE_MAX_ATTEMPTS = 5

TRUSTED_IPS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "trusted_ips.txt"
)
_BUILTIN_TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)
_trusted_ip_networks_cache = None
_trusted_ip_networks_cache_mtime = None
_trusted_ip_networks_lock = threading.Lock()

# USERNAME_PATTERN 在动态导入 re 之前会保持 None，这里在标准库导入完成后重建。
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.@]+$")

API_METHOD_ALLOWLIST = {
    "auto_generate_path_with_api",
    "auto_generate_path_with_provider",
    "clear_current_task_draft",
    "enter_multi_account_mode",
    "enter_single_account_mode",
    "exit_multi_account_mode",
    "export_task_data",
    "generate_new_ua",
    "get_cached_notifications",
    "get_historical_track",
    "get_initial_data",
    "get_notifications",
    "get_params",
    "get_public_theme_styles",
    "get_run_status",
    "get_session_mode_info",
    "get_task_details",
    "get_task_history",
    "get_theme_config",
    "get_theme_styles",
    "get_user_sessions",
    "import_task_data",
    "js_log",
    "load_tasks",
    "login",
    "logout",
    "mark_notification_read",
    "mark_theme_background_consumed",
    "multi_add_account",
    "multi_download_import_template",
    "multi_export_accounts_summary",
    "multi_get_account_params",
    "multi_get_all_accounts_status",
    "multi_get_all_config_users",
    "multi_import_accounts",
    "multi_load_accounts_from_config",
    "multi_path_generation_callback",
    "multi_refresh_all_statuses",
    "multi_refresh_single_status",
    "multi_remove_account",
    "multi_remove_all_accounts",
    "multi_remove_selected_accounts",
    "multi_start_all_accounts",
    "multi_start_single_account",
    "multi_stop_all_accounts",
    "multi_stop_single_account",
    "multi_update_account_param",
    "on_user_selected",
    "process_path",
    "save_amap_key",
    "save_map_provider_key",
    "set_draft_path",
    "set_multi_run_only_incomplete",
    "start_all_runs",
    "start_single_run",
    "stop_run",
    "trigger_attendance",
    "update_param",
}


def _cleanup_expired_two_fa_challenges(now_ts=None):
    current_ts = float(now_ts if now_ts is not None else time.time())
    with two_fa_challenges_lock:
        expired_tokens = [
            token
            for token, challenge in two_fa_challenges.items()
            if float((challenge or {}).get("expires_at", 0) or 0) <= current_ts
        ]
        for token in expired_tokens:
            two_fa_challenges.pop(token, None)


def _create_two_fa_challenge(
    username,
    ttl_seconds=TWO_FA_CHALLENGE_TTL_SECONDS,
    max_attempts=TWO_FA_CHALLENGE_MAX_ATTEMPTS,
):
    _cleanup_expired_two_fa_challenges()
    username = str(username or "").strip()
    if not username:
        raise ValueError("username is required")
    token = secrets.token_urlsafe(32)
    now_ts = time.time()
    with two_fa_challenges_lock:
        two_fa_challenges[token] = {
            "username": username,
            "created_at": now_ts,
            "expires_at": now_ts + max(float(ttl_seconds or 0), 0),
            "attempts": 0,
            "max_attempts": max(int(max_attempts or 1), 1),
        }
    return token


def _consume_two_fa_challenge(token, username, verification_code, verifier):
    _cleanup_expired_two_fa_challenges()
    with two_fa_challenges_lock:
        challenge = two_fa_challenges.get(str(token or ""))
        if not isinstance(challenge, dict):
            return False, "2FA challenge 无效或已过期"
        if str(challenge.get("username") or "") != str(username or "").strip():
            return False, "2FA challenge 与用户不匹配"
        attempts = int(challenge.get("attempts", 0) or 0)
        if attempts >= int(challenge.get("max_attempts", 1) or 1):
            two_fa_challenges.pop(str(token), None)
            return False, "2FA 验证尝试次数过多"

        challenge["attempts"] = attempts + 1
        try:
            is_valid = bool(verifier(username, verification_code))
        except Exception:
            is_valid = False

        if is_valid:
            two_fa_challenges.pop(str(token), None)
            return True, ""

        if challenge["attempts"] >= challenge["max_attempts"]:
            two_fa_challenges.pop(str(token), None)
            return False, "2FA 验证尝试次数过多"
        return False, "2FA验证码错误"


def _is_safe_auth_username(value):
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > MAX_USERNAME_LENGTH:
        return False
    return bool(USERNAME_PATTERN and USERNAME_PATTERN.fullmatch(normalized))


# 学校账号（学号）格式：纯 ASCII 数字，至少 4 位。
# 导入、手动添加、管理端写入、配置保存都必须经过这个校验，避免把名单里的
# “序号/姓名”列当成学号和密码写进 school_accounts（真实事故：1.ini..21.ini、
# 序号.ini 与两条 password=姓名 的 JSON 记录）。
SCHOOL_USERNAME_MIN_DIGITS = 4
SCHOOL_USERNAME_PATTERN = re.compile(r"^[0-9]{%d,}$" % SCHOOL_USERNAME_MIN_DIGITS)


def is_valid_school_username(value):
    """学号必须是纯数字且至少 4 位。"""
    normalized = str(value or "").strip()
    return bool(normalized) and bool(
        SCHOOL_USERNAME_PATTERN.fullmatch(normalized)
    )


# 密码不能包含中文：学校密码只可能是数字/字母/符号；真实事故里名单的
# “姓名”列被当成密码写进了配置（password=朱燕姿 之类）。
SCHOOL_PASSWORD_CJK_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)


def is_valid_school_password(value):
    """密码不得包含中文字符（空密码允许，走缺密码补全流程）。"""
    return not bool(SCHOOL_PASSWORD_CJK_PATTERN.search(str(value or "")))


def _auth_username_storage_key(username):
    normalized = str(username or "").strip()
    if _is_safe_auth_username(normalized):
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"invalid_{digest}"


def _encode_inline_script_json(value):
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _is_api_method_allowed(method):
    return str(method or "") in API_METHOD_ALLOWLIST


def _verify_session_cookie_token(session_id, username, token):
    normalized_username = str(username or "").strip()
    if normalized_username == "guest":
        return True
    normalized_session_id = normalize_session_uuid(session_id)
    normalized_token = str(token or "").strip()
    if not normalized_username or not normalized_session_id or not normalized_token:
        return False
    token_manager_instance = globals().get("token_manager")
    if not token_manager_instance:
        return False
    try:
        verified = token_manager_instance.verify_token(
            normalized_username, normalized_session_id, normalized_token
        )
    except Exception:
        return False
    if isinstance(verified, tuple):
        return bool(verified[0])
    return bool(verified)


def _normalize_payment_jump_url(value, request_host_url):
    normalized = str(value or "").strip()
    if not normalized or any(ord(char) < 32 for char in normalized):
        return "/"
    if "\\" in normalized:
        return "/"

    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme or parsed.netloc:
        base = urllib.parse.urlparse(str(request_host_url or ""))
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            return "/"
        relative = parsed.path or "/"
        if parsed.query:
            relative = f"{relative}?{parsed.query}"
        return relative

    if not normalized.startswith("/") or normalized.startswith("//"):
        return "/"
    return normalized















if sys and sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def import_standard_libraries():
    """
    逐步导入所有必需的标准库。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入 Python 标准库...")
    logging.info("[依赖检查] 正在导入 Python 标准库...")


    std_libs = [
        ("ssl", "import ssl"),
        # eventlet 属于第三方依赖，不应放在标准库检查里。
        # 其缺失应由后续核心依赖检查统一报告为“依赖缺失”，而非 Python 环境损坏。
        # eventlet 相关导入放在 import_core_third_party() 中处理。
        # ("eventlet.wsgi", "import eventlet.wsgi"),
        ("argparse", "import argparse"),
        ("base64", "import base64"),
        ("bisect", "import bisect"),
        ("collections", "import collections"),
        ("configparser", "import configparser"),
        ("copy", "import copy"),
        ("csv", "import csv"),
        ("datetime", "import datetime"),
        ("hashlib", "import hashlib"),
        ("json", "import json"),
        ("math", "import math"),
        ("pickle", "import pickle"),
        ("queue", "import queue"),
        ("random", "import random"),
        ("re", "import re"),
        ("secrets", "import secrets"),
        ("socket", "import socket"),
        ("threading", "import threading"),
        ("time", "import time"),
        ("traceback", "import traceback"),
        ("urllib", "import urllib"),
        ("urllib.request", "import urllib.request"),
        ("uuid", "import uuid"),
        ("warnings", "import warnings"),
        ("atexit", "import atexit"),
        ("io", "import io"),
        ("zipfile", "import zipfile"),
        ("functools", "import functools"),
        # ("ipaddress", "import ipaddress"),
        ("string", "import string"),
        ("shutil", "import shutil"),
        ("concurrent.futures", "import concurrent.futures"),
        ("tempfile", "import tempfile"),
        ("os", "import os"),
        ("codecs", "import codecs"),
    ]

    failed_imports = []

    for name, import_cmd in std_libs:
        try:
            logging.info(f"  -> 正在导入 {name}...")
            logging.info(f"[依赖检查]   -> {name}...")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {name} 导入成功")
            logging.info("✓")
        except ImportError as e:
            logging.error(f"  ✗ {name} 导入失败: {e}")
            logging.error(f"✗ ({e})")
            failed_imports.append({"name": name, "error": str(e)})
            
    global ssl, eventlet, argparse, base64, bisect, collections, configparser, copy, csv, datetime, hashlib, json, math, pickle, queue, random, re, secrets, socket, threading, time, traceback, urllib, uuid, warnings, atexit, io, zipfile, functools, ipaddress, string, shutil, concurrent, codecs


    if sys.platform != "win32":
        try:
            logging.info("  -> 正在导入 fcntl (非Windows)...")
            logging.info("[依赖检查]   -> fcntl (非Windows)...")
            import fcntl

            globals()["fcntl"] = fcntl
            logging.info("  ✓ fcntl 导入成功")
            logging.info("✓")
        except ImportError as e:
            logging.error(f"  ✗ fcntl 导入失败: {e}")
            logging.error(f"✗ ({e})")
            failed_imports.append({"name": "fcntl", "error": str(e)})
    else:
        logging.warning("  -> fcntl 模块在 Windows 平台不可用，已跳过。")
        logging.info("[依赖检查]   -> fcntl (Windows平台跳过)")
    if "eventlet" in globals():
        # 服务器使用 socketio.run() + async_mode="threading"（werkzeug 线程模式），
        # 不再使用 eventlet WSGI 服务器，因此无需调用 monkey_patch。
        # 调用 eventlet.monkey_patch(select=True, socket=True) 会把标准 select 模块
        # 替换为 eventlet 的实现，而 werkzeug 的 worker 线程（非 greenlet）调用它时
        # 会触发 eventlet 为每个线程创建一个新的 epoll hub，导致 epoll fd 泄漏，
        # 最终耗尽文件描述符（OSError: [Errno 24] Too many open files）。
        logging.info("[Eventlet] async_mode=threading 模式下跳过 monkey_patch，避免 epoll fd 泄漏")

    if failed_imports:
        logging.critical(f"标准库导入失败，共 {len(failed_imports)} 个模块")
        print(f"\n{'='*70}")
        print(f"[致命错误] Python 标准库导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个标准库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']}")
            print(f"     错误: {failure['error']}\n")
        print("这可能表示您的 Python 环境已损坏。")
        print("请检查您的 Python 安装或尝试重新安装 Python。")
        print(f"{'='*70}\n")
        sys.exit(1)

    print("[依赖检查] ✓ 所有标准库导入成功！")
    logging.info("所有标准库导入成功！")


def import_core_third_party():
    """
    导入 'check_and_import_dependencies' 未涵盖的核心第三方库。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入核心第三方库 (Pillow, bcrypt, Flask-SocketIO)...")
    print("[依赖检查] 正在导入核心第三方库...")

    core_libs = [
        ("PIL (Pillow)", "from PIL import Image", "Pillow"),
        ("bcrypt", "import bcrypt", "bcrypt"),
        (
            "Flask-SocketIO",
            "from flask_socketio import SocketIO, emit, join_room, leave_room",
            "Flask-SocketIO",
        ),
        ("eventlet", "import eventlet", "eventlet"),
        ("eventlet.wsgi", "import eventlet.wsgi", "eventlet"),
        ("eventlet.tpool", "import eventlet.tpool", "eventlet"),
    ]

    failed_imports = []

    for display_name, import_cmd, pip_name in core_libs:
        try:
            logging.info(f"  -> 正在导入 {display_name}...")
            print(f"[依赖检查]   -> {display_name}...", end=" ")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {display_name} 导入成功")
            print("✓")
        except ImportError as e:
            logging.error(f"  ✗ {display_name} 导入失败: {e}")
            print(f"✗ ({e})")
            failed_imports.append(
                {"name": display_name, "pip_name": pip_name, "error": str(e)}
            )

    if failed_imports:
        logging.critical(f"核心第三方库导入失败，共 {len(failed_imports)} 个模块")
        pip_install_list = " ".join([f["pip_name"] for f in failed_imports])

        print(f"\n{'='*70}")
        print(f"[依赖缺失错误] 核心第三方库导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个核心库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']} (pip包名: {failure['pip_name']})")
            print(f"     错误: {failure['error']}\n")
        print("请在您的终端（命令行）中运行以下命令来安装缺失的库:")
        print(f"\n  pip install {pip_install_list}\n")
        print("如果您使用的是 pip3，请运行:")
        print(f"\n  pip3 install {pip_install_list}\n")
        print(f"{'='*70}\n")
        sys.exit(1)

    print("[依赖检查] ✓ 核心第三方库导入成功！")
    logging.info("核心第三方库导入成功！")

    # 可选第三方库：导入失败不影响主流程，仅记录警告
    optional_libs = [
        ("fake_useragent", "from fake_useragent import UserAgent", "fake-useragent"),
        ("greenlet", "import greenlet", "greenlet"),
    ]
    for display_name, import_cmd, pip_name in optional_libs:
        try:
            exec(import_cmd, globals())
            logging.info(f"  ✓ 可选库 {display_name} 导入成功")
        except ImportError:
            logging.warning(
                f"  [可选] {display_name} 未安装，相关功能将降级运行（pip install {pip_name}）"
            )


def check_and_import_dependencies():
    """
    检查并导入所有主要的第三方库 (Flask, requests, playwright 等)。
    收集所有导入失败的模块，最后统一报告并提供安装命令。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入主要应用依赖库...")
    print("[依赖检查] 开始检查并导入主要应用依赖库...")

    global Flask, render_template_string, session, redirect, url_for, request, jsonify, make_response, g, send_file
    global CORS, pyotp, requests, openpyxl, xlrd, xlwt, chardet, sync_playwright, np
    global cssutils, playwright_available

    global cryptography, socketio

    (
        Flask,
        render_template_string,
        session,
        redirect,
        url_for,
        request,
        jsonify,
        make_response,
        g,
    ) = (None,) * 9
    (
        CORS,
        pyotp,
        requests,
        openpyxl,
        xlrd,
        xlwt,
        chardet,
        sync_playwright,
        np,
        cssutils,
    ) = (None,) * 10
    playwright_available = False

    cryptography = None

    socketio = None

    dependencies = [
        (
            "Flask Web框架",
            "from flask import Flask, render_template_string, session, redirect, url_for, request, jsonify, make_response, g, send_file, send_from_directory, Response , abort",
            "Flask",
        ),
        ("Flask CORS", "from flask_cors import CORS", "flask-cors"),
        ("pyotp (一次性密码)", "import pyotp", "pyotp"),
        ("requests (HTTP库)", "import requests", "requests"),
        ("openpyxl (Excel .xlsx)", "import openpyxl", "openpyxl"),
        ("xlrd (Excel .xls读取)", "import xlrd", "xlrd"),
        ("xlwt (Excel .xls写入)", "import xlwt", "xlwt"),
        ("chardet (编码检测)", "import chardet", "chardet"),
        (
            "Playwright (浏览器自动化)",
            "from playwright.sync_api import sync_playwright",
            "playwright",
        ),
        ("NumPy (科学计算)", "import numpy as np", "numpy"),
        ("cssutils (CSS解析)", "import cssutils", "cssutils"),
        ("cryptography (SSL/加密)", "import cryptography", "cryptography"),
        ("BeautifulSoup (HTML解析)", "from bs4 import BeautifulSoup", "beautifulsoup4"),
        ("typing (类型提示)", "import typing", "typing"),
        ("urllib.parse (URL处理)", "import urllib.parse", "urllib3"),
        ("werkzeug (WSGI工具)", "import werkzeug", "werkzeug"),
        ("cryptography.x509 (证书处理)", "import cryptography.x509", "cryptography"),
    ]

    failed_imports = []

    for display_name, import_cmd, pip_name in dependencies:
        try:
            logging.info(f"  -> 正在导入 {display_name}...")
            print(f"[依赖检查]   -> {display_name}...", end=" ")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {display_name} 导入成功")
            print("✓")

            if pip_name == "playwright":
                playwright_available = True

        except ImportError as e:
            logging.error(f"  ✗ {display_name} 导入失败: {e}")
            print(f"✗ ({e})")
            failed_imports.append(
                {"name": display_name, "pip_name": pip_name, "error": str(e)}
            )

    if failed_imports:
        logging.critical(f"主要应用依赖导入失败，共 {len(failed_imports)} 个模块")
        pip_install_list = " ".join([f["pip_name"] for f in failed_imports])

        print(f"\n{'='*70}")
        print(f"[依赖缺失错误] 主要应用依赖导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个依赖库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']} (pip包名: {failure['pip_name']})")
            print(f"     错误: {failure['error']}\n")
        print("请在您的终端（命令行）中运行以下命令来安装 *所有* 缺失的依赖:")
        print(f"\n  pip install {pip_install_list}\n")
        print("如果您使用的是 pip3，请运行:")
        print(f"\n  pip3 install {pip_install_list}\n")

        if any(f["pip_name"] == "playwright" for f in failed_imports):
            print("--- 特别提示：关于 'playwright' ---")
            print("playwright 库在首次安装后，还需要安装浏览器驱动。")
            print("请在安装完 pip 包后，额外运行一次:")
            print("  playwright install chromium")
            print("--------------------------------------\n")

        print(f"{'='*70}\n")
        sys.exit(1)

    logging.info("所有主要应用依赖库导入完成！")
    print("[依赖检查] ✓ 所有主要应用依赖库导入完成！")
    logging.info("=" * 80)


def initialize_global_variables():
    """
    初始化所有全局变量和应用状态。
    """
    logging.info("开始初始化全局变量...")

    global auth_system, token_manager, html_content, background_state_store
    global web_sessions, web_sessions_lock, session_file_locks, session_file_locks_lock
    global session_activity, session_activity_lock
    global chrome_pool, background_task_manager
    global MAX_MEMORY_SESSIONS  # <--- [修正] 添加这一行，声明为全局变量

    auth_system = AuthSystem()
    token_manager = TokenManager(TOKENS_STORAGE_DIR)
    background_state_store = BackgroundStateStore(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), RANDOM_BACKGROUND_IMAGE_DIR)
    )
    logging.info("认证系统和Token管理器已创建。")

    html_content = ""
    try:
        html_path = "index.html"

        with open(html_path, "r", encoding="utf-8") as file:
            html_content = file.read()
        logging.info("成功读取 index.html 文件！")

    except FileNotFoundError:
        logging.error(f"错误: 未在路径 '{html_path}' 中找到 'index.html' 文件。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"读取文件时发生错误: {e}", exc_info=True)
        sys.exit(1)

    web_sessions = {}
    web_sessions_lock = threading.Lock()

    session_file_locks = {}
    session_file_locks_lock = threading.Lock()

    session_activity = {}
    session_activity_lock = threading.Lock()

    global browsing_activity, browsing_activity_lock
    browsing_activity = {}
    browsing_activity_lock = threading.Lock()

    global admin_view_origin_activity, admin_view_origin_activity_lock
    admin_view_origin_activity = {}
    admin_view_origin_activity_lock = threading.RLock()

    # 全局变量：缓存服务器的公网IP地址（IPv4 和 IPv6）
    # 用于 is_allowed_ip() 函数中判断请求是否来自服务器本身
    # 缓存机制可以避免频繁调用外部API查询公网IP
    global public_ip_cache, public_ip_cache_lock, public_ip_cache_time
    public_ip_cache = {"ipv4": None, "ipv6": None}  # 存储公网IP的字典
    public_ip_cache_lock = threading.Lock()  # 线程锁，保护缓存数据的并发访问
    public_ip_cache_time = 0  # 缓存的时间戳，用于判断缓存是否过期

    logging.info("会话存储和锁已初始化。")

    chrome_pool = None
    background_task_manager = None
    logging.info("浏览器池和任务管理器已初始化为 None。")

    logging.info("全局变量初始化完成。")




# ==============================================================================
#  辅助函数：获取客户端真实IP地址
# ==============================================================================


# ==============================================================================
#  1. 日志系统配置
# ==============================================================================


class SensitiveLogFormatter(logging.Formatter):
    """格式化日志时统一移除凭据、令牌和其他认证材料。"""

    def format(self, record):
        return _redact_sensitive_log_text(super().format(record))


class NoColorFileFormatter(SensitiveLogFormatter):
    """
    自定义日志格式化程序，用于在写入文件前去除ANSI颜色代码。
    """

    ansi_escape_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def format(self, record):
        """
        格式化日志记录并移除颜色代码。
        """
        original_message = super().format(record)
        cleaned_message = self.ansi_escape_regex.sub("", original_message)
        return cleaned_message


class ContextEnrichFilter(logging.Filter):
    """
    为日志记录补充通用上下文字段，避免格式化时缺失字段。
    """

    def filter(self, record):
        record.request_id = "-"
        record.request_user = "-"
        record.client_ip = "-"
        record.request_method = "-"
        record.request_path = "-"

        request_obj = globals().get("request")
        if request_obj is None:
            return True

        try:
            record.request_method = request_obj.method
            record.request_path = request_obj.path

            g_obj = globals().get("g")
            request_id = None
            request_user = None
            if g_obj is not None:
                request_id = getattr(g_obj, "request_id", None)
                request_user = getattr(g_obj, "user", None)

            if not request_id:
                request_id = request_obj.headers.get("X-Request-ID")
            if not request_user:
                request_user = request_obj.headers.get("X-User", None)

            forwarded_for = request_obj.headers.get("X-Forwarded-For", "")
            client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
            if not client_ip:
                client_ip = request_obj.environ.get("REMOTE_ADDR") or request_obj.remote_addr

            if request_id:
                record.request_id = str(request_id)
            if request_user:
                record.request_user = str(request_user)
            if client_ip:
                record.client_ip = str(client_ip)
        except Exception:  # nosec B110 - 非请求上下文时使用默认值，不需要记录
            # 非请求上下文（或上下文访问失败）时使用默认值
            pass

        return True


class CustomLogHandler(logging.FileHandler):
    """
    自定义日志处理器，实现文件大小检查和轮转。

    轮转规则（顺序编号，不搬动历史文件）:
        - `zx-slm-tool.log` 是当前正在写的文件；
        - 每写满一次，就把它改名成下一个编号 `zx-slm-tool-NN.log`，
          NN 从 01 开始递增；**已存在的历史文件保持原名不动**；
        - 因此 `-01` 永远是最旧的，编号越大越新（与时间顺序一致）。
    """

    #: 单个主日志最多保留多少个历史文件（含 01）
    MAX_BACKUP_COUNT = 10

    #: 历史文件编号的位数，例：01 -> "01"
    BACKUP_INDEX_WIDTH = 2

    def __init__(
        self,
        filename,
        mode="a",
        encoding="utf-8",
        max_bytes=10 * 1024 * 1024,
        backup_count=None,
    ):
        """
        初始化自定义日志处理器。
        """
        self.max_bytes = max_bytes
        self.base_filename = filename
        # 每个处理器可独立配置保留数量，缺省用类默认值
        self.backup_count = max(
            1,
            int(
                CustomLogHandler.MAX_BACKUP_COUNT
                if backup_count is None
                else backup_count
            ),
        )
        self.rollover_failure_count = 0
        self.rollover_retry_at = 0.0
        super().__init__(filename, mode, encoding)

    def _resolve_backup_prefix(self):
        """历史文件的前缀：由处理器自己的文件名推导。

        必须按处理器分别推导，不能写死成 `zx-slm-tool`：
        WARNING / ERROR 处理器各自轮转时，若都用同一个前缀，
        它们的备份会互相覆盖，而且会与主日志的备份撞名。
        """
        base = os.path.basename(self.baseFilename)
        if base.endswith(".log"):
            base = base[: -len(".log")]
        return base or "zx-slm-tool"

    def _list_backup_files(self):
        """列出该处理器的历史文件，返回 [(编号, 完整路径)]（按编号升序）。"""
        log_dir = os.path.dirname(self.baseFilename)
        prefix = self._resolve_backup_prefix()
        pattern = re.compile(
            rf"^{re.escape(prefix)}-(\d{{{self.BACKUP_INDEX_WIDTH},}})\.log$"
        )

        found = []
        try:
            entries = os.listdir(log_dir)
        except OSError:
            return found

        for name in entries:
            match = pattern.match(name)
            if not match:
                continue
            found.append((int(match.group(1)), os.path.join(log_dir, name)))

        found.sort(key=lambda item: item[0])
        return found

    def _next_backup_path(self):
        """返回本次轮转应写入的历史文件路径（最大编号 +1）。"""
        log_dir = os.path.dirname(self.baseFilename)
        backups = self._list_backup_files()
        next_index = backups[-1][0] + 1 if backups else 1
        return os.path.join(
            log_dir,
            f"{self._resolve_backup_prefix()}-{next_index:0{self.BACKUP_INDEX_WIDTH}d}.log",
        )

    def _prune_old_backups(self):
        """超过保留上限时，从编号最小（最旧）的开始删除。"""
        backups = self._list_backup_files()
        excess = len(backups) - self.backup_count
        if excess <= 0:
            return

        for index, path in backups[:excess]:
            try:
                os.remove(path)
                print(
                    f"[日志轮转] 已删除最旧的历史日志: {os.path.basename(path)}"
                )
            except OSError as exc:
                print(
                    f"[日志轮转] 删除 {os.path.basename(path)} 失败: {exc}"
                )

    def emit(self, record):
        """
        写入日志记录前检查文件大小。
        """
        try:

            if self.stream and os.path.exists(self.baseFilename):
                self.stream.flush()
                if (
                    os.path.getsize(self.baseFilename) >= self.max_bytes
                    and time.monotonic() >= self.rollover_retry_at
                ):
                    self.do_rollover()

            super().emit(record)

        except Exception:
            self.handleError(record)

    def do_rollover(self):
        """
        执行日志轮转：把当前文件改名成下一个编号，不搬动已存在的历史文件。
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        try:
            target_path = self._next_backup_path()

            # 正常情况下不会撞名；万一撞上（例如手工放了个同号文件），
            # 先让开，避免 rename 覆盖掉已有日志。
            if os.path.exists(target_path):
                os.remove(target_path)

            os.rename(self.baseFilename, target_path)
            print(
                f"[日志轮转] {os.path.basename(self.baseFilename)} -> "
                f"{os.path.basename(target_path)}"
            )
        except Exception as e:
            self.rollover_failure_count += 1
            retry_delay_seconds = min(
                60,
                2 ** min(self.rollover_failure_count, 6),
            )
            self.rollover_retry_at = time.monotonic() + retry_delay_seconds
            print(
                f"[日志轮转] 轮转日志文件失败: {e}；"
                f"{retry_delay_seconds} 秒后重试"
            )
            self.stream = self._open()
            return False

        # 轮转成功后再裁剪，避免"删了旧的却没能建新的"
        self._prune_old_backups()

        self.stream = self._open()
        self.rollover_failure_count = 0
        self.rollover_retry_at = 0.0
        return True


def archive_old_logs():
    """
    归档旧的日志文件和随机背景缓存。
    """

    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)
        print(f"[日志归档] 创建归档目录: {archive_dir}")

    files_to_archive = []
    for filename in os.listdir(log_dir):
        if filename == "zx-slm-tool.log" or (
            filename.startswith("zx-slm-tool-") and filename.endswith(".log")
        ):
            log_path = os.path.join(log_dir, filename)
            if os.path.isfile(log_path) and os.path.getsize(log_path) > 0:
                files_to_archive.append((log_path, filename))

    background_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), RANDOM_BACKGROUND_IMAGE_DIR)
    if os.path.isdir(background_dir):
        for filename in os.listdir(background_dir):
            file_path = os.path.join(background_dir, filename)
            if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                files_to_archive.append(
                    (file_path, f"{RANDOM_BACKGROUND_IMAGE_DIR}/{filename}")
                )

    if not files_to_archive:
        print(f"[日志归档] 没有需要归档的日志文件")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    archive_filename = f"{timestamp}.zip"
    archive_path = os.path.join(archive_dir, archive_filename)

    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path, archive_name in files_to_archive:
                zipf.write(file_path, archive_name)
                print(f"[日志归档] 已压缩: {archive_name}")

        for file_path, archive_name in files_to_archive:
            os.remove(file_path)
            print(f"[日志归档] 已删除原文件: {archive_name}")

        print(f"[日志归档] 归档完成: {archive_path}")

        gc.collect()

    except Exception as e:
        print(f"[日志归档] 归档失败: {e}")

        traceback.print_exc()


def cleanup_archive_directory(archive_dir, max_size_mb):
    """
    清理归档目录，确保不超过指定大小。

    """
    if max_size_mb <= 0:
        return

    if not os.path.exists(archive_dir):
        return

    try:
        archive_files = []
        total_size = 0

        for filename in os.listdir(archive_dir):
            if filename.endswith(".zip"):
                file_path = os.path.join(archive_dir, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    archive_files.append(
                        (file_path, filename, file_size, mtime))
                    total_size += file_size

        max_size_bytes = max_size_mb * 1024 * 1024
        current_size_mb = total_size / (1024 * 1024)

        if total_size <= max_size_bytes:
            print(
                f"[归档清理] 归档目录大小: {current_size_mb:.2f}MB / {max_size_mb}MB (无需清理)"
            )
            return

        print(
            f"[归档清理] 归档目录大小: {current_size_mb:.2f}MB 超过限制 {max_size_mb}MB，开始清理..."
        )

        archive_files.sort(key=lambda x: x[3])

        deleted_count = 0
        for file_path, filename, file_size, _ in archive_files:
            if total_size <= max_size_bytes:
                break

            os.remove(file_path)
            total_size -= file_size
            deleted_count += 1
            print(
                f"[归档清理] 已删除: {filename} ({file_size / (1024 * 1024):.2f}MB)")

        final_size_mb = total_size / (1024 * 1024)
        print(
            f"[归档清理] 清理完成，删除了 {deleted_count} 个文件，当前大小: {final_size_mb:.2f}MB"
        )

        if deleted_count > 0:
            gc.collect()

    except Exception as e:
        print(f"[归档清理] 清理失败: {e}")

        traceback.print_exc()


def setup_logging():
    """
    配置详细的日志系统（带自定义轮转逻辑）。
    """
    log_rotation_size_mb = 10
    log_backup_count = CustomLogHandler.MAX_BACKUP_COUNT
    archive_max_size_mb = 5120
    global log_dir, archive_dir
    log_dir = "logs"
    archive_dir = os.path.join(log_dir, "archive")

    try:
        if os.path.exists(CONFIG_JSON_FILE):
            config = configparser.ConfigParser(strict=False)
            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            if "Logging" in config:
                log_rotation_size_mb = config.getint(
                    "Logging", "log_rotation_size_mb", fallback=10
                )
                log_backup_count = config.getint(
                    "Logging",
                    "log_backup_count",
                    fallback=CustomLogHandler.MAX_BACKUP_COUNT,
                )
                archive_max_size_mb = config.getint(
                    "Logging", "archive_max_size_mb", fallback=5120
                )
                log_dir = config.get("Logging", "log_dir", fallback="logs")
                archive_dir = config.get(
                    "Logging", "archive_dir", fallback="logs/archive"
                )
    except Exception as e:
        print(f"[日志系统] 读取配置失败，使用默认值: {e}")

    # 保留数量至少要能放下 1 个历史文件
    log_backup_count = max(1, int(log_backup_count))

    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        print(f"[日志系统] 创建日志目录: {log_dir}")

    archive_old_logs()

    cleanup_archive_directory(archive_dir, archive_max_size_mb)

    log_file = os.path.join(log_dir, "zx-slm-tool.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()

    log_format = SensitiveLogFormatter(
        "%(asctime)s [%(levelname)s] [pid=%(process)d tid=%(thread)d %(threadName)s] "
        "[req=%(request_id)s user=%(request_user)s ip=%(client_ip)s] "
        "[%(filename)s:%(lineno)d] [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = ContextEnrichFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_format)
    console_handler.addFilter(context_filter)
    logger.addHandler(console_handler)

    max_bytes = log_rotation_size_mb * 1024 * 1024
    file_handler = CustomLogHandler(
        log_file,
        mode="a",
        encoding="utf-8",
        max_bytes=max_bytes,
        backup_count=log_backup_count,
    )
    file_handler.setLevel(logging.DEBUG)

    no_color_formatter = NoColorFileFormatter(
        log_format._fmt, datefmt=log_format.datefmt
    )
    file_handler.setFormatter(no_color_formatter)
    file_handler.addFilter(context_filter)

    logger.addHandler(file_handler)

    warning_log_file = os.path.join(log_dir, "zx-slm-tool-WARNING.log")

    warning_file_handler = CustomLogHandler(
        warning_log_file,
        mode="a",
        encoding="utf-8",
        max_bytes=max_bytes,
        backup_count=log_backup_count,
    )

    warning_file_handler.setLevel(logging.WARNING)

    warning_no_color_formatter = NoColorFileFormatter(
        log_format._fmt,
        datefmt=log_format.datefmt,
    )
    warning_file_handler.setFormatter(warning_no_color_formatter)
    warning_file_handler.addFilter(context_filter)

    logger.addHandler(warning_file_handler)
    error_log_file = os.path.join(log_dir, "zx-slm-tool-ERROR.log")

    error_file_handler = CustomLogHandler(
        error_log_file,
        mode="a",
        encoding="utf-8",
        max_bytes=max_bytes,
        backup_count=log_backup_count,
    )

    error_file_handler.setLevel(logging.ERROR)

    error_no_color_formatter = NoColorFileFormatter(
        log_format._fmt,
        datefmt=log_format.datefmt,
    )
    error_file_handler.setFormatter(error_no_color_formatter)
    error_file_handler.addFilter(context_filter)

    logger.addHandler(error_file_handler)

    # [核心修复] 将所有日志处理器的锁替换为原生锁
    # 解决 ChromeBrowserPool(原生线程) 调用 logging 时因持有 Eventlet 锁导致的崩溃
    try:
        # from eventlet import patcher
        # 获取未被 monkey_patch 的原生 threading 模块
        native_threading = eventlet.patcher.original("threading")
        # 遍历所有已添加的 Handler (FileHandler, StreamHandler等)
        for handler in logger.handlers:
            # 强制替换为原生可重入锁
            handler.lock = native_threading.RLock()
    except Exception as e:
        # 即使失败也不应阻止程序启动，只是可能会有潜在崩溃风险
        print(f"[日志系统] 警告: 替换日志锁失败: {e}")

    global _log_buffer
    if _log_buffer:
        for level_str, msg in _log_buffer:
            level_num = getattr(logging, level_str.upper(), logging.INFO)
            logger.log(level_num, msg.rstrip())

        _log_buffer.clear()
        gc.collect()

    logging.info("=" * 80)
    _install_global_exception_logging(logger)
    logging.info("日志系统初始化完成！")
    logging.info(f"日志文件: {log_file}")
    logging.info(f"警告日志文件: {warning_log_file}")
    logging.info(f"错误日志文件: {error_log_file}")
    logging.info(f"日志级别: DEBUG (所有级别)")
    logging.info(f"日志轮转: 单文件最大{log_rotation_size_mb}MB")
    logging.info(
        f"日志轮转: 最多保留 {log_backup_count} 个历史文件"
        f"（zx-slm-tool-01.log 最旧，编号越大越新）"
    )
    logging.info(
        f"归档目录: {archive_dir}, 最大{archive_max_size_mb}MB{'（不限制）' if archive_max_size_mb == 0 else ''}"
    )
    logging.info("=" * 80)

    return logger


def _install_global_exception_logging(logger):
    """
    安装进程级异常日志钩子（主线程与子线程）。
    """
    global _logging_exception_hooks_installed
    if _logging_exception_hooks_installed:
        return

    original_sys_excepthook = sys.excepthook

    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        if exc_type and issubclass(exc_type, KeyboardInterrupt):
            if original_sys_excepthook:
                original_sys_excepthook(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "捕获到未处理的全局异常（主线程）",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if original_sys_excepthook and original_sys_excepthook is not _sys_excepthook:
            original_sys_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _sys_excepthook

    if hasattr(threading, "excepthook"):
        original_threading_excepthook = threading.excepthook

        def _threading_excepthook(args):
            if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
                if original_threading_excepthook:
                    original_threading_excepthook(args)
                return
            thread_name = args.thread.name if args.thread else "unknown"
            thread_id = args.thread.ident if args.thread else "unknown"
            logger.critical(
                f"捕获到未处理的线程异常（thread={thread_name}, id={thread_id}）",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if (
                original_threading_excepthook
                and original_threading_excepthook is not _threading_excepthook
            ):
                original_threading_excepthook(args)

        threading.excepthook = _threading_excepthook

    try:
        logging.captureWarnings(True)
    except Exception:  # nosec B110 - 某些环境不支持captureWarnings，安全忽略
        pass

    _logging_exception_hooks_installed = True
    logger.info("已启用全局异常捕获与 warnings 转日志")


def auto_init_system():
    """
    自动初始化系统，创建所有必需的文件和目录。
    """
    logging.info("=" * 80)
    logging.info("开始自动初始化系统...")
    print("[系统初始化] 开始自动初始化系统...")

    try:
        logging.info("步骤1: 创建必需的目录...")
        print("[系统初始化] 创建必需的目录...")
        _create_directories()

        logging.info("步骤2: 创建/更新配置文件...")
        print("[系统初始化] 创建/更新配置文件...")
        _create_config_ini()

        logging.info("步骤2.5: 迁移支付方式配置...")
        print("[系统初始化] 检查并迁移支付方式配置...")
        # 调用迁移函数，将 config.ini 中的 payment_methods_config 迁移到 JSON 文件
        # 此函数会检查 payment_methods.json 是否已存在，避免重复迁移
        _migrate_payment_methods_to_json()

        logging.info("步骤2.6: 初始化高德地图去水印控制配置...")
        print("[系统初始化] 初始化高德地图去水印控制配置...")
        # 调用初始化函数，确保 amap_watermark_control.json 配置文件存在
        # 如果文件不存在，会创建默认配置文件
        _initialize_amap_watermark_config()

        logging.info("步骤2.7: 迁移自动签到配置到JSON文件...")
        print("[系统初始化] 检查并迁移自动签到配置...")
        # 调用迁移函数，将 INI 文件中的 auto_attendance_enabled 迁移到 JSON 文件
        # 此函数会扫描所有账号的INI文件，查找启用了自动签到的账号
        # 注意：由于需要学校用户名，完整迁移会在用户登录时完成
        # 修复：函数已移至模块级别，直接调用而非通过Api类
        _migrate_auto_attendance_from_ini()

        # 启动时回收一次超时的自动签到记录。
        # 这些记录可能在进程未运行时就已经到期，且其所属账号此后从未登录，
        # 因此必须有一个不依赖登录状态的清理入口，否则会永久驻留。
        try:
            _sweep_result = expire_stale_auto_attendance_accounts(
                reason="startup_sweep"
            )
            if _sweep_result.get("removed"):
                logging.info(
                    f"[系统初始化] 已回收 {len(_sweep_result['removed'])} 条超时自动签到记录: "
                    f"{_sweep_result['removed']}"
                )
                print(
                    f"[系统初始化] 已回收 {len(_sweep_result['removed'])} 条超时自动签到记录"
                )
            if not _sweep_result.get("save_ok", True):
                logging.warning("[系统初始化] 回收超时自动签到记录时写盘失败，将在下次启动重试")
        except Exception as _sweep_error:
            logging.error(
                f"[系统初始化] 回收超时自动签到记录失败: {_sweep_error}",
                exc_info=True,
            )

        logging.info("步骤2.8: 执行旧版数据结构自动迁移...")
        print("[系统初始化] 执行旧版数据结构自动迁移...")
        _run_auto_data_migrations_from_main()

        logging.info("步骤3: 创建权限配置文件...")
        print("[系统初始化] 创建权限配置文件...")
        _create_permissions_json()

        logging.info("步骤4: 创建默认管理员账号...")
        print("[系统初始化] 创建默认管理员账号...")
        _create_default_admin()

        logging.info("系统初始化完成！")
        logging.info("=" * 80)
        print("[系统初始化] 系统初始化完成！")

    except Exception as e:
        logging.error(f"系统初始化失败: {e}", exc_info=True)
        print(f"[系统初始化] 错误: 系统初始化失败 - {e}")


SCHOOL_ACCOUNTS_DIR = "school_accounts"
SYSTEM_ACCOUNTS_DIR = "system_accounts"
LOGIN_LOGS_DIR = "logs"
SESSION_STORAGE_DIR = "sessions"
TOKENS_STORAGE_DIR = "tokens"
CONFIG_JSON_FILE = os.path.join("configs", "config.json")
CONFIG_JSON_ABS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), CONFIG_JSON_FILE
)
CONFIG_FILE = CONFIG_JSON_ABS_PATH
CONFIG_JSON_LOCK = threading.RLock()
JsonConfigAdapter.default_write_lock = CONFIG_JSON_LOCK
SCHOOL_ACCOUNT_EXECUTION_LOCK = threading.RLock()
SCHOOL_ACCOUNT_EXECUTION_CLAIMS: dict[str, object] = {}
SYSTEM_ACCOUNT_BILLING_LOCK = threading.RLock()


def _normalize_school_account_execution_identity(value) -> str:
    return str(value or "").strip().casefold()


def _claim_school_account_execution(identities, token) -> tuple[bool, str | None]:
    keys = {
        key
        for key in (
            _normalize_school_account_execution_identity(identity)
            for identity in identities
        )
        if key
    }
    if not keys:
        return True, None
    with SCHOOL_ACCOUNT_EXECUTION_LOCK:
        for key in keys:
            owner = SCHOOL_ACCOUNT_EXECUTION_CLAIMS.get(key)
            if owner is not None and owner is not token:
                return False, key
        for key in keys:
            SCHOOL_ACCOUNT_EXECUTION_CLAIMS[key] = token
    return True, None


def _extend_school_account_execution(identities, token) -> tuple[bool, str | None]:
    return _claim_school_account_execution(identities, token)


def _release_school_account_execution(token):
    if token is None:
        return
    with SCHOOL_ACCOUNT_EXECUTION_LOCK:
        for key, owner in list(SCHOOL_ACCOUNT_EXECUTION_CLAIMS.items()):
            if owner is token:
                del SCHOOL_ACCOUNT_EXECUTION_CLAIMS[key]
PERMISSIONS_FILE = "permissions.json"
# 自动签到配置文件
# 用于集中管理所有启用自动签到的学校账号配置
# 替代之前分散在各个INI文件中的auto_attendance_enabled参数
AUTO_ATTENDANCE_CONFIG_FILE = os.path.join(
    "configs", "auto_attendance_config.json")
THEME_DIR = "theme"
RANDOM_BACKGROUND_IMAGE_DIR = "random_background_image"
RANDOM_BACKGROUND_INDEX_FILE = os.path.join(RANDOM_BACKGROUND_IMAGE_DIR, "index.json")
background_state_store = BackgroundStateStore(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), RANDOM_BACKGROUND_IMAGE_DIR)
)


def _identity_key_for_username(username):
    return f"user:{str(username or '').strip()}"


def _bundle_to_public_payload(bundle):
    return {
        "bundle_id": bundle.get("bundle_id", ""),
        "revision": bundle.get("revision", 0),
        "pc": {
            "image_url": bundle.get("pc_image_url", ""),
            "revision": bundle.get("revision", 0),
        },
        "mobile": {
            "image_url": bundle.get("mobile_image_url", ""),
            "revision": bundle.get("revision", 0),
        },
    }


def _pick_available_background_image(target):
    normalized_target = "mobile" if target == "mobile" else "pc"
    if "auth_system" not in globals() or auth_system is None:
        return ""
    images = auth_system._peek_default_theme_background_images([normalized_target])
    return str(images.get(normalized_target) or "")


def _create_preview_bundle_payload():
    bundle = background_state_store.create_bundle(
        pc_url=_pick_available_background_image("pc"),
        mobile_url=_pick_available_background_image("mobile"),
        source="anonymous_preview",
        consume=False,
    )
    return {
        **_bundle_to_public_payload(bundle),
        "state": bundle.get("state", "preview"),
        "source": "anonymous_preview",
    }


def _consume_bundle_assignments(bundle):
    cache_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        RANDOM_BACKGROUND_IMAGE_DIR,
    )
    for image_url in (
        bundle.get("pc_image_url", ""),
        bundle.get("mobile_image_url", ""),
    ):
        if image_url:
            try:
                _mark_random_background_file_expired(cache_dir, image_url, expired=True)
            except Exception:
                logging.debug("标记背景图为已消耗失败: %s", image_url, exc_info=True)


def _bind_login_bundle_for_user(
    username,
    preview_bundle_id,
    source,
    replace_existing,
):
    identity_key = _identity_key_for_username(username)
    existing = background_state_store.get_identity_bundle(identity_key)
    bundle = (
        background_state_store.get_bundle(preview_bundle_id)
        if preview_bundle_id
        else None
    )
    # A login without a preview is not a request to rotate the user's image.
    # Reuse the persisted identity bundle before consulting the random cache.
    if not bundle and existing:
        return existing
    if not bundle:
        bundle = background_state_store.create_bundle(
            pc_url=_pick_available_background_image("pc"),
            mobile_url=_pick_available_background_image("mobile"),
            source=source,
            consume=True,
        )
    if existing and existing.get("bundle_id") == bundle.get("bundle_id"):
        return existing
    if existing and not replace_existing:
        return existing
    background_state_store.bind_identity(
        identity_key,
        bundle["bundle_id"],
        source,
    )
    _consume_bundle_assignments(bundle)
    auth_system._refresh_default_theme_background_cache_async(["pc", "mb"])
    return background_state_store.get_identity_bundle(identity_key)


def _bind_guest_bundle_for_session(
    session_id,
    preview_bundle_id,
    source,
    replace_existing,
):
    existing = background_state_store.get_guest_session_bundle(session_id)
    bundle = (
        background_state_store.get_bundle(preview_bundle_id)
        if preview_bundle_id
        else None
    )
    if not bundle and existing:
        return existing
    if not bundle:
        bundle = background_state_store.create_bundle(
            pc_url=_pick_available_background_image("pc"),
            mobile_url=_pick_available_background_image("mobile"),
            source=source,
            consume=True,
        )
    if existing and existing.get("bundle_id") == bundle.get("bundle_id"):
        return existing
    if existing and not replace_existing:
        return existing
    background_state_store.bind_guest_session(
        session_id,
        bundle["bundle_id"],
        source,
    )
    _consume_bundle_assignments(bundle)
    auth_system._refresh_default_theme_background_cache_async(["pc", "mb"])
    return background_state_store.get_guest_session_bundle(session_id)


def _resolve_user_theme_background(username):
    identity_key = _identity_key_for_username(username)
    bundle = background_state_store.get_identity_bundle(identity_key)
    if not bundle:
        bundle = _bind_login_bundle_for_user(
            username=username,
            preview_bundle_id="",
            source="uuid_fallback",
            replace_existing=False,
        )
    return _bundle_to_public_payload(bundle)


def _resolve_uuid_theme_background(session_id, username, is_guest):
    if is_guest:
        bundle = background_state_store.get_guest_session_bundle(session_id)
        if not bundle:
            bundle = _bind_guest_bundle_for_session(
                session_id=session_id,
                preview_bundle_id="",
                source="guest_uuid_fallback",
                replace_existing=False,
            )
        return _bundle_to_public_payload(bundle)
    return _resolve_user_theme_background(username)


def _resolve_identity_background_for_request_identity(identity):
    if not identity or not identity.get("authenticated"):
        return None
    if identity.get("principal_type") == "guest":
        session_id = str(identity.get("session_id") or "")
        return (
            background_state_store.get_guest_session_bundle(session_id)
            if session_id
            else None
        )
    username = str(identity.get("username") or "")
    return (
        background_state_store.get_identity_bundle(
            _identity_key_for_username(username)
        )
        if username
        else None
    )


def _apply_identity_bundle_to_theme_config(theme_config, session_id):
    if not isinstance(theme_config, dict) or not session_id:
        return theme_config
    state = load_session_state(session_id)
    if not isinstance(state, dict):
        return theme_config
    username = str(state.get("auth_username") or "")
    is_guest = bool(state.get("is_guest") or username == "guest")
    bundle = (
        background_state_store.get_guest_session_bundle(session_id)
        if is_guest
        else background_state_store.get_identity_bundle(
            _identity_key_for_username(username)
        )
    )
    if not bundle:
        return theme_config
    env = theme_config.setdefault("global_environment_variables", {})
    if bundle.get("pc_image_url"):
        env["auth_login_container_background"] = (
            "linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), "
            f'url("{bundle["pc_image_url"]}") center / cover no-repeat fixed'
        )
    if bundle.get("mobile_image_url"):
        env["mobile_auth_login_content_background"] = (
            "linear-gradient(rgba(255,255,255,0.12), rgba(255,255,255,0.12)), "
            f'url("{bundle["mobile_image_url"]}") center / cover no-repeat'
        )
    return theme_config


def _list_selectable_sessions_for_identity(identity):
    if not identity or not identity.get("authenticated"):
        return []
    if identity.get("principal_type") == "guest":
        session_id = str(identity.get("session_id") or "")
        if not session_id:
            return []
        return [{
            "session_id": session_id,
            "is_current": True,
            "is_guest": True,
            "login_success": True,
            "has_background_binding": bool(
                background_state_store.get_guest_session_bundle(session_id)
            ),
        }]
    username = str(identity.get("username") or "")
    if not username:
        return []
    identity_bundle = background_state_store.get_identity_bundle(
        _identity_key_for_username(username)
    )
    current_id = str(identity.get("session_id") or "")
    sessions = []
    for session_id in auth_system.get_user_sessions(username):
        state = load_session_state(session_id)
        if not state or state.get("auth_username") != username:
            continue
        sessions.append({
            "session_id": session_id,
            "is_current": session_id == current_id,
            "is_guest": False,
            "login_success": bool(state.get("login_success", False)),
            "last_activity": state.get("last_accessed", 0),
            "created_at": state.get("created_at", 0),
            "has_background_binding": bool(identity_bundle),
        })
    sessions.sort(
        key=lambda item: (
            0 if item["is_current"] else 1,
            -float(item.get("last_activity", 0) or 0),
        )
    )
    return sessions


def _build_site_bootstrap_response(session_id=""):
    identity = _resolve_request_identity()
    sessions = _list_selectable_sessions_for_identity(identity)
    bundle = _resolve_identity_background_for_request_identity(identity)
    bundle_source = (
        "identity_binding"
        if identity.get("principal_type") == "user"
        else "guest_binding"
    )
    # A stale auth cookie must not hide a still-valid UUID's persisted
    # background binding. Reading this state is intentionally read-only.
    requested_session_id = normalize_session_uuid(session_id)
    if not bundle and requested_session_id:
        state = load_session_state(requested_session_id)
        if isinstance(state, dict):
            username = str(state.get("auth_username") or "")
            is_guest = bool(state.get("is_guest") or username == "guest")
            bundle = (
                background_state_store.get_guest_session_bundle(requested_session_id)
                if is_guest
                else background_state_store.get_identity_bundle(
                    _identity_key_for_username(username)
                )
            )
            if bundle:
                bundle_source = "guest_binding" if is_guest else "identity_binding"
    theme_background = (
        {
            **_bundle_to_public_payload(bundle),
            "source": bundle_source,
        }
        if bundle
        else _create_preview_bundle_payload()
    )
    return {
        "success": True,
        "identity": {
            **identity,
            "quick_login_available": bool(sessions),
            "session_count": len(sessions),
        },
        "quick_login": {
            "available": bool(sessions),
            "sessions": sessions,
        },
        "theme_background": theme_background,
    }
THEME_METADATA_FIELDS = {"id", "label", "description", "placeholder"}
SESSION_INDEX_FILE = None
LOGIN_LOG_FILE = None
AUDIT_LOG_FILE = None


# ========================================================================
# [通用工具函数] 文件备份和重置功能
# 用于在遇到文件读取异常（特别是JSON解析错误）时自动备份损坏的文件并重置
# ========================================================================

def _backup_and_reset_corrupted_file(file_path, default_content="", file_type="json"):
    """
    备份损坏的文件并用默认内容重置

    功能说明：
        当文件读取异常（特别是JSON解析错误）时，此函数会：
        1. 创建 ./logs/backup/ 目录（如果不存在）
        2. 将损坏的文件复制到备份目录，文件名格式为：原文件名_时间戳.backup
        3. 根据文件类型，用默认内容覆写原文件
        4. 记录日志说明已备份和重置

    参数:
        file_path (str): 要备份的文件路径（绝对路径或相对路径）
        default_content: 重置后的默认内容
            - 对于JSON文件：可以是dict或list，函数会自动转换为JSON字符串
            - 对于ini文件：应该是字符串，可以是空字符串或默认配置文本
            - 对于text文件：应该是字符串
        file_type (str): 文件类型，可选值："json", "ini", "text"，默认为"json"

    返回值:
        bool: 如果成功备份并重置返回True，否则返回False

    异常处理：
        所有异常都会被捕获并记录到日志中，确保不会影响主业务逻辑

    示例:
        # JSON文件，默认内容为空字典
        _backup_and_reset_corrupted_file(os.path.join("configs", "config.json"), {}, "json")

        # JSON文件，默认内容为空列表
        _backup_and_reset_corrupted_file("messages.json", [], "json")

        # JSON文件，默认内容为空对象
        _backup_and_reset_corrupted_file(os.path.join("configs", "config.json"), {}, "json")
    """
    try:
        # 首先检查源文件是否存在
        # 如果文件不存在，则无需备份，直接返回False
        if not os.path.exists(file_path):
            logging.warning(f"[文件备份] 文件不存在，无需备份: {file_path}")
            return False

        # 创建备份目录：./logs/backup/
        # exist_ok=True 表示如果目录已存在不会报错
        backup_dir = os.path.join("logs", "backup")
        os.makedirs(backup_dir, exist_ok=True)

        # 生成备份文件名
        # 格式：原文件名（不含路径）_时间戳.backup
        # 例如：payment_methods_20251217_123045.json.backup
        base_name = os.path.basename(file_path)  # 获取文件名（不含路径）
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # 生成时间戳
        backup_filename = f"{base_name}_{timestamp}.backup"  # 组装备份文件名
        backup_path = os.path.join(backup_dir, backup_filename)  # 完整的备份文件路径

        # 使用 shutil.copy2() 复制文件到备份目录
        # copy2() 会同时复制文件内容和元数据（如时间戳、权限等）
        shutil.copy2(file_path, backup_path)
        logging.info(f"[文件备份] 已备份损坏文件: {file_path} -> {backup_path}")

        # 根据文件类型，准备要写入的内容
        if file_type == "json":
            # 对于JSON文件，需要将Python对象（dict或list）转换为JSON字符串
            # 如果default_content已经是字符串，直接使用；否则转换为JSON格式
            if isinstance(default_content, str):
                # 已经是字符串，直接使用
                content_to_write = default_content
            else:
                # 是dict或list，需要转换为JSON字符串
                # indent=2: 使用2个空格缩进，使输出更易读
                # ensure_ascii=False: 允许中文字符不被转义
                content_to_write = json.dumps(
                    default_content, indent=2, ensure_ascii=False)
        else:
            # 对于ini或text文件，default_content应该已经是字符串
            # 如果不是字符串，强制转换为字符串
            content_to_write = str(default_content) if not isinstance(
                default_content, str) else default_content

        # 用默认内容覆写原文件
        # 使用 'w' 模式会清空原文件内容并写入新内容
        # encoding='utf-8' 确保中文内容正确写入
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_to_write)

        # 记录重置操作的日志
        logging.info(f"[文件备份] 已用默认内容重置文件: {file_path}")

        # 操作成功，返回True
        return True

    except Exception as e:
        # 捕获所有可能的异常（文件操作失败、权限错误、磁盘空间不足等）
        # 记录错误日志，但不抛出异常，确保不影响主业务逻辑
        logging.error(f"[文件备份] 备份和重置文件失败 ({file_path}): {e}", exc_info=True)
        # 操作失败，返回False
        return False


# ========================================================================
# 自动签到配置管理函数
# 这些函数用于管理集中化的自动签到配置文件（JSON格式）
# 替代之前分散在各个INI文件中的auto_attendance_enabled参数
# ========================================================================



















def _create_directories():
    """
    创建程序运行所需的目录结构，目录路径从 config.json 配置文件读取。
    """
    global SCHOOL_ACCOUNTS_DIR, SYSTEM_ACCOUNTS_DIR, LOGIN_LOGS_DIR
    global SESSION_STORAGE_DIR, TOKENS_STORAGE_DIR
    global SESSION_INDEX_FILE, LOGIN_LOG_FILE, AUDIT_LOG_FILE

    default_dirs = {
        "school_accounts_dir": "school_accounts",
        "system_accounts_dir": "system_accounts",
        "log_dir": "logs",
        "sessions_dir": "sessions",
        "tokens_dir": "tokens",
    }

    config_file = os.path.join(os.path.dirname(__file__), CONFIG_JSON_FILE)
    if os.path.exists(config_file):
        try:
            config = _read_config_ini(config_file) or configparser.ConfigParser(strict=False)

            if config.has_section("System"):
                default_dirs["school_accounts_dir"] = config.get(
                    "System",
                    "school_accounts_dir",
                    fallback=default_dirs["school_accounts_dir"],
                )
                default_dirs["system_accounts_dir"] = config.get(
                    "System",
                    "system_accounts_dir",
                    fallback=default_dirs["system_accounts_dir"],
                )
                default_dirs["sessions_dir"] = config.get(
                    "System", "sessions_dir", fallback=default_dirs["sessions_dir"]
                )
                default_dirs["tokens_dir"] = config.get(
                    "System", "tokens_dir", fallback=default_dirs["tokens_dir"]
                )

            if config.has_section("Logging"):
                default_dirs["log_dir"] = config.get(
                    "Logging", "log_dir", fallback=default_dirs["log_dir"]
                )

            print(f"[配置读取] 成功从 config.json 读取目录配置")
        except Exception as e:
            print(f"[配置读取] 警告: 读取 config.json 失败，使用默认配置: {e}")
    else:
        print(f"[配置读取] config.json 不存在，使用默认目录配置")

    base_dir = os.path.dirname(__file__)
    SCHOOL_ACCOUNTS_DIR = os.path.join(
        base_dir, default_dirs["school_accounts_dir"])
    SYSTEM_ACCOUNTS_DIR = os.path.join(
        base_dir, default_dirs["system_accounts_dir"])
    LOGIN_LOGS_DIR = os.path.join(base_dir, default_dirs["log_dir"])
    SESSION_STORAGE_DIR = os.path.join(base_dir, default_dirs["sessions_dir"])
    TOKENS_STORAGE_DIR = os.path.join(base_dir, default_dirs["tokens_dir"])

    directories = {
        "school_accounts": SCHOOL_ACCOUNTS_DIR,
        "system_accounts": SYSTEM_ACCOUNTS_DIR,
        "theme": os.path.join(base_dir, THEME_DIR),
        "logs": LOGIN_LOGS_DIR,
        "sessions": SESSION_STORAGE_DIR,
        "tokens": TOKENS_STORAGE_DIR,
    }

    for name, directory in directories.items():
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"[目录创建] 创建目录: {name} -> {directory}")
            logging.info(f"[系统初始化] 创建目录: {name} -> {directory}")
        else:
            print(f"[目录创建] 目录已存在: {name} -> {directory}")

    user_accounts_dir = os.path.join(SCHOOL_ACCOUNTS_DIR, "user_accounts")
    if not os.path.exists(user_accounts_dir):
        os.makedirs(user_accounts_dir, exist_ok=True)
        print(f"[目录创建] 创建目录: user_accounts -> {user_accounts_dir}")
        logging.info(f"[系统初始化] 创建目录: user_accounts -> {user_accounts_dir}")
    else:
        print(f"[目录创建] 目录已存在: user_accounts -> {user_accounts_dir}")

    SESSION_INDEX_FILE = os.path.join(SESSION_STORAGE_DIR, "_index.json")
    LOGIN_LOG_FILE = os.path.join(LOGIN_LOGS_DIR, "login_history.jsonl")
    AUDIT_LOG_FILE = os.path.join(LOGIN_LOGS_DIR, "audit.jsonl")

    print(f"[目录创建] 所有目录创建完成")

    # 重建 system_accounts/_index.json 索引（用于快速查找用户文件）
    try:
        _rebuild_system_accounts_index()
        print(f"[系统账号索引] 索引重建完成")
    except Exception as _idx_e:
        print(f"[系统账号索引] 索引重建失败（将在运行时自动修复）: {_idx_e}")

    # 初始化各目录索引文件并迁移历史目录
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        _ensure_json_index_file(
            os.path.join(base_dir, "background_tasks", "_index.json"), "tasks"
        )
        _ensure_json_index_file(
            os.path.join(base_dir, "uploads", "_index.json"), "files"
        )
        _ensure_json_index_file(
            os.path.join(base_dir, "User_Billing", "_index.json"), "users"
        )
        _migrate_legacy_removed_accounts_dir()
    except Exception as _e:
        logging.warning(f"[目录创建] 初始化索引/迁移目录失败: {_e}")


def _rebuild_system_accounts_index():
    """
    重建 system_accounts/_index.json 索引文件。
    扫描所有 .json 文件（排除 _index.json 和子目录中的文件），
    读取每个文件的 auth_username，构建索引。
    """
    try:
        # 确保目录存在
        if not os.path.isdir(SYSTEM_ACCOUNTS_DIR):
            return
        
        accounts = {}
        # 遍历顶层目录中的所有JSON文件
        for filename in os.listdir(SYSTEM_ACCOUNTS_DIR):
            # 跳过 _index.json 本身
            if filename == "_index.json":
                continue
            # 只处理 .json 文件
            if not filename.endswith(".json"):
                continue
            # 跳过子目录（只处理直接在该目录下的文件）
            filepath = os.path.join(SYSTEM_ACCOUNTS_DIR, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                # 提取 auth_username
                au = user_data.get("auth_username")
                if au:
                    # 文件名（不含扩展名）即为哈希值
                    accounts[au] = filename[:-5]  # 去掉 .json 后缀
            except Exception as e:
                logging.warning(f"[系统账号索引] 读取文件 {filename} 失败: {e}")
        
        # 构建索引数据
        index_data = {
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "accounts": accounts
        }
        
        # 写入索引文件
        index_path = os.path.join(SYSTEM_ACCOUNTS_DIR, "_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"[系统账号索引] 重建索引完成，共 {len(accounts)} 个账号")
    except Exception as e:
        logging.error(f"[系统账号索引] 重建索引失败: {e}", exc_info=True)


def _ensure_json_index_file(index_path, root_key):
    """
    确保索引文件存在且结构合法。
    """
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        index_data = None
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    index_data = loaded
            except Exception:
                index_data = None
        if index_data is None:
            index_data = {}
        if root_key not in index_data or not isinstance(index_data.get(root_key), dict):
            index_data[root_key] = {}
        index_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[索引文件] 初始化失败: {index_path}, 错误: {e}")


def _migrate_legacy_removed_accounts_dir():
    """
    将历史删除账号目录迁移到新的 Remove_Acoount 目录。
    兼容旧目录：
      1) system_accounts/remove
      2) Remove_Account
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base_dir, "Remove_Acoount")
        legacy_dirs = [
            os.path.join(SYSTEM_ACCOUNTS_DIR, "remove"),
            os.path.join(base_dir, "Remove_Account"),
        ]
        os.makedirs(target_dir, exist_ok=True)
        for legacy_dir in legacy_dirs:
            if not os.path.isdir(legacy_dir):
                continue
            for fname in os.listdir(legacy_dir):
                src = os.path.join(legacy_dir, fname)
                dst = os.path.join(target_dir, fname)
                if not os.path.isfile(src):
                    continue
                if os.path.exists(dst):
                    continue
                try:
                    shutil.copy2(src, dst)
                except Exception as _e:
                    logging.warning(f"[删除账号迁移] 迁移文件失败: {src} -> {dst}, 错误: {_e}")
        _ensure_json_index_file(os.path.join(target_dir, "_index.json"), "removed_accounts")
    except Exception as e:
        logging.warning(f"[删除账号迁移] 迁移目录失败: {e}")


def _rebuild_background_tasks_index():
    """
    重建 background_tasks/_index.json（兼容旧版本无索引场景）。
    """
    try:
        task_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background_tasks")
        os.makedirs(task_dir, exist_ok=True)
        tasks = {}
        for filename in os.listdir(task_dir):
            if filename == "_index.json" or not filename.endswith(".json"):
                continue
            filepath = os.path.join(task_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    task_state = json.load(f)
                session_id = task_state.get("session_id")
                if not session_id:
                    continue
                task_hash = hashlib.sha256(session_id.encode()).hexdigest()
                tasks[task_hash] = {
                    "session_id": session_id,
                    "created_at": task_state.get("created_at", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    "file": filename
                }
            except Exception as _e:
                logging.warning(f"[后台任务迁移] 读取任务文件失败 {filename}: {_e}")

        index_path = os.path.join(task_dir, "_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tasks": tasks
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[后台任务迁移] 重建索引失败: {e}")


def _rebuild_uploads_index():
    """
    重建 uploads/_index.json（兼容旧版本无索引场景）。
    """
    try:
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        files = {}
        for filename in os.listdir(uploads_dir):
            if filename == "_index.json":
                continue
            filepath = os.path.join(uploads_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                stat = os.stat(filepath)
                files[filename] = {
                    "uploaded_at": datetime.datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "original_name": filename,
                    "size": stat.st_size
                }
            except Exception as _e:
                logging.warning(f"[上传迁移] 读取文件信息失败 {filename}: {_e}")

        index_path = os.path.join(uploads_dir, "_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "files": files
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[上传迁移] 重建索引失败: {e}")


def _rebuild_removed_accounts_index():
    """
    重建 Remove_Acoount/_index.json（兼容旧版本无索引场景）。
    """
    try:
        remove_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Remove_Acoount")
        os.makedirs(remove_dir, exist_ok=True)
        removed_accounts = {}
        for filename in os.listdir(remove_dir):
            if filename == "_index.json" or not filename.endswith(".json"):
                continue
            filepath = os.path.join(remove_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                auth_username = backup_data.get("auth_username")
                deleted_at = backup_data.get("deleted_at")
                if not auth_username:
                    continue
                removed_accounts[auth_username] = {
                    "backup_file": filename,
                    "deleted_at": deleted_at
                }
            except Exception as _e:
                logging.warning(f"[删除账号迁移] 读取备份文件失败 {filename}: {_e}")

        with open(os.path.join(remove_dir, "_index.json"), "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "removed_accounts": removed_accounts
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[删除账号迁移] 重建索引失败: {e}")


def _rebuild_user_billing_index():
    """
    重建 User_Billing/_index.json（自动迁移旧数据后便于统计）。
    """
    try:
        billing_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "User_Billing")
        os.makedirs(billing_root, exist_ok=True)
        users = {}
        for auth_username in os.listdir(billing_root):
            user_dir = os.path.join(billing_root, auth_username)
            if not os.path.isdir(user_dir):
                continue
            total = 0
            pending = 0
            paid = 0
            for filename in os.listdir(user_dir):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(user_dir, filename)
                if not os.path.isfile(filepath):
                    continue
                total += 1
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        record = json.load(f)
                    if record.get("status") == "paid":
                        paid += 1
                    else:
                        pending += 1
                except Exception:
                    pending += 1
            if total > 0:
                users[auth_username] = {
                    "total": total,
                    "pending": pending,
                    "paid": paid
                }

        with open(os.path.join(billing_root, "_index.json"), "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "users": users
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[账单迁移] 重建索引失败: {e}")


def _run_auto_data_migrations_from_main():
    """
    自动执行从旧 main 分支数据结构到当前版本的数据迁移（幂等）。
    """
    try:
        _migrate_legacy_removed_accounts_dir()
        _rebuild_system_accounts_index()
        _rebuild_removed_accounts_index()
        _rebuild_background_tasks_index()
        _rebuild_uploads_index()
        _rebuild_user_billing_index()
        logging.info("[自动迁移] 旧版数据结构自动迁移完成")
    except Exception as e:
        logging.warning(f"[自动迁移] 执行失败: {e}")


def _update_system_accounts_index(auth_username, hash_filename, action):
    """
    增量更新 system_accounts/_index.json 索引文件。
    
    参数:
        auth_username: 用户名
        hash_filename: 哈希文件名（不含 .json 后缀），action为"remove"时可为None
        action: "add" 或 "remove"
    """
    try:
        index_path = os.path.join(SYSTEM_ACCOUNTS_DIR, "_index.json")
        
        # 读取现有索引（如果存在）
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
            except Exception:
                index_data = {"accounts": {}}
        else:
            index_data = {"accounts": {}}
        
        # 确保 accounts 字段存在
        if "accounts" not in index_data:
            index_data["accounts"] = {}
        
        if action == "add" and hash_filename:
            # 添加或更新用户条目
            index_data["accounts"][auth_username] = hash_filename
            logging.debug(f"[系统账号索引] 添加用户到索引: {auth_username}")
        elif action == "remove":
            # 从索引中移除用户条目
            if auth_username in index_data["accounts"]:
                del index_data["accounts"][auth_username]
                logging.debug(f"[系统账号索引] 从索引移除用户: {auth_username}")
        
        # 更新时间戳
        index_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # 写入索引文件
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"[系统账号索引] 更新索引失败 (action={action}, user={auth_username}): {e}", exc_info=True)


def _get_default_config():
    """
    获取默认配置项字典。
    """
    config = configparser.ConfigParser(strict=False)

    config["Admin"] = {"super_admin": "admin"}

    config["Config"] = {
        "default_ui": "old",
        "frontend_mode": "original",
    }

    config["Guest"] = {
        "allow_guest_login": "true",
        "max_active_guest_sessions": "100",
        "guest_session_inactivity_timeout": "300",
        "guest_token_ttl_seconds": "3600",
        "guest_token_grace_seconds": "60",
    }

    config["System"] = {
        "session_expiry_days": "7",
        "school_accounts_dir": "school_accounts",
        "system_accounts_dir": "system_accounts",
        "sessions_dir": "sessions",
        "tokens_dir": "tokens",
        "permissions_file": "permissions.json",
        "session_monitor_check_interval": "60",
        "session_inactivity_timeout": "300",
    }

    config["Logging"] = {
        "log_rotation_size_mb": "10",
        "log_backup_count": "10",
        "archive_max_size_mb": "5120",
        "random_background_cache_max_size_mb": "1024",
        "log_dir": "logs",
        "archive_dir": "logs/archive",
    }

    config["Security"] = {
        "password_storage": "plaintext",
        "brute_force_protection": "true",
        "login_log_retention_days": "90",
    }

    config["Daily_Restart"] = {
        "enabled": "false",
        "time": "00:00",
    }

    config["Map"] = {
        "provider": "amap",
        "amap_js_key": "",
        "tencent_map_key": "",
        "tianditu_token": "",
        "baidu_map_ak": "",
    }

    config["IP_Location"] = {
        # 查询顺序（逗号分隔）：默认 UapiPro -> 高德 -> 百度
        "query_order": "uapipro,amap,baidu",
        # 高德 Web API Key（IP定位）
        "amap_web_api_key": "",
        # UapiPro API Key（Bearer）
        "uapipro_api_key": "",
    }

    config["IP_Location"] = {
        # 查询顺序（逗号分隔）：默认 UapiPro -> 高德 -> 百度
        "query_order": "uapipro,amap,baidu",
        # 高德 Web API Key（IP定位）
        "amap_web_api_key": "",
        # UapiPro API Key（Bearer）
        "uapipro_api_key": "",
    }

    config["Captcha"] = {
        "length": "4",
        "scale_factor": "2",
        "noise_level": "0.08",
    }

    config["CDN"] = {
        "cdn_enabled": "true",
        "cache_time": "3600",
    }

    config["Features"] = {
        "enable_phone_modification": "false",
        "enable_phone_login": "false",
        "enable_phone_registration_verify": "false",
        "enable_sms_service": "false",
        "account_cancellation_wait_hours": "24",
    }

    config["SMS_Service_SMSBao"] = {
        "username": "",
        "api_key": "",
        "signature": "【电科大跑步助手】",
        "template_register": "您的验证码是：{code}，{minutes}分钟内有效。",
        "code_expire_minutes": "5",
        "send_interval_seconds": "180",
        "rate_limit_per_account_day": "10",
        "rate_limit_per_ip_day": "20",
        "rate_limit_per_phone_day": "5",
    }

    # 备案信息配置节，用于配置网站的ICP备案号和公安网备案号信息
    # 这些信息通常需要在网站底部显示，以符合中国互联网信息服务的法律要求
    config["Beian"] = {
        # ICP备案号：由中国工信部颁发的互联网信息服务备案编号
        # 格式示例："京ICP备12345678号"，留空则表示未备案或不显示
        "icp_number": "",
        # 是否显示ICP备案信息：控制ICP备案号是否在网站底部显示
        # 取值："true" 表示显示，"false" 表示不显示（默认不显示）
        "show_icp": "false",
        # 公安网备案号：由中国公安部门颁发的网络安全备案编号
        # 格式示例："京公网安备 11010802012345号"，留空则表示未备案或不显示
        "police_number": "",
        # 是否显示公安网备案信息：控制公安网备案号是否在网站底部显示
        # 取值："true" 表示显示，"false" 表示不显示（默认不显示）
        "show_police": "false",
    }

    # 百度云文本审核服务配置节，用于配置百度云API的访问凭证
    # 百度云文本审核服务可以检测用户提交的文本内容是否包含违规信息（如色情、暴力、政治敏感等）
    config["baidu_cloud"] = {
        # API Key：在百度云控制台创建应用后获取的API密钥（必填）
        "api_key": "",
        # Secret Key：在百度云控制台创建应用后获取的密钥（必填）
        "secret_key": "",
        # 策略ID：自定义审核策略的ID（可选，留空则使用百度云默认审核策略）
        "strategy_id": "",
    }

    # 内容审核功能配置节，用于控制是否启用留言内容审核
    # 此配置项决定是否在用户发表留言时调用百度云文本审核服务进行内容检测
    config["Content_Review"] = {
        # 是否启用留言内容审核（true/false）
        # true：启用审核，留言将通过百度云文本审核服务检测后才能发布
        # false：不启用审核，留言直接发布（默认值）
        # 注意：启用此功能需要先在[baidu_cloud]配置节中配置有效的API密钥
        "enable_message_review": "false",
    }

    # 彩虹易支付V2配置节，用于配置在线支付接口参数
    # 彩虹易支付是一个第三方支付平台，支持支付宝、微信支付等多种支付方式
    # 使用前需要在彩虹易支付平台注册商户账号并获取相关参数
    config["Rainbow_YiPay"] = {
        # 易支付接口域名：彩虹易支付平台提供的API接口地址（必填）
        # 格式示例："https://api.example.com" 或 "https://pay.yourdomain.com"
        # 注意：请填写完整的域名地址，包含 http:// 或 https:// 协议头，不要在末尾添加斜杠
        "host": "",
        # 商户ID（PID）：在彩虹易支付平台注册后获取的唯一商户标识（必填）
        # 格式：通常为纯数字，例如 "10001"
        "pid": "",
        # 商户私钥（KEY）：在彩虹易支付平台获取的商户RSA私钥（必填）
        # 这是一个重要的安全参数，用于对发送给支付平台的请求进行RSA签名，请妥善保管，切勿泄露
        # 格式：PEM格式的RSA私钥字符串
        # 示例：-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----
        # 用途：商户使用私钥对请求参数签名，平台使用商户公钥验证签名
        "key": "",
        # 应用域名地址：用于自动设置return_url和notify_url的域名前缀（可选）
        # 格式示例："https://yourdomain.com" 或 "https://run.zelly.cn"
        # 如果配置了此项，系统将自动拼接完整的回调地址（如：https://yourdomain.com/api/payment/yipay/notify）
        # 如果留空，则使用前端传入的app_host参数
        # 注意：必须包含协议头（http:// 或 https://），末尾不要添加斜杠
        "app_host": "",
        # 平台公钥（RSA公钥）：彩虹易支付平台的RSA公钥（必填）
        # 格式：PEM格式的RSA公钥字符串
        # 用途：在收到支付平台的异步通知时，使用此公钥验证平台的签名，确保通知的真实性和完整性
        # 说明：平台使用私钥对回调通知签名，商户使用平台公钥验证签名
        # 示例：-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhki...\n-----END PUBLIC KEY-----
        # 注意：必须配置此公钥，否则无法验证支付回调通知的真实性
        "pubc_key": "",
        # 商品ID：用于标识商品类型的唯一标识符
        # 格式：整数，例如 "1001"
        # 默认值：1001（跑步助手服务）
        # 用途：在支付记录中区分不同类型的商品或服务
        "product_id": "1001",
        # 启用的支付方式：管理员可配置的支付方式列表
        # 格式：使用逗号分隔的支付方式代码字符串
        # 支持的支付方式：
        #   - alipay: 支付宝支付（推荐，覆盖率最高）
        #   - wxpay: 微信支付（移动端常用）
        #   - bank: 网银支付（适合大额支付）
        # 示例：
        #   - "alipay,wxpay"         启用支付宝和微信支付
        #   - "alipay,wxpay,bank"    启用所有支付方式
        #   - "alipay"               只启用支付宝支付
        # 默认值："alipay,wxpay" 启用支付宝和微信支付
        # 注意：
        #   1. 启用的支付方式必须在您的易支付商户后台已开通
        #   2. 前端创建订单时会验证支付方式是否在启用列表中
        #   3. 修改此配置后无需重启服务器，下次创建订单时生效
        "enabled_payment_methods": "alipay,wxpay",
        # 注意：支付方式详细配置（payment_methods_config）已迁移到独立的 payment_methods.json 文件
        # 如需修改支付方式的名称、图标、描述等信息，请直接编辑 payment_methods.json 文件
        # 支付超时时间（秒）：订单创建后多长时间内未支付视为超时
        # 格式：整数，单位为秒
        # 默认值：900（15分钟）
        # 用途：用于标记超时未支付的订单，便于系统自动关闭或提醒用户
        # 注意：
        #   1. 此配置仅用于本地订单超时判断，不影响易支付平台的订单有效期
        #   2. 建议设置为10-3600秒之间
        "payment_timeout_minutes": "900",
    }

    # ============================================================
    # [Payment_Settings] 支付费用配置节
    # ============================================================
    # 此配置节用于设置跑步任务的费用标准和新用户初始免费次数
    # 当用户欠费时，系统将根据此配置计算需要缴纳的金额
    config["Payment_Settings"] = {
        # 是否需要付费（true/false）
        # true：启用付费模式，用户需要支付才能使用跑步服务
        # false：免费模式，所有用户可无限次使用，不扣除次数，不产生欠费
        # 默认值：true（需要付费）
        # 注意：当设置为false时，或者single_run_cost<=0时，系统将跳过所有付费相关逻辑
        "require_payment": "true",
        # 单次跑步任务费用（单位：元）
        # 用于计算用户欠费金额 = 欠费次数 × single_run_cost
        # 默认值：1.0元/次
        # 管理员可根据实际情况调整此费用
        # 注意：
        # 1. 修改后仅对新产生的欠费生效，已有订单不受影响
        # 2. 设置为0或负数时，相当于关闭付费功能，所有用户可免费使用
        "single_run_cost": "1.0",
        # 新用户注册时获得的默认免费次数（整数）
        # 用于在用户注册时自动设置available_runs字段的初始值
        # 默认值：10次
        # 特殊值：
        # - 0：新用户无免费次数，需要管理员手动分配或立即付费
        # - -1：新用户获得无限次数（不推荐，除非完全免费模式）
        # - 正整数：新用户获得指定次数的免费使用额度
        # 示例：
        # - 设置为10：新用户注册后可免费使用10次
        # - 设置为0：新用户注册后需要购买次数才能使用
        # 注意：
        # 1. 此配置仅影响新注册用户，已注册用户不受影响
        # 2. 管理员可随时通过用户管理面板修改个别用户的可用次数
        # 3. 此值会在注册页面的提示文本中显示（如："注册即可得 {available_runs} 次校园跑"）
        "default_available_runs": "2",
    }

    # ============================================================
    # [Profile_Display] 个人资料显示配置节
    # ============================================================
    # 此配置节用于控制个人资料页面中available_runs（剩余免费次数）的显示行为
    config["Profile_Display"] = {
        # 是否在个人资料页面显示剩余免费次数（true/false）
        # true：在个人资料页面显示available_runs字段
        # false：不显示available_runs字段
        # 默认值：true（显示）
        "show_available_runs": "true",
        # 剩余免费次数的显示格式（字符串模板）
        # 使用 {available_runs} 作为占位符，将被替换为实际的剩余次数数值
        # 示例：
        #   - "剩余免费次数：{available_runs} 次"  （默认格式）
        #   - "您还有 {available_runs} 次免费跑步机会"
        #   - "Free runs left: {available_runs}"
        # 默认值："剩余免费次数：{available_runs} 次"
        "available_runs_format": "剩余免费次数：{available_runs} 次",
    }

    # ============================================================
    # [Registration_Display] 注册页面显示配置节
    # ============================================================
    # 此配置节用于控制注册页面中关于available_runs（初始免费次数）的提示信息
    config["Registration_Display"] = {
        # 是否在注册页面显示免费次数提示（true/false）
        # true：在注册表单中显示初始免费次数的提示信息
        # false：不显示提示信息
        # 默认值：true（显示）
        "show_available_runs_on_register": "true",
        # 注册页面的免费次数提示文本（字符串模板）
        # 使用 {available_runs} 作为占位符，将被替换为新用户注册时获得的初始免费次数
        # 此数值从配置文件的 [Payment_Settings].default_available_runs 读取
        # 示例：
        #   - "注册即可得 {available_runs} 次校园跑"  （默认格式）
        #   - "新用户福利：{available_runs} 次免费跑步"
        #   - "Sign up and get {available_runs} free runs!"
        # 默认值："注册即可得 {available_runs} 次校园跑"
        # 注意：此提示文本通常显示在注册按钮附近或表单顶部，用于吸引用户注册
        "register_available_runs_hint": "注册即可得 {available_runs} 次校园跑",
    }

    # 新手帮助配置节：控制桌面端新手帮助按钮显示与跳转
    config["Help"] = {
        # 是否在桌面端显示新手帮助悬浮按钮（true/false）
        # true：显示悬浮按钮并允许跳转；false：不显示
        "show_newbie_help": "false",
        # 新手帮助跳转地址（完整URL，留空表示不跳转）
        "newbie_help_url": "",
    }

    return config


def _write_config_with_comments(config_obj, filepath):
    """
    将配置写入文件，包含详细的中文注释。

    由于ConfigParser不保留注释，这个函数手动写入带注释的配置文件。
    当 filepath 以 ".json" 结尾，或 config_obj 是 JsonConfigAdapter 实例时，
    直接调用 JsonConfigAdapter.save() 保存为 JSON 格式。
    同时，如果 ./configs/config.json 已存在，也同步更新它。
    """
    resolved_filepath = filepath
    if isinstance(resolved_filepath, str) and str(resolved_filepath).endswith(".json"):
        if not os.path.isabs(resolved_filepath):
            resolved_filepath = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), resolved_filepath
            )

    # ── JSON 快速路径 ─────────────────────────────────────────────────────
    _is_json_adapter = isinstance(config_obj, JsonConfigAdapter)
    _is_json_file = str(resolved_filepath).endswith(".json")
    if _is_json_adapter or _is_json_file:
        with CONFIG_JSON_LOCK:
            if _is_json_adapter:
                config_obj._path = resolved_filepath
                config_obj.save()
            else:
                # 将 configparser 对象序列化为 JSON（合并写入，避免覆盖未修改配置）
                data = {}
                try:
                    if os.path.exists(resolved_filepath):
                        with open(resolved_filepath, "r", encoding="utf-8") as _jf:
                            existing_data = json.load(_jf)
                        if isinstance(existing_data, dict):
                            for _sec, _opts in existing_data.items():
                                if isinstance(_opts, dict):
                                    data[_sec] = {
                                        _k: str(_v) for _k, _v in _opts.items()
                                    }
                                else:
                                    data[_sec] = {}
                except Exception as _merge_err:
                    logging.warning(
                        f"[配置写入] 读取现有 JSON 配置用于合并失败，将继续仅写入传入配置: {_merge_err}"
                    )
                for sec in config_obj.sections():
                    data[sec] = dict(config_obj.items(sec))

                abs_filepath = os.path.abspath(resolved_filepath)
                parent_dir = os.path.dirname(abs_filepath) or "."
                os.makedirs(parent_dir, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", delete=False, dir=parent_dir, suffix=".tmp"
                ) as _tmpf:
                    json.dump(data, _tmpf, indent=2, ensure_ascii=False)
                    tmp_path = _tmpf.name
                os.replace(tmp_path, abs_filepath)
        return

    # ── 同步更新 JSON 配置（如果 JSON 文件已存在）─────────────────────────
    _json_cfg_path = CONFIG_JSON_FILE if "CONFIG_JSON_FILE" in globals() else None
    if _json_cfg_path and os.path.exists(_json_cfg_path):
        try:
            _jadapter = JsonConfigAdapter(_json_cfg_path)
            for _sec in config_obj.sections():
                if not _jadapter.has_section(_sec):
                    _jadapter.add_section(_sec)
                for _k, _v in config_obj.items(_sec):
                    _jadapter.set(_sec, _k, _v)
            _jadapter.save()
        except Exception as _je:
            logging.warning(f"[配置同步] 同步 JSON 配置失败（非致命）: {_je}")

    try:
        # strict=False：允许读取包含重复节的配置文件，避免因config.ini历史原因存在重复节时抛出DuplicateSectionError
        existing_config = configparser.ConfigParser(strict=False)
        if os.path.exists(filepath):
            existing_config.read(filepath, encoding="utf-8")
            for section in existing_config.sections():
                if not config_obj.has_section(section):
                    config_obj.add_section(section)
                for key, value in existing_config.items(section, raw=True):
                    if not config_obj.has_option(section, key):
                        config_obj.set(section, key, value)
    except Exception as e:
        logging.warning(f"读取配置文件用于补全缺失项失败: {e}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# ========================================\n")
        f.write("# 跑步工具配置文件\n")
        f.write("# ========================================\n")
        f.write("# 说明：修改配置后需要重启程序生效\n")
        f.write("# ========================================\n\n")

        # 写入 [Config] 节，确保 theme_style 等全局参数被持久化
        if config_obj.has_section("Config") or config_obj.has_option(
            "Config", "theme_style"
        ):
            f.write("[Config]\n")
            f.write("# 全局配置参数 (主题、自动签到等)\n")

            # 优先写入已知的重要参数
            known_keys = [
                "theme_base_color",
                "theme_style",
                "auto_attendance_stop_after_success",
                "auto_attendance_success_limit",
                "auto_attendance_refresh_s",
                "attendance_user_radius_m",
            ]

            # 如果config_obj中有这些节，则写入
            if config_obj.has_section("Config"):
                for key, value in config_obj.items("Config"):
                    f.write(f"{key} = {value}\n")
            f.write("\n")

        f.write("[Admin]\n")
        f.write("# 超级管理员账号名称（有且只有一个）\n")
        f.write("# 注意：super_admin 只能在此配置文件中设置，不能在界面创建\n")
        f.write("# 默认管理员账号将在首次启动时创建，首次登录后请立即修改密码\n")
        f.write(
            f"super_admin = {config_obj.get('Admin', 'super_admin', fallback='admin')}\n\n"
        )

        f.write("[Guest]\n")
        f.write("# 是否允许游客登录（true/false）\n")
        f.write("# true：允许未注册用户以游客身份使用系统（权限受限）\n")
        f.write("# false：禁止游客登录，所有用户必须注册\n")
        f.write(
            f"allow_guest_login = {config_obj.get('Guest', 'allow_guest_login', fallback='true')}\n\n"
        )
        f.write("# 最大活跃访客会话数（0 表示禁止创建）\n")
        f.write(
            f"max_active_guest_sessions = {config_obj.get('Guest', 'max_active_guest_sessions', fallback='100')}\n"
        )
        f.write("# 访客会话闲置超时，单位秒\n")
        f.write(
            f"guest_session_inactivity_timeout = {config_obj.get('Guest', 'guest_session_inactivity_timeout', fallback='300')}\n"
        )
        f.write("# 访客 Token 最小有效期，单位秒\n")
        f.write(
            f"guest_token_ttl_seconds = {config_obj.get('Guest', 'guest_token_ttl_seconds', fallback='3600')}\n"
        )
        f.write("# Token 至少比访客会话多保持的时间，单位秒\n")
        f.write(
            f"guest_token_grace_seconds = {config_obj.get('Guest', 'guest_token_grace_seconds', fallback='60')}\n\n"
        )

        f.write("[System]\n")
        f.write("# 会话过期时间（天）\n")
        f.write("# 超过此时间未访问的会话将自动清理\n")
        f.write(
            f"session_expiry_days = {config_obj.get('System', 'session_expiry_days', fallback='7')}\n"
        )
        f.write("# 学校账号数据存储目录\n")
        f.write(
            f"school_accounts_dir = {config_obj.get('System', 'school_accounts_dir', fallback='school_accounts')}\n"
        )
        f.write("# 系统账号数据存储目录\n")
        f.write(
            f"system_accounts_dir = {config_obj.get('System', 'system_accounts_dir', fallback='system_accounts')}\n"
        )
        f.write("# 权限配置文件路径\n")
        f.write(
            f"permissions_file = {config_obj.get('System', 'permissions_file', fallback='permissions.json')}\n"
        )

        f.write("# 会话持久化数据存储目录\n")
        f.write(
            f"sessions_dir = {config_obj.get('System', 'sessions_dir', fallback='sessions')}\n"
        )
        f.write("# API令牌数据存储目录\n")
        f.write(
            f"tokens_dir = {config_obj.get('System', 'tokens_dir', fallback='tokens')}\n"
        )

        f.write("# 会话监控检查间隔时间（秒）\n")
        f.write("# 系统每隔此时间检查一次会话活跃状态，默认60秒\n")
        f.write(
            f"session_monitor_check_interval = {config_obj.get('System', 'session_monitor_check_interval', fallback='60')}\n"
        )
        f.write("# 会话不活跃超时时间（秒）\n")
        f.write(
            "# 会话超过此时间无活动（且无正在执行的任务）将被自动清理，默认300秒（5分钟）\n"
        )
        f.write(
            f"session_inactivity_timeout = {config_obj.get('System', 'session_inactivity_timeout', fallback='300')}\n\n"
        )

        # [Logging] 配置
        f.write("[Logging]\n")
        f.write("# 单个日志文件最大大小（MB）\n")
        f.write("# 超过此大小时会把当前日志改名为下一个编号（如 zx-slm-tool-01.log）\n")
        f.write("# 编号从 01 开始递增，01 最旧、编号越大越新；历史文件不会被搬动\n")
        f.write(
            f"log_rotation_size_mb = {config_obj.get('Logging', 'log_rotation_size_mb', fallback='10')}\n"
        )
        f.write("# 历史日志最多保留多少个（按编号从最旧开始删除）\n")
        f.write(
            f"log_backup_count = {config_obj.get('Logging', 'log_backup_count', fallback='10')}\n"
        )
        f.write("# 归档目录最大大小（MB）\n")
        f.write("# 超过此大小时会删除最早的归档文件，设置为0表示不限制\n")
        f.write(
            f"archive_max_size_mb = {config_obj.get('Logging', 'archive_max_size_mb', fallback='5120')}\n"
        )
        f.write("# 主题随机背景缓存目录最大大小（MB）\n")
        f.write("# 超过此大小时会删除 random_background_image 中最早的缓存文件，设置为0表示不限制\n")
        f.write(
            f"random_background_cache_max_size_mb = {config_obj.get('Logging', 'random_background_cache_max_size_mb', fallback='1024')}\n"
        )
        f.write("# 日志文件存储目录\n")
        f.write(
            f"log_dir = {config_obj.get('Logging', 'log_dir', fallback='logs')}\n")
        f.write("# 日志归档目录（启动时会自动压缩旧日志到此目录）\n")
        f.write(
            f"archive_dir = {config_obj.get('Logging', 'archive_dir', fallback='logs/archive')}\n\n"
        )

        # [Security] 配置
        f.write("[Security]\n")
        f.write("# 密码存储方式（plaintext/sha256/bcrypt）\n")
        f.write("# plaintext：明文存储（不推荐，仅用于测试）\n")
        f.write("# sha256：SHA256哈希（已弃用，不够安全）\n")
        f.write("# bcrypt：bcrypt加密（推荐，自动加盐，抗暴力破解）\n")
        f.write(
            f"password_storage = {config_obj.get('Security', 'password_storage', fallback='plaintext')}\n"
        )
        f.write("# 是否启用暴力破解防护（true/false）\n")
        f.write("# true：启用登录尝试限制和账号临时锁定\n")
        f.write(
            f"brute_force_protection = {config_obj.get('Security', 'brute_force_protection', fallback='true')}\n"
        )
        f.write("# 登录日志保留天数\n")
        f.write("# 超过此时间的登录审计日志将被清理\n")
        f.write(
            f"login_log_retention_days = {config_obj.get('Security', 'login_log_retention_days', fallback='90')}\n\n"
        )

        # [Map] 配置
        f.write("[Map]\n")
        f.write("# 高德地图 JS API 密钥\n")
        f.write("# 用于前端地图显示，请在高德开放平台申请：https://console.amap.com/\n")
        f.write("# 申请类型：Web端(JS API)，服务平台：Web端\n")
        f.write(
            f"amap_js_key = {config_obj.get('Map', 'amap_js_key', fallback='')}\n\n"
        )

        # ========================================
        # [CDN] CDN缓存配置
        # ========================================
        f.write("# ========================================\n")
        f.write("# CDN缓存配置\n")
        f.write("# ========================================\n")
        f.write("[CDN]\n")
        f.write("# 是否启用CDN缓存（true/false）\n")
        f.write("# true：启用CDN缓存，提高静态资源加载速度\n")
        f.write("# false：禁用CDN缓存，所有资源直接从服务器获取\n")
        f.write(
            f"cdn_enabled = {config_obj.get('CDN', 'cdn_enabled', fallback='false')}\n"
        )
        f.write("# CDN缓存时间（秒）\n")
        f.write("# 设置静态资源在CDN上的缓存有效期\n")
        f.write("# 建议值：3600（1小时）、21600（6小时）、86400（24小时）\n")
        f.write(
            f"cache_time = {config_obj.get('CDN', 'cache_time', fallback='3600')}\n\n"
        )

        # ========================================
        # [Captcha] 本地验证码生成器配置
        # ========================================
        f.write("# ========================================\n")
        f.write("# 本地验证码生成器配置\n")
        f.write("# ========================================\n")
        f.write("# 使用MicroPixelCaptcha生成黑白像素风格验证码\n")
        f.write("# 无需第三方API，更稳定、更安全、响应更快\n")
        f.write("# ========================================\n\n")
        f.write("[Captcha]\n")
        f.write("# 验证码字符数（3-6）\n")
        f.write(
            f"length = {config_obj.get('Captcha', 'length', fallback='4')}\n")
        f.write("# 像素细分倍数（2-32）\n")
        f.write(
            f"scale_factor = {config_obj.get('Captcha', 'scale_factor', fallback='2')}\n"
        )
        f.write("# 噪点比例（0.0-0.3）\n")
        f.write(
            f"noise_level = {config_obj.get('Captcha', 'noise_level', fallback='0.08')}\n\n"
        )

        # [Features] 功能开关配置
        f.write("[Features]\n")
        f.write("# 是否允许用户修改手机号（true/false）\n")
        f.write("# true：用户可在个人资料中修改手机号\n")
        f.write(
            f"enable_phone_modification = {config_obj.get('Features', 'enable_phone_modification', fallback='false')}\n"
        )
        f.write("# 是否支持手机号登录（true/false）\n")
        f.write("# true：用户可使用手机号+密码登录（手机号作为login_id）\n")
        f.write(
            f"enable_phone_login = {config_obj.get('Features', 'enable_phone_login', fallback='false')}\n"
        )
        f.write("# 注册时是否需要短信验证（true/false）\n")
        f.write("# true：用户注册时必须填写手机号并通过短信验证码验证\n")
        f.write(
            f"enable_phone_registration_verify = {config_obj.get('Features', 'enable_phone_registration_verify', fallback='false')}\n"
        )
        f.write("# 短信服务总开关（true/false）\n")
        f.write("# false：关闭所有短信功能，即使其他选项为true也不会发送短信\n")
        f.write(
            f"enable_sms_service = {config_obj.get('Features', 'enable_sms_service', fallback='false')}\n"
        )
        f.write("# 账号注销申请的冷静期（小时），默认 24 小时\n")
        f.write("# 用户申请注销后，在等待期内登录可撤销注销\n")
        f.write(
            f"account_cancellation_wait_hours = {config_obj.get('Features', 'account_cancellation_wait_hours', fallback='24')}\n\n"
        )

        # [SMS_Service_SMSBao] 短信宝服务配置
        f.write("[SMS_Service_SMSBao]\n")
        f.write("# 短信宝服务配置（官网：https://www.smsbao.com/）\n")
        f.write("# 用于发送验证码、通知等短信\n")
        f.write("# 注意：使用前需要在短信宝注册账号并配置账户余额\n")
        f.write("# 短信宝账户用户名\n")
        f.write(
            f"username = {config_obj.get('SMS_Service_SMSBao', 'username', fallback='')}\n"
        )
        f.write("# 短信宝API密钥（在短信宝后台获取）\n")
        f.write(
            f"api_key = {config_obj.get('SMS_Service_SMSBao', 'api_key', fallback='')}\n"
        )
        f.write("# 短信签名（需提前在短信宝审核通过，格式：【签名内容】）\n")
        f.write(
            f"signature = {config_obj.get('SMS_Service_SMSBao', 'signature', fallback='【电科大跑步助手】')}\n"
        )
        f.write(
            "# 注册验证码短信模板（{code}会被替换为验证码，{minutes}会被替换为有效期分钟数）\n"
        )
        f.write(
            f"template_register = {config_obj.get('SMS_Service_SMSBao', 'template_register', fallback='您的验证码是：{{code}}，{{minutes}}分钟内有效。')}\n"
        )
        f.write("# 验证码有效期（分钟），默认5分钟，管理员可根据需要修改\n")
        f.write(
            f"code_expire_minutes = {config_obj.get('SMS_Service_SMSBao', 'code_expire_minutes', fallback='5')}\n"
        )
        f.write("# 发送间隔（秒），默认180秒（3分钟），防止频繁发送，增强安全性\n")
        f.write(
            f"send_interval_seconds = {config_obj.get('SMS_Service_SMSBao', 'send_interval_seconds', fallback='180')}\n"
        )
        f.write("# 单个账号每天最多发送次数（防止滥用）\n")
        f.write(
            f"rate_limit_per_account_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_account_day', fallback='10')}\n"
        )
        f.write("# 单个IP每天最多发送次数（防止攻击）\n")
        f.write(
            f"rate_limit_per_ip_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_ip_day', fallback='20')}\n"
        )
        f.write("# 单个手机号每天最多发送次数（防止骚扰）\n")
        f.write(
            f"rate_limit_per_phone_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_phone_day', fallback='5')}\n\n"
        )

        # [Help] 新手帮助配置节 (用于控制桌面端悬浮按钮显示与跳转)
        f.write("[Help]\n")
        f.write("# 是否在桌面端显示新手帮助悬浮按钮（true/false）\n")
        f.write("# true：在桌面端页面左上角显示悬浮帮助按钮，点击后弹出拟态确认框并可跳转；\n")
        f.write("# false：不显示悬浮按钮\n")
        f.write(
            f"show_newbie_help = {config_obj.get('Help', 'show_newbie_help', fallback='false')}\n"
        )
        f.write("# 新手帮助跳转地址（完整URL，留空表示无跳转）\n")
        f.write(
            f"newbie_help_url = {config_obj.get('Help', 'newbie_help_url', fallback='')}\n\n"
        )
        # [SSL] 配置 - 新增SSL配置节的写入逻辑
        f.write("[SSL]\n")
        f.write("# SSL/HTTPS 配置\n")
        f.write("# 是否启用SSL（true/false）\n")
        f.write("# true：启用HTTPS协议访问\n")
        f.write("# false：使用HTTP协议访问\n")
        f.write(
            f"ssl_enabled = {config_obj.get('SSL', 'ssl_enabled', fallback='false')}\n"
        )
        f.write("# SSL证书文件路径\n")
        f.write("# 用于HTTPS服务的证书文件（PEM格式）\n")
        f.write(
            f"ssl_cert_path = {config_obj.get('SSL', 'ssl_cert_path', fallback='ssl/fullchain.pem')}\n"
        )
        f.write("# SSL私钥文件路径\n")
        f.write("# 用于HTTPS服务的私钥文件（KEY格式）\n")
        f.write(
            f"ssl_key_path = {config_obj.get('SSL', 'ssl_key_path', fallback='ssl/privkey.key')}\n"
        )
        f.write("# 是否仅允许HTTPS访问（true/false）\n")
        f.write("# true：禁止HTTP访问，所有HTTP请求将被重定向到HTTPS\n")
        f.write("# false：同时允许HTTP和HTTPS访问\n")
        f.write(
            "# 由于端口具有绑定优先级，只要开启HTTPS，但未开启此选项，HTTP可能仍然无法访问\n"
        )
        f.write(
            f"https_only = {config_obj.get('SSL', 'https_only', fallback='false')}\n\n"
        )

        # [Beian] 备案信息配置
        # 此配置节用于设置网站的ICP备案和公安网备案信息
        f.write("[Beian]\n")
        f.write("# 网站备案信息配置\n")
        f.write("# 根据中国相关法律法规，经营性网站需要进行ICP备案和公安网备案\n")
        f.write("# ICP备案号（工信部）\n")
        f.write("# 格式示例：京ICP备12345678号\n")
        f.write("# 留空则不显示（即使show_icp为true）\n")
        f.write(
            f"icp_number = {config_obj.get('Beian', 'icp_number', fallback='')}\n")
        f.write("# 是否在页面底部显示ICP备案信息（true/false）\n")
        f.write("# true：显示ICP备案号并链接至 http://beian.miit.gov.cn\n")
        f.write("# false：不显示ICP备案信息\n")
        f.write(
            f"show_icp = {config_obj.get('Beian', 'show_icp', fallback='false')}\n")
        f.write("# 公安网备案号（公安部）\n")
        f.write("# 格式示例：京公网安备 11010802012345号\n")
        f.write("# 留空则不显示（即使show_police为true）\n")
        f.write(
            f"police_number = {config_obj.get('Beian', 'police_number', fallback='')}\n"
        )
        f.write("# 是否在页面底部显示公安网备案信息（true/false）\n")
        f.write("# true：显示公安网备案号并链接至 https://beian.mps.gov.cn\n")
        f.write("# false：不显示公安网备案信息\n")
        f.write(
            f"show_police = {config_obj.get('Beian', 'show_police', fallback='false')}\n\n"
        )

        # [baidu_cloud] 百度云文本审核服务配置
        # 这个配置节包含了百度云API的访问凭证和审核策略设置
        f.write("[baidu_cloud]\n")
        f.write("# 百度云文本审核服务配置\n")
        f.write("# 用于检测用户提交的文本内容是否包含违规信息（如色情、暴力、政治敏感等）\n")
        f.write(
            "# 申请地址：https://console.bce.baidu.com/ai/#/ai/antiporn/overview/index\n")
        f.write("# API Key（必填）：在百度云控制台创建应用后获取\n")
        f.write(
            f"api_key = {config_obj.get('baidu_cloud', 'api_key', fallback='')}\n")
        f.write("# Secret Key（必填）：在百度云控制台创建应用后获取\n")
        f.write(
            f"secret_key = {config_obj.get('baidu_cloud', 'secret_key', fallback='')}\n")
        f.write("# 策略ID（可选）：不填则使用百度云默认审核策略\n")
        f.write("# 如需自定义审核策略，请在百度云控制台配置后填写策略ID\n")
        f.write(
            f"strategy_id = {config_obj.get('baidu_cloud', 'strategy_id', fallback='')}\n\n")

        # ============================================================
        # [Content_Review] 内容审核配置
        # ============================================================
        # 这个配置节用于控制留言板的内容审核功能
        # 当启用此功能后，用户发表的留言将先通过百度云文本审核服务进行检测
        # 只有通过审核的留言才能成功发布，不合规的留言将被拦截并记录
        f.write("[Content_Review]\n")
        f.write("# 内容审核功能配置\n")
        f.write("# 是否启用留言内容审核（true/false）\n")
        f.write("# true：启用审核，使用百度云文本审核服务检测留言内容\n")
        f.write("#       留言将被检测是否包含违规信息（色情、暴力、政治敏感等）\n")
        f.write("#       不合规的留言将被拒绝并保存到 logs/rejected_messages.json\n")
        f.write("# false：不启用审核，留言直接发布（默认）\n")
        f.write("# 注意：启用此功能需要先配置百度云API密钥（见上方[baidu_cloud]配置节）\n")
        f.write(
            f"enable_message_review = {config_obj.get('Content_Review', 'enable_message_review', fallback='false')}\n\n")

        # ============================================================
        # [Rainbow_YiPay] 彩虹易支付V2配置
        # ============================================================
        # 彩虹易支付是一个第三方支付平台，提供支付宝、微信支付等多种在线支付方式
        # 适用于需要集成在线支付功能的网站或应用
        # 官方文档：请参考您的彩虹易支付服务商提供的API文档
        f.write("# ============================================================\n")
        f.write("# 彩虹易支付V2配置\n")
        f.write("# ============================================================\n")
        f.write("# 彩虹易支付是第三方支付聚合平台，支持支付宝、微信支付等多种支付方式\n")
        f.write("# 使用前需要：\n")
        f.write("# 1. 在彩虹易支付平台注册商户账号\n")
        f.write("# 2. 获取商户ID（PID）和商户密钥（KEY）\n")
        f.write("# ============================================================\n\n")
        f.write("[Rainbow_YiPay]\n")
        f.write("# 易支付接口域名（必填）\n")
        f.write("# 这是彩虹易支付平台提供的API接口地址\n")
        f.write("# 格式示例：https://api.example.com 或 https://pay.yourdomain.com\n")
        f.write("# 注意：必须包含协议头（http:// 或 https://），末尾不要添加斜杠\n")
        f.write(
            f"host = {config_obj.get('Rainbow_YiPay', 'host', fallback='')}\n")
        f.write("# 商户ID（PID）（必填）\n")
        f.write("# 在彩虹易支付平台注册后获取的唯一商户标识\n")
        f.write("# 格式：通常为纯数字，例如：10001\n")
        f.write(
            f"pid = {config_obj.get('Rainbow_YiPay', 'pid', fallback='')}\n")
        f.write("# 商户私钥（KEY）（必填）\n")
        f.write("# 这是商户的RSA私钥，用于对发送给支付平台的请求进行签名\n")
        f.write("# 格式：PEM格式的RSA私钥字符串\n")
        f.write(
            "# 示例：-----BEGIN RSA PRIVATE KEY-----\\nMIIEowIBAAKCAQEA...\\n-----END RSA PRIVATE KEY-----\n")
        f.write("# 用途：商户使用私钥签名请求，平台使用商户公钥验证签名\n")
        f.write("# 注意：请妥善保管私钥，切勿泄露\n")
        f.write(
            f"key = {config_obj.get('Rainbow_YiPay', 'key', fallback='')}\n")
        f.write("# 应用域名地址（可选）\n")
        f.write("# 用于自动设置return_url和notify_url的域名前缀\n")
        f.write("# 格式示例：https://yourdomain.com 或 https://run.zelly.cn\n")
        f.write("# 如果配置了此项，系统将自动拼接完整的回调地址\n")
        f.write("# 如果留空，则使用前端传入的app_host参数\n")
        f.write("# 注意：必须包含协议头（http:// 或 https://），末尾不要添加斜杠\n")
        f.write(
            f"app_host = {config_obj.get('Rainbow_YiPay', 'app_host', fallback='')}\n")
        f.write("# 平台公钥（RSA公钥）（必填）\n")
        f.write("# 这是彩虹易支付平台的RSA公钥，用于验证平台返回的回调通知签名\n")
        f.write("# 格式：PEM格式的RSA公钥字符串\n")
        f.write(
            "# 示例：-----BEGIN PUBLIC KEY-----\\nMIIBIjANBgkqhki...\\n-----END PUBLIC KEY-----\n")
        f.write("# 用途：平台使用私钥对回调通知签名，商户使用平台公钥验证签名\n")
        f.write("# 说明：请在彩虹易支付平台获取并填入平台的RSA公钥\n")
        f.write("# 注意：必须配置此公钥，否则无法验证支付回调通知的真实性\n")
        f.write(
            f"pubc_key = {config_obj.get('Rainbow_YiPay', 'pubc_key', fallback='')}\n")
        f.write("# 启用的支付方式\n")
        f.write("# 管理员可配置启用哪些支付方式，使用逗号分隔\n")
        f.write("# 支持的支付方式：\n")
        f.write("#   - alipay: 支付宝支付（推荐，覆盖率最高）\n")
        f.write("#   - wxpay: 微信支付（移动端常用）\n")
        f.write("#   - bank: 网银支付（适合大额支付）\n")
        f.write("# 示例：\n")
        f.write("#   - alipay,wxpay         启用支付宝和微信支付\n")
        f.write("#   - alipay,wxpay,bank    启用所有支付方式\n")
        f.write("#   - alipay               只启用支付宝支付\n")
        f.write("# 默认值：alipay,wxpay\n")
        f.write("# 注意：\n")
        f.write("# 1. 启用的支付方式必须在您的易支付商户后台已开通\n")
        f.write("# 2. 前端创建订单时会验证支付方式是否在启用列表中\n")
        f.write("# 3. 修改此配置后无需重启服务器，下次创建订单时生效\n")
        f.write(
            f"enabled_payment_methods = {config_obj.get('Rainbow_YiPay', 'enabled_payment_methods', fallback='alipay,wxpay')}\n")
        f.write("# 商品ID（可选）\n")
        f.write("# 用于标识商品类型的唯一标识符\n")
        f.write("# 格式：整数，例如：1001\n")
        f.write("# 默认值：1001（跑步助手服务）\n")
        f.write("# 用途：在支付记录中区分不同类型的商品或服务\n")
        f.write(
            f"product_id = {config_obj.get('Rainbow_YiPay', 'product_id', fallback='1001')}\n")
        f.write("# 支付超时时间（秒）\n")
        f.write("# 订单创建后多长时间内未支付视为超时\n")
        f.write("# 格式：整数，单位为秒\n")
        f.write("# 默认值：30（30秒）\n")
        f.write("# 用途：用于标记超时未支付的订单，便于系统自动关闭或提醒用户\n")
        f.write("# 注意：\n")
        f.write("# 1. 此配置仅用于本地订单超时判断，不影响易支付平台的订单有效期\n")
        f.write("# 2. 建议设置为10-60秒之间\n")
        f.write(
            f"payment_timeout_minutes = {config_obj.get('Rainbow_YiPay', 'payment_timeout_minutes', fallback='30')}\n\n")

        # ============================================================
        # [Payment_Settings] 支付费用配置
        # ============================================================
        f.write("# ============================================================\n")
        f.write("# 支付费用配置\n")
        f.write("# ============================================================\n")
        f.write("# 此配置节用于设置跑步任务的费用标准和新用户初始免费次数\n")
        f.write("# 当用户欠费时，系统将根据此配置计算需要缴纳的金额\n")
        f.write("# ============================================================\n\n")
        f.write("[Payment_Settings]\n")
        f.write("# 是否需要付费（true/false）\n")
        f.write("# true：启用付费模式，用户需要支付才能使用跑步服务\n")
        f.write("# false：免费模式，所有用户可无限次使用，不扣除次数，不产生欠费\n")
        f.write("# 默认值：true（需要付费）\n")
        f.write("# 注意：\n")
        f.write("# 1. 当设置为false时，或者single_run_cost<=0时，系统将跳过所有付费相关逻辑\n")
        f.write("# 2. 免费模式下，用户仍然可以手动结算费用，但不会自动扣费\n")
        f.write(
            f"require_payment = {config_obj.get('Payment_Settings', 'require_payment', fallback='true')}\n\n")
        f.write("# 单次跑步任务费用（单位：元）\n")
        f.write("# 用于计算用户欠费金额 = 欠费次数 × single_run_cost\n")
        f.write("# 默认值：1.0元/次\n")
        f.write("# 管理员可根据实际情况调整此费用\n")
        f.write("# 注意：\n")
        f.write("# 1. 费用必须为正数，支持小数（如：0.5、1.5、2.0）\n")
        f.write("# 2. 修改后仅对新产生的欠费生效，已有订单不受影响\n")
        f.write("# 3. 设置为0或负数时，相当于关闭付费功能，所有用户可免费使用\n")
        f.write(
            f"single_run_cost = {config_obj.get('Payment_Settings', 'single_run_cost', fallback='1.0')}\n\n")
        f.write("# 新用户注册时获得的默认免费次数（整数）\n")
        f.write("# 用于在用户注册时自动设置available_runs字段的初始值\n")
        f.write("# 默认值：10次\n")
        f.write("# 特殊值：\n")
        f.write("# - 0：新用户无免费次数，需要管理员手动分配或立即付费\n")
        f.write("# - -1：新用户获得无限次数（不推荐，除非完全免费模式）\n")
        f.write("# - 正整数：新用户获得指定次数的免费使用额度\n")
        f.write("# 示例：\n")
        f.write("# - 设置为10：新用户注册后可免费使用10次\n")
        f.write("# - 设置为0：新用户注册后需要购买次数才能使用\n")
        f.write("# 注意：\n")
        f.write("# 1. 此配置仅影响新注册用户，已注册用户不受影响\n")
        f.write("# 2. 管理员可随时通过用户管理面板修改个别用户的可用次数\n")
        f.write("# 3. 此值会在注册页面的提示文本中显示（如：注册即可得 {available_runs} 次校园跑）\n")
        f.write(
            f"default_available_runs = {config_obj.get('Payment_Settings', 'default_available_runs', fallback='10')}\n\n")

        # ============================================================
        # [Profile_Display] 个人资料显示配置
        # ============================================================
        f.write("# ============================================================\n")
        f.write("# 个人资料显示配置\n")
        f.write("# ============================================================\n")
        f.write("# 此配置节用于控制个人资料页面中available_runs（剩余免费次数）的显示行为\n")
        f.write("# ============================================================\n\n")
        f.write("[Profile_Display]\n")
        f.write("# 是否在个人资料页面显示剩余免费次数（true/false）\n")
        f.write("# true：在个人资料页面显示available_runs字段\n")
        f.write("# false：不显示available_runs字段\n")
        f.write("# 默认值：true（显示）\n")
        f.write(
            f"show_available_runs = {config_obj.get('Profile_Display', 'show_available_runs', fallback='true')}\n")
        f.write("# 剩余免费次数的显示格式（字符串模板）\n")
        f.write("# 使用 {available_runs} 作为占位符，将被替换为实际的剩余次数数值\n")
        f.write("# 示例：\n")
        f.write("#   - 剩余免费次数：{available_runs} 次（默认格式）\n")
        f.write("#   - 您还有 {available_runs} 次免费跑步机会\n")
        f.write("#   - Free runs left: {available_runs}\n")
        f.write("# 默认值：剩余免费次数：{available_runs} 次\n")
        f.write(
            f"available_runs_format = {config_obj.get('Profile_Display', 'available_runs_format', fallback='剩余免费次数：{{available_runs}} 次')}\n\n")

        # ============================================================
        # [Registration_Display] 注册页面显示配置
        # ============================================================
        f.write("# ============================================================\n")
        f.write("# 注册页面显示配置\n")
        f.write("# ============================================================\n")
        f.write("# 此配置节用于控制注册页面中关于available_runs（初始免费次数）的提示信息\n")
        f.write("# ============================================================\n\n")
        f.write("[Registration_Display]\n")
        f.write("# 是否在注册页面显示免费次数提示（true/false）\n")
        f.write("# true：在注册表单中显示初始免费次数的提示信息\n")
        f.write("# false：不显示提示信息\n")
        f.write("# 默认值：true（显示）\n")
        f.write(
            f"show_available_runs_on_register = {config_obj.get('Registration_Display', 'show_available_runs_on_register', fallback='true')}\n")
        f.write("# 注册页面的免费次数提示文本（字符串模板）\n")
        f.write("# 使用 {available_runs} 作为占位符，将被替换为新用户注册时获得的初始免费次数\n")
        f.write("# 此数值从配置文件的 [Payment_Settings].default_available_runs 读取\n")
        f.write("# 示例：\n")
        f.write("#   - 注册即可得 {available_runs} 次校园跑（默认格式）\n")
        f.write("#   - 新用户福利：{available_runs} 次免费跑步\n")
        f.write("#   - Sign up and get {available_runs} free runs!\n")
        f.write("# 默认值：注册即可得 {available_runs} 次校园跑\n")
        f.write("# 注意：此提示文本通常显示在注册按钮附近或表单顶部，用于吸引用户注册\n")
        f.write(
            f"register_available_runs_hint = {config_obj.get('Registration_Display', 'register_available_runs_hint', fallback='注册即可得 {{available_runs}} 次校园跑')}\n\n")


def is_weak_password(password):
    """
    检测密码是否为弱密码
    """
    # 1. 检查密码长度
    # 密码长度必须至少8个字符，这是安全的基本要求
    if len(password) < 6:
        return (True, "密码长度不能少于6个字符")

    # 2. 检查是否为纯数字
    # 纯数字密码容易被暴力破解，安全性极低
    if password.isdigit():
        return (True, "密码不能为纯数字")

    # 3. 检查是否为纯字母
    # 纯字母密码缺乏复杂性，容易被字典攻击破解
    if password.isalpha():
        return (True, "密码不能为纯字母，需包含数字或特殊字符")

    # 4. 常见弱密码列表
    # 这些密码在各种密码泄露事件中出现频率极高，黑客工具都会优先尝试
    common_weak_passwords = [
        'password', 'password123', 'admin123', 'admin',
        '12345678', '123456789', '87654321', 'qwerty',
        'qwerty123', 'abc123', 'abcd1234', '11111111',
        '00000000', 'test1234', 'user1234', 'pass1234',
        'a1b2c3d4', '1q2w3e4r', 'qwertyui', 'asdfghjk',
    ]
    # 使用 lower() 进行不区分大小写的比较，避免用户用大小写混淆绕过检测
    if password.lower() in common_weak_passwords:
        return (True, "密码过于简单，请使用更复杂的密码")

    # 5. 检查键盘序列（连续的键盘按键）
    # 键盘序列容易被猜测，因为人们倾向于使用手指在键盘上连续按键的模式
    keyboard_patterns = [
        '123456', '234567', '345678', '456789', '567890',
        'qwerty', 'asdfgh', 'zxcvbn', 'qazwsx', 'zaq12wsx',
    ]
    # 转换为小写进行检查，防止用户通过大小写混淆绕过检测
    password_lower = password.lower()
    for pattern in keyboard_patterns:
        # 检查密码中是否包含这些键盘序列模式
        if pattern in password_lower:
            return (True, "密码包含键盘序列，请使用更复杂的密码")

    # 6. 检查重复字符（如：aaaa1111, 11112222）
    # 使用 set() 获取密码中不同字符的数量
    # 如果不同字符种类少于4种，说明密码重复性太高，缺乏多样性
    if len(set(password)) < 4:
        return (True, "密码字符重复过多，请使用更多样化的字符")

    # 通过所有检查，密码强度合格
    # 返回 False 表示不是弱密码，reason 为空字符串
    return (False, "")


def get_baidu_access_token(api_key, secret_key):
    """
    获取百度云API的access_token

    百度云的所有API调用都需要先获取access_token作为身份验证凭证。
    该函数通过API Key和Secret Key向百度OAuth 2.0服务请求access_token。

    参数:
        api_key (str): 百度云应用的API Key，在百度云控制台创建应用后获取
        secret_key (str): 百度云应用的Secret Key，在百度云控制台创建应用后获取

    返回:
        dict: 包含以下键的字典：
            - access_token (str or None): 成功时返回access_token字符串，失败时为None
            - error (str or None): 成功时为None，失败时返回错误信息

    使用示例:
        result = get_baidu_access_token("your_api_key", "your_secret_key")
        if result["error"] is None:
            print("获取token成功")
        else:
            print("获取token失败")
    """
    # 注意：requests库已在模块级别通过_try_import_third_party()导入
    # 不需要在函数内部重复导入

    # 百度云OAuth 2.0 token获取接口的URL
    # 该接口使用client_credentials授权模式（客户端凭证模式）
    token_url = "https://aip.baidubce.com/oauth/2.0/token"

    # 构造请求参数
    # grant_type: OAuth 2.0的授权类型，这里使用client_credentials（客户端凭证）
    # client_id: 即百度云的API Key
    # client_secret: 即百度云的Secret Key
    params = {
        "grant_type": "client_credentials",  # 授权类型：客户端凭证模式
        "client_id": api_key,                # 百度云API Key
        "client_secret": secret_key          # 百度云Secret Key
    }

    try:
        # 发送GET请求到百度云token获取接口
        # timeout=10: 设置请求超时时间为10秒，防止长时间等待导致程序挂起
        # 如果10秒内没有响应，将抛出requests.exceptions.Timeout异常
        response = requests.get(token_url, params=params, timeout=10)

        # 检查HTTP响应状态码
        # raise_for_status()会在状态码为4xx或5xx时抛出HTTPError异常
        # 例如：404 Not Found、500 Internal Server Error等
        response.raise_for_status()

        # 尝试将响应内容解析为JSON格式
        # 百度云API的响应都是JSON格式的数据
        data = response.json()

        # 检查响应中是否包含access_token字段
        # 成功的响应格式：{"access_token": "...", "expires_in": 2592000}
        # 失败的响应格式：{"error": "...", "error_description": "..."}
        if "access_token" in data:
            # 成功获取token，返回结果
            return {
                "access_token": data["access_token"],  # 返回access_token
                "error": None                          # 没有错误
            }
        else:
            # 响应中没有access_token，说明请求失败
            # 从响应中提取错误信息，如果没有error字段则使用默认信息
            error_msg = data.get("error_description",
                                 data.get("error", "未知错误"))
            return {
                "access_token": None,                                  # token获取失败
                "error": f"百度云API返回错误: {error_msg}"              # 返回错误信息
            }

    except requests.exceptions.Timeout:
        # 捕获请求超时异常
        # 当请求时间超过timeout参数设置的时间时触发
        return {
            "access_token": None,
            "error": "请求超时，请检查网络连接或稍后重试"
        }

    except requests.exceptions.ConnectionError:
        # 捕获连接错误异常
        # 例如：DNS解析失败、网络不可达、服务器拒绝连接等
        return {
            "access_token": None,
            "error": "网络连接失败，请检查网络设置"
        }

    except requests.exceptions.HTTPError as e:
        # 捕获HTTP错误异常（4xx、5xx状态码）
        # 例如：401 Unauthorized、403 Forbidden、500 Internal Server Error
        logging.warning(f"[百度云Token] HTTP请求失败: {type(e).__name__}")
        return {
            "access_token": None,
            "error": "HTTP请求失败，请稍后重试"
        }

    except ValueError:
        # 捕获JSON解析错误
        # 当响应内容不是有效的JSON格式时触发
        return {
            "access_token": None,
            "error": "响应数据格式错误，无法解析JSON"
        }

    except Exception as e:
        # 捕获所有其他未预期的异常
        # 作为最后的兜底处理，确保函数不会因为未知错误而崩溃
        logging.warning(f"[百度云Token] 请求异常: {type(e).__name__}")
        return {
            "access_token": None,
            "error": "请求百度云服务失败，请稍后重试"
        }


def check_text_content(text, strategy_id=None, user_id=None, user_ip=None, phone_sha256=None, device_id=None):
    """
    调用百度云文本审核服务检测文本内容是否合规

    该函数将文本内容提交到百度云内容审核平台进行审核，检测是否包含违规内容。
    百度云会根据预设的审核策略，检测文本中的色情、暴力、政治敏感、违禁品等内容。

    参数:
        text (str): 待审核的文本内容（必填），这是唯一的必需参数
        strategy_id (str, 可选): 审核策略ID，不填则使用百度云默认策略
        user_id (str, 可选): 用户自定义的用户ID，用于标识提交审核的用户
        user_ip (str, 可选): 用户的IP地址，用于风险识别和统计分析
        phone_sha256 (str, 可选): 用户手机号的SHA256哈希值，用于风险识别
        device_id (str, 可选): 用户设备的唯一标识，用于风险识别

    返回:
        dict: 包含以下键的字典：
            - success (bool): 是否成功调用API（True表示成功，False表示失败）
            - conclusion (str): 审核结论文本，可能的值：
                * "合规": 内容符合规范，可以正常展示
                * "不合规": 内容存在违规，不应展示
                * "疑似": 内容可能存在违规，建议人工复审
                * "审核失败": API调用失败或发生错误
            - conclusion_type (int): 审核结论类型编码：
                * 1: 合规
                * 2: 不合规
                * 3: 疑似
                * 4: 审核失败
            - data (list): 详细的审核结果数组，包含具体的违规类型和位置信息
            - error (str or None): 错误信息，成功时为None，失败时包含错误详情

    使用示例:
        # 基本用法（只检测文本）
        result = check_text_content("这是一段需要审核的文本内容")
        if result["success"]:
            if result["conclusion"] == "合规":
                print("内容审核通过")
            else:
                print(f"内容审核未通过: {result['conclusion']}")
                print(f"详细信息: {result['data']}")
        else:
            print(f"审核失败: {result['error']}")

        # 完整用法（包含所有可选参数）
        result = check_text_content(
            text="这是一段需要审核的文本内容",
            strategy_id="your_strategy_id",
            user_id="user_123",
            user_ip="192.168.1.1",
            phone_sha256="sha256_hash_of_phone",
            device_id="device_123"
        )
    """
    # 注意：requests库已在模块级别通过_try_import_third_party()导入
    # 不需要在函数内部重复导入

    # 读取百度云配置信息
    # 使用统一的配置读取函数读取config.ini文件中的[baidu_cloud]配置节
    try:
        # 调用统一的配置读取函数，该函数会返回RawConfigParser对象或None
        config = _read_config_ini(CONFIG_JSON_FILE)

        # 检查配置文件是否成功读取
        # 如果返回None，说明配置文件读取失败（文件不存在、权限问题等）
        if config is None:
            # 配置文件读取失败，返回标准错误响应
            return {
                "success": False,
                "conclusion": "审核失败",
                "conclusion_type": 4,
                "data": [],
                "error": "无法读取配置文件config.ini"
            }

        # 从配置文件中获取API Key和Secret Key
        # 如果配置项不存在或为空，则get方法会返回空字符串
        api_key = config.get("baidu_cloud", "api_key", fallback="").strip()
        secret_key = config.get(
            "baidu_cloud", "secret_key", fallback="").strip()

        # 验证API凭证格式
        # API Key和Secret Key必须至少24个字符（百度云实际长度通常更长）
        if api_key and len(api_key) < 24:
            logging.warning(
                f"[百度云文本审核] API Key长度异常（{len(api_key)}字符），预期至少24字符")
        if secret_key and len(secret_key) < 24:
            logging.warning(
                f"[百度云文本审核] Secret Key长度异常（{len(secret_key)}字符），预期至少24字符")

        # 如果配置文件中设置了策略ID，且函数调用时未指定，则使用配置文件中的值
        if not strategy_id:
            strategy_id = config.get(
                "baidu_cloud", "strategy_id", fallback="").strip()

        # 检查API Key和Secret Key是否已配置
        # 这两个参数是调用百度云API的必需凭证
        if not api_key or not secret_key:
            return {
                "success": False,
                "conclusion": "审核失败",
                "conclusion_type": 4,
                "data": [],
                "error": "百度云API Key或Secret Key未配置，请在config.ini中配置[baidu_cloud]节"
            }

    except Exception as e:
        # 捕获配置文件读取过程中的任何异常
        # 例如：文件不存在、权限不足、编码错误等
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": f"读取配置文件失败: {str(e)}"
        }

    # 第一步：获取access_token
    # 调用上面定义的get_baidu_access_token函数获取API访问令牌
    token_result = get_baidu_access_token(api_key, secret_key)

    # 检查token获取是否成功
    if token_result["error"] is not None:
        # token获取失败，直接返回错误
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": f"获取access_token失败: {token_result['error']}"
        }

    # 从token_result中提取access_token
    access_token = token_result["access_token"]

    # 第二步：调用文本审核API
    # 百度云文本审核接口的URL，需要将access_token作为URL参数传递
    censor_url = f"https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined?access_token={access_token}"

    # 设置HTTP请求头
    # Content-Type指定请求体的格式为表单编码（application/x-www-form-urlencoded）
    # 这是百度云文本审核API要求的格式
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # 构造请求体数据
    # 使用字典存储所有参数，requests会自动将其编码为x-www-form-urlencoded格式
    data = {
        "text": text  # 必填参数：待审核的文本内容
    }

    # 添加可选参数（如果提供了值）
    # 只有当参数不为None且不为空字符串时才添加到请求中
    if strategy_id:
        data["strategyId"] = strategy_id  # 策略ID
    if user_id:
        data["userId"] = user_id  # 用户ID
    if user_ip:
        data["userIp"] = user_ip  # 用户IP
    if phone_sha256:
        data["phoneSha256"] = phone_sha256  # 手机号SHA256
    if device_id:
        data["deviceId"] = device_id  # 设备ID

    try:
        # 发送POST请求到百度云文本审核接口
        # data参数会被自动编码为application/x-www-form-urlencoded格式
        # timeout=10：设置10秒超时，防止长时间等待
        response = requests.post(
            censor_url, headers=headers, data=data, timeout=10)

        # 检查HTTP响应状态码
        # 如果状态码不是2xx，raise_for_status()会抛出HTTPError异常
        response.raise_for_status()

        # 解析响应的JSON数据
        result = response.json()

        # 检查API是否返回了错误
        # 百度云API在出错时会返回error_code和error_msg字段
        if "error_code" in result:
            # API返回了错误码，说明请求失败
            error_code = result.get("error_code")
            error_msg = result.get("error_msg", "未知错误")
            return {
                "success": False,
                "conclusion": "审核失败",
                "conclusion_type": 4,
                "data": [],
                "error": f"百度云API错误 (错误码: {error_code}): {error_msg}"
            }

        # 从响应中提取审核结果
        # conclusion: 审核结论文本（"合规"、"不合规"、"疑似"、"审核失败"）
        # conclusionType: 审核结论类型（1-4的整数）
        # data: 详细的审核结果数组
        conclusion = result.get("conclusion", "审核失败")
        conclusion_type = result.get("conclusionType", 4)
        data_list = result.get("data", [])

        # 返回成功的结果
        return {
            "success": True,              # API调用成功
            "conclusion": conclusion,      # 审核结论文本
            "conclusion_type": conclusion_type,  # 审核结论类型编码
            "data": data_list,            # 详细审核结果
            "error": None                 # 没有错误
        }

    except requests.exceptions.Timeout:
        # 请求超时异常
        # 当API响应时间超过timeout参数设置的时间时触发
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": "请求超时，百度云服务响应时间过长，请稍后重试"
        }

    except requests.exceptions.ConnectionError:
        # 网络连接错误
        # 例如：无法连接到百度云服务器、DNS解析失败等
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": "网络连接失败，无法连接到百度云服务，请检查网络设置"
        }

    except requests.exceptions.HTTPError as e:
        # HTTP错误（4xx、5xx状态码）
        # 例如：401未授权、403禁止访问、500服务器内部错误等
        logging.warning(f"[百度云文本审核] HTTP请求失败: {type(e).__name__}")
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": "HTTP请求失败，请稍后重试"
        }

    except ValueError:
        # JSON解析错误
        # 当百度云API返回的响应不是有效的JSON格式时触发
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": "响应数据格式错误，无法解析百度云API返回的JSON数据"
        }

    except Exception as e:
        # 捕获所有其他未预期的异常
        # 这是最后的兜底处理，确保函数始终返回标准格式的结果
        logging.warning(f"[百度云文本审核] 请求异常: {type(e).__name__}")
        return {
            "success": False,
            "conclusion": "审核失败",
            "conclusion_type": 4,
            "data": [],
            "error": "文本审核服务异常，请稍后重试"
        }




def _migrate_ini_to_json(ini_config, json_path: str):
    """将 configparser 对象的内容迁移到 JSON 文件（仅在目标 JSON 不存在时调用）。"""
    try:
        data = {}
        for section in ini_config.sections():
            data[section] = dict(ini_config.items(section))
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"[配置迁移] config.ini 已迁移至 {json_path}")
    except Exception as e:
        logging.warning(f"[配置迁移] 迁移到 JSON 失败（非致命）: {e}")


def _create_default_json_config(json_path: str):
    """当 config.ini 和 config.json 都不存在时，创建包含默认值的 JSON 配置文件。"""
    try:
        default = _get_default_config() if "_get_default_config" in globals() else {}
        data = {}
        if hasattr(default, "sections"):
            for section in default.sections():
                data[section] = dict(default.items(section))
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"[配置初始化] 已创建默认 JSON 配置文件: {json_path}")
    except Exception as e:
        logging.warning(f"[配置初始化] 创建默认 JSON 配置失败（非致命）: {e}")


def _read_config_ini(config_file=CONFIG_FILE):
    """
    统一的配置文件读取函数。

    读取规则：
      1. 仅使用 ./configs/config.json（返回 JsonConfigAdapter）
      2. 若文件不存在，自动创建默认 config.json
      3. 若文件损坏，自动备份后重建默认 config.json

    参数:
        config_file: JSON 文件路径，默认为 CONFIG_JSON_FILE

    返回:
        configparser.RawConfigParser 或 JsonConfigAdapter 对象；读取失败返回 None

    说明:
        - 使用 RawConfigParser / JsonConfigAdapter 保持键名的大小写
        - 统一使用 utf-8 编码读取
        - 包含错误处理，读取失败时记录日志并返回 None
    """
    try:
        json_cfg_path = config_file or CONFIG_FILE
        if not os.path.isabs(json_cfg_path):
            json_cfg_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), json_cfg_path
            )

        # 不存在则创建默认 JSON
        if not os.path.exists(json_cfg_path):
            logging.warning(f"[配置] {json_cfg_path} 不存在，将创建默认 JSON 配置")
            _create_default_json_config(json_cfg_path)

        # 文件存在但损坏：先备份再重建，避免配置丢失
        try:
            with open(json_cfg_path, "r", encoding="utf-8") as vf:
                json.load(vf)
        except json.JSONDecodeError:
            backup_file = f"{json_cfg_path}.corrupted.{int(time.time())}.bak"
            try:
                shutil.copy2(json_cfg_path, backup_file)
                logging.error(f"[配置] JSON 配置损坏，已备份到: {backup_file}")
            except Exception as be:
                logging.error(f"[配置] JSON 损坏备份失败: {be}")
            _create_default_json_config(json_cfg_path)
        except FileNotFoundError:
            _create_default_json_config(json_cfg_path)

        adapter = JsonConfigAdapter(json_cfg_path)
        logging.debug(f"[配置] 已从 {json_cfg_path} 加载 JSON 配置")
        return adapter

    except Exception as e:
        # 捕获所有可能的异常（文件不存在、权限问题、编码错误等）
        # 记录错误日志，包含完整的堆栈信息以便调试
        logging.error(f"读取配置文件 {config_file} 失败: {e}", exc_info=True)
        # 返回None表示读取失败，调用方需要检查返回值
        return None


def _create_config_ini():
    """创建或更新 JSON 配置文件（config.json），自动补全缺失参数。"""
    default_config = _get_default_config()
    config_file = CONFIG_FILE

    if os.path.exists(config_file):
        # 检查文件是否为空
        if os.path.getsize(config_file) == 0:
            print(f"[配置文件] 检测到 {config_file} 为空，正在重新创建默认配置...")
            _write_config_with_comments(default_config, config_file)
            return

        print("[配置文件] config.json 已存在，检查是否需要更新...")
        try:
            existing_config = JsonConfigAdapter(config_file)
        except Exception as e:
            # 捕获所有解析错误（包括重复项、格式错误等），备份并重置
            print(f"\n[错误] 读取配置文件 '{config_file}' 失败: {e}")
            logging.error(f"配置文件读取失败: {e}")

            # import shutil

            backup_file = config_file + ".bak"
            try:
                shutil.copy2(config_file, backup_file)
                print(f"[配置文件] 已将损坏的配置文件备份为: {backup_file}")
            except Exception as copy_err:
                print(f"[配置文件] 备份失败: {copy_err}")

            print("[配置文件] 正在使用默认配置覆盖损坏的文件...")
            _write_config_with_comments(default_config, config_file)
            return

        updated = False
        for section in default_config.sections():
            if not existing_config.has_section(section):
                existing_config.add_section(section)
                updated = True
                print(f"[配置文件] 添加新的配置节: {section}")
                for key, value in default_config.items(section):
                    existing_config.set(section, key, value)
                    print(f"[配置文件] 为新节添加配置项: [{section}] {key}")
            else:
                existing_keys_lower = {
                    k.lower() for k in existing_config.options(section)
                }
                for key, value in default_config.items(section):
                    if key.lower() not in existing_keys_lower:
                        existing_config.set(section, key, value)
                        updated = True
                        print(f"[配置文件] 添加缺失的配置项: [{section}] {key}")

        if updated:
            try:
                _write_config_with_comments(existing_config, config_file)
                logging.info("配置文件已更新：自动补全缺失参数")
                print("[配置文件] 配置文件已更新并保存（包含详细注释）")
            except Exception as e:
                print(f"[错误] 保存更新后的 config.json 失败: {e}")
                logging.error(f"保存更新后的 config.json 失败: {e}")
        else:
            print("[配置文件] 配置文件无需更新")
    else:
        print("[配置文件] config.json 不存在，创建新配置文件...")
        _write_config_with_comments(default_config, config_file)
        print("[配置文件] 配置文件创建完成（包含详细注释）")


def _get_default_payment_methods_config():
    """
    获取默认的支付方式配置

    返回值:
        dict: 默认的支付方式配置字典，包含所有支持的支付方式及其显示信息

    说明:
        此函数返回系统默认支持的支付方式配置，包括：
        - alipay: 支付宝支付
        - wxpay: 微信支付
        - bank: 网银支付
        - qqpay: QQ钱包
        - unionpay: 云闪付

        每个支付方式包含以下字段：
        - name: 中文名称，用于前端显示
        - icon: 图标类型，固定为 "svg"
        - svg: SVG图标的完整代码
        - description: 支付方式的详细描述
        - borderColor: 悬停时的边框颜色样式类（Tailwind CSS）
        - textColor: 文字颜色样式类（Tailwind CSS）
    """
    # 返回默认的支付方式配置字典
    # 此配置包含了系统支持的所有支付方式及其前端显示样式
    return {


        # 支付宝支付配置
        "alipay": {
            "name": "支付宝支付",  # 显示名称
            "icon": "svg",  # 图标类型标识
            # SVG 图标代码，使用天蓝色主题，包含货币符号图标
            "svg": '<svg t="1765858760722" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="2038" width="200" height="200"><path d="M543.940818 632.713724s-119.827669 151.276279-261.021488 151.276279c-141.252896 0-170.929198-71.876909-170.929198-123.569207 0-51.633221 29.380917-107.815364 149.563048-115.928593 120.123054-8.113229 282.446715 88.221521 282.446715 88.221521h-0.059077zM1023.999803 696.910635l-329.373475-110.769209s25.304611-37.907685 52.322451-112.187056c27.017841-74.299063 30.897225-115.101516 30.897225-115.101516l-213.228266-1.752615v-72.82214l258.225181-1.831384V230.990725H564.578353V113.782132h-126.483668v117.169208H197.179039v51.495375l240.915646-1.693538v78.099677h-193.240578v40.782761h397.764846s-4.391384 33.122455-19.633227 74.299063c-15.241843 41.1963-30.936609 77.272601-30.936609 77.272601s-186.781503-65.378449-285.183945-65.378449c-98.422135 0-218.111958 39.542146-229.730418 154.289201-11.53969 114.687978 55.768605 176.797504 150.587048 199.679961 94.838136 22.980919 182.390119-0.216615 258.619028-37.553223 76.228908-37.257839 151.039971-121.97413 151.039971-121.974131l383.881772 186.427041A189.439964 189.439964 0 0 1 834.382609 1023.999803H189.617194C84.991984 1024.098265 0.098462 939.362281 0 834.756763V189.597502C-0.098462 84.991984 84.657214 0.098462 189.262733 0h645.119876C939.007819-0.098462 1023.901342 84.637522 1023.999803 189.262733V696.910635z" fill="#02A9F1" p-id="2039"></path></svg>',
            "description": "支持支付宝扫码支付",  # 支付方式描述
            "borderColor": "hover:border-sky-500",  # 鼠标悬停时的边框颜色
            "textColor": "text-sky-600"  # 文字颜色
        },
        # 微信支付配置
        "wxpay": {
            "name": "微信支付",  # 显示名称
            "icon": "svg",  # 图标类型标识
            # SVG 图标代码，使用绿色主题，包含聊天图标
            "svg": '<svg t="1765858698694" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1581" width="200" height="200"><path d="M0 488.96v-30.72C2.56 430.08 7.68 404.48 15.36 378.88c20.48-66.56 53.76-122.88 99.84-171.52C179.2 138.24 256 94.72 340.48 66.56c48.64-15.36 97.28-23.04 145.92-25.6 40.96-2.56 79.36 0 120.32 7.68 33.28 5.12 64 12.8 97.28 25.6 79.36 28.16 148.48 71.68 207.36 133.12 7.68 7.68 12.8 15.36 20.48 23.04-2.56 0-2.56 2.56-5.12 2.56-20.48 10.24-40.96 20.48-61.44 28.16-143.36 66.56-286.72 133.12-430.08 197.12-28.16 12.8-56.32 10.24-81.92-5.12-20.48-12.8-38.4-25.6-58.88-38.4-12.8-10.24-25.6-17.92-40.96-28.16-12.8-7.68-20.48-2.56-20.48 12.8v2.56c2.56 12.8 5.12 25.6 10.24 38.4 25.6 61.44 51.2 120.32 76.8 181.76 7.68 17.92 20.48 25.6 35.84 23.04 10.24 0 20.48-2.56 28.16-7.68 30.72-15.36 58.88-33.28 87.04-51.2 156.16-92.16 309.76-184.32 465.92-276.48 10.24-7.68 23.04-12.8 33.28-20.48 0 2.56 2.56 2.56 2.56 5.12 5.12 10.24 10.24 17.92 12.8 28.16 28.16 61.44 40.96 125.44 35.84 192-2.56 28.16-7.68 56.32-15.36 84.48-17.92 61.44-48.64 115.2-92.16 163.84-51.2 56.32-115.2 99.84-184.32 128-40.96 15.36-81.92 28.16-122.88 35.84-28.16 5.12-56.32 7.68-81.92 7.68h-46.08c-20.48-2.56-40.96-2.56-58.88-5.12-30.72-5.12-61.44-12.8-89.6-23.04H322.56c-12.8 7.68-23.04 15.36-35.84 23.04-28.16 17.92-53.76 33.28-81.92 48.64-5.12 2.56-12.8 5.12-17.92 5.12s-10.24-2.56-10.24-10.24c0-5.12 0-12.8 2.56-17.92 5.12-38.4 12.8-74.24 20.48-112.64 0-5.12 0-7.68-5.12-10.24-15.36-12.8-30.72-23.04-46.08-38.4-51.2-46.08-92.16-102.4-117.76-166.4C20.48 599.04 12.8 568.32 7.68 537.6c-2.56-12.8-2.56-25.6-2.56-40.96-5.12 0-5.12-2.56-5.12-7.68z" fill="#6BCC03" p-id="1582"></path></svg>',
            "description": "支持微信扫码支付",  # 支付方式描述
            "borderColor": "hover:border-green-500",  # 鼠标悬停时的边框颜色
            "textColor": "text-green-600"  # 文字颜色
        },
        # 网银支付配置
        "bank": {
            "name": "网银支付",  # 显示名称
            "icon": "svg",  # 图标类型标识
            # SVG 图标代码，使用蓝色主题，包含银行卡图标
            "svg": '<svg t="1765858843045" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4458" width="200" height="200"><path d="M333.2 800H100c-22.9 0-40-21.5-35.2-44.4l94.5-453.9c9.4-45.3 48.6-77.6 93.9-77.6H467c22.9 0 40 21.5 35.2 44.4l-98.6 473.4c-7.1 33.8-36.4 58.1-70.4 58.1z" fill="#DD2C34" p-id="4459"></path><path d="M540.6 800H307.5c-22.9 0-40-21.5-35.2-44.4l94.5-453.9c9.4-45.3 48.6-77.6 93.9-77.6h213.8c22.9 0 40 21.5 35.2 44.4l-98.6 473.4c-7.1 33.8-36.5 58.1-70.5 58.1z" fill="#01488A" p-id="4460"></path><path d="M790.2 800H557c-22.9 0-40-21.5-35.2-44.4l94.5-453.9c9.4-45.3 48.6-77.6 93.9-77.6H924c22.9 0 40 21.5 35.2 44.4l-98.6 473.4c-7.1 33.8-36.4 58.1-70.4 58.1z" fill="#008189" p-id="4461"></path><path d="M185.5 392.1h21.7l-12 69.1-3 17c-0.2 1.4-0.3 2.8-0.3 4.1 0 5 1.5 9.2 4.6 12.5 3.1 3.3 7.5 4.9 13.3 4.9 5.2 0 9.6-1.2 13-3.6 3.4-2.4 6.1-5.9 7.9-10.6 1.9-4.7 3.8-12.6 5.7-23.9l12.1-69.5h21.7l-12 69.6c-2.5 14.6-5.5 25.8-8.8 33.6-3.3 7.8-8.3 14.1-15.1 18.9-6.7 4.9-15.2 7.3-25.5 7.3-12.3 0-21.7-3.6-28.2-10.9-6.5-7.3-9.8-16.6-9.8-28 0-2.4 0.2-4.9 0.5-7.7 0.2-1.9 1-7.1 2.5-15.8l11.7-67zM290.4 427.2H310l-2 12c4.9-5.1 9.5-8.7 13.7-10.9 4.3-2.2 8.7-3.3 13.4-3.3 6.3 0 11.3 2.2 14.9 6.5 3.6 4.3 5.4 10.1 5.4 17.3 0 3.2-0.8 9.4-2.4 18.4l-9 52.1h-20.7l9.1-52.3c1.3-7.8 2-12.5 2-14 0-3.2-0.8-5.7-2.3-7.5-1.6-1.8-3.7-2.7-6.5-2.7-3 0-6.4 1.5-10.1 4.6-3.7 3.1-6.6 7.1-8.7 12.1-1.5 3.6-3.3 10.9-5.2 22l-6.6 37.8h-20.7l16.1-92.1zM384.6 427.2h20.7l-16 92.1h-20.7l16-92.1z m6-35.1h20.7l-3.9 22.6h-20.7l3.9-22.6zM416.9 481.1c0-17.1 4-30.7 12-40.8 8-10.2 18.5-15.2 31.5-15.2 11.3 0 20.1 3.7 26.4 11.2 6.3 7.5 9.5 17.6 9.5 30.2 0 14.9-4 27.8-11.9 38.7-7.9 10.9-18.5 16.3-31.9 16.3-7.2 0-13.6-1.7-19.2-5.2s-9.7-8.4-12.5-14.8c-2.6-6.3-3.9-13.1-3.9-20.4z m58.9-17.8c0-5.9-1.4-10.6-4.3-14.2-2.9-3.6-6.5-5.3-11.1-5.3-4.5 0-8.4 1.7-11.9 5s-6.1 8.2-8.1 14.5c-1.9 6.3-2.9 12.2-2.9 17.5 0 6.6 1.5 11.8 4.5 15.7 3 3.9 6.7 5.8 11.2 5.8 5.7 0 10.4-2.9 14.3-8.8 5.6-8.3 8.3-18.3 8.3-30.2zM524.6 427.2h19.6l-2 12c4.9-5.1 9.5-8.7 13.7-10.9 4.3-2.2 8.7-3.3 13.4-3.3 6.3 0 11.3 2.2 14.9 6.5 3.6 4.3 5.4 10.1 5.4 17.3 0 3.2-0.8 9.4-2.4 18.4l-9 52.1h-20.7l9.1-52.3c1.3-7.8 2-12.5 2-14 0-3.2-0.8-5.7-2.3-7.5-1.6-1.8-3.7-2.7-6.5-2.7-3 0-6.4 1.5-10.1 4.6-3.7 3.1-6.6 7.1-8.7 12.1-1.5 3.6-3.3 10.9-5.2 22l-6.6 37.8h-20.7l16.1-92.1zM624.5 519.3h-21.8l22.1-127.2h43c7.6 0 13.7 1.1 18.1 3.3 4.4 2.2 8 5.8 10.6 10.8 2.6 5 3.9 11 3.9 17.9 0 6.4-1 12.7-3.1 18.7-2.1 6.1-4.6 10.9-7.6 14.6-3 3.6-6.2 6.4-9.7 8.3-3.5 1.9-8.1 3.3-14 4.3-3.4 0.6-9.8 0.9-19.2 0.9H633l-8.5 48.4z m12.1-69.5h6.7c11.5 0 19.1-0.9 23-2.6 3.8-1.7 6.9-4.5 9.1-8.3 2.2-3.8 3.3-8 3.3-12.6 0-3.1-0.6-5.6-1.7-7.5-1.1-2-2.7-3.4-4.8-4.3-2-0.9-6.6-1.3-13.7-1.3H643l-6.4 36.6zM734.6 453.3l-20.2-2.1c2.3-8.2 6.3-14.6 12.1-19.3 5.7-4.6 13.3-6.9 22.8-6.9 9.8 0 17.1 2.4 21.8 7.2 4.7 4.8 7.1 10.6 7.1 17.5 0 2.8-0.2 5.7-0.6 8.9-0.4 3.1-1.8 11.3-4.3 24.6-2 11-3 18.7-3 23.1 0 3.9 0.6 8.3 1.7 13.1h-20.1c-0.8-3.4-1.3-6.8-1.5-10.4-3 4-6.5 7.2-10.5 9.3-3.9 2.2-7.9 3.3-11.9 3.3-6.3 0-11.6-2.5-15.7-7.5s-6.2-11.4-6.2-19.3c0-8.8 2.3-15.8 6.8-21.1 4.5-5.3 12.6-8.4 24.3-9.5 9.8-1 16.4-2.2 19.7-3.6 0.9-3.5 1.3-6.2 1.3-8.3 0-2.7-0.9-4.9-2.7-6.7-1.8-1.8-4.4-2.7-7.9-2.7-3.7 0-6.6 0.9-8.8 2.7s-3.4 4.4-4.2 7.7z m19.7 23.1c-1.2 0.4-2.9 0.8-5 1.1-10.4 1.5-17.2 3.7-20.3 6.6-2.3 2.1-3.4 4.9-3.4 8.4 0 2.9 0.9 5.3 2.6 7.3 1.7 2 4 3 6.8 3 3.1 0 6.1-0.9 8.8-2.7s4.8-4.2 6.2-7c1.4-2.9 2.6-7.3 3.6-13.4l0.7-3.3zM798.2 427.2h20.6l5.2 45.9c1.3 11.8 2 20.1 2.2 24.8 2.7-9.4 6.4-19.4 11.1-29.8l18.3-40.9h21.9l-47.3 101.2c-3.9 8.4-7 14.3-9.2 17.6-2.2 3.4-4.9 6-8.1 7.9-3.1 1.9-6.9 2.9-11.4 2.9-4.4 0-9.3-0.9-14.8-2.8l1.8-18.6c2.5 0.9 4.9 1.3 7.3 1.3 6.3 0 11.6-5.8 15.6-17.4l-13.2-92.1z" fill="#FFFFFF" p-id="4462"></path><path d="M491.9 660.3c-1.1 4.5-2 8.6-2.6 12.4-9.5 4.2-19.9 9.2-31.3 15.1-3.4 1.8-6.7 3.9-10 6.3l-6.1-10.5c4.7-3.3 7.6-7.1 8.8-11.4l9.5-33.9h-23.5l2.9-10.5h23.5l6.2-22.3h-11.6l2.9-10.4c-2.5 2.5-5.1 5-7.7 7.3-1.1-3.7-2.6-7.1-4.5-10.4 15.1-13.9 28.3-29.6 39.7-47.1l11.5 3.7c-4.8 6.9-9.8 13.5-15 19.8h31.5l-2.9 10.5h-37.5c-4.9 5.6-9.9 10.9-15.1 16h44l-2.9 10.5h-20l-6.2 22.3h24.8l-2.9 10.5h-24.8l-10.1 36.3c8.1-3.8 17.9-8.6 29.4-14.2zM594 631.4l6.3 8.8c-13.1 7-26 13.5-38.7 19.5 7.7 9.8 19.1 16.7 34.3 20.7-4.7 4.3-8.8 8.1-12.1 11.6-30.1-11.1-45.5-32.8-46.1-65.3h-16.1l-13.9 49.7c10.2-3.9 21.5-8.4 33.8-13.7-1.2 4.7-2.1 8.8-2.6 12.4-9.8 3.8-22.2 8.9-37 15.4-1.9 0.9-4.7 2.6-8.6 5.2l-6.1-10.5c4.6-3.4 7.5-7.1 8.6-11.3l34-121.7h84.7l-21.9 78.4H580l1.1-3.8h-31c0.6 9.6 2.8 17.9 6.5 25.2 13-6.5 25.4-13.4 37.4-20.6z m-10-15l6.1-22h-59.6l-6.1 22H584z m15-53.8h-59.6l-6.1 21.8h59.6l6.1-21.8zM627.1 661.1c4.5-0.6 9-1.2 13.5-1.9l25.9-92.6h-11.1l3-10.7h74l-3 10.7h-12.8l-23.7 84.8c5.4-0.9 10.9-1.7 16.3-2.6-0.9 4.2-1.5 7.7-1.8 10.7-5.7 1-11.6 2-17.6 3l-9 32.3h-12.5l8.4-30c-15.4 2.6-32 5.5-49.7 8.6l0.1-12.3z m52.7-7.7l6-21.6h-25l-7.1 25.5 26.1-3.9z m-16.1-31.9h25l6.2-22.3h-25l-6.2 22.3z m9.1-32.7h25l6.2-22.3h-25l-6.2 22.3z m35.9 27.3h39.5c2.5-7.4 5.3-16.6 8.3-27.6h-35.3l3.2-11.3h46.2c7.2-7.3 16.9-18 29.2-32.2l11.8 5.6c-9.8 9.8-18.9 18.7-27.2 26.5H813l-3.2 11.3h-40.1c-3.1 11-5.9 20.2-8.3 27.6h46.5l-3.2 11.3H760c1.9 24.3 12.6 42.3 32 54.1-5.1 3.7-9.8 7.5-14.2 11.4-16.4-13.7-25.9-30.8-28.4-51.4-12.4 21.8-31.2 39.4-56.4 52.9-2.4-4-4.7-7.3-6.8-9.9C713.7 671 733 652 744 627.2h-38.5l3.2-11.1z m29.4-64.8l11.7-6.3c4.9 6.9 9.2 14.5 13 22.7l-13 6.9c-2.9-7-6.8-14.8-11.7-23.3z" fill="#FFFFFF" p-id="4463"></path></svg>',
            "description": "支持各大银行网银支付",  # 支付方式描述
            "borderColor": "hover:border-blue-500",  # 鼠标悬停时的边框颜色
            "textColor": "text-blue-600"  # 文字颜色
        }


    }


def _read_payment_methods_config():
    """
    读取支付方式配置文件

    返回值:
        dict: 支付方式配置字典，如果文件不存在或读取失败，则返回默认配置

    说明:
        此函数负责从 payment_methods.json 文件中读取支付方式配置。
        - 如果文件存在且格式正确，返回文件中的配置
        - 如果文件不存在，返回默认配置
        - 如果读取过程中发生错误（如JSON格式错误），记录错误日志并返回默认配置

    异常处理:
        所有异常都会被捕获，确保函数始终返回一个有效的配置字典
    """
    # 定义配置文件路径为当前目录下的 payment_methods.json
    config_file = "payment_methods.json"

    try:
        # 检查配置文件是否存在
        if os.path.exists(config_file):
            # 文件存在，尝试打开并读取
            # 使用 utf-8 编码确保中文内容正确读取
            with open(config_file, 'r', encoding='utf-8') as f:
                # 使用 json.load 解析JSON文件内容
                # 返回解析后的字典对象
                return json.load(f)
        else:
            # 文件不存在，返回默认配置
            # 这是正常情况（首次运行或文件被删除）
            return _get_default_payment_methods_config()
    # 特别捕获JSON解析错误：当配置文件为空或格式错误时
    # 这通常是由于文件损坏或手动编辑错误导致的，属于预期的错误情况
    except json.JSONDecodeError as e:
        # 使用WARNING级别记录日志，因为这不是严重错误，系统可以使用默认配置继续运行
        logging.warning(f"[支付方式配置] 配置文件JSON格式错误，使用默认配置: {str(e)}")

        # 调用通用备份函数，备份损坏的文件并重置为默认配置
        # 使用_get_default_payment_methods_config()获取默认配置内容
        _backup_and_reset_corrupted_file(
            config_file,
            _get_default_payment_methods_config(),
            "json"
        )

        # 返回默认配置，确保系统可以正常运行
        return _get_default_payment_methods_config()
    except Exception as e:
        # 捕获其他所有可能的异常（文件读取错误、权限错误等）
        # 记录错误日志，便于排查问题
        logging.error(f"[支付方式配置] 读取配置文件失败: {str(e)}")
        # 即使发生错误，也返回默认配置，确保系统可以正常运行
        return _get_default_payment_methods_config()


def _write_payment_methods_config(methods_config):
    """
    写入支付方式配置文件

    参数:
        methods_config (dict): 支付方式配置字典，将被写入到JSON文件

    说明:
        此函数负责将支付方式配置写入到 payment_methods.json 文件。
        - 使用 utf-8 编码确保中文内容正确保存
        - 使用 ensure_ascii=False 保持中文字符不被转义
        - 使用 indent=2 格式化JSON输出，便于人工编辑

    异常处理:
        如果写入失败，会记录错误日志并重新抛出异常，由调用方处理
    """
    # 定义配置文件路径为当前目录下的 payment_methods.json
    config_file = "payment_methods.json"

    try:
        # 打开文件进行写入，如果文件不存在则创建
        # 使用 utf-8 编码确保中文内容正确保存
        with open(config_file, 'w', encoding='utf-8') as f:
            # 使用 json.dump 将字典对象序列化为JSON并写入文件
            # ensure_ascii=False: 保持中文字符不被转义为 \uXXXX 格式
            # indent=2: 使用2个空格缩进，使JSON格式更易读
            json.dump(methods_config, f, ensure_ascii=False, indent=2)
        # 写入成功，记录信息日志
        logging.info(f"[支付方式配置] 配置已保存到 {config_file}")
    except Exception as e:
        # 捕获所有可能的异常（权限错误、磁盘空间不足等）
        # 记录错误日志，便于排查问题
        logging.error(f"[支付方式配置] 写入配置文件失败: {str(e)}")
        # 重新抛出异常，让调用方知道写入失败
        # 这样调用方可以决定如何处理（如回滚操作、向用户显示错误等）
        raise


def _migrate_payment_methods_to_json():
    """
    一次性迁移：将 config.ini 中的 payment_methods_config 迁移到 JSON 文件

    说明:
        此函数用于从旧版本升级时自动迁移配置数据。
        - 如果 payment_methods.json 已存在，则跳过迁移（避免覆盖用户自定义配置）
        - 如果 config.ini 中存在旧配置，则读取并迁移到新的JSON文件
        - 如果没有旧配置，则创建默认配置文件

    迁移策略:
        1. 检查 JSON 文件是否已存在
        2. 如果不存在，尝试从 config.ini 读取旧配置
        3. 如果旧配置存在，迁移到新文件
        4. 如果旧配置不存在或读取失败，创建默认配置

    异常处理:
        所有异常都会被捕获，确保即使迁移失败也不影响应用启动
    """
    # 定义目标配置文件路径
    config_file = "payment_methods.json"

    # 检查 JSON 配置文件是否已存在
    if os.path.exists(config_file):
        # 文件已存在，说明已经迁移过或用户已自定义配置
        # 直接返回，避免覆盖用户的配置
        return

    # JSON 文件不存在，尝试从 config.ini 迁移旧配置
    try:
        # 创建 ConfigParser 对象用于读取 INI 文件
        config = configparser.ConfigParser(strict=False)
        # 读取 config.ini 文件，使用 utf-8 编码
        config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()

        # 检查 Rainbow_YiPay 节中是否存在 payment_methods_config 配置项
        if config.has_option("Rainbow_YiPay", "payment_methods_config"):
            # 旧配置存在，读取配置项的值（JSON字符串格式）
            old_config_str = config.get(
                "Rainbow_YiPay", "payment_methods_config")
            # 将JSON字符串解析为字典对象
            methods_config = json.loads(old_config_str)

            # 将解析后的配置写入新的 JSON 文件
            _write_payment_methods_config(methods_config)

            # 记录迁移成功的日志
            logging.info("[支付方式配置] 已从 config.ini 迁移到 payment_methods.json")
        else:
            # config.ini 中没有旧配置，创建默认配置
            _write_payment_methods_config(
                _get_default_payment_methods_config())
            # 记录创建默认配置的日志
            logging.info("[支付方式配置] 已创建默认配置文件 payment_methods.json")
    except Exception as e:
        # 捕获所有可能的异常（文件不存在、JSON解析错误、写入失败等）
        # 记录错误日志，但不中断应用启动
        logging.error(f"[支付方式配置] 迁移失败: {str(e)}")
        # 即使迁移失败，也尝试创建默认配置，确保系统可以正常运行
        try:
            _write_payment_methods_config(
                _get_default_payment_methods_config())
        except:
            # 如果创建默认配置也失败，只能记录错误
            # 这种情况下系统可能无法正常工作，需要用户手动处理
            pass


# ============================================================
# 高德地图去水印控制配置管理函数
# 用于管理用户的高德地图去水印权限
# ============================================================


def _get_default_amap_watermark_config():
    """
    获取高德地图去水印控制的默认配置

    返回值:
        dict: 默认的水印控制配置字典

    说明:
        此函数返回一个包含默认配置的字典结构。
        默认配置包括：
        - _comment: 配置文件说明，帮助用户理解文件用途
        - _description: 详细描述配置的作用
        - default: 默认的水印显示设置（true表示允许去水印，false表示不允许）
        - users: 用户级别的个性化配置字典，默认为空

    配置结构:
        {
            "_comment": "配置说明",
            "_description": "详细描述",
            "default": true/false,  # 默认水印显示设置
            "users": {
                "username": true/false  # 用户名: 是否允许去水印
            }
        }
    """
    # 返回默认配置结构
    # 使用有序字典确保注释字段显示在最前面，便于阅读
    # 从config.ini读取初始默认值
    initial_default = _get_watermark_removal_default()

    return {
        "_comment": "高德地图去水印个性化控制配置",
        "_description": "为每个用户配置是否允许去除高德地图水印，未配置的用户使用默认值",
        "default": initial_default,  # 默认水印显示设置
        "users": {}  # 初始为空字典，后续可按需添加用户配置
    }


def _read_amap_watermark_config():
    """
    读取高德地图去水印控制配置文件

    返回值:
        dict: 水印控制配置字典，如果文件不存在或读取失败，则返回默认配置

    说明:
        此函数负责从 amap_watermark_control.json 文件中读取去水印控制配置。
        - 如果文件存在且格式正确，返回文件中的配置
        - 如果文件不存在，返回默认配置（不会自动创建文件）
        - 如果读取过程中发生错误（如JSON格式错误），记录错误日志并返回默认配置

    异常处理:
        所有异常都会被捕获，确保函数始终返回一个有效的配置字典
        即使配置文件损坏，也不会影响系统的正常运行
    """
    # 定义配置文件路径为当前目录下的 amap_watermark_control.json
    config_file = "amap_watermark_control.json"

    try:
        # 检查配置文件是否存在
        if os.path.exists(config_file):
            # 文件存在，尝试打开并读取
            # 使用 utf-8 编码确保中文内容正确读取
            with open(config_file, 'r', encoding='utf-8') as f:
                # 使用 json.load 解析JSON文件内容
                # 返回解析后的字典对象
                config = json.load(f)

                # 验证配置文件的基本结构是否正确
                # 确保 "users" 字段存在且为字典类型
                if not isinstance(config.get("users"), dict):
                    # 如果结构不正确，记录警告并返回默认配置
                    logging.warning(f"[水印控制] 配置文件结构不正确，使用默认配置")
                    return _get_default_amap_watermark_config()

                # 配置文件格式正确，返回读取的配置
                return config
        else:
            # 文件不存在，返回默认配置
            # 这是正常情况（首次运行或文件被删除）
            return _get_default_amap_watermark_config()
    except json.JSONDecodeError as e:
        # JSON 格式错误，记录详细错误信息
        logging.error(f"[水印控制] 配置文件JSON格式错误: {str(e)}")

        # 调用通用备份函数，备份损坏的文件并重置为默认配置
        _backup_and_reset_corrupted_file(
            config_file,
            _get_default_amap_watermark_config(),
            "json"
        )

        # 返回默认配置，确保系统可以正常运行
        return _get_default_amap_watermark_config()
    except Exception as e:
        # 捕获所有其他可能的异常（文件读取错误等）
        logging.error(f"[水印控制] 读取配置文件失败: {str(e)}")
        # 返回默认配置，确保系统可以正常运行
        return _get_default_amap_watermark_config()


def _write_amap_watermark_config(config):
    """
    写入高德地图去水印控制配置文件

    参数:
        config (dict): 水印控制配置字典，将被写入到JSON文件

    说明:
        此函数负责将水印控制配置写入到 amap_watermark_control.json 文件。
        - 使用 utf-8 编码确保中文内容正确保存
        - 使用 ensure_ascii=False 保持中文字符不被转义
        - 使用 indent=2 格式化JSON输出，便于人工编辑

    写入前验证:
        在写入前会验证配置结构的有效性，确保 "users" 字段存在且为字典类型

    异常处理:
        如果写入失败，会记录错误日志并重新抛出异常，由调用方处理
    """
    # 定义配置文件路径为当前目录下的 amap_watermark_control.json
    config_file = "amap_watermark_control.json"

    try:
        # 验证配置数据的有效性
        # 确保 config 是字典类型且包含 "users" 字段
        if not isinstance(config, dict) or "users" not in config:
            # 配置数据无效，记录错误并抛出异常
            error_msg = "配置数据格式无效，必须包含 'users' 字段"
            logging.error(f"[水印控制] {error_msg}")
            raise ValueError(error_msg)

        # 确保 "users" 字段是字典类型
        if not isinstance(config["users"], dict):
            error_msg = "'users' 字段必须是字典类型"
            logging.error(f"[水印控制] {error_msg}")
            raise ValueError(error_msg)

        # 打开文件进行写入，如果文件不存在则创建
        # 使用 utf-8 编码确保中文内容正确保存
        with open(config_file, 'w', encoding='utf-8') as f:
            # 使用 json.dump 将字典对象序列化为JSON并写入文件
            # ensure_ascii=False: 保持中文字符不被转义为 \uXXXX 格式
            # indent=2: 使用2个空格缩进，使JSON格式更易读
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 写入成功，记录信息日志
        logging.info(f"[水印控制] 配置已保存到 {config_file}")
    except Exception as e:
        # 捕获所有可能的异常（权限错误、磁盘空间不足等）
        # 记录错误日志，便于排查问题
        logging.error(f"[水印控制] 写入配置文件失败: {str(e)}")
        # 重新抛出异常，让调用方知道写入失败
        # 这样调用方可以决定如何处理（如回滚操作、向用户显示错误等）
        raise


def _initialize_amap_watermark_config():
    """
    初始化高德地图去水印控制配置文件

    说明:
        此函数在应用启动时调用，用于确保配置文件存在且格式正确。
        - 如果配置文件不存在，创建默认配置文件
        - 如果配置文件存在但格式错误，记录警告但不覆盖（避免丢失数据）
        - 创建文件时会添加详细的注释，方便用户理解和修改

    执行逻辑:
        1. 检查配置文件是否存在
        2. 如果不存在，读取当前配置（会返回默认配置）
        3. 将配置写入文件（创建新文件）
        4. 如果文件已存在，只验证格式，不进行修改

    异常处理:
        所有异常都会被捕获，确保即使初始化失败也不影响应用启动
    """
    # 定义配置文件路径
    config_file = "amap_watermark_control.json"

    try:
        # 检查配置文件是否存在
        if not os.path.exists(config_file):
            # 配置文件不存在，需要创建默认配置文件
            logging.info(f"[水印控制] 配置文件不存在，正在创建默认配置...")

            # 获取默认配置
            default_config = _get_default_amap_watermark_config()

            # 将默认配置写入文件
            _write_amap_watermark_config(default_config)

            # 创建成功，记录信息日志
            logging.info(f"[水印控制] 默认配置文件已创建")
        else:
            # 配置文件已存在，验证其格式是否正确
            # 尝试读取配置文件
            config = _read_amap_watermark_config()

            # 如果读取成功（返回的不是默认配置），说明文件格式正确
            # 注意：这里我们简单地验证 "users" 字段是否存在
            if "users" in config:
                logging.info(f"[水印控制] 配置文件已存在且格式正确")
            else:
                # 文件存在但格式可能有问题，记录警告
                logging.warning(f"[水印控制] 配置文件格式可能有问题，请检查")
    except Exception as e:
        # 捕获所有异常，确保初始化失败不影响应用启动
        logging.error(f"[水印控制] 初始化配置文件失败: {str(e)}")
        # 不抛出异常，允许应用继续启动


def _get_watermark_removal_default():
    """
    从 config.ini 读取高德地图去水印的默认值

    返回值:
        bool: 默认的去水印设置，True 表示允许，False 表示禁止

    说明:
        此函数从 config.ini 文件的 [Map] 节读取 watermark_removal_default 配置项。
        - 如果配置项存在且值为 "true"（不区分大小写），返回 True
        - 如果配置项存在且值为 "false"（不区分大小写），返回 False
        - 如果配置项不存在或读取失败，返回默认值 True（允许去水印）

    配置格式:
        [Map]
        watermark_removal_default = true

    异常处理:
        所有异常都会被捕获，返回默认值 True，确保系统可以正常运行
    """
    try:
        # 创建 ConfigParser 对象用于读取 INI 文件
        config = configparser.ConfigParser(strict=False)

        # 读取 config.ini 文件，使用 utf-8 编码
        config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()

        # 检查 [Map] 节是否存在
        if config.has_section("Map"):
            # [Map] 节存在，尝试读取 watermark_removal_default 配置项
            # getboolean 方法会自动将 "true"/"false" 字符串转换为布尔值
            # fallback 参数指定当配置项不存在时的默认值
            return config.getboolean("Map", "watermark_removal_default", fallback=True)
        else:
            # [Map] 节不存在，返回默认值 True
            logging.warning(f"[水印控制] config.ini 中未找到 [Map] 节，使用默认值 True")
            return True
    except Exception as e:
        # 捕获所有可能的异常（文件不存在、读取错误、格式错误等）
        logging.error(f"[水印控制] 读取默认配置失败: {str(e)}，使用默认值 True")
        # 返回默认值 True，确保系统可以正常运行
        return True


def _normalize_watermark_default_value(value):
    """
    标准化水印控制的默认值，将各种类型的值统一转换为布尔类型

    参数:
        value: 任意类型的值，可能来自JSON配置文件

    返回值:
        bool: 转换后的布尔值

    说明:
        此函数用于处理配置文件中default字段的各种可能情况：
        - 如果是布尔值，直接返回
        - 如果是字符串"true"（不区分大小写），返回True
        - 如果是字符串"false"（不区分大小写），返回False
        - 如果是数字1，返回True
        - 如果是数字0，返回False
        - 如果是None或其他无效值，返回None（调用方需要进一步处理）

    用途:
        - 兼容手动编辑配置文件时可能产生的格式错误
        - 确保即使配置值类型不正确，也能尝试转换而不是直接失败
    """
    # [类型检查] 如果已经是布尔类型，直接返回
    if isinstance(value, bool):
        return value

    # [字符串转换] 如果是字符串类型，尝试转换为布尔值
    if isinstance(value, str):
        # 将字符串转换为小写，方便比较
        value_lower = value.lower().strip()

        # 检查是否为"true"（表示允许去水印）
        if value_lower == "true":
            return True

        # 检查是否为"false"（表示不允许去水印）
        elif value_lower == "false":
            return False

        # 字符串既不是"true"也不是"false"，无法转换
        # 返回None，让调用方决定如何处理
        else:
            return None

    # [数字转换] 如果是数字类型（int或float），尝试转换为布尔值
    if isinstance(value, (int, float)):
        # 1表示True（允许去水印）
        if value == 1:
            return True
        # 0表示False（不允许去水印）
        elif value == 0:
            return False
        # 其他数字无法转换，返回None
        else:
            return None

    # [其他类型] 对于None或其他无法识别的类型，返回None
    # 调用方应该检查返回值是否为None，并使用备用方案（如从config.ini读取）
    return None


def _create_permissions_json(force=False):
    """创建默认的permissions.json权限配置文件"""
    # 增加 force 参数判断，如果为 True 则跳过存在性检查，直接覆盖（即清空重建）
    if not force and os.path.exists("permissions.json"):
        print("[权限配置] permissions.json 已存在，跳过创建")
        return

    print("[权限配置] 创建新的 permissions.json 文件...")
    permissions = {
        "permission_groups": {
            "guest": {
                "name": "游客",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": False,
                    "delete_tasks": False,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": False,
                    "view_user_details": True,
                    "modify_user_settings": False,
                    "execute_multi_account": False,
                    "use_attendance": False,
                    "view_logs": False,
                    "clear_logs": False,
                    "auto_fill_password": False,
                    "view_school_account_passwords": False,
                    "bypass_overdue": False,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": False,
                    "use_login_button": True,
                    "use_multi_account_button": False,
                    "use_import_button": False,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": False,
                    "delete_any_messages": False,
                    "modify_config": False,
                },
            },
            "user": {
                "name": "普通用户",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": False,
                    "use_attendance": True,
                    "view_logs": False,
                    "clear_logs": False,
                    "auto_fill_password": False,
                    "view_school_account_passwords": False,
                    "bypass_overdue": False,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "use_login_button": True,
                    "use_multi_account_button": False,
                    "use_import_button": False,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": False,
                    "modify_config": True,
                    "view_session_details": True,
                },
            },
            "admin": {
                "name": "管理员",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": True,
                    "use_attendance": True,
                    "view_logs": True,
                    "clear_logs": True,
                    "manage_users": True,
                    "manage_permissions": True,
                    "reset_user_password": True,
                    "view_audit_logs": True,
                    "view_all_sessions": True,
                    "force_logout_users": True,
                    "auto_fill_password": True,
                    "view_school_account_passwords": True,
                    "bypass_overdue": True,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "manage_user_sessions": True,
                    "view_session_details": True,
                    "use_login_button": True,
                    "use_multi_account_button": True,
                    "use_import_button": True,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": True,
                    "view_captcha_history": True,
                    "modify_config": True,
                    "manage_system": True,
                },
            },
            "super_admin": {
                "name": "超级管理员",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": True,
                    "use_attendance": True,
                    "view_logs": True,
                    "clear_logs": True,
                    "manage_users": True,
                    "manage_permissions": True,
                    "reset_user_password": True,
                    "view_audit_logs": True,
                    "view_all_sessions": True,
                    "force_logout_users": True,
                    "manage_system": True,
                    "create_permission_groups": True,
                    "delete_permission_groups": True,
                    "modify_permission_groups": True,
                    "auto_fill_password": True,
                    "view_school_account_passwords": True,
                    "bypass_overdue": True,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "manage_user_sessions": True,
                    "view_captcha_history": True,
                    "view_session_details": True,
                    "god_mode": True,
                    "use_login_button": True,
                    "use_multi_account_button": True,
                    "use_import_button": True,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": True,
                    "modify_config": True,
                },
            },
        },
        "user_groups": {},
        "user_custom_permissions": {},
    }

    with open("permissions.json", "w", encoding="utf-8") as f:
        json.dump(permissions, f, indent=2, ensure_ascii=False)
    print("[权限配置] permissions.json 文件创建完成")


def _create_default_admin():
    """创建默认的管理员账号"""
    admin_dir = "system_accounts"
    if not os.path.exists(admin_dir):
        os.makedirs(admin_dir, exist_ok=True)
        print(f"[管理员账号] 创建目录: {admin_dir}")

    username = "admin"
    filename = hashlib.sha256(username.encode()).hexdigest()
    admin_file = os.path.join(admin_dir, f"{filename}.json")

    if os.path.exists(admin_file):
        print("[管理员账号] 默认管理员账号已存在，跳过创建")
        logging.info(
            f"[系统初始化] 管理员账号已存在 --> 文件路径: {admin_file}, 跳过创建流程"
        )
        return

    print("[管理员账号] 创建默认管理员账号 (用户名: admin)...")
    logging.info(
        f"[系统初始化] 开始创建默认管理员账号 --> 用户名: admin, 权限组: super_admin, 文件路径: {admin_file}"
    )
    admin_data = {
        "auth_username": "admin",
        "password": "admin",
        "group": "super_admin",
        "created_at": time.time(),
        "last_login": None,
        "session_ids": [],
        "2fa_enabled": False,
        "2fa_secret": None,
        "avatar_url": "default_avatar.png",
        "max_sessions": -1,
        "theme": "light",
        "phone": "",
        "nickname": "超级管理员",
        # 可用执行次数字段：记录用户还可以执行多少次任务
        # 默认值为0，表示初始状态下没有可用次数
        # 当值为 -1 时表示无限次数（适用于超级管理员等特殊账户）
        "available_runs": -1,
    }

    with open(admin_file, "w", encoding="utf-8") as f:
        json.dump(admin_data, f, indent=2, ensure_ascii=False)
    print("[管理员账号] 默认管理员账号创建完成")
    logging.info(
        f"[系统初始化] 管理员账号创建成功 --> 文件路径: {admin_file}, 账号信息: 用户名=admin, 权限组=super_admin, 双因素认证=未启用, 最大会话数=无限制, 主题=light"
    )


def get_session_file_path(session_id: str) -> str:
    """根据 session_id (UUID) 计算会话文件的完整路径"""
    session_hash = hashlib.sha256(session_id.encode()).hexdigest()
    return os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")


SESSION_UUID_V4_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
    re.IGNORECASE,
)

ADMIN_ORIGIN_SESSION_HEADER = "X-Admin-Origin-Session-ID"


def normalize_session_uuid(session_id):
    """返回有效 UUID v4 字符串；无效或空值返回空字符串。"""
    normalized = str(session_id or "").strip()
    if not normalized or normalized.lower() in {"null", "undefined", "none"}:
        return ""
    if not SESSION_UUID_V4_PATTERN.match(normalized):
        return ""
    return normalized.lower()


# 从请求路径中提取 /uuid=<uuid> 形式的会话 UUID
PATH_SESSION_UUID_PATTERN = re.compile(
    r"/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})",
    re.IGNORECASE,
)


def resolve_request_session_id():
    """
    解析当前请求所属的会话 UUID，按可靠性依次回退：

        1. X-Session-ID 请求头（前端显式携带，最可靠）
        2. session_id Cookie（服务端下发，httponly）
        3. 请求路径中的 /uuid=<uuid>

    背景:
        前端只在通过 /uuid=<uuid> 打开页面时才持有会话 UUID
        （getAuthenticatedSessionHeaderValue() 依赖 authSessionUUID /
        sessionUUID）。直接从根路径打开首页时两者都为空，请求头会是空串，
        于是任何"仅信任请求头"的接口都会误判为"缺少会话ID参数"。

    返回值:
        str: 规范化后的 UUID v4；三者都拿不到时返回空字符串。
    """
    header_session_id = normalize_session_uuid(
        request.headers.get("X-Session-ID", "")
    )
    if header_session_id:
        return header_session_id

    cookie_session_id = normalize_session_uuid(request.cookies.get("session_id", ""))
    if cookie_session_id:
        return cookie_session_id

    path_match = PATH_SESSION_UUID_PATTERN.search(request.path or "")
    return normalize_session_uuid(path_match.group(1) if path_match else "")


def resolve_admin_origin_session_context(
    target_session_id, origin_session_id, token, lock_held=False
):
    """验证管理员查看态的来源会话，返回来源管理员身份上下文。"""
    target_session_id = normalize_session_uuid(target_session_id)
    origin_session_id = normalize_session_uuid(origin_session_id)
    if (
        not target_session_id
        or not origin_session_id
        or target_session_id == origin_session_id
        or not token
    ):
        return None

    def _read_origin_api_context():
        origin_api = web_sessions.get(origin_session_id)
        if origin_api is None:
            return None, False, True, None, "guest"
        is_authenticated = getattr(origin_api, "is_authenticated", False)
        is_guest = getattr(origin_api, "is_guest", True)
        origin_username = getattr(origin_api, "auth_username", None)
        origin_group = getattr(origin_api, "auth_group", "guest")
        return origin_api, is_authenticated, is_guest, origin_username, origin_group

    if lock_held:
        (
            origin_api,
            is_authenticated,
            is_guest,
            origin_username,
            origin_group,
        ) = _read_origin_api_context()
    else:
        with web_sessions_lock:
            (
                origin_api,
                is_authenticated,
                is_guest,
                origin_username,
                origin_group,
            ) = _read_origin_api_context()

    if not is_authenticated or is_guest or not origin_username:
        return None

    is_valid, reason = token_manager.verify_token(
        origin_username,
        origin_session_id,
        token,
    )
    if not is_valid:
        logging.warning(
            f"[管理员查看] 来源会话 {origin_session_id[:8]} token 无效 ({reason})"
        )
        return None

    if not auth_system.check_permission(origin_username, "view_all_sessions"):
        logging.warning(
            f"[管理员查看] 用户 {origin_username} 缺少 view_all_sessions 权限"
        )
        return None

    # 查看态请求是来源会话仍被使用的唯一证据：必须在这里续期，
    # 否则来源会话会在不活跃超时后被回收并连带吊销该用户的 token，
    # 管理员查看态随即整体 401 掉线。
    touch_admin_view_origin_session(origin_session_id)

    return {
        "session_id": origin_session_id,
        "username": origin_username,
        "group": origin_group,
        "api_instance": origin_api,
    }


def resolve_admin_view_identity(session_id, token, session_owner_username=""):
    """解析“管理员查看态”调用者的真实身份（不要求是超级管理员）。

    背景:
        能进入他人会话的不一定是超级管理员：老版 UI 的查看态（上帝模式）和
        Vue 版 /auth/switch_session 都只要求 view_all_sessions（默认 admin /
        super_admin 组都具备）。命名路由（例如 /api/check_overdue）和通用
        /api/<path:method> 此前只给“超级管理员 token”兜底，非超级管理员的
        管理员进入他人会话后这些接口会直接 401，前端表现为掉线。

    判定（与来源会话校验保持一致，按权限放行）:
        - 请求会话有效、token 非空，且 token 持有者不是被查看会话的持有者；
        - token 能在令牌目录中反查到持有者，并通过该持有者的有效期校验；
        - 持有者具备 view_all_sessions 权限；超级管理员保留兜底。

    返回:
        dict | None: {"username", "group", "session_id"}；校验失败返回 None。
    """
    normalized_session_id = normalize_session_uuid(session_id)
    normalized_token = str(token or "").strip()
    if not normalized_session_id or not normalized_token:
        return None

    session_owner = str(session_owner_username or "").strip()
    auth_system_instance = globals().get("auth_system")
    token_manager_instance = globals().get("token_manager")
    if auth_system_instance is None or token_manager_instance is None:
        return None

    reverse_lookup = getattr(
        token_manager_instance, "resolve_username_by_token", None
    )
    if not callable(reverse_lookup):
        return None

    try:
        token_owner = reverse_lookup(normalized_token)
    except Exception as error:
        logging.warning("[管理员查看] 反查 token 持有者失败: %s", error)
        return None

    # 只接受明确的用户名字符串，避免异常返回值被当成有效身份。
    if not isinstance(token_owner, str):
        return None
    token_owner = token_owner.strip()
    if not token_owner or token_owner == session_owner:
        return None

    try:
        verification = token_manager_instance.verify_token(
            token_owner,
            normalized_session_id,
            normalized_token,
        )
    except Exception as error:
        logging.warning("[管理员查看] 校验 token 持有者失败: %s", error)
        return None

    if isinstance(verification, tuple):
        is_valid = bool(verification) and verification[0] is True
    else:
        is_valid = verification is True
    if not is_valid:
        return None

    super_admin = ""
    try:
        super_admin = str(
            auth_system_instance.config.get(
                "Admin", "super_admin", fallback="admin"
            )
            or ""
        ).strip()
    except Exception:
        super_admin = ""

    try:
        has_permission = (
            auth_system_instance.check_permission(
                token_owner, "view_all_sessions"
            )
            is True
        )
    except Exception as error:
        logging.warning("[管理员查看] 校验查看权限失败: %s", error)
        return None

    if not has_permission:
        if not super_admin or token_owner != super_admin:
            logging.warning(
                "[管理员查看] 用户 %s 缺少 view_all_sessions 权限，拒绝查看态访问",
                token_owner,
            )
            return None
        logging.info(
            "[管理员查看] 超级管理员 %s 走保留兜底（未显式持有 view_all_sessions）",
            token_owner,
        )

    group = ""
    try:
        get_group = getattr(auth_system_instance, "get_user_group", None)
        if callable(get_group):
            group = str(get_group(token_owner) or "").strip()
    except Exception as error:
        logging.debug("[管理员查看] 读取用户组失败: %s", error)
    if not group:
        group = "super_admin" if token_owner == super_admin else "user"

    logging.info(
        "[管理员查看] 允许 %s(%s) 以查看态访问用户 %s 的会话 %s",
        token_owner,
        group,
        session_owner or "(未知)",
        normalized_session_id[:8],
    )
    return {
        "username": token_owner,
        "group": group,
        "session_id": normalized_session_id,
    }


def is_persistent_business_session(api_instance):
    """Return whether an in-memory API instance represents a business session."""
    return getattr(api_instance, "_is_persistent_session", True) is not False


def is_multi_account_logged_in(account_session):
    """Return whether one account in a multi-account session is logged in."""
    return bool(getattr(account_session, "is_first_login_verified", False))


def get_business_session_login_success(api_instance):
    """Resolve the session-list login badge for single and multi-account modes."""
    if not getattr(api_instance, "is_multi_account_mode", False):
        return bool(getattr(api_instance, "login_success", False))

    accounts = getattr(api_instance, "accounts", {}) or {}
    return any(is_multi_account_logged_in(account) for account in accounts.values())


def promote_auth_session_to_persistent(source_session_id, target_session_id):
    """Promote a temporary auth context in place and move it to a new session ID."""
    source_session_id = normalize_session_uuid(source_session_id)
    target_session_id = normalize_session_uuid(target_session_id)
    if not source_session_id or not target_session_id or source_session_id == target_session_id:
        return None

    with web_sessions_lock:
        api_instance = web_sessions.get(source_session_id)
        if api_instance is None or is_persistent_business_session(api_instance):
            return None
        if target_session_id in web_sessions:
            raise ValueError("目标会话ID已存在")

        del web_sessions[source_session_id]
        api_instance._web_session_id = target_session_id
        api_instance._is_persistent_session = True
        api_instance._session_created_at = time.time()
        web_sessions[target_session_id] = api_instance
        if "session_activity" in globals() and "session_activity_lock" in globals():
            with session_activity_lock:
                last_activity = session_activity.pop(source_session_id, None)
                if last_activity is not None:
                    session_activity[target_session_id] = last_activity
        logging.info(
            f"临时认证会话已自动转换为持久业务会话: "
            f"{source_session_id[:8]}... -> {target_session_id[:8]}..."
        )
        return api_instance


AUTH_OPTIONAL_API_METHODS = {"get_initial_data"}


def is_auth_optional_api_method(method):
    """这些通用 API 可在尚未创建业务会话时用于只读初始化。"""
    normalized = str(method or "").strip()
    return normalized in AUTH_OPTIONAL_API_METHODS


def should_use_auth_optional_api_context(
    method, session_id="", session_exists=False, restored_state=None
):
    """判断通用 API 是否应降级到临时只读初始化上下文。"""
    if not is_auth_optional_api_method(method):
        return False
    if not session_id:
        return True
    if session_exists:
        return False
    if restored_state and restored_state.get("login_success"):
        return False
    return True


def resolve_auth_optional_api_session_id(method, session_id, api_instance):
    """认证可选 API 使用临时上下文时，不保留不可恢复的请求会话ID。"""
    if api_instance is None:
        return session_id
    if not should_use_auth_optional_api_context(method, session_id):
        return session_id
    if getattr(api_instance, "_is_persistent_session", True):
        return session_id
    if getattr(api_instance, "_web_session_id", ""):
        return session_id
    return ""


# ==============================================================================
# 彩虹易支付V2客户端 - 在线支付接口集成
# ==============================================================================




def _normalize_yipay_device(device_value=None):
    """
    统一归一化易支付设备类型。
    支持值：pc/mobile/qq/wechat/alipay
    """
    valid_devices = {"pc", "mobile", "qq", "wechat", "alipay"}
    raw_device = str(device_value or "").strip().lower()
    if raw_device in valid_devices:
        return raw_device

    ua = (request.headers.get("User-Agent", "") or "").lower()
    if "alipayclient" in ua or "alipay" in ua:
        return "alipay"
    if "micromessenger" in ua:
        return "wechat"
    if " qq/" in f" {ua}" or ("mqqbrowser" in ua and "mobile" in ua):
        return "qq"
    if any(k in ua for k in ["mobile", "android", "touch", "webos", "hpwos"]):
        return "mobile"
    return "pc"


class RainbowYiPayClient:
    """
    彩虹易支付V2接口客户端类

    功能说明：
    这个类封装了彩虹易支付（Rainbow Yi Pay）V2版本的所有API接口
    支持创建支付订单、查询订单状态、验证支付回调签名等功能

    支付流程：
    1. 调用 create_order() 创建支付订单，获取支付跳转URL
    2. 用户在支付页面完成支付
    3. 支付成功后，彩虹易支付会异步回调 notify_url
    4. 调用 verify_sign() 验证回调签名，确认支付成功
    5. 可通过 query_order() 主动查询订单状态

    安全机制：
    - 使用MD5签名算法验证所有请求和回调
    - 签名密钥存储在服务器端，不会暴露给客户端
    - 异步回调必须验证签名，防止伪造通知
    """

    def __init__(self, config_file=CONFIG_JSON_FILE):
        """
        初始化彩虹易支付客户端

        参数:
            config_file (str): 配置文件路径，默认为 ".\\configs\\config.json"

        功能:
            从配置文件中读取彩虹易支付的商户参数，包括：
            - host: 易支付接口域名
            - pid: 商户ID
            - key: 商户密钥（用于签名）
            - notify_url: 异步通知URL
            - return_url: 同步返回URL

        异常:
            如果配置文件不存在或配置项缺失，会记录错误日志
        """
        # 使用统一的配置读取函数，支持 JSON 格式配置文件
        self.config = _read_config_ini(config_file) or configparser.ConfigParser(strict=False)

        # 从配置文件的 [Rainbow_YiPay] 节读取易支付接口域名
        # fallback 参数指定当配置项不存在时的默认值（空字符串）
        self.host = self.config.get("Rainbow_YiPay", "host", fallback="")

        # 读取商户ID（PID），这是商户在易支付平台的唯一标识
        self.pid = self.config.get("Rainbow_YiPay", "pid", fallback="")

        # 读取商户密钥（KEY），用于生成和验证签名，必须保密
        self.key = self.config.get("Rainbow_YiPay", "key", fallback="")

        # 读取异步通知URL，支付成功后易支付会向这个URL发送POST请求
        self.notify_url = self.config.get(
            "Rainbow_YiPay", "notify_url", fallback="")

        # 读取同步返回URL，用户支付完成后浏览器会跳转到这个URL
        self.return_url = self.config.get(
            "Rainbow_YiPay", "return_url", fallback="")

        # 记录日志：彩虹易支付客户端初始化成功
        # 日志中包含商户ID，方便调试和追踪
        logging.info(f"[彩虹易支付] 客户端初始化成功 - 商户ID: {self.pid}")

    def create_order(self, out_trade_no, name, money, pay_type="alipay",
                     return_url=None, client_app_host=None, payment_type="web",
                     device_get=None, auth_code=None, sub_openid=None, sub_appid=None,
                     clientip=None):
        """
        创建支付订单
        """
        # 按接口约定固定 method=web，由平台根据 device 自动判断实际拉起方式
        method = "web"
        logging.info(
            f"[彩虹易支付] 创建订单请求 - 订单号: {out_trade_no}, 商品名称: {name}, 金额: {money}, 支付方式: {pay_type}, 接口类型: {method}，服务器端地址：{client_app_host}，设备：{device_get}")
        if pay_type == "jsapi":
            if not sub_openid or not sub_appid:
                return {"success": False, "message": "jsapi支付方式需要提供sub_openid和sub_appid"}
            logging.info("[彩虹易支付] 检测到jsapi支付方式，必要参数已提供")
        if pay_type == "scan":
            if not auth_code:
                return {"success": False, "message": "scan支付方式需要提供auth_code"}
            logging.info("[彩虹易支付] 检测到scan支付方式，付款码已提供")

        # 声明使用全局 requests 变量
        # requests 已在 check_and_import_dependencies() 中导入
        global requests

        # 兜底客户端IP，避免易支付拒绝“clientip不能为空”
        clientip = str(clientip or "").strip()
        if not clientip:
            try:
                clientip = str(
                    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                    or request.environ.get("REMOTE_ADDR")
                    or request.remote_addr
                    or ""
                ).strip()
            except Exception:
                clientip = ""
            if not clientip:
                clientip = "127.0.0.1"
            logging.warning(f"[彩虹易支付] clientip 为空，已使用兜底IP: {clientip}")

        # 兜底客户端IP，避免易支付拒绝“clientip不能为空”
        clientip = str(clientip or "").strip()
        if not clientip:
            try:
                clientip = str(
                    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                    or request.environ.get("REMOTE_ADDR")
                    or request.remote_addr
                    or ""
                ).strip()
            except Exception:
                clientip = ""
            if not clientip:
                clientip = "127.0.0.1"
            logging.warning(f"[彩虹易支付] clientip 为空，已使用兜底IP: {clientip}")

        # 检查必需的配置参数是否已填写
        # 如果 host、pid 或 key 为空，说明配置不完整，无法创建订单
        if not self.host or not self.pid or not self.key:
            # 记录错误日志
            logging.error("[彩虹易支付] 配置不完整，无法创建订单")
            # 返回失败响应
            return {"success": False, "message": "彩虹易支付配置不完整，请联系管理员"}

        # 构造异步通知URL（notify_url）
        # 从配置文件中读取应用的公网访问域名（app_host）
        # app_host 是本应用的公网访问地址，例如："https://yourdomain.com"
        app_host_frome_config = self.config.get(
            "Rainbow_YiPay", "app_host", fallback="").strip()

        # 初始化最终结果变量
        final_app_host = None

        # 定义无效字符串列表，方便复用
        invalid_values = ["", "http://", "https://",
                          "null", "NULL", "None", "none", "undefined"]

        # 1. 优先检查配置文件中的 Host (优先级最高)
        if app_host_frome_config is not None and app_host_frome_config not in invalid_values:
            # 实例化一次即可，避免重复开销
            verifier = IPVerifier()

            if not verifier.is_private_ip(app_host_frome_config):
                if verifier.check_app_host(app_host_frome_config):
                    final_app_host = verifier.normalize_host_url(
                        app_host_frome_config)
                    logging.info(
                        f"[支付验证] 验证成功 - 将优先使用 app_host_from_config: {app_host_frome_config}")
                    logging.info(
                        f"[彩虹易支付] 配置的 app_host 验证通过: {final_app_host}")
                else:
                    logging.error(
                        f"[彩虹易支付] 配置的 app_host 格式不正确或不可用: {app_host_frome_config}")
            else:
                logging.warning(
                    f"[彩虹易支付] 配置的 app_host 为私有IP，跳过: {app_host_frome_config}")
        else:
            # 只有当 config 为空时才打印这个 warning，或者可以选择不打印，直接进入下一步
            logging.warning(f"[彩虹易支付] 配置的 app_host 为空或无效，尝试使用 client_app_host")

        # 2. 如果配置文件无效 (final_app_host 仍为 None)，则检查传入的 Client Host (优先级次之)
        if final_app_host is None:
            if client_app_host is not None and client_app_host not in invalid_values:
                #  - 这里的逻辑是如果上面没拿到值，才走这里
                verifier = IPVerifier()

                if not verifier.is_private_ip(client_app_host):
                    if verifier.check_app_host(client_app_host):
                        final_app_host = verifier.normalize_host_url(
                            client_app_host)
                        logging.info(
                            f"[支付验证] 验证成功 - 使用传入的 client_app_host: {client_app_host}")
                        logging.info(
                            f"[彩虹易支付] 传入的 client_app_host 验证通过: {final_app_host}")
                    else:
                        logging.error(
                            f"[彩虹易支付] 传入的 client_app_host 格式不正确或不可用: {client_app_host}")
                else:
                    logging.warning(
                        f"[彩虹易支付] 传入的 client_app_host 为私有IP: {client_app_host}")
            else:
                logging.warning(
                    f"[彩虹易支付] 传入的 client_app_host 为空或无效: {client_app_host}")

        # 3. 最终结果赋值 (为了兼容你后续代码可能使用的变量名 'app_host')
        app_host = final_app_host

        if app_host is None:
            logging.error(
                f"[彩虹易支付] 致命错误: 无法获取有效的 app_host (配置和客户端传入均无效)，无法构造回调URL")

            return {"success": False, "message": "彩虹易支付配置缺少 app_host，请联系管理员"}

        # 验证 app_host 格式是否正确
        # 必须以 http:// 或 https:// 开头，以确保URL格式正确
        if not (app_host.startswith("http://") or app_host.startswith("https://")):
            # 记录错误日志：app_host 格式不正确
            logging.error(f"[彩虹易支付] app_host 格式不正确（缺少协议头）: {app_host}")
            # 返回失败响应，提示管理员修正配置
            return {"success": False, "message": "彩虹易支付配置 app_host 格式不正确，必须包含 http:// 或 https://"}

        # 移除 app_host 末尾的斜杠（如果存在）
        # 这样可以避免构造出双斜杠的URL，例如：https://example.com//api/...
        # rstrip('/') 会移除字符串末尾的所有斜杠
        app_host = app_host.rstrip('/')

        # 自动构造异步通知URL
        # 格式：{app_host}/api/payment/yipay_notify
        # 这是彩虹易支付专用的异步通知接收地址
        # 当用户支付成功后，彩虹易支付服务器会向这个URL发送POST请求
        notify_url = f"{app_host}/api/payment/yipay_notify"

        # 确定同步返回URL（return_url）
        # 仅允许与当前 app_host 同源的完整 URL；不允许跨站地址。
        return_url = _normalize_payment_return_url(
            return_url,
            app_host=app_host,
            notify_url=notify_url,
        )
        if return_url is None:
            return_url = notify_url

        device = _normalize_yipay_device(device_get)

        # 构造订单参数字典
        # 这些参数将被发送到彩虹易支付API
        params = {
            "pid": self.pid,                    # 商户ID
            "type": pay_type,                   # 支付方式（alipay/wxpay）
            "out_trade_no": out_trade_no,       # 商户订单号（必须唯一）
            "notify_url": notify_url,           # 异步通知URL（动态构造）
            "return_url": return_url,           # 同步返回URL（可动态传入）
            "name": name,                       # 商品名称
            "money": str(money),                # 支付金额（转为字符串）
            "method": method,                   # 接口类型（web/jump/jsapi/app/scan/applet）
            "device": device,                   # 支付设备（pc/mobile/qq/wechat/alipay）
            "clientip": clientip,
        }

        # auth_code参数：仅scan接口类型需要
        if auth_code and method == "scan":
            params["auth_code"] = auth_code

        # sub_openid和sub_appid参数：仅jsapi接口类型需要
        if method == "jsapi":
            if sub_openid:
                params["sub_openid"] = sub_openid
            if sub_appid:
                params["sub_appid"] = sub_appid

        # 获取当前时间戳
        params["timestamp"] = int(time.time())

        RainbowYiPayRsaSigner = RsaSigner(self.key)

        data_to_sent = RainbowYiPayRsaSigner.generate_sign(params)
        safe_order_data = {
            key: value
            for key, value in params.items()
            if key not in {
                "auth_code",
                "sub_openid",
                "sub_appid",
                "return_url",
                "notify_url",
            }
        }

        # 构造完整的API请求URL
        # 彩虹易支付的创建订单接口路径为 /api/pay/create
        api_url = f"{self.host}/api/pay/create"

        # 记录信息日志：开始创建订单
        logging.info(
            f"[彩虹易支付] 创建订单 - 订单号: {out_trade_no}, 金额: {money}元, 支付方式: {pay_type}")

        logging.info(
            f"[彩虹易支付] 发起请求 - URL: {api_url}, 已签名参数数量: {len(data_to_sent)}",
            extra={"method": "POST"},
        )

        try:
            # 向彩虹易支付API发送POST请求
            response = requests.post(api_url, data=data_to_sent, timeout=10)

            logging.info(
                f"[彩虹易支付] 收到响应 - 状态码: {response.status_code}, "
                f"响应长度: {len(response.content or b'')}"
            )

            # 检查HTTP响应状态码
            # status_code 200 表示请求成功
            if response.status_code == 200:
                # 尝试解析响应内容为JSON格式
                # 易支付API通常返回JSON格式的响应
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    # 如果响应不是有效的JSON，可能是HTML格式的支付页面
                    # 某些易支付版本直接返回支付页面HTML
                    # 此时 response.url 就是支付URL
                    logging.warning("[彩虹易支付] API返回非JSON响应，使用响应URL作为支付链接")
                    return {
                        "success": True,
                        "message": "订单创建成功",
                        "pay_url": response.url,  # 使用重定向后的URL
                        "order_data": safe_order_data,
                    }

                # 检查API响应中的状态码
                # code=0 表示成功，其他值表示失败（根据API文档）
                if result.get("code") == 0:
                    # 订单创建成功
                    # 获取平台订单号
                    trade_no = result.get("trade_no", "")

                    # 获取发起支付类型（jump/html/qrcode/urlscheme/jsapi/app/scan/wxplugin/wxapp）
                    pay_type_response = result.get("pay_type", "")

                    # 获取发起支付参数
                    pay_info = result.get("pay_info", "")

                    # 兼容旧版：提取支付URL
                    # pay_url可能直接是pay_info（当pay_type为jump时），或者需要从pay_info中解析
                    pay_url = pay_info
                    if not pay_url:
                        # 如果pay_info为空，尝试从其他字段获取
                        pay_url = result.get("payurl") or result.get(
                            "url") or result.get("qrcode")

                    # 检查是否成功获取到支付信息
                    if pay_info or pay_url:
                        logging.info(
                            f"[彩虹易支付] 订单创建成功 - 平台订单号: {trade_no}, 支付类型: {pay_type_response}")
                        data_to_sent2 = {
                            "success": True,
                            "message": "订单创建成功",
                            "pay_url": pay_url,           # 兼容旧版
                            "trade_no": trade_no,         # 平台订单号
                            "pay_type": pay_type_response,  # 发起支付类型
                            "pay_info": pay_info,         # 发起支付参数
                            "order_data": safe_order_data,
                        }
                        return data_to_sent2
                    else:
                        # API响应中没有支付信息
                        logging.error("[彩虹易支付] API响应中缺少支付信息")
                        return {
                            "success": False,
                            "message": "易支付API响应异常，缺少支付信息",
                        }
                else:
                    # 订单创建失败，API返回了错误信息
                    error_msg = result.get("msg") or result.get(
                        "message") or "未知错误"
                    logging.error(
                        f"[彩虹易支付] 创建订单失败 - "
                        f"错误信息长度: {len(str(error_msg))}"
                    )
                    return {
                        "success": False,
                        "message": "创建订单失败，请稍后重试",
                    }
            else:
                # HTTP请求失败（非200状态码）
                logging.error(
                    f"[彩虹易支付] HTTP请求失败 - 状态码: {response.status_code}"
                )
                return {
                    "success": False,
                    "message": f"支付接口请求失败 (HTTP {response.status_code})",
                }

        except requests.exceptions.Timeout:
            # 请求超时异常
            logging.error("[彩虹易支付] 请求超时")
            return {"success": False, "message": "支付接口请求超时，请稍后重试"}

        except requests.exceptions.RequestException as e:
            # 其他网络请求异常（如网络不通、DNS解析失败等）
            logging.error(f"[彩虹易支付] 网络请求异常: {type(e).__name__}")
            return {"success": False, "message": "网络请求失败，请稍后重试"}

        except Exception as e:
            # 捕获所有未预期的异常
            logging.error(f"[彩虹易支付] 创建订单异常: {type(e).__name__}")
            logging.error(traceback.format_exc())
            return {"success": False, "message": "创建订单时发生错误，请稍后重试"}


# ==============================================================================
# 认证和权限管理系统
# ==============================================================================

def _get_guest_config(config):
    defaults = _get_default_config()

    def read_value(key, fallback):
        if config and config.has_option("Guest", key):
            return config.get("Guest", key, fallback=str(fallback))
        return fallback

    return {
        "allow_guest_login": str(
            read_value(
                "allow_guest_login",
                defaults.get("Guest", "allow_guest_login", fallback=True),
            )
        ).lower()
        in ("true", "1", "yes", "on"),
        "max_active_guest_sessions": int(
            read_value(
                "max_active_guest_sessions",
                defaults.get(
                    "Guest", "max_active_guest_sessions", fallback=100
                ),
            )
        ),
        "guest_session_inactivity_timeout": int(
            read_value(
                "guest_session_inactivity_timeout",
                defaults.get(
                    "Guest", "guest_session_inactivity_timeout", fallback=300
                ),
            )
        ),
        "guest_token_ttl_seconds": int(
            read_value(
                "guest_token_ttl_seconds",
                defaults.get(
                    "Guest", "guest_token_ttl_seconds", fallback=3600
                ),
            )
        ),
        "guest_token_grace_seconds": int(
            read_value(
                "guest_token_grace_seconds",
                defaults.get(
                    "Guest", "guest_token_grace_seconds", fallback=60
                ),
            )
        ),
    }


def _apply_guest_config_updates(config, guest_data):
    if not isinstance(guest_data, dict):
        return
    if not config.has_section("Guest"):
        config.add_section("Guest")
    if "allow_guest_login" in guest_data:
        config.set(
            "Guest",
            "allow_guest_login",
            str(bool(guest_data["allow_guest_login"])).lower(),
        )
    validators = {
        "max_active_guest_sessions": 0,
        "guest_session_inactivity_timeout": 60,
        "guest_token_ttl_seconds": 60,
        "guest_token_grace_seconds": 0,
    }
    for key, minimum in validators.items():
        if key not in guest_data:
            continue
        value = int(guest_data[key])
        if value < minimum:
            raise ValueError(f"{key} must be >= {minimum}")
        config.set("Guest", key, str(value))


def _count_active_guest_sessions(timeout_seconds):
    now = time.time()
    count = 0
    session_dir = globals().get("SESSION_STORAGE_DIR", "sessions")
    if not os.path.isdir(session_dir):
        return 0
    for path in glob.glob(os.path.join(session_dir, "*.json")):
        if os.path.basename(path).startswith("_"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fp:
                state = json.load(fp)
            if not state.get("is_guest"):
                continue
            if now - float(state.get("last_accessed", 0)) > timeout_seconds:
                continue
            count += 1
        except (OSError, ValueError, TypeError):
            continue
    return count


def _create_guest_session_atomic(
    session_id,
    preview_bundle_id,
    max_active_guest_sessions,
):
    with GUEST_SESSION_CREATION_LOCK:
        config = _read_config_ini(CONFIG_FILE) or _get_default_config()
        guest_config = _get_guest_config(config)
        if not guest_config["allow_guest_login"]:
            return {"success": False, "code": "guest_login_disabled"}
        active_count = _count_active_guest_sessions(
            guest_config["guest_session_inactivity_timeout"]
        )
        limit = int(max_active_guest_sessions)
        if active_count >= limit:
            return {
                "success": False,
                "code": "guest_limit_reached",
                "active_guest_sessions": active_count,
                "max_active_guest_sessions": limit,
            }
        return {
            "success": True,
            "session_id": session_id,
            "preview_bundle_id": str(preview_bundle_id or ""),
        }


def _load_guest_session_record(session_id):
    path = get_session_file_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fp:
        state = json.load(fp)
    if not state.get("is_guest") or state.get("auth_username") != "guest":
        return None
    return state


def _touch_guest_session(session_id):
    state = _load_guest_session_record(session_id)
    if not state:
        return False
    config = _read_config_ini(CONFIG_FILE) or _get_default_config()
    guest_config = _get_guest_config(config)
    session_expires_at = (
        time.time() + guest_config["guest_session_inactivity_timeout"]
    )
    with web_sessions_lock:
        api_instance = web_sessions.get(session_id)
        if api_instance:
            save_session_state(session_id, api_instance, force_save=True)
    if token_manager and getattr(token_manager, "guest_store", None):
        token_manager.guest_store.refresh(session_id, session_expires_at)
    return True


def _resolve_request_identity():
    auth_token = request.cookies.get("auth_token", "")
    session_id = normalize_session_uuid(request.cookies.get("session_id", ""))
    if not auth_token:
        return {"authenticated": False, "principal_type": "anonymous"}
    guest_store = getattr(token_manager, "guest_store", None)
    guest_session_id = guest_store.find_session_id(auth_token) if guest_store else ""
    if guest_session_id:
        session_record = _load_guest_session_record(guest_session_id)
        if not session_record:
            guest_store.invalidate(guest_session_id)
            return {"authenticated": False, "principal_type": "anonymous"}
        _touch_guest_session(guest_session_id)
        return {
            "authenticated": True,
            "principal_type": "guest",
            "username": "guest",
            "session_id": guest_session_id,
            "is_current": guest_session_id == session_id,
        }
    tokens_dir = globals().get("TOKENS_STORAGE_DIR", "tokens")
    for username_path in glob.glob(os.path.join(tokens_dir, "*.json")):
        username = os.path.splitext(os.path.basename(username_path))[0]
        valid, _reason = token_manager.verify_token(
            username, session_id, auth_token
        )
        if valid:
            return {
                "authenticated": True,
                "principal_type": "user",
                "username": username,
                "session_id": session_id,
            }
    return {"authenticated": False, "principal_type": "anonymous"}



# ==============================================================================
# 4. 前端界面 (HTML/CSS/JS)
# ==============================================================================


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 打包和开发环境"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def check_port_available(host, port):
    """检查端口是否可用"""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


IP_CACHE_FILE = os.path.join("logs", "ip_location_cache.json")
ip_location_cache = {}
ip_cache_lock = threading.Lock()
CACHE_DURATION_SECONDS = 86400
IP_CACHE_TTL_SECONDS = CACHE_DURATION_SECONDS
IP_CACHE_MAX_ENTRIES = 2000

PHONE_CACHE_FILE = os.path.join("logs", "phone_location_cache.json")
phone_location_cache = {}
phone_cache_lock = threading.Lock()
PHONE_CACHE_TTL_SECONDS = 30 * 86400
PHONE_CACHE_MAX_ENTRIES = 1000


def _prune_timestamped_cache(cache, ttl_seconds, max_entries, now_ts=None):
    current_ts = float(now_ts if now_ts is not None else time.time())
    ttl_seconds = max(float(ttl_seconds), 0.0)
    max_entries = max(int(max_entries), 0)
    removed_expired = 0
    removed_overflow = 0

    for key, entry in list(cache.items()):
        if not isinstance(entry, dict):
            cache.pop(key, None)
            removed_expired += 1
            continue
        try:
            timestamp = float(entry.get("timestamp", 0) or 0)
        except (TypeError, ValueError):
            cache.pop(key, None)
            removed_expired += 1
            continue
        if timestamp <= 0 or current_ts - timestamp >= ttl_seconds:
            cache.pop(key, None)
            removed_expired += 1

    while len(cache) > max_entries:
        cache.pop(next(iter(cache)), None)
        removed_overflow += 1

    if removed_expired or removed_overflow:
        logging.info(
            "[缓存诊断] 清理完成: remaining=%d, expired=%d, overflow=%d, "
            "ttl_seconds=%s, max_entries=%d",
            len(cache),
            removed_expired,
            removed_overflow,
            ttl_seconds,
            max_entries,
        )

    return {
        "remaining": len(cache),
        "removed_expired": removed_expired,
        "removed_overflow": removed_overflow,
    }


def _touch_cache_key(cache, key):
    if key not in cache:
        return
    cache[key] = cache.pop(key)


def _load_ip_cache():
    """启动时加载IP归属地缓存文件"""
    global ip_location_cache
    if not os.path.exists(IP_CACHE_FILE):
        logging.info("[IP缓存] 缓存文件不存在，将创建新缓存")
        return

    with ip_cache_lock:
        try:
            with open(IP_CACHE_FILE, "r", encoding="utf-8") as f:
                ip_location_cache = json.load(f)
            _prune_timestamped_cache(
                ip_location_cache,
                IP_CACHE_TTL_SECONDS,
                IP_CACHE_MAX_ENTRIES,
            )
            logging.info(f"[IP缓存] 成功加载 {len(ip_location_cache)} 条IP缓存记录")
        except json.JSONDecodeError as e:
            logging.error(f"[IP缓存] 加载缓存文件失败（JSON解析错误）: {e}")

            # 调用通用备份函数，备份损坏的缓存文件并重置为空字典
            _backup_and_reset_corrupted_file(
                IP_CACHE_FILE,
                {},
                "json"
            )

            ip_location_cache = {}
        except OSError as e:
            logging.warning(f"[IP缓存] 加载缓存文件失败（文件操作错误）: {e}，将创建新缓存")
            ip_location_cache = {}


def _save_ip_cache():
    """保存IP归属地缓存到文件（线程安全）"""
    with ip_cache_lock:
        try:
            _prune_timestamped_cache(
                ip_location_cache,
                IP_CACHE_TTL_SECONDS,
                IP_CACHE_MAX_ENTRIES,
            )
            os.makedirs(os.path.dirname(IP_CACHE_FILE), exist_ok=True)
            cache_copy = ip_location_cache.copy()

            with open(IP_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_copy, f, indent=2, ensure_ascii=False)
            logging.debug("[IP缓存] IP缓存已保存到文件")
        except OSError as e:
            logging.error(f"[IP缓存] 保存缓存文件失败: {e}")
        except Exception as e:
            logging.error(f"[IP缓存] 序列化缓存数据失败: {e}")


def _load_phone_cache():
    global phone_location_cache
    if not os.path.exists(PHONE_CACHE_FILE):
        return
    with phone_cache_lock:
        try:
            with open(PHONE_CACHE_FILE, "r", encoding="utf-8") as f:
                phone_location_cache = json.load(f)
            _prune_timestamped_cache(
                phone_location_cache,
                PHONE_CACHE_TTL_SECONDS,
                PHONE_CACHE_MAX_ENTRIES,
            )
        except Exception:
            phone_location_cache = {}


def _save_phone_cache():
    with phone_cache_lock:
        try:
            _prune_timestamped_cache(
                phone_location_cache,
                PHONE_CACHE_TTL_SECONDS,
                PHONE_CACHE_MAX_ENTRIES,
            )
            os.makedirs(os.path.dirname(PHONE_CACHE_FILE), exist_ok=True)
            with open(PHONE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(phone_location_cache.copy(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"[手机缓存] 保存失败: {e}")


def _migrate_ip_location_config_if_needed():
    """
    兼容旧配置并自动迁移 IP_Location 配置。
    优先读取旧的 query_method，按照其优先级重新生成 query_order，
    迁移完成后移除 query_method 配置项。
    """
    try:
        cfg = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
        changed = False
        if not cfg.has_section("IP_Location"):
            cfg.add_section("IP_Location")
            changed = True

        # 检查是否存在旧的 query_method 配置
        has_query_method = cfg.has_option("IP_Location", "query_method")
        has_query_order = cfg.has_option("IP_Location", "query_order")
        
        if has_query_method and not has_query_order:
            # 存在旧配置但没有新配置，进行迁移
            legacy_method = cfg.get("IP_Location", "query_method", fallback="uapipro").strip().lower()
            base_order = ["uapipro", "amap", "baidu"]
            if legacy_method in ("uapipro", "amap", "baidu", "pconline"):
                # 将旧的优先方式放在首位
                new_order = [legacy_method] + [x for x in base_order if x != legacy_method]
            else:
                new_order = base_order
            cfg.set("IP_Location", "query_order", ",".join(new_order))
            changed = True
            logging.info(f"[配置迁移] IP查询方式从 query_method({legacy_method}) 迁移到 query_order({','.join(new_order)})")
        elif not has_query_order:
            # 既没有旧配置也没有新配置，设置默认值
            cfg.set("IP_Location", "query_order", "uapipro,amap,baidu")
            changed = True
        
        # 移除旧的 query_method 配置项（如果存在）
        if has_query_method:
            cfg.remove_option("IP_Location", "query_method")
            changed = True
            logging.info("[配置迁移] 已移除旧的 query_method 配置项")
            
        if not cfg.has_option("IP_Location", "amap_web_api_key"):
            cfg.set("IP_Location", "amap_web_api_key", "")
            changed = True
        if not cfg.has_option("IP_Location", "uapipro_api_key"):
            cfg.set("IP_Location", "uapipro_api_key", "")
            changed = True

        if changed:
            _write_config_with_comments(cfg, CONFIG_JSON_FILE)
            logging.info("[配置迁移] IP_Location 配置迁移完成")
    except Exception as e:
        logging.warning(f"[配置迁移] IP_Location 迁移失败: {e}")


def update_session_activity(session_id):
    """更新会话活动时间"""
    with session_activity_lock:
        session_activity[session_id] = time.time()


def update_session_activity(session_id):
    """更新会话活动时间（线程安全）"""
    if not session_id:
        return
    with session_activity_lock:
        session_activity[session_id] = time.time()
        logging.debug(f"[会话活跃] 更新会话 {session_id} 的活跃时间")


def touch_admin_view_origin_session(origin_session_id):
    """记录管理员查看态来源会话仍在被使用，并同步其会话/浏览活跃度。

    背景:
        管理员用老版 UI 强制进入他人会话后不会再调用 /auth/switch_session，
        自身会话的 API 流量全部转移到目标会话。如果不在这里同步活跃度:
          1. 会话不活跃监控会在 session_inactivity_timeout 后回收来源会话；
          2. 回收时因为"用户没有其他浏览行为"，还会删除该用户的 token 文件；
        两步叠加后管理员查看态的所有请求都会 401，前端表现为掉线。

    这里同时更新三处状态:
        - admin_view_origin_activity: 保活窗口记录，供会话监控识别查看态；
        - session_activity: 不活跃监控与内存上限淘汰都按它排序；
        - browsing_activity: 清理该用户其他会话时据此跳过 token 失效。

    保活属于尽力而为的辅助状态，任何异常都不能影响本次鉴权结果。
    """
    session_id = normalize_session_uuid(origin_session_id)
    if not session_id:
        return

    try:
        now = time.time()
        with admin_view_origin_activity_lock:
            admin_view_origin_activity[session_id] = now

        update_session_activity(session_id)

        with browsing_activity_lock:
            browsing_activity[session_id] = now

        logging.debug(
            "[管理员查看] 已续期来源会话: session=%s",
            session_id[:8],
        )
    except Exception as error:
        logging.warning(
            "[管理员查看] 续期来源会话活跃状态失败（不影响本次鉴权）: "
            "session=%s, error=%s",
            session_id[:8],
            error,
        )


def is_admin_view_origin_session_active(session_id, now_ts=None, ttl=None):
    """判断来源会话是否仍在管理员查看态保活窗口内。"""
    session_id = normalize_session_uuid(session_id)
    if not session_id:
        return False

    now_value = time.time() if now_ts is None else float(now_ts)
    window = (
        ADMIN_VIEW_ORIGIN_KEEPALIVE_SECONDS if ttl is None else float(ttl)
    )
    with admin_view_origin_activity_lock:
        last_touch = admin_view_origin_activity.get(session_id, 0)
    if not last_touch:
        return False
    return (now_value - last_touch) <= window


def is_admin_view_origin_owner_active(session_id, owner_username, timeout_seconds):
    """来源会话的持有者是否仍在通过其他会话使用应用。

    查看态页面完全空闲 30 分钟后保活窗口会失效，此时如果查看者仍在发请求
    （例如 Vue 版 /auth/switch_session 切过去之后，请求只带目标会话，不携带
    来源会话头），来源会话会被不活跃监控回收并连带吊销查看者的 token。
    这里用"查看者的 token 最近仍被刷新"作为仍在使用的证据：只要查看者还在
    任何页面活动，来源会话就不回收；完全空闲时仍回到普通回收逻辑。
    """
    session_id = normalize_session_uuid(session_id)
    owner = str(owner_username or "").strip()
    if not session_id or not owner:
        return False

    with admin_view_origin_activity_lock:
        if session_id not in admin_view_origin_activity:
            return False

    return _is_user_token_in_active_use(owner, timeout_seconds)


def clear_admin_view_origin_session(session_id):
    """清理来源会话保活记录（会话被显式销毁或回收时调用）。"""
    session_id = normalize_session_uuid(session_id)
    if not session_id:
        return
    with admin_view_origin_activity_lock:
        admin_view_origin_activity.pop(session_id, None)


def _collect_other_user_sessions(username, exclude_session_id):
    """收集该用户名下仍然真实存在的其他会话。

    用于判断"被销毁的会话是不是该用户唯一的会话"：

        - 内存中（web_sessions）仍活跃、且属于该用户的其他会话；
        - 用户文件登记的、并且确实存在持久化状态文件的其他会话。

    只登记在用户文件里但既不在内存也没有状态文件的会话 ID 属于历史残留，
    不能因为它的存在而让 token 一直不失效。
    """
    username = str(username or "").strip()
    if not username:
        return []

    exclude_session_id = normalize_session_uuid(exclude_session_id)
    others = []

    try:
        with web_sessions_lock:
            live_sessions = list(web_sessions.items())
        for sid, api_instance in live_sessions:
            if not sid or sid == exclude_session_id:
                continue
            if getattr(api_instance, "auth_username", "") == username:
                others.append(sid)
    except Exception as error:
        logging.warning("[会话清理] 统计内存中的其他会话失败: %s", error)

    try:
        stored_sessions = auth_system.get_user_sessions(username) or []
    except Exception as error:
        logging.warning("[会话清理] 读取用户会话列表失败: %s", error)
        stored_sessions = []

    for sid in stored_sessions:
        if not sid or sid == exclude_session_id or sid in others:
            continue
        try:
            if os.path.exists(get_session_file_path(sid)):
                others.append(sid)
        except Exception:
            continue

    return others


def _is_user_token_in_active_use(username, timeout_seconds):
    """判断该用户的 token 是否仍在被使用（最近刷新过）。

    TokenManager 是"每用户一个 token"。取消其中一个会话时如果直接删除
    token，会连带吊销该用户仍在使用的其他页面：

        - 管理员查看态（上帝模式）下，管理员自身会话不再收到请求，
          browsing_activity 里没有它的记录；
        - /auth/switch_session 切到他人会话后，活动会话在 web_sessions 里
          登记为别人的会话，get_user_sessions(管理员) 里也没有它。

    上面两种情况下 token 文件仍会被每个请求刷新（通用 API 会
    refresh_token），因此以 token 的最近活动时间作为"仍在使用"的判据。
    读取失败或时间戳非法时返回 False，保持原来的失效逻辑。
    """
    token_manager_instance = globals().get("token_manager")
    if token_manager_instance is None:
        return False

    getter = getattr(token_manager_instance, "get_token_last_activity", None)
    if not callable(getter):
        return False

    try:
        last_activity = float(getter(username) or 0)
    except Exception:
        return False

    if last_activity <= 0:
        return False

    try:
        window = float(timeout_seconds)
    except Exception:
        window = 0
    if window <= 0:
        return False

    return (time.time() - last_activity) < window


def _cleanup_chrome_context_for_session(session_id):
    if not session_id:
        return

    pool = globals().get("chrome_pool")
    if not pool:
        logging.debug(
            "[浏览器上下文] 未初始化或已禁用，跳过会话清理: session=%s",
            session_id,
        )
        return

    try:
        logging.info("[浏览器上下文] 正在释放会话资源: session=%s", session_id)
        pool.cleanup_context(session_id)
        logging.info("[浏览器上下文] 会话资源已释放: session=%s", session_id)
    except Exception as error:
        logging.warning(
            "[浏览器上下文] 会话清理失败: session=%s, error=%s",
            session_id,
            error,
            exc_info=True,
        )


def _get_windows_process_memory_counters():
    if os.name != "nt":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL
        if get_process_memory_info(
            get_current_process(),
            ctypes.byref(counters),
            counters.cb,
        ):
            return counters
    except Exception:
        pass
    return None


def _get_process_max_rss_mb():
    counters = _get_windows_process_memory_counters()
    if counters is not None:
        return round(
            float(counters.PeakWorkingSetSize) / (1024 * 1024),
            2,
        )

    try:
        import resource

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return round(float(rss_kb) / (1024 * 1024), 2)
        return round(float(rss_kb) / 1024, 2)
    except Exception:
        return None


def _get_process_rss_mb():
    counters = _get_windows_process_memory_counters()
    if counters is not None:
        return round(float(counters.WorkingSetSize) / (1024 * 1024), 2)

    try:
        with open("/proc/self/statm", "r", encoding="ascii") as statm_file:
            resident_pages = int(statm_file.read().split()[1])
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return round(
            resident_pages * page_size / (1024 * 1024),
            2,
        )
    except Exception:
        return None


def _get_health_uptime_seconds():
    monotonic_start = globals().get("server_start_monotonic")
    if monotonic_start is None:
        return 0.0

    try:
        return max(time.monotonic() - float(monotonic_start), 0.0)
    except Exception:
        return 0.0


def _safe_runtime_collection_size(collection_name, lock_name=None):
    collection = globals().get(collection_name)
    if collection is None:
        return 0

    lock = globals().get(lock_name) if lock_name else None
    try:
        if lock is not None:
            with lock:
                return len(collection)
        return len(collection)
    except Exception:
        return -1


def _collect_runtime_memory_diagnostics():
    account_threads = [
        thread
        for thread in threading.enumerate()
        if getattr(thread, "name", "").startswith("AccountRefresh-")
    ]
    multi_monitor_threads = [
        thread
        for thread in threading.enumerate()
        if getattr(thread, "name", "") == "MultiAccountMonitor"
    ]

    playwright_contexts = None
    pool = globals().get("chrome_pool")
    if pool is not None and hasattr(pool, "_contexts"):
        try:
            playwright_contexts = len(pool._contexts)
        except Exception:
            playwright_contexts = -1

    server_start_time = globals().get("server_start_time")
    server_start_time_formatted = None
    if server_start_time is not None:
        try:
            server_start_time_formatted = datetime.datetime.fromtimestamp(
                float(server_start_time)
            ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            server_start_time_formatted = None

    gc_counts = None
    gc_thresholds = None
    if gc is not None:
        try:
            gc_counts = list(gc.get_count())
            gc_thresholds = list(gc.get_threshold())
        except Exception:
            pass

    return {
        "process_id": os.getpid(),
        "server_start_time": server_start_time,
        "server_start_time_formatted": server_start_time_formatted,
        "rss_mb": _get_process_rss_mb(),
        "max_rss_mb": _get_process_max_rss_mb(),
        "active_threads": threading.active_count(),
        "account_refresh_threads": len(account_threads),
        "multi_monitor_threads": len(multi_monitor_threads),
        "playwright_contexts": playwright_contexts,
        "web_sessions": _safe_runtime_collection_size(
            "web_sessions", "web_sessions_lock"
        ),
        "admin_view_origins": _safe_runtime_collection_size(
            "admin_view_origin_activity", "admin_view_origin_activity_lock"
        ),
        "ip_cache": _safe_runtime_collection_size("ip_location_cache", "ip_cache_lock"),
        "phone_cache": _safe_runtime_collection_size(
            "phone_location_cache", "phone_cache_lock"
        ),
        "sms_codes": _safe_runtime_collection_size("sms_verification_codes"),
        "gc_counts": gc_counts,
        "gc_thresholds": gc_thresholds,
    }


def _log_runtime_memory_diagnostics(context):
    diagnostics = _collect_runtime_memory_diagnostics()

    logging.info(
        "[内存诊断] 快照: context=%s, web_sessions=%d, "
        "admin_view_origins=%d, "
        "account_refresh_threads=%d, multi_monitor_threads=%d, "
        "process_threads=%d, playwright_contexts=%s, ip_cache=%d, "
        "phone_cache=%d, sms_codes=%d, rss_mb=%s, max_rss_mb=%s",
        context,
        diagnostics["web_sessions"],
        diagnostics["admin_view_origins"],
        diagnostics["account_refresh_threads"],
        diagnostics["multi_monitor_threads"],
        diagnostics["active_threads"],
        diagnostics["playwright_contexts"],
        diagnostics["ip_cache"],
        diagnostics["phone_cache"],
        diagnostics["sms_codes"],
        diagnostics["rss_mb"],
        diagnostics["max_rss_mb"],
    )


def cleanup_session(session_id, reason="manual"):
    """清理指定会话（支持指定原因）"""
    if not session_id or session_id == "null" or session_id.strip() == "":
        logging.debug(f"跳过清理无效会话ID: '{session_id}'")
        return

    logging.info(f"清理会话: {session_id} (原因: {reason})")
    cleanup_inactive_session(session_id, reason=reason)


def cleanup_inactive_session(session_id, reason="manual"):
    """清理不活跃的会话"""
    if not session_id or session_id == "null" or session_id.strip() == "":
        logging.debug(f"跳过清理无效会话ID: '{session_id}'")
        return

    try:
        logging.info(
            "[会话清理] 开始: session=%s, reason=%s",
            session_id,
            reason,
        )
        runtime_username = None
        api_instance = None
        with web_sessions_lock:
            api_instance = web_sessions.pop(session_id, None)

        if api_instance is None:
            logging.warning(
                "[会话清理] 内存中未找到会话，将继续清理残留资源: session=%s",
                session_id,
            )
        else:
            logging.info(
                "[会话清理] 已从 web_sessions 移除: session=%s, remaining=%d",
                session_id,
                len(web_sessions),
            )

        if api_instance is not None and hasattr(
            api_instance, "stop_run_flag"
        ):
            api_instance.stop_run_flag.set()

        if api_instance is not None and hasattr(
            api_instance, "auth_username"
        ) and not getattr(api_instance, "is_guest", True):
            username = api_instance.auth_username
            runtime_username = username
            other_sessions = []
            is_token_in_use = False
            timeout = 300
            try:
                if os.path.exists(CONFIG_FILE):
                    cfg = _read_config_ini(CONFIG_FILE)
                    if cfg:
                        timeout = cfg.getint(
                            "System",
                            "session_inactivity_timeout",
                            fallback=300,
                        )
                other_sessions = _collect_other_user_sessions(
                    username, session_id
                )
            except Exception as e:
                logging.error(f"检查用户其他会话失败: {e}", exc_info=True)

            if other_sessions:
                # 该用户还有其他会话：销毁其中一个会话不应该吊销"每用户一个"
                # 的 token，否则其他页面会被一起踢下线。
                logging.info(
                    "[会话清理] 用户 %s 还有其他 %d 个会话，跳过 token 失效: session=%s",
                    username,
                    len(other_sessions),
                    session_id,
                )
            else:
                # 这是该用户最后一个会话：默认应该吊销 token；但如果能证明
                # token 仍在被刷新（管理员查看态/切换态下，活动会话在
                # web_sessions 里登记为别人的会话），删除它会让查看者的整个
                # 浏览态 401 掉线，因此仍然保留。
                # 这一步必须独立于上面的其他会话检查：否则检查出错时会误删。
                try:
                    is_token_in_use = _is_user_token_in_active_use(
                        username, timeout
                    )
                except Exception as e:
                    logging.error(f"检查 token 活动状态失败: {e}", exc_info=True)
                    is_token_in_use = False
                if is_token_in_use:
                    logging.info(
                        "[会话清理] 用户 %s 的 token 仍在活动使用中，跳过 token 失效: session=%s",
                        username,
                        session_id,
                    )

            try:
                auth_system.unlink_session_from_user(username, session_id)
            except Exception as auth_error:
                logging.warning(
                    "[会话清理] 解绑认证会话失败，继续释放本地资源: "
                    "user=%s, session=%s, error=%s",
                    username,
                    session_id,
                    auth_error,
                    exc_info=True,
                )

            if not other_sessions and not is_token_in_use:
                try:
                    token_manager.invalidate_token(username, session_id)
                    logging.info(
                        "[会话清理] 已使用户 %s 最后一个会话 %s 的 token 失效",
                        username,
                        session_id,
                    )
                except Exception as token_error:
                    logging.warning(
                        "[会话清理] token 失效失败，继续释放本地资源: "
                        "user=%s, session=%s, error=%s",
                        username,
                        session_id,
                        token_error,
                        exc_info=True,
                    )

        if api_instance is not None:
            shutdown = getattr(api_instance, "shutdown_session_runtime", None)
            if callable(shutdown):
                try:
                    shutdown(reason=reason)
                except Exception as error:
                    logging.error(
                        "[会话运行时] 清理会话资源失败: session=%s, error=%s",
                        session_id,
                        error,
                        exc_info=True,
                    )
            else:
                stop_run_flag = getattr(api_instance, "stop_run_flag", None)
                if stop_run_flag is not None:
                    stop_run_flag.set()

        _cleanup_chrome_context_for_session(session_id)
        _release_map_key_runtime_session(session_id, runtime_username)
        # 会话已销毁，来源会话保活记录同步失效，避免残留记录让这个 UUID 一直不被回收。
        clear_admin_view_origin_session(session_id)
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        session_file = os.path.join(
            SESSION_STORAGE_DIR, f"{session_hash}.json")
        if os.path.exists(session_file):
            os.remove(session_file)
            logging.info(f"已删除会话文件: {session_hash}")
        with session_activity_lock:
            if session_id in session_activity:
                del session_activity[session_id]
        with browsing_activity_lock:
            if session_id in browsing_activity:
                del browsing_activity[session_id]
        with session_file_locks_lock:
            if session_hash in session_file_locks:
                del session_file_locks[session_hash]
        index = _load_session_index()
        if session_id in index:
            del index[session_id]
            _save_session_index(index)

        with web_sessions_lock:
            remaining_sessions = len(web_sessions)
        logging.info(
            "[会话清理] 完成: session=%s, reason=%s, remaining_sessions=%d",
            session_id,
            reason,
            remaining_sessions,
        )
        _log_runtime_memory_diagnostics(
            f"session_cleanup:{reason}"
        )
    except Exception as e:
        logging.error(
            "[会话清理] 失败: session=%s, error=%s",
            session_id,
            e,
            exc_info=True,
        )


def _multi_account_has_running_worker(api_instance) -> bool:
    """多账号会话里是否还有账号 worker 正在跑任务。

    多账号的“开始前等待 / 任务间等待”都发生在账号 worker 线程内部，worker
    存活即代表该账号的任务流程（含两种等待）仍在进行，不能按空闲回收。

    监控不依赖 multi_run_stop_flag：该标志现在会在最后一个 worker 退出后
    复位（api_runtime._mark_multi_account_run_stopped_if_idle），但直接读
    账号 worker 状态可以避免任何标志维护失误让空闲会话再次被永久保活。
    也不能改用 has_pending_tasks：它只表示“还有可执行任务”，账号没在跑
    时同样为真。
    """
    accounts = getattr(api_instance, "accounts", None)
    if not accounts:
        return False
    for acc in list(accounts.values()):
        worker = getattr(acc, "worker_thread", None)
        if worker is not None and worker.is_alive():
            return True
    return False


def _session_has_running_background_task(session_id) -> bool:
    """会话级后台任务（background_task_manager）是否仍在执行。"""
    manager = globals().get("background_task_manager")
    if manager is None:
        return False
    try:
        state = manager.get_task_status(session_id)
    except Exception:
        logging.warning(
            "[会话监控] 读取后台任务状态失败: session=%s",
            session_id,
            exc_info=True,
        )
        return False
    return bool(state) and str(state.get("status", "")).strip() == "running"


def monitor_session_inactivity():
    """
    监控会话不活跃状态并清理
    """
    check_interval = 60
    inactivity_timeout = 300

    try:
        if os.path.exists(CONFIG_JSON_FILE):
            config = configparser.ConfigParser(strict=False)
            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            if config.has_section("System"):
                check_interval = config.getint(
                    "System", "session_monitor_check_interval", fallback=60
                )
                inactivity_timeout = config.getint(
                    "System", "session_inactivity_timeout", fallback=300
                )
    except Exception as e:
        logging.warning(f"读取会话监控配置失败，使用默认值: {e}")

    while True:
        try:
            time.sleep(check_interval)
            current_time = time.time()
            inactive_sessions_to_cleanup = []
            active_sessions_to_update = []
            with web_sessions_lock:
                sessions_snapshot = list(web_sessions.items())

            for session_id, api_instance in sessions_snapshot:
                if not session_id or session_id == "null" or session_id.strip() == "" or session_id == "undefined":
                    continue
                if not api_instance:
                    continue
                with session_activity_lock:
                    if session_id not in session_activity:
                        session_activity[session_id] = current_time
                    last_activity = session_activity[session_id]

                has_background_activity = False
                is_multi = getattr(
                    api_instance, "is_multi_account_mode", False)

                if is_multi:
                    # 多账号模式直接按“账号 worker 是否还在跑”判断：
                    # multi_run_stop_flag 已经会在最后一个 worker 退出后复位，
                    # 但监控不依赖该标志，避免标志维护失误让空闲会话无法回收。
                    if _multi_account_has_running_worker(
                        api_instance
                    ) or _session_has_running_background_task(session_id):
                        has_background_activity = True
                        logging.debug(
                            f"[会话监控] {session_id} 多账号任务执行中")
                elif (
                    hasattr(api_instance, "stop_run_flag")
                    and not api_instance.stop_run_flag.is_set()
                ):
                    has_background_activity = True
                    logging.debug(f"[会话监控] {session_id} 单账号跑步任务执行中")

                # 检查是否有启用自动签到的账号（从JSON配置读取）
                if is_multi:
                    accounts = getattr(api_instance, "accounts", None) or {}
                    # 多账号模式下，检查是否有任何账号启用了自动签到
                    auto_attendance_count = 0
                    for username, acc in accounts.items():
                        acc_user_data = getattr(acc, "user_data", None)
                        if acc_user_data and acc_user_data.username:
                            if _is_auto_attendance_enabled(acc_user_data.username):
                                auto_attendance_count += 1

                    logging.debug(
                        f"[会话监控] {session_id} 多账号模式，启用自动签到的账号数: {auto_attendance_count}/{len(accounts)}"
                    )
                    if accounts and auto_attendance_count > 0:
                        has_background_activity = True
                        logging.debug(f"[会话监控] {session_id} 多账号自动签到开启中")
                else:
                    # 单账号模式，检查当前用户是否启用了自动签到
                    user_data = getattr(api_instance, "user_data", None)
                    auto_attendance = False
                    if user_data and user_data.username:
                        auto_attendance = _is_auto_attendance_enabled(
                            user_data.username)

                    logging.debug(
                        f"[会话监控] {session_id} 单账号模式自动签到状态: {auto_attendance}"
                    )

                    if auto_attendance:
                        has_background_activity = True
                        logging.debug(f"[会话监控] {session_id} 单账号自动签到开启中")

                # 管理员查看态来源会话：管理员正在用这个会话查看他人会话，
                # 它本身收不到普通 API 流量，但绝不能按不活跃回收，
                # 否则回收会连带吊销管理员的 token，查看态整体 401 掉线。
                if not has_background_activity and is_admin_view_origin_session_active(
                    session_id, current_time
                ):
                    has_background_activity = True
                    logging.debug(
                        f"[会话监控] {session_id} 处于管理员查看态保活窗口，更新活跃时间"
                    )
                if (
                    not has_background_activity
                    and is_admin_view_origin_owner_active(
                        session_id,
                        getattr(api_instance, "auth_username", None),
                        inactivity_timeout,
                    )
                ):
                    # 保活窗口过期（查看态页面长时间没有携带来源会话头的请求），
                    # 但查看者仍在其他会话发请求：同样不能回收来源会话。
                    has_background_activity = True
                    logging.debug(
                        f"[会话监控] {session_id} 的查看者仍在使用中，更新活跃时间"
                    )

                # --- 结果处理 ---
                if has_background_activity:
                    active_sessions_to_update.append(session_id)
                    logging.debug(f"[会话监控] {session_id} 有后台任务，更新活跃时间")
                elif (current_time - last_activity) > inactivity_timeout:
                    logging.debug(f"[会话监控] {session_id} 超过不活跃超时阈值")
                    inactive_sessions_to_cleanup.append(session_id)
                else:
                    logging.debug(
                        f"[会话监控] {session_id} 仍在活跃期内，上次活跃时间: {current_time - last_activity:.1f}秒前"
                    )

            if active_sessions_to_update:
                with session_activity_lock:
                    for sid in active_sessions_to_update:
                        session_activity[sid] = current_time

            if inactive_sessions_to_cleanup:
                logging.info(
                    f"[会话监控] 发现 {len(inactive_sessions_to_cleanup)} 个超时且无后台任务的会话，准备清理"
                )
                for sid in inactive_sessions_to_cleanup:
                    cleanup_inactive_session(sid, reason="inactive_timeout")

        except Exception as e:
            logging.error(f"会话监控线程错误: {e}", exc_info=True)


def start_session_monitor():
    """启动会话不活跃监控"""
    monitor_thread = threading.Thread(
        target=monitor_session_inactivity, daemon=True)
    monitor_thread.start()
    logging.info("会话监控线程已启动")

def load_all_sessions(args):
    """启动时加载所有持久化会话"""
    if not os.path.exists(SESSION_STORAGE_DIR):
        return
    index = _load_session_index()
    new_index = {}

    successful_sessions = {}

    loaded_count = 0
    for filename in os.listdir(SESSION_STORAGE_DIR):
        if filename == "_index.json":
            continue

        if filename.endswith(".json"):
            session_file = os.path.join(SESSION_STORAGE_DIR, filename)
            session_id = None
            session_hash = filename[:-5]
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                session_id = state.get("session_id")
                if not session_id:
                    raise ValueError(f"文件 {filename} 缺少 session_id")
                last_accessed = state.get("last_accessed", 0)
                if time.time() - last_accessed > 7 * 24 * 3600:
                    logging.info(
                        f"清理过期会话: {session_id[:8]}... (文件: {filename})"
                    )
                    try:
                        os.remove(session_file)
                    except Exception as remove_err:
                        logging.error(f"删除过期会话文件 {filename} 失败: {remove_err}")
                    continue
                api_instance = Api(args)
                api_instance._session_created_at = state.get(
                    "created_at", time.time())
                api_instance._web_session_id = session_id
                restore_session_to_api_instance(api_instance, state)
                logging.info(
                    f"成功恢复会话: {session_id}... (用户: {api_instance.auth_username if hasattr(api_instance, 'auth_username') else 'Unknown'}, 文件: {filename})"
                )
                web_sessions[session_id] = api_instance
                session_activity[session_id] = last_accessed
                successful_sessions[session_id] = session_hash
                loaded_count += 1

            except (
                json.JSONDecodeError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
            ) as e:
                logging.error(
                    f"加载或恢复会话文件 {filename} 失败: {e}", exc_info=False
                )
                logging.warning(f"将删除损坏的/无法恢复的会话文件: {filename}")
                try:
                    os.remove(session_file)
                except Exception as remove_err:
                    logging.error(f"删除损坏的会话文件 {filename} 失败: {remove_err}")
                continue
            except Exception as e:
                logging.error(
                    f"处理会话文件 {filename} 时发生未知错误: {e}", exc_info=True
                )
                try:
                    os.remove(session_file)
                except Exception as remove_err:
                    logging.error(
                        f"删除未知错误的会话文件 {filename} 失败: {remove_err}"
                    )
                continue
    if successful_sessions:
        _save_session_index(successful_sessions)
        logging.info(f"会话索引已更新，包含 {len(successful_sessions)} 个有效会话")
    elif not any(
        f.endswith(".json") and f != "_index.json"
        for f in os.listdir(SESSION_STORAGE_DIR)
    ):
        _save_session_index({})
        logging.info("会话目录为空，已清空会话索引。")
    if new_index:
        _save_session_index(new_index)
        logging.debug(f"会话索引已更新，包含 {len(new_index)} 个有效会话")

    if loaded_count > 0:
        logging.info(f"共加载 {loaded_count} 个持久化会话")

def _cleanup_playwright():
    """
    在程序退出时清理Playwright资源。

    此函数会先调用 cleanup_thread() 清理 Playwright 资源，
    然后调用 shutdown() 停止专用工作线程。
    """
    global chrome_pool
    if chrome_pool:
        logging.info("捕获到程序退出信号，正在清理 Playwright 资源...")
        try:
            # 先清理 Playwright 资源（浏览器、上下文等）
            chrome_pool.cleanup_thread()
            # 再停止专用工作线程
            chrome_pool.shutdown()
            logging.info("Playwright浏览器自动化框架资源清理完成")
        except Exception as e:
            logging.error(f"清理 Playwright 资源时发生错误: {e}", exc_info=False)
    else:
        logging.debug("Playwright 池未初始化，无需清理。")


def start_background_auto_attendance(args):
    """
    在服务器启动时扫描所有.ini配置文件，为启用自动签到的账号启动后台工作线程。
    """
    try:
        logging.info("正在启动后台自动签到服务...")

        accounts_dir = SCHOOL_ACCOUNTS_DIR

        if not os.path.exists(accounts_dir):
            logging.warning(f"后台签到：未找到账号目录 {accounts_dir}，跳过。")
            return

        enabled_accounts = []

        for filename in os.listdir(accounts_dir):
            if filename.endswith(".ini"):
                username = os.path.splitext(filename)[0]
                try:
                    temp_api = Api(args)
                    # 从新路径加载密码
                    auth_username = getattr(temp_api, "auth_username", None)
                    password = None
                    if auth_username:
                        accounts = temp_api._load_user_school_accounts(
                            auth_username)
                        account_info = accounts.get(username)
                        if account_info:
                            password = account_info.get("password")

                    if not password:
                        logging.debug(
                            f"后台签到：跳过账号 {username}，因为未在 {filename} 中找到密码。"
                        )
                        continue

                    # 从JSON配置读取自动签到启用状态
                    # 首先需要获取学校账号用户名，这需要登录后才能获取
                    # 为了避免在这里登录，我们从INI文件的params中读取（如果存在）
                    # 但最准确的方式是从JSON配置文件中根据学校用户名查找
                    # 这里暂时保持原逻辑，但添加注释说明需要改进
                    # TODO: 考虑在JSON配置中添加INI用户名到学校用户名的映射
                    if temp_api.params.get("auto_attendance_enabled", False):
                        # 注意：这里仍从INI读取，因为后台服务启动时还未登录
                        # 实际的自动签到检查会使用JSON配置
                        enabled_accounts.append(
                            {
                                "username": username,
                                "password": password,
                                "params": dict(temp_api.params),
                            }
                        )
                        logging.info(f"后台签到：找到启用自动签到的账号: {username}")
                    else:
                        logging.debug(
                            f"后台签到：账号 {username} 未启用自动签到，跳过。"
                        )

                except Exception as e:
                    logging.error(
                        f"后台签到：加载账号 {username} 失败: {e}", exc_info=True
                    )

        if not enabled_accounts:
            logging.info("后台签到：未找到启用自动签到的账号。")
            return

        if len(enabled_accounts) == 1:
            account = enabled_accounts[0]
            logging.info(f"后台签到：使用单账号模式，账号: {account['username']}")

            service_api = Api(args)
            service_api.is_multi_account_mode = False
            service_api.params = account["params"]
            try:
                login_result = service_api.login(
                    account["username"], account["password"]
                )
                if login_result.get("success"):
                    logging.info(f"后台签到：账号 {account['username']} 登录成功")
                    service_api.stop_auto_refresh.clear()
                    service_api.auto_refresh_thread = threading.Thread(
                        target=service_api._auto_refresh_worker,
                        daemon=True,
                        name=f"BackgroundAttendance-{account['username']}",
                    )
                    service_api.auto_refresh_thread.start()
                    globals()["_background_service_api"] = service_api
                    logging.info(f"后台签到：单账号模式启动成功")
                else:
                    logging.error(
                        f"后台签到：账号 {account['username']} 登录失败: {login_result.get('message')}"
                    )
            except Exception as e:
                logging.error(
                    f"后台签到：账号 {account['username']} 登录时发生错误: {e}",
                    exc_info=True,
                )

        else:
            logging.info(f"后台签到：使用多账号模式，共 {len(enabled_accounts)} 个账号")

            service_api = Api(args)
            service_api.is_multi_account_mode = True
            service_api._load_global_config()
            service_api.global_params["auto_attendance_enabled"] = True
            for account in enabled_accounts:
                try:
                    acc_session = AccountSession(
                        account["username"], account["password"], service_api
                    )
                    acc_session.params = account["params"]
                    service_api.accounts[account["username"]] = acc_session
                except Exception as e:
                    logging.error(
                        f"后台签到：创建账号会话失败 {account['username']}: {e}",
                        exc_info=True,
                    )
            service_api.stop_multi_auto_refresh.clear()
            service_api.multi_auto_refresh_thread = threading.Thread(
                target=service_api._multi_auto_attendance_worker,
                daemon=True,
                name="BackgroundAttendanceWorker-Multi",
            )
            service_api.multi_auto_refresh_thread.start()
            globals()["_background_service_api"] = service_api
            logging.info(
                f"后台签到：多账号模式启动成功，已加载 {len(service_api.accounts)} 个账号"
            )

    except Exception as e:
        logging.error(f"启动后台自动签到服务时发生严重错误: {e}", exc_info=True)


# ============================================================================
# SSL/HTTPS 配置和证书管理相关函数
# 这些函数用于加载、验证和管理SSL证书，支持HTTPS服务
# ============================================================================

# 密码恢复（暴力破解）功能的后端实现
# 警告：此功能仅用于合法的学校账号密码恢复
# 需要超级管理员权限，所有操作都会被详细记录
# ============================================================================

# 全局变量：存储密码恢复任务管理器
brute_force_manager = None

def _send_startup_notification_to_log_forwarder(host, port):
    """
    通过UDP向日志转发器发送Flask启动通知

    工作流程：
    1. 等待Flask服务器真正就绪（通过HTTP健康检查）
    2. 发送UDP启动通知到日志转发器
    3. 等待日志转发器的UDP确认响应
    4. 如果未收到确认，每5秒重试一次
    5. 如果1分钟内未成功，记录错误并停止尝试

    参数：
        host (str): Flask服务器地址
        port (int): Flask服务器端口
    """
    current_thread = threading.current_thread()
    logging.info(f"[UDP 通知] 函数在线程中启动: Thread[{current_thread.name}, id={current_thread.ident}]")
    
    # import socket
    # import time

    # 声明使用全局 requests 变量
    # requests 已在 check_and_import_dependencies() 中导入
    global requests

    # UDP配置
    LOG_FORWARDER_UDP_PORT = 9999  # 日志转发器监听端口
    MAIN_UDP_PORT = 9998  # main.py监听确认响应的端口
    STARTUP_MESSAGE = "FLASK_STARTED"  # 启动通知消息
    ACK_MESSAGE = "ACK_RECEIVED"  # 确认消息
    MAX_WAIT_TIME = 60  # 最大等待时间（秒）
    RETRY_INTERVAL = 5  # 重试间隔（秒）

    try:
        # 第1步：等待Flask服务器就绪（通过HTTP健康检查）
        logging.info("[UDP通知] 等待Flask服务器完全就绪...")
        flask_ready = False
        health_check_start = time.time()

        while time.time() - health_check_start < 30:  # 最多等待30秒
            try:
                response = requests.get(f"http://{host}:{port}/", timeout=1)
                if response.status_code in [
                    200,
                    404,
                    302,
                ]:  # 任何响应都表示服务器已启动
                    flask_ready = True
                    logging.info("[UDP通知] Flask服务器已就绪")
                    break
            except:
                time.sleep(0.5)  # 等待0.5秒后重试

        if not flask_ready:
            logging.warning("[UDP通知] Flask服务器健康检查超时，仍然尝试发送UDP通知")

        # 第2步：创建UDP socket用于发送通知和接收确认
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("127.0.0.1", MAIN_UDP_PORT))  # 绑定本地端口接收确认
        udp_socket.settimeout(RETRY_INTERVAL)  # 设置接收超时为重试间隔

        logging.info(f"[UDP通知] 已创建UDP socket，监听端口 {MAIN_UDP_PORT}")

        # 第3步：循环发送启动通知并等待确认
        start_time = time.time()
        attempt_count = 0
        confirmed = False

        while time.time() - start_time < MAX_WAIT_TIME:
            attempt_count += 1

            try:
                # 发送启动通知
                udp_socket.sendto(
                    STARTUP_MESSAGE.encode("utf-8"),
                    ("127.0.0.1", LOG_FORWARDER_UDP_PORT),
                )
                logging.info(
                    f"[UDP通知] 第{attempt_count}次尝试：已发送启动通知到日志转发器（端口{LOG_FORWARDER_UDP_PORT}）"
                )

                # 等待确认响应
                try:
                    data, addr = udp_socket.recvfrom(1024)
                    message = data.decode("utf-8")

                    if message == ACK_MESSAGE:
                        logging.info(
                            f"[UDP通知] ✓ 收到日志转发器的确认响应（来自 {addr}）"
                        )
                        logging.info("[UDP通知] 日志转发握手成功完成")
                        confirmed = True
                        break
                    else:
                        logging.warning(f"[UDP通知] 收到未知消息: {message}")

                except socket.timeout:
                    elapsed = int(time.time() - start_time)
                    logging.warning(
                        f"[UDP通知] 等待确认超时（已尝试{attempt_count}次，已用时{elapsed}秒），"
                        f"将在{RETRY_INTERVAL}秒后重试..."
                    )
                    # 超时后会在下一次循环重试

            except Exception as e:
                logging.error(f"[UDP通知] 发送通知时出错: {e}")
                time.sleep(RETRY_INTERVAL)

        # 第4步：检查是否成功
        if not confirmed:
            logging.error(
                f"[UDP通知] ✗ 在{MAX_WAIT_TIME}秒内未收到日志转发器的确认响应"
            )
            logging.error("[UDP通知] 日志转发系统可能未正常启动")
            logging.error("[UDP通知] 注意：这可能导致nginx日志未能转发到Python日志系统")

        # 第5步：关闭UDP socket
        udp_socket.close()
        logging.info("[UDP通知] UDP通知线程结束")

    except Exception as e:
        logging.error(f"[UDP通知] UDP通知线程发生异常: {e}", exc_info=True)


def _billing_now_utc_string():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _billing_now_beijing_string():
    return datetime.datetime.now(datetime.timezone.utc).astimezone(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%d %H:%M:%S")


def _billing_utc_to_beijing_string(value):
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return raw.replace("T", " ").replace("Z", "")


def _migrate_billing_record_beijing_times(record):
    changed = False
    for key in ("created_at", "paid_at", "admin_cleared_at", "reason_updated_at", "updated_at"):
        beijing_key = f"{key}_beijing"
        if record.get(key) and not record.get(beijing_key):
            record[beijing_key] = _billing_utc_to_beijing_string(record.get(key))
            changed = True
    return changed


def _migrate_billing_file_beijing_times(filepath, record):
    if not _migrate_billing_record_beijing_times(record):
        return False
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return True


def _create_user_billing_record(auth_username, school_username, reason, amount):
    """
    为学校账号创建账单记录。
    
    参数:
        auth_username: (已弃用，保留兼容) 认证用户名，不再用于确定存储路径
        school_username: 学校账号用户名（核心标识符）
        reason: 账单原因（如"完成校园跑一次（单价：0.8元每次）"）
        amount: 金额（float）
    
    返回:
        billing_id: 账单ID（UUID字符串），失败返回None
        
    变更说明:
        账单现在存储在 User_Billing/School_Bills/{school_username}/ 目录下
        不再按 auth_username 分文件夹，以便多用户共享同一学校账号的账单
    """
    try:
        # 构建账单目录路径: User_Billing/School_Bills/{school_username}/
        # 注意：这里使用 School_Bills 子目录来避免与旧数据（用户名目录）冲突
        billing_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "User_Billing", "School_Bills", school_username)
        # 如果目录不存在则创建
        os.makedirs(billing_dir, exist_ok=True)
        
        # 生成唯一的UUID，确保不与现有文件冲突
        billing_id = str(uuid.uuid4())
        while os.path.exists(os.path.join(billing_dir, f"{billing_id}.json")):
            billing_id = str(uuid.uuid4())
        
        # 获取当前时间戳（ISO格式）
        created_at = _billing_now_utc_string()
        created_at_beijing = _billing_now_beijing_string()
        
        # 构建账单数据
        billing_data = {
            "billing_id": billing_id,
            "auth_username": auth_username, # 仅供记录，不影响存储
            "school_username": school_username,
            "reason": reason,
            "amount": round(float(amount), 2),
            "created_at": created_at,
            "created_at_beijing": created_at_beijing,
            "status": "pending",
            "payment_orders": [],
            "final_payment_order": None,
            "paid_at": None
        }
        
        # 写入账单文件
        billing_file = os.path.join(billing_dir, f"{billing_id}.json")
        with open(billing_file, "w", encoding="utf-8") as f:
            json.dump(billing_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"[账单] 为学校账号 {school_username} (操作者: {auth_username}) 创建账单记录: {billing_id}, 原因: {reason}, 金额: {amount}")
        return billing_id
    except Exception as e:
        logging.error(f"[账单] 创建账单记录失败 (学校账号: {school_username}): {e}", exc_info=True)
        return None


def _build_run_billing_reason(count, single_run_cost):
    """
    构建校园跑账单描述，统一自动与手动添加账单文案。
    """
    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 1
    if count < 1:
        count = 1

    try:
        single_run_cost = round(float(single_run_cost), 2)
    except (ValueError, TypeError):
        single_run_cost = 1.0

    cost_text = f"{single_run_cost:g}"
    run_text = "一次" if count == 1 else f"{count}次"
    return f"完成校园跑{run_text}（单价：{cost_text}元每次）"


def _get_single_run_cost_value(config_obj=None):
    """
    获取并规范化单次跑步价格。
    """
    try:
        cfg = config_obj or _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
        single_run_cost = round(float(cfg.get("Payment_Settings", "single_run_cost", fallback="1.0")), 2)
        if single_run_cost <= 0:
            return 1.0
        return single_run_cost
    except Exception:
        return 1.0


def _generate_payment_product_name_by_amount(total_amount, single_run_cost):
    """
    按“金额 / 单次跑步价格（向上取整）”计算数量并生成商品名称。
    """
    try:
        amount_value = round(float(total_amount), 2)
    except (ValueError, TypeError):
        amount_value = 0.0

    try:
        cost_value = round(float(single_run_cost), 2)
    except (ValueError, TypeError):
        cost_value = 1.0

    if cost_value <= 0:
        cost_value = 1.0

    if amount_value <= 0:
        quantity = 1
    else:
        quantity = max(1, int(math.ceil(amount_value / cost_value)))

    generator = LoMeiGenerator()
    product_name = generator.generate(quantity)
    if not product_name:
        product_name = f"{quantity}份现捞小吃"

    return product_name, quantity


def _count_pending_bills_for_school(school_username):
    """
    统计指定学校账号在 ./User_Billing/School_Bills 下的待支付账单数量。
    """
    try:
        school_username = str(school_username or "").strip()
        if not school_username:
            return 0
        billing_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "User_Billing",
            "School_Bills",
            school_username,
        )
        if not os.path.isdir(billing_dir):
            return 0

        pending_count = 0
        for filename in os.listdir(billing_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(billing_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    record = json.load(f)
                if str(record.get("status", "pending")).strip().lower() == "pending":
                    pending_count += 1
            except Exception as e:
                logging.warning(
                    f"[欠费检查] 读取账单文件失败（忽略该文件）: {filepath}, 错误: {e}"
                )
        return pending_count
    except Exception as e:
        logging.warning(f"[欠费检查] 统计待支付账单失败: {school_username}, 错误: {e}")
        return 0


def _collect_overdue_accounts_from_billing(school_usernames):
    """
    根据 ./User_Billing/School_Bills 中的待支付账单统计欠费账号列表。
    """
    overdue_accounts = []
    for school_username in list(dict.fromkeys(school_usernames or [])):
        pending_count = _count_pending_bills_for_school(school_username)
        if pending_count > 0:
            overdue_accounts.append(
                {
                    "school_username": school_username,
                    "overdue_count": pending_count,
                }
            )
    return overdue_accounts


sms_verification_codes = {}
sms_extended_once_keys = set()
SMS_VERIFICATION_CODE_MAX_ENTRIES = 5000

# 短信发送频率限制使用的缓存（IP / 手机号 / 上次发送时间）。
#
# 历史背景：这个 cache 原本与 sms_verification_codes 一起在
# start_web_server() 里用 global 初始化。d78b438 把 Web 服务拆到
# web_server.py 时，cache 的初始化随 start_web_server 一起搬走了，但
# 使用它的 sms_send_code / sms_test_send（现在位于本模块的
# _register_sms_routes 内）没有跟着搬，于是这两个接口一被调用就抛
# NameError: name 'cache' is not defined。
#
# 这里在 main.py 重新提供模块级 cache，与同模块的 sms_verification_codes
# 放在一起；web_server.py 里另有一个同名的独立 cache，两者互不影响
# （main.py 中的使用点都是本模块内的裸名字引用）。
cache = {}


def _build_sms_extend_once_key(phone, code):
    normalized_phone = str(phone or "").strip()
    normalized_code = str(code or "").strip()
    if not normalized_phone or not normalized_code:
        return ""
    return f"{normalized_phone}:{normalized_code}"


def _is_sms_extend_allowed_once(phone, code):
    key = _build_sms_extend_once_key(phone, code)
    if not key:
        return False
    return key not in sms_extended_once_keys


def _mark_sms_extend_used_once(phone, code):
    key = _build_sms_extend_once_key(phone, code)
    if key:
        sms_extended_once_keys.add(key)


def _reset_sms_extend_once_for_phone(phone):
    normalized_phone = str(phone or "").strip()
    if not normalized_phone:
        return
    stale_keys = [
        key for key in sms_extended_once_keys if key.startswith(f"{normalized_phone}:")
    ]
    for key in stale_keys:
        sms_extended_once_keys.discard(key)


def _cleanup_expired_sms_verification_codes(now_ts=None, max_entries=None):
    current_ts = float(now_ts if now_ts is not None else time.time())
    limit = max(
        int(
            SMS_VERIFICATION_CODE_MAX_ENTRIES
            if max_entries is None
            else max_entries
        ),
        0,
    )
    expired_phones = []

    for phone, value in list(sms_verification_codes.items()):
        if (
            not isinstance(value, (tuple, list))
            or len(value) != 2
        ):
            expired_phones.append(phone)
            continue
        try:
            expires_at = float(value[1] or 0)
        except (TypeError, ValueError):
            expired_phones.append(phone)
            continue
        if expires_at <= current_ts:
            expired_phones.append(phone)

    for phone in expired_phones:
        sms_verification_codes.pop(phone, None)
        _reset_sms_extend_once_for_phone(phone)

    removed_overflow = 0
    while len(sms_verification_codes) > limit:
        phone, _ = min(
            sms_verification_codes.items(),
            key=lambda item: float(item[1][1] or 0),
        )
        sms_verification_codes.pop(phone, None)
        _reset_sms_extend_once_for_phone(phone)
        removed_overflow += 1

    if expired_phones or removed_overflow:
        logging.info(
            "[短信缓存诊断] 清理完成: remaining=%d, expired=%d, "
            "overflow=%d, max_entries=%d, extend_markers=%d",
            len(sms_verification_codes),
            len(expired_phones),
            removed_overflow,
            limit,
            len(sms_extended_once_keys),
        )

    return {
        "remaining": len(sms_verification_codes),
        "removed_expired": len(expired_phones),
        "removed_overflow": removed_overflow,
    }


def _normalize_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _register_health_route(app):
    @app.route("/health")
    def health():
        """
        健康检查端点（分级可见性 + 组件重要性聚合）
        """

        request_start_time = time.time()
        uptime_seconds = _get_health_uptime_seconds()

        def format_uptime(seconds):
            days = int(seconds // 86400)
            seconds %= 86400
            hours = int(seconds // 3600)
            seconds %= 3600
            minutes = int(seconds // 60)
            seconds = int(seconds % 60)
            parts = []
            if days > 0:
                parts.append(f"{days}天")
            if hours > 0:
                parts.append(f"{hours}小时")
            if minutes > 0:
                parts.append(f"{minutes}分钟")
            if seconds > 0 or len(parts) == 0:
                parts.append(f"{seconds}秒")
            return "".join(parts)

        uptime_formatted = format_uptime(uptime_seconds)

        components = [
            _check_running_core_health(),
            _check_payment_system_health(),
            _check_sms_system_health(),
        ]
        status, http_status, summary = _aggregate_health_status(components)

        request_end_time = time.time()
        response_time_ms = round((request_end_time - request_start_time) * 1000, 2)

        payload = {
            "status": status,
            "uptime_seconds": int(uptime_seconds),
            "response_time_ms": response_time_ms,
            "uptime_formatted": uptime_formatted,
        }

        token = request.cookies.get("auth_token")
        is_admin = _is_admin_health_view_from_token(token)
        payload.update(_build_health_comment_fields(is_admin=is_admin))

        if is_admin:
            payload["components"] = {c["name"]: c for c in components}
            payload["summary"] = summary
            payload["memory_diagnostics"] = _collect_runtime_memory_diagnostics()

        response = jsonify(payload)
        response.status_code = http_status
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def _register_payment_routes(app, login_required):
    _register_payment_verify_probe_route(app)
    _register_payment_verify_host_route_for_tests(app, login_required)



def _register_sms_routes(app, login_required):
    from flask import g, jsonify, request

    @app.route("/api/sms/send_code", methods=["POST"])
    def sms_send_code():
        try:
            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            if (
                config.get("Features", "enable_sms_service", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "短信服务未启用"})

            data = request.get_json() or {}
            phone = data.get("phone", "").strip()
            scene = data.get("scene", "register").strip()
            captcha_input = data.get("captcha", "").strip()
            captcha_id = data.get("captcha_id", "").strip()

            is_captcha_valid, captcha_error_msg = verify_captcha(
                captcha_id, captcha_input
            )
            if not is_captcha_valid:
                return jsonify({"success": False, "message": captcha_error_msg})
            if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})

            sms_interval_seconds = int(
                config.get("SMS_Service_SMSBao", "send_interval_seconds", fallback="180")
            )
            last_send_key = f"sms_last_send_{phone}"
            last_send_time = cache.get(last_send_key, 0)
            current_time = time.time()

            if last_send_time and (current_time - last_send_time) < sms_interval_seconds:
                remaining_seconds = int(
                    sms_interval_seconds - (current_time - last_send_time)
                )
                return jsonify(
                    {
                        "success": False,
                        "message": f"发送过于频繁，请{remaining_seconds}秒后再试",
                        "retry_after": remaining_seconds,
                    }
                )

            client_ip = request.environ.get("REMOTE_ADDR") or request.remote_addr
            current_date = time.strftime("%Y-%m-%d")
            ip_limit_key = f"sms_ip_{client_ip}_{current_date}"
            ip_count = cache.get(ip_limit_key, 0)
            ip_limit = int(
                config.get("SMS_Service_SMSBao", "rate_limit_per_ip_day", fallback="20")
            )
            if ip_count >= ip_limit:
                return jsonify(
                    {
                        "success": False,
                        "message": f"IP每日发送次数已达上限({ip_limit}次)",
                    }
                )

            phone_limit_key = f"sms_phone_{phone}_{current_date}"
            phone_count = cache.get(phone_limit_key, 0)
            phone_limit = int(
                config.get(
                    "SMS_Service_SMSBao", "rate_limit_per_phone_day", fallback="5"
                )
            )
            if phone_count >= phone_limit:
                return jsonify(
                    {
                        "success": False,
                        "message": f"该手机号每日发送次数已达上限({phone_limit}次)",
                    }
                )

            code = "".join([str(random.randint(0, 9)) for _ in range(6)])
            username = config.get("SMS_Service_SMSBao", "username", fallback="")
            api_key = config.get("SMS_Service_SMSBao", "api_key", fallback="")
            signature = config.get(
                "SMS_Service_SMSBao", "signature", fallback="【电科大跑步助手】"
            )
            code_expire_minutes = int(
                config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")
            )
            template = config.get(
                "SMS_Service_SMSBao",
                "template_register",
                fallback=f"您的验证码是：{{code}}，{code_expire_minutes}分钟内有效。",
            )
            if not username or not api_key:
                return jsonify(
                    {"success": False, "message": "短信服务配置不完整，请联系管理员"}
                )

            content = _build_sms_verification_content(
                signature, template, code, code_expire_minutes
            )
            url = f"http://api.smsbao.com/sms?u={username}&p={api_key}&m={phone}&c={urllib.parse.quote(content)}"
            response = urllib.request.urlopen(url, timeout=10)
            result = response.read().decode("utf-8").strip()
            if result == "0":
                code_expire_seconds = code_expire_minutes * 60
                _cleanup_expired_sms_verification_codes()
                sms_verification_codes[phone] = (code, time.time() + code_expire_seconds)
                _reset_sms_extend_once_for_phone(phone)
                cache[ip_limit_key] = ip_count + 1
                cache[phone_limit_key] = phone_count + 1
                cache[last_send_key] = current_time
                return jsonify(
                    {
                        "success": True,
                        "message": f"验证码已发送，{code_expire_minutes}分钟内有效",
                        "expire_minutes": code_expire_minutes,
                        "retry_after": sms_interval_seconds,
                    }
                )

            error_msg = _get_smsbao_error_message(result)
            logging.error(
                f"[SMS] 验证码发送失败: phone={phone}, scene={scene}, smsbao_result={result}, error={error_msg}"
            )
            return jsonify(
                {
                    "success": False,
                    "message": f"发送失败：{error_msg}",
                    "error_code": result,
                }
            )
        except Exception as e:
            logging.error(
                f"[SMS] 验证码发送异常: phone={phone}, scene={scene}, error={e}",
                exc_info=True,
            )
            return jsonify({"success": False, "message": "短信服务暂时不可用，请稍后重试"})

    @app.route("/api/sms/test_send", methods=["POST"])
    @login_required
    def sms_test_send():
        try:
            current_user = g.user
            user_group = auth_system.get_user_group(current_user)
            if user_group not in ["admin", "super_admin"]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "权限不足，仅管理员可使用测试功能",
                        }
                    ),
                    403,
                )

            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            if (
                config.get("Features", "enable_sms_service", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "短信服务未启用，请先在配置中启用"})

            data = request.get_json() or {}
            phone = data.get("phone", "").strip()
            custom_code = data.get("code", "").strip()
            if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})
            if custom_code:
                if not re.match(r"^\d{4,8}$", custom_code):
                    return jsonify(
                        {
                            "success": False,
                            "message": "自定义验证码格式不正确，仅支持4-8位数字",
                        }
                    )
                code = custom_code
            else:
                code = "".join([str(random.randint(0, 9)) for _ in range(6)])

            username = config.get("SMS_Service_SMSBao", "username", fallback="")
            api_key = config.get("SMS_Service_SMSBao", "api_key", fallback="")
            signature = config.get(
                "SMS_Service_SMSBao", "signature", fallback="【电科大跑步助手】"
            )
            code_expire_minutes = int(
                config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")
            )
            template = config.get(
                "SMS_Service_SMSBao",
                "template_register",
                fallback=f"您的验证码是：{{code}}，{code_expire_minutes}分钟内有效。",
            )
            if not username or not api_key:
                return jsonify(
                    {"success": False, "message": "短信服务配置不完整，请联系管理员"}
                )

            content = _build_sms_verification_content(
                signature, template, code, code_expire_minutes
            )
            url = f"http://api.smsbao.com/sms?u={username}&p={api_key}&m={phone}&c={urllib.parse.quote(content)}"
            response = urllib.request.urlopen(url, timeout=10)
            result = response.read().decode("utf-8").strip()
            if result == "0":
                return jsonify(
                    {
                        "success": True,
                        "message": f"测试短信发送成功！验证码：{code}",
                        "code": code,
                        "phone": phone,
                    }
                )

            error_msg = _get_smsbao_error_message(result)
            return jsonify(
                {
                    "success": False,
                    "message": f"发送失败：{error_msg}",
                    "error_code": result,
                }
            )
        except Exception as e:
            logging.error(
                f"[SMS] 测试短信发送异常: phone={phone}, error={e}",
                exc_info=True,
            )
            return jsonify({"success": False, "message": "短信服务暂时不可用，请稍后重试"})

    @app.route("/api/admin/sms/config", methods=["GET"])
    @login_required
    def get_sms_config():
        try:
            if not auth_system.check_permission(g.user, "modify_config"):
                return jsonify(
                    {
                        "success": False,
                        "message": "权限不足，需要配置修改权限（modify_config）",
                    }
                ), 403

            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            return jsonify({"success": True, "config": _get_sms_config_view_data(config)})
        except Exception:
            return jsonify({"success": False, "message": "获取配置失败"}), 500

    @app.route("/api/admin/sms/config", methods=["POST"])
    @login_required
    def save_sms_config():
        try:
            if not auth_system.check_permission(g.user, "modify_config"):
                return jsonify(
                    {
                        "success": False,
                        "message": "权限不足，需要配置修改权限（modify_config）",
                    }
                ), 403

            data = request.get_json() or {}
            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            config = _apply_sms_config_updates(config, data)
            _write_config_with_comments(config, CONFIG_JSON_FILE)
            return jsonify({"success": True, "message": "配置已保存"})
        except Exception:
            return jsonify({"success": False, "message": "保存失败"}), 500




def _validate_product_name_generator_startup_config():
    """在服务启动前校验商品名生成器行业模式配置。"""
    try:
        validate_product_name_generator_mode(PRODUCT_NAME_GENERATOR_MODE)
        logging.info(
            "[启动校验] 商品名生成器行业模式配置有效: %s",
            PRODUCT_NAME_GENERATOR_MODE,
        )
    except ValueError as exc:
        message = f"[启动校验] 商品名生成器行业模式配置无效: {exc}"
        print(message)
        logging.error(message)
        raise SystemExit(1) from exc


def _build_main_arg_parser():
    parser = argparse.ArgumentParser(description="跑步助手 - Web服务器模式")
    parser.add_argument(
        "--port", type=int, default=5000, help="Web服务器端口（默认5000）"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Web服务器地址（默认127.0.0.1）"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头Chrome模式（默认启用）",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="debug",
        help="设置日志级别（默认 debug）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试日志（兼容旧参数，等同于 --log-level debug）",
    )
    parser.add_argument("--daily-restart-helper", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-parent-pid", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-python-executable", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-main-script-path", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-cwd", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-log-path", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--daily-restart-marker-path", type=str, help=argparse.SUPPRESS)
    parser.add_argument(
        "--daily-restart-forward-args-json",
        type=str,
        default="[]",
        help=argparse.SUPPRESS,
    )
    return parser


def _acquire_single_instance_lock(lock_path=None):
    """Acquire a process-lifetime lock for this checkout."""
    global _SINGLE_INSTANCE_LOCK_HANDLE

    if _SINGLE_INSTANCE_LOCK_HANDLE is not None:
        return True

    target_path = lock_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "logs",
        ".zx-slm-tool.lock",
    )
    target_dir = os.path.dirname(target_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    lock_handle = open(target_path, "a+b")
    try:
        lock_handle.seek(0)
        lock_handle.write(b"\0")
        lock_handle.flush()
        lock_handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_handle.close()
        return False

    _SINGLE_INSTANCE_LOCK_HANDLE = lock_handle
    return True



def main():
    """主函数，启动Web服务器模式（已弃用桌面模式）"""
    parser = _build_main_arg_parser()
    args = parser.parse_args()

    if getattr(args, "daily_restart_helper", False):
        return _run_daily_restart_helper(args)

    if not _acquire_single_instance_lock():
        print(
            "检测到当前目录已有跑步助手实例正在运行，"
            "为避免日志和会话文件冲突，本次启动已取消。"
        )
        return 1

    # ========== 第1步：导入内置模块 ==========
    # ========== 第2步：初始化日志系统 ==========
    try:
        setup_logging()
    except Exception as e:
        print(f"[错误] 日志系统初始化失败: {e}")
        traceback.print_exc()
    _load_ip_cache()
    _load_phone_cache()
    _migrate_ip_location_config_if_needed()
    # _start_default_theme_background_cache_warmup() # 启动太早了，等核心模块加载后再启动
    # ========== 第3步：导入所有依赖库 ==========
    import_standard_libraries()
    import_core_third_party()
    check_and_import_dependencies()
    global LoMeiGenerator, PRODUCT_NAME_GENERATOR_MODE, validate_product_name_generator_mode
    if os.path.exists("product_name_generator.py"):
        from product_name_generator import (
            LoMeiGenerator,
            PRODUCT_NAME_GENERATOR_MODE,
            validate_product_name_generator_mode,
        )
        _validate_product_name_generator_startup_config()
    else:
        raise ImportError("缺少 product_name_generator.py 文件，无法继续运行。")

    # ========== 第4步：初始化系统 ==========
    auto_init_system()
    initialize_global_variables()
    # ========== 第5步：解析命令行参数 ==========
    # ========== 第6步：配置日志级别 ==========
    selected_level_name = "debug" if args.debug else args.log_level
    log_level = getattr(logging, selected_level_name.upper(), logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for existing_handler in root_logger.handlers:
        # 文件分流处理器（WARNING/ERROR）需保留各自阈值，只下调 DEBUG/INFO 处理器
        if existing_handler.level <= logging.INFO:
            existing_handler.setLevel(log_level)

    logging.info("=" * 60)
    logging.info("跑步助手 Web 模式启动中...")
    level_name_map = {
        logging.DEBUG: "调试",
        logging.INFO: "信息",
        logging.WARNING: "警告",
        logging.ERROR: "错误",
        logging.CRITICAL: "严重",
    }
    logging.info(
        f"日志级别: {level_name_map.get(log_level, selected_level_name.upper())} ({selected_level_name.upper()})"
    )
    logging.info(f"服务器地址: {args.host}:{args.port}")
    logging.info("=" * 60)
    # ========== 第7步：检查Playwright是否可用 ==========
    if not playwright_available:
        print("\n" + "=" * 60)
        print("错误: 需要安装 Playwright 以在服务器端运行Chrome")
        print("请运行以下命令:")
        print("  pip install playwright")
        print("  python -m playwright install chromium")
        print("=" * 60 + "\n")
        sys.exit(1)
    # ========== 第8步：检查并选择可用端口 ==========
    initial_port = args.port
    DEFAULT_PORT = 5000
    if initial_port != DEFAULT_PORT:
        logging.info(f"用户已明确指定端口 {initial_port}。")
        logging.warning(f"将 *直接尝试* 绑定到端口 {initial_port}。")
        logging.warning(
            f"注意：如果此端口已被占用，或需要更高权限 (例如在 Linux/macOS 上绑定端口 80)，程序将会启动失败。"
        )
    else:
        logging.info(f"用户正在使用默认端口 {DEFAULT_PORT}。正在检查端口可用性...")
        if not check_port_available(args.host, args.port):
            logging.warning(
                f"默认端口 {args.port} 不可用或已被占用，尝试自动查找可用端口..."
            )
            found_port = None
            alternative_ports = [8080, 8000, 3000,
                                 5001, 8888, 9000, 5005, 5050]
            for port in alternative_ports:
                logging.info(f"尝试端口 {port}...")
                if check_port_available(args.host, port):
                    found_port = port
                    logging.info(f"找到可用端口: {found_port}")
                    break
            if not found_port:
                logging.info(
                    "常用备选端口均不可用，尝试在 10000-65535 范围内查找随机可用端口..."
                )
                max_random_tries = 20
                for i in range(max_random_tries):
                    random_port = random.randint(10000, 65535)  # nosec B311 - 用于查找可用端口，非安全用途
                    if check_port_available(args.host, random_port):
                        found_port = random_port
                        logging.info(f"找到可用随机端口: {found_port}")
                        break
                    time.sleep(0.01)
            if not found_port:
                logging.error(
                    f"自动查找端口失败。默认端口 {initial_port} 及所有尝试的备选/随机端口均不可用。"
                )
                print(f"\n{'='*60}")
                print(f"错误: 无法自动找到可用的网络端口。")
                print(
                    f"请检查端口 {initial_port} 或其他常用端口是否被占用，或手动指定一个可用端口:"
                )
                print(f"  python main.py --port <可用端口号>")
                print(f"{'='*60}\n")
                sys.exit(1)
            else:
                args.port = found_port
        else:
            logging.info(f"默认端口 {DEFAULT_PORT} 可用。")
            
    _start_default_theme_background_cache_warmup()
    # ========== 第9步：启动Web服务器 ==========
    logging.info("启动Web服务器模式（使用服务器端Chrome渲染）...")
    start_web_server(args)


if __name__ == "__main__":
    main()
