"""Restricted, authenticated same-origin proxy for map SDK resources."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import socket
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests
from flask import Response, g, jsonify, make_response, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from map_runtime_origin import resolve_backend_page_origin


PROXY_COOKIE_NAME = "map_proxy_context"
PROXY_COOKIE_PATH = "/map-proxy"
PROXY_COOKIE_MAX_AGE = 30 * 60
MAX_REQUEST_BODY_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_CONCURRENT_REQUESTS = 12
QUEUE_WAIT_TIMEOUT = 3.0
REQUEST_TIMEOUT = (3.05, 10)
TILE_DEADLINE_SECONDS = 12.0
TILE_ATTEMPT_SECONDS = 6.0
PROXY_HOSTS = {
    "amap": frozenset({
        "webapi.amap.com", "restapi.amap.com", "vdata.amap.com", "a.amap.com",
        "jsapi.amap.com", "o4.amap.com",
        *(f"jsapi-data{number}.amap.com" for number in range(1, 6)),
        *(f"{prefix}{number:02d}.is.autonavi.com" for prefix in ("webrd", "wprd", "webst") for number in range(1, 5)),
    }),
    "tencent": frozenset({
        "map.qq.com", "mapapi.qq.com", "apis.map.qq.com", "pr.map.qq.com",
        "apikey.map.qq.com", "overseactrl.map.qq.com", "confinfo.map.qq.com",
        "vectorsdk.map.qq.com", "mapstyle.qpic.cn",
        *(f"{prefix}{number}.map.gtimg.com" for prefix in ("rt", "p") for number in range(4)),
    }),
    "baidu": frozenset({
        "api.map.baidu.com",
        *(f"{prefix}{number}.map.bdimg.com" for prefix in ("api", "online", "shangetu") for number in range(4)),
        *(f"apimaponline{number}.bdimg.com" for number in range(4)),
        *(f"maponline{number}.bdimg.com" for number in range(4)),
        *(f"d{number}.map.baidu.com" for number in range(4)),
        "dlswbr.baidu.com", "miao.baidu.com", "webmap0.bdimg.com",
    }),
    "tianditu": frozenset({
        "api.tianditu.gov.cn", "api.tianditu.com",
        *(f"t{number}.{suffix}" for number in range(8) for suffix in ("tianditu.gov.cn", "tianditu.com")),
    }),
}

_CONTROL_QUERY_FIELDS = frozenset({
    "session_id", "session_uuid", "admin_origin_session_id", "origin_session_id",
    "auth_token", "x_session_id",
})
_TEXT_CONTENT_TYPES = ("javascript", "ecmascript", "text/css", "application/css")
_HOST_PATTERN_CACHE = {}
_JSONP_CALLBACK_FIELDS = frozenset({"callback", "cb", "jsonp", "jsonpcallback"})
_JSONP_MIME_TYPES = frozenset({"application/json", "text/json", "text/plain", "application/octet-stream"})
_JSONP_CALLBACK_PATTERN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\Z")


def _map_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _map_setting(config, key, fallback=None):
    if isinstance(config, dict):
        section = config.get("Map", config)
        return section.get(key, fallback) if isinstance(section, dict) else fallback
    try:
        return config.get("Map", key, fallback=fallback)
    except Exception:
        return fallback


def _valid_host(host, provider):
    if not isinstance(host, str) or host != host.lower() or host.endswith("."):
        return False
    if any(char in host for char in ("@", ":", "%", "\\", "/", "\x00")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return host in PROXY_HOSTS.get(provider, ())


def _resolve_public_host(host, resolver=socket.getaddrinfo):
    try:
        records = resolver(host, 443, type=socket.SOCK_STREAM)
    except Exception:
        return False
    addresses = set()
    for record in records or ():
        try:
            addresses.add(ipaddress.ip_address(record[4][0]))
        except (ValueError, IndexError, TypeError):
            return False
    return bool(addresses) and all(address.is_global for address in addresses)


def _strip_control_query(raw_query):
    try:
        fields = parse_qsl(raw_query, keep_blank_values=True, max_num_fields=256)
    except ValueError:
        return None
    filtered = [(key, value) for key, value in fields if key.strip().lower() not in _CONTROL_QUERY_FIELDS]
    return urlencode(filtered, doseq=True)


def _safe_text_charset(content_type):
    match = re.search(r"(?:^|;)\s*charset\s*=\s*[\"']?([^;\"'\s]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else "utf-8"


def _reject_non_json_constant(_value):
    raise ValueError("non-JSON constant")


def _validated_jsonp_content_type(body, content_type, query, fetch_destination=""):
    """Correct vendor MIME only for an exact callback containing strict JSON."""
    if content_type.split(";", 1)[0].strip().lower() not in _JSONP_MIME_TYPES:
        return None
    if fetch_destination not in ("", "script"):
        return None
    callbacks = [value for key, values in query.lists() if key.lower() in _JSONP_CALLBACK_FIELDS for value in values]
    if len(callbacks) != 1:
        return None
    callback = callbacks[0]
    if (
        len(callback) > 256
        or not _JSONP_CALLBACK_PATTERN.fullmatch(callback)
        or any(part in {"__proto__", "prototype", "constructor", "eval", "Function", "setTimeout", "setInterval"}
               for part in callback.split("."))
    ):
        return None
    charset = _safe_text_charset(content_type)
    try:
        text = body.decode(charset)
        envelope = re.fullmatch(
            r"\s*(?:/\*\*/\s*)?(?:" + re.escape(callback) + r"\s*&&\s*)?"
            + re.escape(callback) + r"\s*\(\s*([\s\S]+)\s*\)\s*;?\s*",
            text.lstrip("\ufeff"),
        )
        if not envelope:
            return None
        json.loads(envelope.group(1), parse_constant=_reject_non_json_constant)
    except (ValueError, UnicodeDecodeError, LookupError, RecursionError):
        return None
    return f"application/javascript; charset={charset}"


def _rewrite_vendor_urls(body, provider, app_origin, backend_origin):
    """Rewrite only exact allowlisted provider hosts in JS/CSS response bodies."""
    text = body
    if backend_origin:
        origin_pattern = re.escape(backend_origin).replace("/", r"\\*/")
        text = re.sub(origin_pattern, "", text, flags=re.IGNORECASE)

    hosts = sorted(PROXY_HOSTS.get(provider, ()), key=len, reverse=True)
    pattern = _HOST_PATTERN_CACHE.get(provider)
    if pattern is None:
        alternatives = "|".join(re.escape(host) for host in hosts)
        pattern = re.compile(
            r"(?P<prefix>(?:https?:)?(?:(?:\\)?/){2})(?P<host>" + alternatives +
            r")(?:\\?:(?P<port>80|443)|:(?P<plain_port>80|443))?"
            r"(?P<tail>(?:(?:\\)?/|\?)[^\s\"'<>`)\\]*)?",
            re.IGNORECASE,
        )
        _HOST_PATTERN_CACHE[provider] = pattern

    def replace(match):
        host = match.group("host").lower()
        if not _valid_host(host, provider):
            return match.group(0)
        prefix = match.group("prefix").replace("\\/", "/")
        # SDKs also build bases as protocol+"//host" or protocol+"://host".
        # Rewriting a fragment creates malformed https:http://... URLs; the
        # browser hooks handle the completed URL when the SDK uses it.
        if ":" not in prefix:
            preceding = text[max(0, match.start() - 80):match.start()]
            if preceding.endswith(":") or re.search(r"\+\s*[\"']$", preceding):
                return match.group(0)
        tail = (match.group("tail") or "").replace("\\/", "/")
        candidate = (prefix if ":" in prefix else "https:" + prefix) + host + tail
        parsed = urlsplit(candidate)
        if parsed.hostname != host or parsed.port not in (None, 80, 443):
            return match.group(0)
        local = f"{app_origin}/map-proxy/{provider}/https/{host}{parsed.path}"
        if parsed.query:
            local += "?" + parsed.query
        return local

    return pattern.sub(replace, text)


class MapProxyAccessLogFilter(logging.Filter):
    """Hide proxy URLs (especially vendor keys in query strings) in WSGI logs."""

    @staticmethod
    def _scrub(value):
        if isinstance(value, str) and "/map-proxy/" in value:
            return re.sub(r"(/map-proxy/[^?\s\"]+)\?[^\s\"]*", r"\1?<redacted>", value)
        if isinstance(value, tuple):
            return tuple(MapProxyAccessLogFilter._scrub(item) for item in value)
        if isinstance(value, list):
            return [MapProxyAccessLogFilter._scrub(item) for item in value]
        if isinstance(value, dict):
            return {
                MapProxyAccessLogFilter._scrub(key): MapProxyAccessLogFilter._scrub(item)
                for key, item in value.items()
            }
        return value

    def filter(self, record):
        record.msg = self._scrub(record.msg)
        record.args = self._scrub(record.args)
        return True


class _MapProxy:
    def __init__(self, app, get_runtime_config, authorize_actor, transport, dns_resolver,
                 max_request_body_bytes, max_response_bytes, max_concurrent_requests,
                 on_context_authenticated=None):
        self.app = app
        self.get_runtime_config = get_runtime_config
        self.authorize_actor = authorize_actor
        self.on_context_authenticated = on_context_authenticated
        self.transport = transport or self._request_upstream
        self.dns_resolver = dns_resolver
        self.max_request_body_bytes = max_request_body_bytes
        self.max_response_bytes = max_response_bytes
        self.semaphore = threading.BoundedSemaphore(max_concurrent_requests)
        # Bound active requests plus two waves waiting for an upstream slot.
        self.admission_semaphore = threading.BoundedSemaphore(max_concurrent_requests * 3)
        self.serializer = URLSafeTimedSerializer(app.secret_key, salt="zx-map-proxy-context-v1")

    @staticmethod
    def _request_upstream(method, url, *, headers, body, timeout):
        with requests.Session() as session:
            session.trust_env = False
            return session.request(method, url, headers=headers, data=body, timeout=timeout,
                                  allow_redirects=False, stream=True)

    def _request_tianditu_tile(self, method, url, headers, body, host):
        started = time.monotonic()
        deadline = started + TILE_DEADLINE_SECONDS
        for attempt in range(1, 3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.ReadTimeout('tile deadline exceeded')
            budget = min(TILE_ATTEMPT_SECONDS, remaining)
            connect = min(REQUEST_TIMEOUT[0], budget / 2)
            upstream = None
            try:
                upstream = self.transport(method, url, headers=headers, body=body,
                                          timeout=(connect, budget - connect))
                status = int(getattr(upstream, 'status_code', getattr(upstream, 'status', 502)))
                if status in (502, 503, 504) and attempt < 2:
                    logging.warning('[MapProxy] provider=tianditu host=%s stage=tile attempt=%d status=%d elapsed_ms=%d',
                                    host, attempt, status, int((time.monotonic() - started) * 1000))
                    upstream.close()
                    upstream = None
                    continue
                payload = _read_limited_response(upstream, self.max_response_bytes, deadline=deadline)
                return upstream, payload
            except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as error:
                logging.warning('[MapProxy] provider=tianditu host=%s stage=tile attempt=%d error=%s elapsed_ms=%d',
                                host, attempt, type(error).__name__, int((time.monotonic() - started) * 1000))
                if upstream is not None:
                    upstream.close()
                    upstream = None
                if attempt == 2:
                    raise
            except Exception:
                if upstream is not None:
                    upstream.close()
                raise

    def _verify_actor(self):
        signed_context = request.cookies.get(PROXY_COOKIE_NAME, "")
        auth_token = request.cookies.get("auth_token", "")
        if not signed_context or not auth_token:
            return None
        try:
            claims = self.serializer.loads(signed_context, max_age=PROXY_COOKIE_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return None
        username = claims.get("username") if isinstance(claims, dict) else None
        token_digest = claims.get("token_digest") if isinstance(claims, dict) else None
        actor_session_id = claims.get("actor_session_id") if isinstance(claims, dict) else None
        require_view_all = claims.get("require_view_all") if isinstance(claims, dict) else None
        if not isinstance(username, str) or not username or not isinstance(token_digest, str) or not _normalize_session_id(actor_session_id):
            return None
        expected = hmac.new(self.app.secret_key.encode(), auth_token.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, token_digest):
            return None
        try:
            if not self.authorize_actor(username, auth_token, actor_session_id, bool(require_view_all)):
                return None
        except Exception:
            return None
        return username

    def register(self, login_required):
        logger = logging.getLogger("werkzeug")
        if not any(isinstance(item, MapProxyAccessLogFilter) for item in logger.filters):
            logger.addFilter(MapProxyAccessLogFilter())

        @self.app.route("/api/map-proxy/context", methods=["POST"])
        @login_required
        def map_proxy_context():
            origin_header = request.headers.get("Origin", "")
            expected_origin = _request_origin()
            if not origin_header or origin_header.rstrip("/") != expected_origin:
                return jsonify({"success": False, "message": "请求来源无效"}), 403
            config = self.get_runtime_config()
            if not _map_bool(_map_setting(config, "frontend_proxy_enabled", False)):
                return jsonify({"success": False, "message": "地图代理未启用"}), 404
            target_session_id = _normalize_session_id(request.headers.get("X-Session-ID", ""))
            business_session_id = _normalize_session_id(
                getattr(g, "viewed_session_id", "") or getattr(g, "session_id", "")
            )
            if not target_session_id or target_session_id != business_session_id:
                return jsonify({"success": False, "message": "会话无效"}), 401
            origin_session_id = _normalize_session_id(request.headers.get("X-Admin-Origin-Session-ID", ""))
            require_view_all = bool(origin_session_id and origin_session_id != target_session_id)
            if getattr(g, "admin_view_without_origin", False):
                require_view_all = True
            username = str(getattr(g, "user", "") or "").strip()
            auth_token = request.cookies.get("auth_token", "")
            actor_session_id = _normalize_session_id(getattr(g, "session_id", ""))
            if getattr(g, "admin_view_without_origin", False):
                require_view_all = True
            if not actor_session_id:
                return jsonify({"success": False, "message": "会话无效"}), 401
            if not username or not auth_token:
                return jsonify({"success": False, "message": "未登录或会话无效"}), 401
            try:
                if not self.authorize_actor(username, auth_token, actor_session_id, require_view_all):
                    return jsonify({"success": False, "message": "权限不足"}), 403
                if self.on_context_authenticated is not None and self.on_context_authenticated(
                    username, actor_session_id
                ) is not True:
                    return jsonify({"success": False, "message": "地图代理认证续期失败"}), 403
            except Exception:
                return jsonify({"success": False, "message": "权限不足"}), 403
            digest = hmac.new(self.app.secret_key.encode(), auth_token.encode(), hashlib.sha256).hexdigest()
            signed = self.serializer.dumps({
                "username": username,
                "token_digest": digest,
                "actor_session_id": actor_session_id,
                "require_view_all": require_view_all,
            })
            response = make_response(jsonify({"success": True, "expires_in": PROXY_COOKIE_MAX_AGE}))
            response.set_cookie(
                PROXY_COOKIE_NAME,
                signed,
                max_age=PROXY_COOKIE_MAX_AGE,
                httponly=True,
                secure=_request_origin().startswith("https://"),
                samesite="Strict",
                path=PROXY_COOKIE_PATH,
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Origin"
            return response

        @self.app.route("/map-proxy/<provider>/<scheme>/<host>", methods=["GET", "POST", "OPTIONS"])
        @self.app.route("/map-proxy/<provider>/<scheme>/<host>/", methods=["GET", "POST", "OPTIONS"])
        @self.app.route("/map-proxy/<provider>/<scheme>/<host>//", methods=["GET", "POST", "OPTIONS"], merge_slashes=False)
        @self.app.route("/map-proxy/<provider>/<scheme>/<host>/<path:resource_path>", methods=["GET", "POST", "OPTIONS"])
        def map_request_proxy(provider, scheme, host, resource_path=""):
            if provider not in PROXY_HOSTS:
                return make_response("", 404)
            config = self.get_runtime_config()
            if not _map_bool(_map_setting(config, "frontend_proxy_enabled", False)):
                return make_response("", 404)
            origin_header = request.headers.get("Origin", "")
            if request.method == "OPTIONS":
                if not origin_header or origin_header.rstrip("/") != _request_origin():
                    return make_response("", 403)
                response = make_response("", 204)
                response.headers["Access-Control-Allow-Origin"] = origin_header
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
                response.headers["Access-Control-Max-Age"] = "600"
                response.headers["Vary"] = "Origin"
                return response
            if origin_header and origin_header.rstrip("/") != _request_origin():
                return make_response("", 403)
            username = self._verify_actor()
            if not username:
                return make_response("", 401)
            if scheme != "https" or not _valid_host(host, provider):
                return make_response("", 400)
            if (
                len(resource_path) > 4096
                or any(ord(char) < 32 or char == "\\" for char in resource_path)
                or len(request.query_string) > 4096
            ):
                return make_response("", 414)
            if request.content_length and request.content_length > self.max_request_body_bytes:
                return make_response("", 413)
            if not self.admission_semaphore.acquire(blocking=False):
                return make_response("", 429)
            upstream = None
            active_acquired = False
            try:
                active_acquired = self.semaphore.acquire(timeout=QUEUE_WAIT_TIMEOUT)
                if not active_acquired:
                    return make_response("", 429)
                query = _strip_control_query(request.query_string.decode("latin-1"))
                if query is None:
                    return make_response("", 400)
                runtime_origin, source = resolve_backend_page_origin(
                    config, provider, _request_origin()
                )
                if not _resolve_public_host(host, self.dns_resolver):
                    return make_response("", 400)
                path = "/" + resource_path
                url = f"https://{host}{path}" + ("?" + query if query else "")
                body = None
                if request.method == "POST":
                    body = request.stream.read(self.max_request_body_bytes + 1)
                if body is not None and len(body) > self.max_request_body_bytes:
                    return make_response("", 413)
                outbound_headers = {
                    "User-Agent": "Mozilla/5.0 (compatible; ZXMapProxy/1.0)",
                    "Accept": request.headers.get("Accept", "*/*")[:512],
                    "Referer": runtime_origin + "/",
                    "Origin": runtime_origin,
                }
                for header in ("Content-Type", "Accept-Language", "Range", "If-None-Match", "If-Modified-Since"):
                    value = request.headers.get(header)
                    if value and len(value) <= 1024:
                        outbound_headers[header] = value
                stage = _resource_stage(provider, host, path)
                tile_body = None
                if request.method == 'GET' and stage == 'tile' and provider == 'tianditu':
                    upstream, tile_body = self._request_tianditu_tile(request.method, url, outbound_headers, body, host)
                else:
                    upstream = self.transport(request.method, url, headers=outbound_headers,
                                              body=body, timeout=REQUEST_TIMEOUT)
                status = int(getattr(upstream, "status_code", getattr(upstream, "status", 502)))
                response_headers = getattr(upstream, "headers", {})
                if 300 <= status < 400 and status != 304:
                    logging.warning("[MapProxy] blocked redirect provider=%s host=%s source=%s", provider, host, source)
                    return make_response("", 502)
                if status == 304:
                    return make_response("", 304)
                content_length = response_headers.get("Content-Length", "") if hasattr(response_headers, "get") else ""
                try:
                    if content_length and int(content_length) > self.max_response_bytes:
                        return make_response("", 502)
                except (ValueError, TypeError):
                    pass
                response_body = tile_body if tile_body is not None else _read_limited_response(upstream, self.max_response_bytes)
                content_type = str(response_headers.get("Content-Type", "application/octet-stream"))
                jsonp_content_type = _validated_jsonp_content_type(
                    response_body, content_type, request.args,
                    request.headers.get("Sec-Fetch-Dest", ""),
                ) if request.method == "GET" and 200 <= status < 300 else None
                if jsonp_content_type:
                    content_type = jsonp_content_type
                elif any(kind in content_type.lower() for kind in _TEXT_CONTENT_TYPES):
                    charset = _safe_text_charset(content_type)
                    try:
                        text_body = response_body.decode(charset, errors="replace")
                    except LookupError:
                        text_body = response_body.decode("utf-8", errors="replace")
                        charset = "utf-8"
                    text_body = _rewrite_vendor_urls(text_body, provider, _request_origin(), runtime_origin)
                    if (
                        request.headers.get("Sec-Fetch-Dest") == "worker"
                        and request.headers.get("Sec-Fetch-Mode") != "cors"
                        and any(kind in content_type.lower() for kind in ("javascript", "ecmascript"))
                    ):
                        script_url = json.dumps(_request_origin() + "/scripts/map-request-proxy.js")
                        worker_config = json.dumps({"enabled": True, "provider": provider, "basePath": "/map-proxy"})
                        text_body = f"importScripts({script_url});self.ZXMapRequestProxy.install({worker_config});\n" + text_body
                    try:
                        response_body = text_body.encode(charset, errors="replace")
                    except LookupError:
                        response_body = text_body.encode("utf-8", errors="replace")
                    content_type = re.sub(r";\s*charset\s*=\s*[^;]+", "", content_type, flags=re.IGNORECASE)
                    content_type += f"; charset={charset}"
                response = Response(response_body, status=status, content_type=content_type)
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Content-Type-Options"] = "nosniff"
                if origin_header:
                    response.headers["Access-Control-Allow-Origin"] = origin_header
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    response.headers["Vary"] = "Origin"
                for header in ("ETag", "Last-Modified", "Content-Language"):
                    value = response_headers.get(header) if hasattr(response_headers, "get") else None
                    if value:
                        response.headers[header] = value
                logging.info("[MapProxy] provider=%s host=%s source=%s stage=%s status=%d", provider, host, source, stage, status)
                return response
            except ValueError:
                return make_response("", 502)
            except Exception as error:
                logging.warning("[MapProxy] upstream failure provider=%s host=%s error=%s", provider, host, type(error).__name__)
                return make_response("", 502)
            finally:
                try:
                    if upstream is not None:
                        close = getattr(upstream, "close", None)
                        if callable(close):
                            close()
                finally:
                    try:
                        if active_acquired:
                            self.semaphore.release()
                    finally:
                        self.admission_semaphore.release()


def _normalize_session_id(value):
    candidate = str(value or "").strip().lower()
    return candidate if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", candidate) else ""


def _request_origin():
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request.scheme.lower()
    return f"{scheme}://{request.host.lower()}"


def _resource_stage(provider, host, path):
    if provider == 'tianditu':
        if re.fullmatch(r't[0-7]\.tianditu\.(?:gov\.cn|com)', host) and re.fullmatch(r'/(?:vec|cva)_[cw]/wmts', path):
            return 'tile'
        if path.rstrip('/') == '/drive':
            return 'route'
        if '/extend' in path:
            return 'sdk_extension'
    return 'sdk' if path.rstrip('/') == '/api' or path.endswith('.js') else 'resource'


def _read_limited_response(response, limit, *, deadline=None):
    chunks = []
    total = 0
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        pieces = iterator(chunk_size=64 * 1024)
    else:
        stream = getattr(response, "stream", None)
        if callable(stream):
            pieces = stream(amt=64 * 1024, decode_content=True)
        else:
            content = getattr(response, "content", None)
            if content is None:
                read = getattr(response, "read", None)
                content = read(limit + 1) if callable(read) else b""
            pieces = (content,)
    for chunk in pieces:
        if deadline is not None and time.monotonic() >= deadline:
            raise requests.ReadTimeout('tile deadline exceeded')
        if not chunk:
            continue
        total += len(chunk)
        if total > limit:
            raise ValueError("response too large")
        chunks.append(chunk)
    return b"".join(chunks)


def register_map_proxy_routes(app, login_required, get_runtime_config, authorize_actor,
                              transport=None, dns_resolver=socket.getaddrinfo,
                              max_request_body_bytes=MAX_REQUEST_BODY_BYTES,
                              max_response_bytes=MAX_RESPONSE_BYTES,
                              max_concurrent_requests=MAX_CONCURRENT_REQUESTS,
                              on_context_authenticated=None):
    """Register the authenticated context bootstrap and restricted vendor proxy."""
    proxy = _MapProxy(
        app,
        get_runtime_config,
        authorize_actor,
        transport,
        dns_resolver,
        max_request_body_bytes,
        max_response_bytes,
        max_concurrent_requests,
        on_context_authenticated,
    )
    proxy.register(login_required)
    return proxy
