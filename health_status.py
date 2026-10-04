from __future__ import annotations

import hashlib
import json
import logging
import os
import time


from main_runtime import _main


def _safe_get_config_for_health():
    try:
        cfg = _main()._read_config_ini(_main().CONFIG_JSON_FILE)
        if cfg:
            return cfg
    except Exception:
        pass
    try:
        return _main()._get_default_config()
    except Exception:
        return None


def _collect_auth_usernames_for_token_lookup():
    usernames = set()

    try:
        if getattr(_main(), "auth_system", None):
            permissions = getattr(_main().auth_system, "permissions", None)
            if isinstance(permissions, dict):
                user_groups = permissions.get("user_groups", {})
                if isinstance(user_groups, dict):
                    usernames.update(
                        str(u).strip() for u in user_groups.keys() if str(u).strip()
                    )

            config = getattr(_main().auth_system, "config", None)
            if config is not None:
                try:
                    super_admin = config.get("Admin", "super_admin", fallback="admin")
                    if super_admin:
                        usernames.add(str(super_admin).strip())
                except Exception:
                    pass
    except Exception:
        pass

    try:
        if os.path.isdir(_main().SYSTEM_ACCOUNTS_DIR):
            for filename in os.listdir(_main().SYSTEM_ACCOUNTS_DIR):
                if filename == "_index.json" or not filename.endswith(".json"):
                    continue
                file_path = os.path.join(_main().SYSTEM_ACCOUNTS_DIR, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    auth_username = str(data.get("auth_username", "")).strip()
                    if auth_username:
                        usernames.add(auth_username)
                except Exception:
                    continue
    except Exception:
        pass

    if usernames:
        return sorted(usernames)

    try:
        if getattr(_main(), "auth_system", None) and hasattr(
            _main().auth_system,
            "list_users",
        ):
            for user in _main().auth_system.list_users() or []:
                if isinstance(user, dict):
                    auth_username = str(user.get("auth_username", "")).strip()
                    if auth_username:
                        usernames.add(auth_username)
    except Exception:
        pass

    return sorted(usernames)


def _get_health_token_index_path():
    try:
        tokens_dir = getattr(_main().token_manager, "tokens_dir", "")
    except Exception:
        tokens_dir = ""
    tokens_dir = str(tokens_dir or "").strip()
    if not tokens_dir:
        return None
    return os.path.join(tokens_dir, "_health_token_index.json")



def _build_health_token_index_key(token):
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return ""
    return hashlib.sha256(normalized_token.encode("utf-8")).hexdigest()



def _read_health_token_index():
    index_path = _main()._get_health_token_index_path()
    if not index_path or not os.path.exists(index_path):
        return {}
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        normalized_index = {}
        for token_key, username in data.items():
            normalized_key = str(token_key or "").strip()
            normalized_username = str(username or "").strip()
            if normalized_key and normalized_username:
                normalized_index[normalized_key] = normalized_username
        return normalized_index
    except Exception:
        return {}



def _write_health_token_index(index_data):
    index_path = _main()._get_health_token_index_path()
    if not index_path:
        return
    safe_index = {}
    if isinstance(index_data, dict):
        for token_key, username in index_data.items():
            normalized_key = str(token_key or "").strip()
            normalized_username = str(username or "").strip()
            if normalized_key and normalized_username:
                safe_index[normalized_key] = normalized_username
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(safe_index, f, indent=2, ensure_ascii=False)
    except Exception:
        pass



def _validate_cached_health_token_owner(username, token):
    normalized_username = str(username or "").strip()
    normalized_token = str(token or "").strip()
    if not normalized_username or not normalized_token:
        return False
    if not getattr(_main(), "token_manager", None):
        return False
    try:
        verified = _main().token_manager.verify_token(normalized_username, "", normalized_token)
        if isinstance(verified, tuple):
            return bool(verified[0])
        return bool(verified)
    except Exception:
        return False



def _resolve_username_by_token(token):
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    if not getattr(_main(), "token_manager", None):
        return None

    cached_index = {}
    token_key = _main()._build_health_token_index_key(normalized_token)
    try:
        cached_index = _main()._read_health_token_index()
        cached_username = str(cached_index.get(token_key, "")).strip()
        if cached_username:
            if _main()._validate_cached_health_token_owner(cached_username, normalized_token):
                return cached_username
            cached_index.pop(token_key, None)
            _main()._write_health_token_index(cached_index)
    except Exception:
        cached_index = {}

    usernames = _main()._collect_auth_usernames_for_token_lookup()
    for username in usernames:
        try:
            verified = _main().token_manager.verify_token(username, "", normalized_token)
            if isinstance(verified, tuple):
                is_valid = bool(verified[0])
            else:
                is_valid = bool(verified)
            if is_valid:
                try:
                    cached_index[token_key] = username
                    _main()._write_health_token_index(cached_index)
                except Exception:
                    pass
                return username
        except Exception:
            continue

    return None


def _is_admin_health_view_from_token(token=None):
    token_value = token
    if token_value is None:
        try:
            if hasattr(_main(), "request"):
                token_value = _main().request.cookies.get("auth_token")
        except Exception:
            token_value = None

    normalized_token = str(token_value or "").strip()
    if not normalized_token:
        return False

    username = _main()._resolve_username_by_token(normalized_token)
    if not username:
        return False

    try:
        if not getattr(_main(), "auth_system", None):
            return False
        user_group = _main().auth_system.get_user_group(username)
        return user_group in ["admin", "super_admin"]
    except Exception:
        return False


def _check_running_core_health():
    component = {
        "name": "running_core",
        "critical": True,
        "status": "ok",
        "message": "跑步执行链路正常",
        "checks": {},
    }

    try:
        now_ts = time.time()
        checks = component["checks"]

        manager = getattr(_main(), "background_task_manager", None)
        checks["background_task_manager_exists"] = bool(manager)
        if not manager:
            component["status"] = "error"
            component["message"] = "后台任务管理器未初始化"
            return component

        lock = getattr(manager, "lock", None)
        tasks = {}
        if lock is not None and hasattr(lock, "__enter__"):
            with lock:
                tasks = getattr(manager, "tasks", {}) or {}
        else:
            tasks = getattr(manager, "tasks", {}) or {}

        web_sessions_obj = getattr(_main(), "web_sessions", {})
        web_sessions_valid = isinstance(web_sessions_obj, dict)
        checks["web_sessions_structure_valid"] = web_sessions_valid
        if not web_sessions_valid:
            component["status"] = "error"
            component["message"] = "会话状态结构异常"
            return component

        if not isinstance(tasks, dict):
            component["status"] = "error"
            component["message"] = "后台任务状态结构异常"
            return component

        running_tasks = [
            t for t in tasks.values()
            if isinstance(t, dict) and str(t.get("status", "")).lower() == "running"
        ]
        checks["running_task_count"] = len(running_tasks)

        stale_count = 0
        malformed_running_count = 0
        for task in running_tasks:
            last_update = task.get("last_update")
            if last_update is None:
                malformed_running_count += 1
                continue
            try:
                if (now_ts - float(last_update)) > 600:
                    stale_count += 1
            except Exception:
                malformed_running_count += 1

        checks["stale_running_task_count"] = stale_count
        checks["malformed_running_task_count"] = malformed_running_count

        chrome = getattr(_main(), "chrome_pool", None)
        checks["chrome_pool_exists"] = bool(chrome)
        contexts_count = 0
        contexts_accessible = False
        if chrome and hasattr(chrome, "_contexts"):
            try:
                contexts_count = len(getattr(chrome, "_contexts", {}) or {})
                contexts_accessible = True
            except Exception:
                contexts_accessible = False
        checks["chrome_contexts_accessible"] = contexts_accessible
        checks["chrome_contexts_count"] = contexts_count

        if running_tasks and (not chrome or not contexts_accessible):
            component["status"] = "error"
            component["message"] = "存在运行任务但浏览器执行上下文不可用"
        elif malformed_running_count > 0:
            component["status"] = "error"
            component["message"] = "运行任务状态字段异常"
        elif stale_count > 0:
            component["status"] = "degraded"
            component["message"] = "检测到运行任务长时间无更新，可能卡滞"

    except Exception as e:
        component["status"] = "error"
        component["message"] = f"运行核心检查异常: {e}"

    return component


def _check_payment_system_health():
    component = {
        "name": "payment_system",
        "critical": False,
        "status": "ok",
        "message": "支付系统配置正常",
        "checks": {},
    }

    try:
        config = _main()._safe_get_config_for_health()
        checks = component["checks"]
        if config is None:
            component["status"] = "degraded"
            component["message"] = "支付配置读取失败"
            return component

        require_payment = _main()._normalize_bool(
            config.get("Payment_Settings", "require_payment", fallback="true"),
            default=True,
        )
        checks["require_payment"] = require_payment

        host = str(config.get("Rainbow_YiPay", "host", fallback="")).strip()
        pid = str(config.get("Rainbow_YiPay", "pid", fallback="")).strip()
        key = str(config.get("Rainbow_YiPay", "key", fallback="")).strip()
        timeout_raw = str(
            config.get("Rainbow_YiPay", "payment_timeout_minutes", fallback="900")
        ).strip()

        checks["has_host"] = bool(host)
        checks["has_pid"] = bool(pid)
        checks["has_key"] = bool(key)

        timeout_valid = True
        try:
            timeout_value = int(timeout_raw)
            timeout_valid = timeout_value > 0
        except Exception:
            timeout_valid = False
        checks["timeout_valid"] = timeout_valid

        orders_dir_exists = os.path.isdir(_main().PAYMENT_ORDERS_DIR)
        checks["payment_orders_dir_exists"] = orders_dir_exists

        qr_cache_index_ok = True
        qr_cache_index_size = 0
        try:
            qr_index = _main()._load_qr_cache_index()
            if isinstance(qr_index, dict):
                qr_cache_index_size = len(qr_index)
            else:
                qr_cache_index_ok = False
        except Exception:
            qr_cache_index_ok = False
        checks["qr_cache_index_ok"] = qr_cache_index_ok
        checks["qr_cache_index_size"] = qr_cache_index_size

        if require_payment and (not host or not pid or not key):
            component["status"] = "degraded"
            component["message"] = "支付开启但关键参数缺失"
        elif require_payment and not timeout_valid:
            component["status"] = "degraded"
            component["message"] = "支付超时配置无效"
        elif require_payment and not orders_dir_exists:
            component["status"] = "degraded"
            component["message"] = "支付订单目录不可用"
        elif require_payment and not qr_cache_index_ok:
            component["status"] = "degraded"
            component["message"] = "支付二维码缓存索引异常"
        elif not timeout_valid:
            component["status"] = "degraded"
            component["message"] = "支付超时配置无效"

    except Exception as e:
        component["status"] = "degraded"
        component["message"] = f"支付系统检查异常: {e}"

    return component


def _check_sms_system_health():
    component = {
        "name": "sms_system",
        "critical": False,
        "status": "ok",
        "message": "短信系统配置正常",
        "checks": {},
    }

    try:
        config = _main()._safe_get_config_for_health()
        checks = component["checks"]
        if config is None:
            component["status"] = "degraded"
            component["message"] = "短信配置读取失败"
            return component

        enabled = _main()._normalize_bool(
            config.get("Features", "enable_sms_service", fallback="false"),
            default=False,
        )
        checks["enable_sms_service"] = enabled

        if not enabled:
            component["message"] = "短信服务未启用"
            return component

        username = str(config.get("SMS_Service_SMSBao", "username", fallback="")).strip()
        api_key = str(config.get("SMS_Service_SMSBao", "api_key", fallback="")).strip()
        signature = str(config.get("SMS_Service_SMSBao", "signature", fallback="")).strip()
        template_register = str(
            config.get("SMS_Service_SMSBao", "template_register", fallback="")
        ).strip()

        checks["has_username"] = bool(username)
        checks["has_api_key"] = bool(api_key)
        checks["has_signature"] = bool(signature)
        checks["has_template_register"] = bool(template_register)

        sms_cache_accessible = isinstance(getattr(_main(), "sms_verification_codes", None), dict)
        checks["sms_cache_accessible"] = sms_cache_accessible

        send_interval_valid = True
        code_expire_valid = True
        try:
            send_interval_valid = int(
                str(config.get("SMS_Service_SMSBao", "send_interval_seconds", fallback="180")).strip()
            ) > 0
        except Exception:
            send_interval_valid = False

        try:
            code_expire_valid = int(
                str(config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")).strip()
            ) > 0
        except Exception:
            code_expire_valid = False

        checks["send_interval_valid"] = send_interval_valid
        checks["code_expire_valid"] = code_expire_valid

        if not all([username, api_key, signature, template_register]):
            component["status"] = "degraded"
            component["message"] = "短信服务已启用但配置不完整"
        elif not send_interval_valid or not code_expire_valid:
            component["status"] = "degraded"
            component["message"] = "短信限流或验证码时效配置无效"
        elif not sms_cache_accessible:
            component["status"] = "degraded"
            component["message"] = "短信验证码缓存未就绪"

    except Exception as e:
        component["status"] = "degraded"
        component["message"] = f"短信系统检查异常: {e}"

    return component


def _aggregate_health_status(components):
    critical_failed_count = 0
    non_critical_failed_count = 0

    for component in components or []:
        status = str(component.get("status", "")).lower()
        is_critical = bool(component.get("critical", False))

        if is_critical and status == "error":
            critical_failed_count += 1
        if (not is_critical) and status in ["degraded", "error"]:
            non_critical_failed_count += 1

    if critical_failed_count > 0:
        return (
            "error",
            503,
            {
                "critical_failed_count": critical_failed_count,
                "non_critical_failed_count": non_critical_failed_count,
            },
        )

    if non_critical_failed_count > 0:
        return (
            "degraded",
            200,
            {
                "critical_failed_count": critical_failed_count,
                "non_critical_failed_count": non_critical_failed_count,
            },
        )

    return (
        "ok",
        200,
        {
            "critical_failed_count": 0,
            "non_critical_failed_count": 0,
        },
    )


def _build_health_comment_fields(is_admin=False):
    base_comment = {
        "status": "整体健康状态：ok=正常，degraded=部分非核心异常，error=核心异常",
        "uptime_seconds": "服务启动后累计运行秒数",
        "response_time_ms": "本次 /health 请求处理耗时（毫秒）",
        "uptime_formatted": "运行时长的人类可读格式",
    }

    if not is_admin:
        return {"_comment": base_comment}

    return {
        "_comment": base_comment,
        "_meta_zh": {
            "components": {
                "running_core": "跑步执行主链路（核心）",
                "payment_system": "支付系统（非核心）",
                "sms_system": "短信系统（非核心）",
            },
            "summary": {
                "critical_failed_count": "核心异常组件数量",
                "non_critical_failed_count": "非核心异常组件数量",
            },
            "memory_diagnostics": {
                "rss_mb": "当前进程常驻内存（MB）",
                "max_rss_mb": "进程峰值常驻内存（MB）",
                "active_threads": "当前活动线程数",
                "account_refresh_threads": "账号刷新线程数",
                "multi_monitor_threads": "多账号监控线程数",
                "playwright_contexts": "Playwright 浏览器上下文数",
                "web_sessions": "内存中的网页会话数",
                "ip_cache": "IP 位置缓存条数",
                "phone_cache": "手机号位置缓存条数",
                "sms_codes": "短信验证码条数",
                "gc_counts": "各代垃圾回收计数",
            },
        },
    }
