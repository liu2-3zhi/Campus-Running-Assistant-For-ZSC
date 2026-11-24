from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import sys
import threading
import time
import types

import pytest


def load_cache(monkeypatch, **env):
    for key in (
        "APP_CACHE_BACKEND",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DATABASE",
        "REDIS_CONNECT_TIMEOUT",
        "REDIS_SOCKET_TIMEOUT",
        "CACHE_MAX_ENTRIES",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import runtime_cache

    return importlib.reload(runtime_cache)


def test_memory_cache_calls_loader_once_and_returns_json_isolated(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    calls = []

    def loader():
        calls.append(True)
        return {"items": ["first"], "nested": {"enabled": True}}

    first = cache.cached_json("school:owner", loader, ttl=30)
    first["items"].append("mutated")
    second = cache.cached_json("school:owner", loader, ttl=30)

    assert calls == [True]
    assert second == {"items": ["first"], "nested": {"enabled": True}}


def test_memory_cache_expires_and_invalidates(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    now = [100.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: now[0])
    calls = []

    def loader():
        calls.append(len(calls) + 1)
        return {"value": calls[-1]}

    assert cache.cached_json("key", loader, ttl=0.01) == {"value": 1}
    now[0] += 0.02
    assert cache.cached_json("key", loader, ttl=1) == {"value": 2}
    cache.invalidate_cache("key")
    assert cache.cached_json("key", loader, ttl=1) == {"value": 3}


def test_redis_failure_falls_back_to_memory_without_repeating_loader(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="redis")

    class BrokenRedis:
        def get(self, *_args, **_kwargs):
            raise OSError("redis down")

        def setex(self, *_args, **_kwargs):
            raise OSError("redis down")

        def delete(self, *_args, **_kwargs):
            raise OSError("redis down")

    monkeypatch.setattr(cache, "_redis_client", BrokenRedis())
    calls = []

    def loader():
        calls.append(True)
        return {"ok": True}

    assert cache.cached_json("redis-key", loader, ttl=30) == {"ok": True}
    assert cache.cached_json("redis-key", loader, ttl=30) == {"ok": True}
    assert calls == [True]


def test_invalid_loader_result_is_not_cached(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    calls = []

    def loader():
        calls.append(True)
        return {"bad": object()}

    with pytest.raises(TypeError):
        cache.cached_json("bad", loader, ttl=30)
    with pytest.raises(TypeError):
        cache.cached_json("bad", loader, ttl=30)
    assert len(calls) == 2


def test_cache_key_does_not_put_raw_key_in_redis_payload(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="redis")
    seen = {}

    class FakeRedis:
        def setex(self, key, ttl, value):
            seen.update(key=key, ttl=ttl, value=value)

        def get(self, *_args, **_kwargs):
            return None

        def delete(self, *_args, **_kwargs):
            return 1

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())
    raw_key = "school-owner/password/UA"
    cache.cached_json(raw_key, lambda: {"safe": True}, ttl=7)

    assert raw_key not in seen["key"]
    assert raw_key not in seen["value"]
    assert json.loads(seen["value"]) == {"safe": True}
    assert seen["ttl"] == 7


def test_none_is_a_cached_json_value(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    calls = []

    def loader():
        calls.append(True)
        return None

    assert cache.cached_json("nullable", loader) is None
    assert cache.cached_json("nullable", loader) is None
    assert len(calls) == 1


def test_same_key_concurrent_loads_are_coalesced(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    calls = []
    barrier = threading.Barrier(4)

    def loader():
        calls.append(True)
        time.sleep(0.02)
        return {"value": 1}

    def run():
        barrier.wait()
        return cache.cached_json("concurrent", loader, ttl=30)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: run(), range(4)))
    assert results == [{"value": 1}] * 4
    assert len(calls) == 1


def test_memory_cache_is_bounded_lru(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory", CACHE_MAX_ENTRIES="16")
    for index in range(16):
        cache.cached_json(f"key-{index}", lambda index=index: index)
    # Touch the first key so it is retained as the least-recently-used entry.
    assert cache.cached_json("key-0", lambda: "reloaded") == 0
    cache.cached_json("key-new", lambda: "new")
    assert "key-0" in cache._memory_entries
    assert "key-1" not in cache._memory_entries


def test_redis_hit_and_invalidation_remove_both(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="redis")
    values = {}
    deleted = []

    class FakeRedis:
        def get(self, key):
            return values.get(key)

        def setex(self, key, _ttl, value):
            values[key] = value

        def delete(self, key):
            deleted.append(key)
            return values.pop(key, None) is not None

    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis_client", fake)
    first_calls = []
    assert cache.cached_json("scope:key", lambda: first_calls.append(1) or {"v": 1}) == {"v": 1}
    cache.clear_memory_cache()
    assert cache.cached_json("scope:key", lambda: {"v": 2}) == {"v": 1}
    cache.invalidate_cache("scope:key")
    assert deleted == [cache._redis_key("scope:key")]
    assert cache.cached_json("scope:key", lambda: {"v": 3}) == {"v": 3}
    assert first_calls == [1]


def test_healthy_redis_does_not_hide_another_workers_invalidation(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="redis")
    values = {}

    class FakeRedis:
        def get(self, key):
            return values.get(key)

        def setex(self, key, _ttl, value):
            values[key] = value

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())
    assert cache.cached_json("shared", lambda: {"v": 1}) == {"v": 1}
    values.clear()  # Another process invalidates the remote key.
    assert cache.cached_json("shared", lambda: {"v": 2}) == {"v": 2}


def test_nonfinite_ttl_is_rejected(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    with pytest.raises(ValueError):
        cache.cached_json("key", lambda: 1, ttl=float("inf"))


def test_oversized_values_are_returned_but_not_cached(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="memory")
    monkeypatch.setattr(cache, "_MAX_ENTRY_BYTES", 4)
    calls = []

    def loader():
        calls.append(True)
        return {"value": "too large"}

    assert cache.cached_json("large", loader) == {"value": "too large"}
    assert cache.cached_json("large", loader) == {"value": "too large"}
    assert len(calls) == 2


def test_redis_constructor_disables_retries_for_fast_fallback(monkeypatch):
    cache = load_cache(monkeypatch, APP_CACHE_BACKEND="redis")
    seen = {}
    fake_redis = types.ModuleType("redis")
    fake_backoff = types.ModuleType("redis.backoff")
    fake_retry = types.ModuleType("redis.retry")

    class Retry:
        def __init__(self, _backoff, retries):
            self.retries = retries

    fake_backoff.NoBackoff = lambda: object()
    fake_retry.Retry = Retry
    fake_redis.Redis = lambda **kwargs: seen.update(kwargs) or object()
    monkeypatch.setitem(sys.modules, "redis", fake_redis)
    monkeypatch.setitem(sys.modules, "redis.backoff", fake_backoff)
    monkeypatch.setitem(sys.modules, "redis.retry", fake_retry)

    assert cache._get_redis() is not None
    assert seen["retry"].retries == 0
    assert seen["socket_timeout"] == 0.25
    assert seen["socket_connect_timeout"] == 0.25
    assert seen["max_connections"] == 32
