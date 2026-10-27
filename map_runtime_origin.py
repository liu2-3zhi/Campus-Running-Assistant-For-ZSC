"""Backend-only map page origins and partial administrator configuration updates."""

import copy
import ipaddress
import json
import re
from urllib.parse import urlsplit


MAP_RUNTIME_PATH = "/map-runtime"
MAP_RUNTIME_MARKER = "zx-local-map-runtime-v1"
MAP_RUNTIME_PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="zx-map-runtime" content="zx-local-map-runtime-v1">
<meta name="referrer" content="strict-origin"><title>Map Runtime</title></head>
<body></body></html>"""

PROVIDER_KEY_FIELDS = {"amap": "js_key", "tencent": "map_key", "tianditu": "token", "baidu": "ak"}
LEGACY_KEY_FIELDS = {"amap": "amap_js_key", "tencent": "tencent_map_key", "tianditu": "tianditu_token", "baidu": "baidu_map_ak"}


def normalize_backend_page_origin(value):
    """Accept a pasted HTTP URL, retaining only its validated origin."""
    if not isinstance(value, str):
        raise ValueError("后端规划页面来源必须是 HTTP/HTTPS 地址")
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value) or "\\" in value:
        raise ValueError("后端规划页面来源不能包含控制字符或反斜杠")
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc or not parsed.hostname:
            raise ValueError()
        if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
            raise ValueError()
        if parsed.netloc.endswith(":"):
            raise ValueError()
        port = parsed.port
        hostname = parsed.hostname
        if "%" in hostname or (port is not None and port < 1):
            raise ValueError()
        if ":" in hostname:
            hostname = "[" + str(ipaddress.IPv6Address(hostname)) + "]"
        else:
            hostname = hostname.encode("idna").decode("ascii").lower()
            if re.fullmatch(r"[0-9.]+", hostname):
                ipaddress.IPv4Address(hostname)
            if len(hostname) > 253 or any(not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
                                          for label in hostname.rstrip(".").split(".")):
                raise ValueError()
        scheme = parsed.scheme.lower()
        suffix = "" if port is None or (scheme, port) in (("http", 80), ("https", 443)) else f":{port}"
        return f"{scheme}://{hostname}{suffix}"
    except (ValueError, UnicodeError):
        raise ValueError("后端规划页面来源无效，请输入不含账号密码的 HTTP/HTTPS 地址") from None


def resolve_backend_page_origin(config, provider, request_origin=None):
    providers = config.get("Map", "providers", fallback=None)
    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
        except (TypeError, ValueError):
            providers = None
    provider_config = providers.get(provider, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    candidates = (
        (provider_config.get("backend_page_origin", ""), "provider"),
        (config.get("Map", "backend_page_origin", fallback=""), "global"),
        (request_origin or "", "request"),
    )
    for candidate, source in candidates:
        origin = normalize_backend_page_origin(candidate)
        if origin:
            return origin, source
    raise ValueError("缺少后端规划页面来源，请在系统配置中填写 HTTP/HTTPS 来源")


def merge_map_settings(config, updates):
    """Merge only submitted fields; an explicit empty string clears a value."""
    if not isinstance(updates, dict):
        raise ValueError("地图配置格式无效")
    existing = config.get("Map", "providers", fallback=None)
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except (TypeError, ValueError):
            existing = None
    providers = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    submitted = updates.get("providers", {})
    if not isinstance(submitted, dict):
        raise ValueError("地图供应商配置格式无效")
    for provider, key_field in PROVIDER_KEY_FIELDS.items():
        current = providers.get(provider)
        current = current if isinstance(current, dict) else {}
        current.setdefault(key_field, str(config.get("Map", LEGACY_KEY_FIELDS[provider], fallback="") or "").strip())
        current.setdefault("backend_page_origin", "")
        if provider == "amap":
            current.setdefault("security_js_code", "")
        incoming = submitted.get(provider, {})
        if not isinstance(incoming, dict):
            raise ValueError("地图供应商配置格式无效")
        for field in (key_field, "security_js_code" if provider == "amap" else None):
            if field and field in incoming:
                current[field] = str(incoming[field] or "").strip()
        if key_field not in incoming and LEGACY_KEY_FIELDS[provider] in updates:
            current[key_field] = str(updates[LEGACY_KEY_FIELDS[provider]] or "").strip()
        if "backend_page_origin" in incoming:
            current["backend_page_origin"] = normalize_backend_page_origin(incoming["backend_page_origin"])
        providers[provider] = current
    global_origin = config.get("Map", "backend_page_origin", fallback="")
    if "backend_page_origin" in updates:
        global_origin = normalize_backend_page_origin(updates["backend_page_origin"])
    frontend_proxy_enabled = config.get("Map", "frontend_proxy_enabled", fallback=False)
    if isinstance(frontend_proxy_enabled, str):
        frontend_proxy_enabled = frontend_proxy_enabled.strip().lower() in {"1", "true", "yes", "on"}
    else:
        frontend_proxy_enabled = bool(frontend_proxy_enabled)
    if "frontend_proxy_enabled" in updates:
        value = updates["frontend_proxy_enabled"]
        if isinstance(value, bool):
            frontend_proxy_enabled = value
        elif isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
            frontend_proxy_enabled = value.strip().lower() in {"1", "true", "yes", "on"}
        else:
            raise ValueError("地图代理开关必须为布尔值")
    return {
        "provider": updates.get("provider", config.get("Map", "provider", fallback="amap")),
        "backend_page_origin": global_origin,
        "frontend_proxy_enabled": frontend_proxy_enabled,
        "providers": providers,
    }
