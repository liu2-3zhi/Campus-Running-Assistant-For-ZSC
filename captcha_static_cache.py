"""Process-local cache for the public behavior CAPTCHA SDK assets."""

from collections import OrderedDict
from concurrent.futures import Future
import re
import threading
import time
from typing import NamedTuple

import requests
from werkzeug.datastructures import ResponseCacheControl
from werkzeug.http import parse_cache_control_header


_TTL_SECONDS = 300
_MAX_ASSETS = 32
_MAX_ASSET_BYTES = 1024 * 1024
_MAX_IN_FLIGHT = 32
_TAC_ASSET_PATH = re.compile(
    r"tac/(?:js|css|images)/(?:[\w-]+/)*[\w.-]+\.[a-z0-9]+",
    re.ASCII | re.IGNORECASE,
)
_MEDIA_TYPES = {
    "js": {
        "application/javascript", "text/javascript", "application/x-javascript",
        "application/ecmascript", "text/ecmascript",
    },
    "css": {"text/css"},
    "apng": {"image/apng"},
    "avif": {"image/avif"},
    "gif": {"image/gif"},
    "ico": {"image/vnd.microsoft.icon", "image/x-icon"},
    "jpeg": {"image/jpeg"},
    "jpg": {"image/jpeg"},
    "png": {"image/png"},
    "svg": {"image/svg+xml"},
    "webp": {"image/webp"},
}
_PATH_SUFFIXES = {
    "js": {"js"},
    "css": {"css"},
    "images": _MEDIA_TYPES.keys() - {"js", "css"},
}


class _Asset(NamedTuple):
    content: bytes
    status: int
    content_type: str


def _allowed_media_types(path):
    if path == "loader.js":
        return _MEDIA_TYPES["js"]
    if not _TAC_ASSET_PATH.fullmatch(path):
        return None
    category = path.split("/", 2)[1].lower()
    extension = path.rsplit(".", 1)[1].lower()
    if extension in {"mjs", "cjs"}:
        extension = "js"
    if extension in _PATH_SUFFIXES[category]:
        return _MEDIA_TYPES[extension]
    return None


def _download(base, path, timeout, allowed_types):
    response = requests.get(f"{base}/{path}", timeout=timeout)
    asset = _Asset(
        response.content,
        response.status_code,
        response.headers.get("Content-Type", "application/octet-stream"),
    )
    if (
        not allowed_types
        or asset.status != 200
        or response.history
        or not 0 < len(asset.content) <= _MAX_ASSET_BYTES
        or not asset.content.strip()
        or asset.content_type.split(";", 1)[0].strip().lower() not in allowed_types
        or "Set-Cookie" in response.headers
        or response.headers.get("Vary", "").strip() == "*"
    ):
        return asset, 0
    cache_control = parse_cache_control_header(
        response.headers.get("Cache-Control"), cls=ResponseCacheControl,
    )
    if any(directive in cache_control for directive in ("no-store", "no-cache", "private")):
        return asset, 0
    upstream_ttl = cache_control.s_maxage
    if upstream_ttl is None:
        upstream_ttl = cache_control.max_age
    ttl = _TTL_SECONDS if upstream_ttl is None else min(_TTL_SECONDS, upstream_ttl)
    return asset, ttl


class BehaviorStaticCache:
    def __init__(self):
        self._entries = OrderedDict()
        self._in_flight = {}
        self._lock = threading.Lock()

    def get(self, base, path, *, timeout):
        allowed_types = _allowed_media_types(path)
        if allowed_types is None:
            return _download(base, path, timeout, None)[0]
        key = (base, path)
        with self._lock:
            cached = self._entries.pop(key, None)
            if cached is not None and cached[0] > time.monotonic():
                self._entries[key] = cached
                return cached[1]
            pending = self._in_flight.get(key)
            lead = pending is None and len(self._in_flight) < _MAX_IN_FLIGHT
            if lead:
                pending = self._in_flight[key] = Future()
        if not lead:
            # Only share responses eligible for the cache with waiting callers.
            shared = pending.result() if pending is not None else None
            if shared is not None:
                return shared
            return _download(base, path, timeout, None)[0]
        try:
            asset, ttl = _download(base, path, timeout, allowed_types)
            if ttl > 0:
                with self._lock:
                    self._entries[key] = (time.monotonic() + ttl, asset)
                    while len(self._entries) > _MAX_ASSETS:
                        self._entries.popitem(last=False)
            pending.set_result(asset if ttl > 0 else None)
            return asset
        except BaseException as exc:
            pending.set_exception(exc)
            raise
        finally:
            with self._lock:
                del self._in_flight[key]


behavior_static_cache = BehaviorStaticCache()
