"""Backend-only map page origins and partial administrator configuration updates."""

import copy
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import re
from urllib.parse import urlsplit


TILE_CACHE_DEFAULTS = {"tile_cache_ttl_days": 20, "tile_cache_max_size_gb": 10}


def get_tile_cache_settings(config, updates=None):
    """Read legacy defaults, but reject invalid explicitly submitted values."""
    result = {}
    for field, default in TILE_CACHE_DEFAULTS.items():
        submitted = updates is not None and field in updates
        value = updates[field] if submitted else config.get("Map", field, fallback=default)
        try:
            if isinstance(value, bool) or len(str(value)) > 128:
                raise ValueError()
            number = Decimal(str(value))
            if not number.is_finite() or number <= 0 or number.adjusted() > 12:
                raise ValueError()
            if field == "tile_cache_ttl_days":
                if number != number.to_integral_value():
                    raise ValueError()
                normalized = int(number)
            else:
                if number * 100 != (number * 100).to_integral_value():
                    raise ValueError()
                normalized = float(number)
            result[field] = normalized
        except (ValueError, InvalidOperation, TypeError):
            if submitted:
                label = "地图瓦片缓存时间必须为正整数天数" if field == "tile_cache_ttl_days" else "地图瓦片缓存大小必须为正数 GB，最多两位小数"
                raise ValueError(label) from None
            result[field] = default
    return result


