"""Small JSON cache with a bounded process-local fallback.

``python main.py`` uses memory only. Docker can opt in to Redis so several
application workers share short-lived projections. Cache contents must be
non-sensitive JSON values; cache keys are hashed before being sent to Redis.
Redis is best effort, so cache failures never become request failures.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import logging
import math
import os
import threading
import time


_PREFIX = "campus-running:json:"
_DEFAULT_TTL = 15.0
_DEFAULT_MAX_ENTRIES = 256
_MAX_ENTRY_BYTES = 4 * 1024 * 1024
_REDIS_RETRY_DELAY = 5.0
_MISSING = object()
_UNAVAILABLE = object()
_memory_lock = threading.RLock()
_memory_entries: OrderedDict[str, tuple[float, str]] = OrderedDict()
# Striped locks coalesce concurrent cold loads without growing with user keys.
_load_locks = tuple(threading.RLock() for _ in range(64))
_redis_client = None
_redis_disabled_until = 0.0
_redis_import_failed = False
_redis_last_error_at = 0.0


def _memory_limit() -> int:
    try:
        value = int(os.environ.get("CACHE_MAX_ENTRIES", _DEFAULT_MAX_ENTRIES))
    except (TypeError, ValueError):
        value = _DEFAULT_MAX_ENTRIES
    return max(16, min(value, 10000))


def _load_lock(key: str) -> threading.RLock:
    index = hashlib.sha256(key.encode("utf-8")).digest()[0] % len(_load_locks)
    return _load_locks[index]


def _redis_key(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return _PREFIX + digest


def _json_payload(value):
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def _remember(key: str, payload: str, ttl: float) -> None:
    expires_at = time.monotonic() + ttl
    with _memory_lock:
        _memory_entries.pop(key, None)
        _memory_entries[key] = (expires_at, payload)
        while len(_memory_entries) > _memory_limit():
            _memory_entries.popitem(last=False)


def _memory_get(key: str):
    now = time.monotonic()
    with _memory_lock:
        entry = _memory_entries.get(key)
        if entry is None:
            return _MISSING
        expires_at, payload = entry
        if expires_at <= now:
            _memory_entries.pop(key, None)
            return _MISSING
        _memory_entries.move_to_end(key)
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        invalidate_cache(key)
        return _MISSING


def _disable_redis(error: Exception) -> None:
    global _redis_disabled_until, _redis_last_error_at
    _redis_disabled_until = time.monotonic() + _REDIS_RETRY_DELAY
    now = time.monotonic()
    if now - _redis_last_error_at >= _REDIS_RETRY_DELAY:
        logging.warning(
            "[缓存] Redis 不可用，暂回退内存缓存 error_type=%s",
            type(error).__name__,
        )
        _redis_last_error_at = now


def _get_redis():
    global _redis_client, _redis_import_failed
    if os.environ.get("APP_CACHE_BACKEND", "memory").strip().lower() != "redis":
        return None
    if time.monotonic() < _redis_disabled_until:
        return None
    if _redis_client is not None:
        return _redis_client
    if _redis_import_failed:
        return None
    try:
        import redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry
    except ImportError:
        _redis_import_failed = True
        logging.warning("[缓存] 未安装 redis 客户端，使用内存缓存")
        return None
    try:
        _redis_client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DATABASE", "0")),
            decode_responses=True,
            socket_connect_timeout=float(os.environ.get("REDIS_CONNECT_TIMEOUT", "0.25")),
            socket_timeout=float(os.environ.get("REDIS_SOCKET_TIMEOUT", "0.25")),
            # redis-py 6 retries connection errors by default. A disposable
            # cache should fail over immediately instead of delaying login.
            retry=Retry(NoBackoff(), 0),
            retry_on_error=[],
            max_connections=32,
        )
    except (TypeError, ValueError, OSError) as error:
        _disable_redis(error)
        return None
    return _redis_client


def _redis_get(key: str):
    client = _get_redis()
    if client is None:
        return _UNAVAILABLE
    redis_key = _redis_key(key)
    try:
        payload = client.get(redis_key)
        if payload is None:
            return _MISSING
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            try:
                client.delete(redis_key)
            except Exception:
                pass
            return _MISSING
    except Exception as error:
        _disable_redis(error)
        return _UNAVAILABLE


def _redis_set(key: str, payload: str, ttl: float) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(_redis_key(key), max(1, math.ceil(ttl)), payload)
    except Exception as error:
        _disable_redis(error)


def cached_json(key: str, loader, *, ttl: float = _DEFAULT_TTL):
    """Return a JSON-compatible value cached for ``ttl`` seconds.

    Concurrent cold calls for the same key in this process share one loader
    invocation. Callers should include the owner/scope and data generation in
    keys where those distinctions affect visibility or freshness.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("cache key must be a non-empty string")
    if not callable(loader):
        raise TypeError("loader must be callable")
    try:
        ttl_value = float(ttl)
    except (TypeError, ValueError):
        raise ValueError("ttl must be a finite positive number") from None
    if not math.isfinite(ttl_value) or ttl_value <= 0:
        raise ValueError("ttl must be a finite positive number")

    with _load_lock(key):
        value = _redis_get(key)
        if value is not _MISSING and value is not _UNAVAILABLE:
            return value
        # Redis is authoritative when available. Only use the memory mirror
        # during an outage, otherwise another worker's invalidation is hidden
        # behind a stale local entry and Redis TTL is inadvertently extended.
        if value is _UNAVAILABLE:
            value = _memory_get(key)
            if value is not _MISSING:
                return value

        value = loader()
        payload = _json_payload(value)
        if len(payload.encode("utf-8")) <= _MAX_ENTRY_BYTES:
            _remember(key, payload, ttl_value)
            _redis_set(key, payload, ttl_value)
        return json.loads(payload)


def invalidate_cache(key: str) -> None:
    """Invalidate one exact key in process memory and Redis."""
    if not isinstance(key, str) or not key.strip():
        raise ValueError("cache key must be a non-empty string")
    with _load_lock(key):
        with _memory_lock:
            _memory_entries.pop(key, None)
        client = _get_redis()
        if client is None:
            return
        try:
            client.delete(_redis_key(key))
        except Exception as error:
            _disable_redis(error)


def clear_memory_cache() -> None:
    """Clear process-local entries, primarily for tests and shutdown."""
    with _memory_lock:
        _memory_entries.clear()
