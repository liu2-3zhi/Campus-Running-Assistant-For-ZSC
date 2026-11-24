"""Regression tests for non-blocking CDN warmup and cache-miss responses."""

import ast
from copy import deepcopy
import logging
import os
from pathlib import Path
import threading
from types import SimpleNamespace

from flask import Flask, jsonify, make_response
import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_TREE = ast.parse((ROOT / "web_server.py").read_text(encoding="utf-8"))


def _nested_function(name):
    node = next(node for node in ast.walk(WEB_TREE)
                if isinstance(node, ast.FunctionDef) and node.name == name)
    node = deepcopy(node)
    node.decorator_list = []
    ast.fix_missing_locations(node)
    return node


def _compile_function(name, namespace):
    node = _nested_function(name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "web_server.py"), "exec"), namespace)
    return namespace[name]


def test_init_cdn_cache_only_loads_local_files(tmp_path):
    cached_path = tmp_path / "cached.js"
    cached_path.write_text("cached", encoding="utf-8")
    calls = []
    files = {"cached": "cached.js", "missing": "missing.js"}

    def load_cached_file(filename):
        path = tmp_path / filename
        return path.read_text(encoding="utf-8") if path.exists() else None

    def load_cached_fonts():
        calls.append("fonts")

    def update_single_cdn_file(key, config):
        calls.append(("update", key))
        raise AssertionError("startup must not download CDN files synchronously")

    namespace = {
        "CDN_FILES": {
            key: {"filename": filename, "type": "js"}
            for key, filename in files.items()
        },
        "JS_CACHE_DIR": str(tmp_path),
        "js_cache_storage": {},
        "js_cache_last_update": {},
        "font_cache_storage": {},
        "source_map_storage": {},
        "js_cache_lock": threading.RLock(),
        "source_map_lock": threading.RLock(),
        "load_cached_fonts": load_cached_fonts,
        "load_cached_file": load_cached_file,
        "update_single_cdn_file": update_single_cdn_file,
        "logging": logging,
        "os": os,
    }
    _compile_function("init_cdn_cache", namespace)()

    assert calls == ["fonts"]
    assert namespace["js_cache_storage"] == {"cached": "cached"}
    assert "missing" not in namespace["js_cache_storage"]


def test_cdn_worker_updates_before_waiting():
    events = []

    class StopAfterFirstSleep:
        @staticmethod
        def sleep(seconds):
            events.append(("sleep", seconds))
            raise KeyboardInterrupt

    class FakeThread:
        name = "CDN_Update_Worker"
        ident = 42

    namespace = {
        "threading": SimpleNamespace(current_thread=lambda: FakeThread()),
        "logging": logging,
        "time": StopAfterFirstSleep,
        "update_all_cdn_files": lambda: events.append(("update",)),
    }
    worker = _compile_function("cdn_cache_update_worker", namespace)

    with pytest.raises(KeyboardInterrupt):
        worker()

    assert events == [("update",), ("sleep", 3600)]


def test_configured_cdn_cache_miss_is_retryable_503():
    app = Flask(__name__)
    runtime = SimpleNamespace(
        make_response=make_response,
        jsonify=jsonify,
        _make_frontend_javascript_response=lambda content, **kwargs: make_response(content),
    )
    namespace = {
        "_main": lambda: runtime,
        "CDN_FILES": {"known": {"filename": "known.js", "type": "js"}},
        "js_cache_storage": {},
        "js_cache_lock": threading.RLock(),
        "logging": logging,
    }
    route = _compile_function("get_cdn_cached_file", namespace)
    app.add_url_rule("/api/cdn/<file_key>", view_func=route)

    with app.test_client() as client:
        pending = client.get("/api/cdn/known")
        unknown = client.get("/api/cdn/unknown")
        sourcemap = client.get("/api/cdn/known.map")
        namespace["js_cache_storage"]["known"] = "cached script"
        cached = client.get("/api/cdn/known")

    assert pending.status_code == 503
    assert pending.headers["Retry-After"] == "5"
    assert pending.get_json() == {"success": False, "message": "CDN缓存尚未就绪"}
    assert unknown.status_code == 404
    assert sourcemap.status_code == 204
    assert cached.status_code == 200
    assert cached.get_data(as_text=True) == "cached script"
