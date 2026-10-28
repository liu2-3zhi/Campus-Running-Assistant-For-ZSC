"""Bounded, credential-free route diagnostics shared by workers and API callers."""

import json
import re
import uuid
from urllib.parse import quote, quote_plus


_REDACTED = "<redacted>"
_SECRET_KEY = re.compile(
    r"(?i)(?:key|token|secret|password|passwd|authorization|cookie|session|uuid|"
    r"signature|security[_-]?(?:js[_-]?)?code|openid|credential|captcha)"
)
_GEOMETRY_KEYS = {"path", "routes", "polyline", "waypoints", "target_points", "run_coords", "config", "provider_config", "provider_plan"}
_TEXT_SECRET = re.compile(
    r"(?i)([\"']?\b(?:api[_-]?key|map[_-]?key|js[_-]?key|apikey|key|ak|tk|"
    r"token|password|secret|security[_-]?(?:js[_-]?)?code|session[_-]?id|uuid|"
    r"signature|sign|sig|sn|cookie|authorization)[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&}\]]+)"
)
_URL = re.compile(r"https?://(?:<redacted>|[^\s\"'<>])+", re.I)


def new_diagnostic_id():
    return uuid.uuid4().hex[:12]


def _bounded(text, max_bytes):
    limit = max(0, int(max_bytes))
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    suffix = "..."
    return encoded[:max(0, limit - len(suffix))].decode("utf-8", errors="ignore") + suffix[:limit]


def _scrub_text(text, sensitive_values):
    text = str(text)
    for value in sensitive_values:
        if isinstance(value, (str, int)) and str(value):
            secret = str(value)
            for variant in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(variant, _REDACTED)

    def scrub_url(match):
        url = match.group(0)
        url = re.sub(r"(?i)^(https?://)[^/@]+@", r"\1<redacted>@", url)
        url = re.sub(r"(?i)(?:/uuid=|/session/)[^/?#]+", "/<redacted>", url)
        # Query strings can carry keys, signatures and complete waypoint coordinates.
        return re.split(r"[?#]", url, maxsplit=1)[0] + ("?<redacted>" if "?" in url or "#" in url else "")

    text = _URL.sub(scrub_url, text)
    text = re.sub(r"(?im)(\bauthorization\s*[:=]\s*)(?:bearer\s+)?[^\r\n,;}]+", r"\1<redacted>", text)
    text = re.sub(r"(?im)(\bcookie\s*[:=]\s*)[^\r\n]+", r"\1<redacted>", text)
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", text)
    return _TEXT_SECRET.sub(r"\1<redacted>", text)


def sanitize_diagnostic(value, max_bytes=4096, sensitive_values=()):
    """Return safe UTF-8 text, including for cyclic or malformed SDK objects."""
    try:
        seen = set()

        def clean(item, depth=0):
            if depth > 6:
                return "<depth limit>"
            if isinstance(item, (dict, list, tuple)):
                if id(item) in seen:
                    return "<cycle>"
                seen.add(id(item))
                if isinstance(item, dict):
                    result = {}
                    for key, child in list(item.items())[:40]:
                        key = str(key)
                        normalized = key.lower().replace("-", "_")
                        if _SECRET_KEY.search(key) or normalized in {"ak", "tk", "sign", "sig", "sn"}:
                            result[key] = _REDACTED
                        elif normalized in _GEOMETRY_KEYS:
                            result[key] = "<omitted>"
                        else:
                            result[key] = clean(child, depth + 1)
                    return result
                return [clean(child, depth + 1) for child in item[:12]]
            if item is None or isinstance(item, (bool, int, float)):
                return item
            return _scrub_text(item, sensitive_values)

        safe = clean(value)
        text = safe if isinstance(safe, str) else json.dumps(safe, ensure_ascii=False, default=str)
        return _bounded(text, max_bytes)
    except Exception:
        return _bounded("<unavailable diagnostic>", max_bytes)


def build_route_failure_summary(result):
    result = result if isinstance(result, dict) else {}
    diagnostic = result.get("diagnostic") or {}
    diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
    summary = {
        "diagnostic_id": str(result.get("diagnostic_id") or new_diagnostic_id())[:48],
        "provider": sanitize_diagnostic(result.get("provider") or "unknown", 40),
        "message": sanitize_diagnostic(result.get("error") or result.get("message") or "路径规划失败", 1200),
    }
    for name in ("segment", "error_code", "http_status", "api_type", "stage", "error_explanation", "error_hint"):
        value = result.get(name, diagnostic.get(name))
        if value is not None:
            limit = 240 if name in ("error_explanation", "error_hint") else 80
            summary[name] = value if isinstance(value, (int, float)) else sanitize_diagnostic(value, limit)
    while max(len(json.dumps(summary, ensure_ascii=ascii_only).encode("utf-8")) for ascii_only in (False, True)) > 2048:
        field = next((name for name in ("message", "error_hint", "error_explanation", "stage", "api_type", "error_code", "provider")
                      if isinstance(summary.get(name), str) and summary[name]), None)
        if field is None:
            break
        summary[field] = _bounded(summary[field], len(summary[field].encode("utf-8")) // 2)
    return summary


def generic_route_failure_message(diagnostic_id):
    return "自动生成路径失败，请尝试手动生成路径（诊断编号：%s）" % sanitize_diagnostic(diagnostic_id, 48)


def detailed_route_failure_message(summary):
    fields = []
    if summary.get("segment") is not None:
        fields.append("路段：%s" % sanitize_diagnostic(summary["segment"], 80))
    if summary.get("error_code") not in (None, ""):
        fields.append("错误码：%s" % sanitize_diagnostic(summary["error_code"], 80))
    if summary.get("error_explanation"):
        fields.append(sanitize_diagnostic(summary["error_explanation"], 240))
    if summary.get("error_hint"):
        fields.append("建议：%s" % sanitize_diagnostic(summary["error_hint"], 240))
    context = "；".join(fields)
    return "[%s] %s%s（诊断编号：%s）" % (
        summary["provider"], (context + "；") if context else "", summary["message"], summary["diagnostic_id"],
    )