MAP_RUNTIME_PATH = "/map-runtime"
MAP_RUNTIME_MARKER = "zx-local-map-runtime-v1"
MAP_RUNTIME_PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="zx-map-runtime" content="zx-local-map-runtime-v1">
<meta name="referrer" content="strict-origin"><title>Map Runtime</title></head>
<body></body></html>"""

PROVIDER_KEY_FIELDS = {"amap": "js_key", "tencent": "map_key", "tianditu": "token", "baidu": "ak"}
LEGACY_KEY_FIELDS = {"amap": "amap_js_key", "tencent": "tencent_map_key", "tianditu": "tianditu_token", "baidu": "baidu_map_ak"}
PROVIDER_NAMES = {"amap": "高德", "tencent": "腾讯", "tianditu": "天地图", "baidu": "百度"}


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


def _stored_map_providers(config):
    providers = config.get("Map", "providers", fallback=None)
    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
        except (TypeError, ValueError):
            providers = None
    return providers if isinstance(providers, dict) else {}


def _normalize_map_configs(values, existing=None):
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except (TypeError, ValueError):
            pass
    if not isinstance(values, list) or not values:
        raise ValueError("请至少添加一份地图配置")
    previous = {entry["id"]: entry for entry in existing or []}
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("地图配置格式无效")
        config_id = value.get("id")
        if not isinstance(config_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", config_id):
            raise ValueError("地图配置 ID 必须以字母或数字开头，且最多 128 位字母、数字、下划线或短横线")
        if config_id in seen:
            raise ValueError("地图配置 ID 不能重复")
        seen.add(config_id)
        provider = value.get("provider")
        if not isinstance(provider, str) or provider not in PROVIDER_KEY_FIELDS:
            raise ValueError("地图供应商无效")
        name = value.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100 or any(ord(char) < 32 for char in name):
            raise ValueError("地图配置名称不能为空，且最多 100 个字符")
        old = previous.get(config_id, {})
        if old.get("provider") != provider:
            old = {}
        entry = {"id": config_id, "name": name.strip(), "provider": provider}
        fields = [PROVIDER_KEY_FIELDS[provider], "backend_page_origin"]
        if provider == "amap":
            fields.append("security_js_code")
        for field in fields:
            field_value = value.get(field, old.get(field, ""))
            if field == "backend_page_origin":
                entry[field] = normalize_backend_page_origin(field_value)
            else:
                if isinstance(field_value, (dict, list)):
                    raise ValueError("地图密钥格式无效")
                entry[field] = str(field_value or "").strip()
        result.append(entry)
    return result


def get_map_config_settings(config):
    """Read ordered profiles, migrating the single-profile layout in memory."""
    stored = config.get("Map", "configs", fallback=None)
    provider = str(config.get("Map", "provider", fallback="amap") or "amap").strip().lower()
    if provider not in PROVIDER_KEY_FIELDS:
        provider = "amap"
    if stored is None:
        providers = _stored_map_providers(config)
        configs = []
        for provider_name, key_field in PROVIDER_KEY_FIELDS.items():
            old = providers.get(provider_name, {})
            old = old if isinstance(old, dict) else {}
            entry = {
                "id": "legacy-" + provider_name,
                "name": PROVIDER_NAMES[provider_name] + "1",
                "provider": provider_name,
                key_field: old.get(key_field) or config.get("Map", LEGACY_KEY_FIELDS[provider_name], fallback=""),
                "backend_page_origin": old.get("backend_page_origin", ""),
            }
            if provider_name == "amap":
                entry["security_js_code"] = old.get("security_js_code", "")
            configs.append(entry)
        configs = _normalize_map_configs(configs)
    else:
        configs = _normalize_map_configs(stored)
    fallback = next((entry["id"] for entry in configs if entry["provider"] == provider), configs[0]["id"])
    ids = {entry["id"] for entry in configs}
    result = {"configs": configs}
    for scope in ("frontend", "backend"):
        selected = config.get("Map", scope + "_config_id", fallback="") or fallback
        if not isinstance(selected, str) or selected not in ids:
            raise ValueError("前端或后端选择的地图配置不存在")
        result[scope + "_config_id"] = selected
    return result


def get_map_config_selection(config, scope="backend", provider=None):
    if scope not in ("frontend", "backend"):
        raise ValueError("地图配置用途无效")
    settings = get_map_config_settings(config)
    selected = next(entry for entry in settings["configs"] if entry["id"] == settings[scope + "_config_id"])
    if provider is not None and selected["provider"] != provider:
        selected = next((entry for entry in settings["configs"] if entry["provider"] == provider), None)
    return copy.deepcopy(selected) if selected else {}


def resolve_backend_page_origin(config, provider, request_origin=None, scope="backend"):
    provider_config = get_map_config_selection(config, scope=scope, provider=provider)
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
    settings = get_map_config_settings(config)
    configs = settings["configs"]
    if "configs" in updates:
        configs = _normalize_map_configs(updates["configs"], configs)
    selected_ids = {scope: updates.get(scope + "_config_id", settings[scope + "_config_id"])
                    for scope in ("frontend", "backend")}
    ids = {entry["id"] for entry in configs}
    if any(not isinstance(value, str) or value not in ids for value in selected_ids.values()):
        raise ValueError("前端或后端选择的地图配置不存在")
    if "provider" in updates and "configs" not in updates:
        provider = updates["provider"]
        if not isinstance(provider, str) or provider not in PROVIDER_KEY_FIELDS:
            raise ValueError("地图供应商无效")
        candidate = next((entry for entry in configs if entry["id"] == selected_ids["frontend"] and entry["provider"] == provider),
                         next((entry for entry in configs if entry["provider"] == provider), None))
        if candidate is None:
            raise ValueError("请先添加对应供应商的地图配置")
        selected_ids["frontend"] = candidate["id"]
        if config.get("Map", "configs", fallback=None) is None and "backend_config_id" not in updates:
            selected_ids["backend"] = candidate["id"]
    submitted = updates.get("providers", {})
    if not isinstance(submitted, dict):
        raise ValueError("地图供应商配置格式无效")
    for provider, key_field in PROVIDER_KEY_FIELDS.items():
        incoming = submitted.get(provider, {})
        if not isinstance(incoming, dict):
            raise ValueError("地图供应商配置格式无效")
        if "configs" in updates:
            continue
        current = next((entry for entry in configs if entry["id"] == selected_ids["frontend"] and entry["provider"] == provider),
                       next((entry for entry in configs if entry["provider"] == provider and entry["id"] != selected_ids["backend"]),
                            next((entry for entry in configs if entry["provider"] == provider), None)))
        if current is None:
            fields = (key_field, "security_js_code", "backend_page_origin")
            if any(incoming.get(field) for field in fields) or updates.get(LEGACY_KEY_FIELDS[provider]):
                raise ValueError("请先添加对应供应商的地图配置")
            continue
        replacement = dict(current)
        for field in (key_field, "security_js_code" if provider == "amap" else None):
            if field and field in incoming:
                replacement[field] = str(incoming[field] or "").strip()
        if key_field not in incoming and LEGACY_KEY_FIELDS[provider] in updates:
            replacement[key_field] = str(updates[LEGACY_KEY_FIELDS[provider]] or "").strip()
        if "backend_page_origin" in incoming:
            replacement["backend_page_origin"] = normalize_backend_page_origin(incoming["backend_page_origin"])
        if (config.get("Map", "configs", fallback=None) is not None
                and current["id"] == selected_ids["backend"] != selected_ids["frontend"]
                and replacement != current):
            raise ValueError("请通过地图配置卡片修改后端专用配置")
        current.update(replacement)
    # The old provider map is a frontend projection; independent backend secrets
    # remain available only through the selected backend profile.
    providers = {}
    for provider in PROVIDER_KEY_FIELDS:
        selected = next((entry for entry in configs if entry["id"] == selected_ids["frontend"] and entry["provider"] == provider),
                        next((entry for entry in configs if entry["provider"] == provider), None))
        if selected:
            providers[provider] = {key: value for key, value in selected.items() if key not in ("id", "name", "provider")}
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
        "provider": next(entry["provider"] for entry in configs if entry["id"] == selected_ids["frontend"]),
        "configs": configs,
        "frontend_config_id": selected_ids["frontend"],
        "backend_config_id": selected_ids["backend"],
        "backend_page_origin": global_origin,
        "frontend_proxy_enabled": frontend_proxy_enabled,
        **get_tile_cache_settings(config, updates),
        "providers": providers,
    }
