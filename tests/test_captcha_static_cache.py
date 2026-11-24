from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from flask import Flask, jsonify, make_response, request
import pytest
import requests
from requests.structures import CaseInsensitiveDict

import captcha_static_cache
import web_server


ROUTE_ROOT = "/api/captcha/behavior/"
LOADER_URL = ROUTE_ROOT + "loader.js"


def _upstream(content=b"window.initTAC = function() {};", content_type="application/javascript",
              *, status=200, headers=None):
    return SimpleNamespace(
        content=content,
        status_code=status,
        headers=CaseInsensitiveDict({"Content-Type": content_type, **(headers or {})}),
        history=[],
        text=content.decode("utf-8", errors="replace"),
    )


@pytest.fixture
def proxy():
    app = Flask(__name__)
    conf = {"behavior_base_url": f"https://captcha.test/{uuid4()}", "behavior_api_key": "test-key"}

    def javascript_response(content, *, status=200, headers=None):
        response = make_response(content, status)
        response.mimetype = "application/javascript"
        response.headers.update(headers or {})
        response.headers["X-JS-Hardened"] = "1"
        return response

    runtime = SimpleNamespace(
        _make_frontend_javascript_response=Mock(side_effect=javascript_response),
        _is_javascript_content_type=lambda content_type: content_type == "application/javascript",
        _is_javascript_asset_name=lambda asset: asset.endswith(".js"),
        get_captcha_provider_config=lambda: conf,
        append_behavior_captcha_history=Mock(),
        jsonify=jsonify,
        request=request,
    )
    source_file = Path(web_server.__file__)
    source = source_file.read_text(encoding="utf-8")
    start = source.index("    def _behavior_base_or_error():")
    end = source.index('    @app.route("/api/captcha/get"', start)
    namespace = {**vars(web_server), "app": app, "_main": lambda: runtime}
    exec(compile(dedent(source[start:end]), str(source_file), "exec"), namespace)
    return app.test_client(), conf, runtime


@pytest.mark.parametrize(("path", "content", "media_type"), [
    ("loader.js", b"window.initTAC = function() {};", "application/javascript"),
    ("tac/js/tac.min.js", b"window.TAC = {};", "application/javascript"),
    ("tac/css/tac.css", b".tac { width: 100%; }", "text/css"),
    ("tac/images/slider.png", b"\x89PNG\r\n\x1a\n", "image/png"),
])
def test_successful_static_resource_is_reused_with_same_response(proxy, monkeypatch, path, content, media_type):
    client, conf, runtime = proxy
    fetch = Mock(return_value=_upstream(content, media_type))
    monkeypatch.setattr(requests, "get", fetch)

    first = client.get(ROUTE_ROOT + path)
    second = client.get(ROUTE_ROOT + path)

    assert fetch.call_count == 1
    assert fetch.call_args.args == (f"{conf['behavior_base_url']}/{path}",)
    assert "headers" not in fetch.call_args.kwargs
    assert second.status_code == first.status_code == 200
    assert second.data == first.data == content
    assert second.mimetype == first.mimetype == media_type
    if path.endswith(".js"):
        assert second.headers.get("X-JS-Hardened") == first.headers.get("X-JS-Hardened") == "1"
        assert runtime._make_frontend_javascript_response.call_count == 2


@pytest.mark.parametrize("invalid", [
    _upstream(status=502),
    _upstream(b""),
    _upstream(b"<h1>Hold on</h1>", "text/html"),
    _upstream(headers={"cache-control": "private, no-store"}),
    _upstream(headers={"set-cookie": "upstream=id"}),
])
def test_load_errors_and_non_shareable_responses_are_not_retained(proxy, monkeypatch, invalid):
    client, _conf, _runtime = proxy
    valid = _upstream()
    fetch = Mock(side_effect=[invalid, valid])
    monkeypatch.setattr(requests, "get", fetch)

    assert client.get(LOADER_URL).status_code == invalid.status_code
    assert client.get(LOADER_URL).data == valid.content
    assert client.get(LOADER_URL).data == valid.content
    assert fetch.call_count == 2


def test_a_new_behavior_server_gets_its_own_static_resource(proxy, monkeypatch):
    client, conf, _runtime = proxy
    fetch = Mock(side_effect=[_upstream(b"first"), _upstream(b"second")])
    monkeypatch.setattr(requests, "get", fetch)

    assert client.get(LOADER_URL).data == b"first"
    conf["behavior_base_url"] += "-other"
    assert client.get(LOADER_URL).data == b"second"
    assert client.get(LOADER_URL).data == b"second"
    assert fetch.call_count == 2


def test_dynamic_challenge_and_non_asset_proxy_paths_never_use_static_cache(proxy, monkeypatch):
    client, _conf, _runtime = proxy
    fetch = Mock(return_value=_upstream())
    post = Mock(return_value=_upstream(b'{"code":200}', "application/json"))
    monkeypatch.setattr(requests, "get", fetch)
    monkeypatch.setattr(requests, "post", post)

    for _ in range(2):
        assert client.get(ROUTE_ROOT + "tac/custom/script.js").status_code == 200
        assert client.get(ROUTE_ROOT + "gen").status_code == 200
        assert client.post(ROUTE_ROOT + "check", json={"id": "test-id"}).status_code == 200

    assert fetch.call_count == 4
    assert post.call_count == 2
    assert fetch.call_args.kwargs["headers"] == {"X-Captcha-Key": "test-key"}
    assert post.call_args.kwargs["headers"]["X-Captcha-Key"] == "test-key"


def test_cache_expires_using_upstream_max_age(monkeypatch):
    cache = captcha_static_cache.BehaviorStaticCache()
    clock = SimpleNamespace(now=100)
    monkeypatch.setattr(captcha_static_cache, "time", SimpleNamespace(monotonic=lambda: clock.now))
    fetch = Mock(side_effect=[
        _upstream(b"first", headers={"Cache-Control": "public, max-age=2"}),
        _upstream(b"second"),
    ])
    monkeypatch.setattr(requests, "get", fetch)

    def load():
        return cache.get("https://captcha.test", "loader.js", timeout=5).content

    assert load() == b"first"
    clock.now = 101
    assert load() == b"first"
    clock.now = 102
    assert load() == b"second"
    assert fetch.call_count == 2


def test_cache_evicts_least_recently_used_and_skips_oversize_resources(monkeypatch):
    cache = captcha_static_cache.BehaviorStaticCache()
    monkeypatch.setattr(captcha_static_cache, "_MAX_ASSETS", 2)
    monkeypatch.setattr(captcha_static_cache, "_MAX_ASSET_BYTES", 4)
    fetch = Mock(side_effect=lambda url, timeout: _upstream(
        b"oversize" if url.endswith("large.js") else b"ok",
    ))
    monkeypatch.setattr(requests, "get", fetch)

    def load(name):
        return cache.get("https://captcha.test", f"tac/js/{name}.js", timeout=5).content

    for name in ("a", "b", "a", "c", "a"):
        assert load(name) == b"ok"
    assert fetch.call_count == 3
    assert load("b") == b"ok"
    assert fetch.call_count == 4
    assert load("large") == load("large") == b"oversize"
    assert fetch.call_count == 6


@pytest.mark.parametrize("first_fails", [False, True])
def test_concurrent_cache_misses_share_one_fetch_and_recover_after_exception(monkeypatch, first_fails):
    cache = captcha_static_cache.BehaviorStaticCache()
    waiting = Event()
    downloading = Event()
    finish_download = Event()

    class ObservedFuture(Future):
        def result(self):
            waiting.set()
            return super().result()

    def fetch(_url, timeout):
        downloading.set()
        assert finish_download.wait(5)
        if first_fails:
            raise requests.Timeout("mocked")
        return _upstream()

    download = Mock(side_effect=fetch)
    monkeypatch.setattr(captcha_static_cache, "Future", ObservedFuture)
    monkeypatch.setattr(requests, "get", download)

    def load():
        return cache.get("https://captcha.test", "loader.js", timeout=5).content

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(load)
        try:
            assert downloading.wait(5)
            second = pool.submit(load)
            assert waiting.wait(5)
        finally:
            finish_download.set()
        for result in (first, second):
            if first_fails:
                with pytest.raises(requests.Timeout):
                    result.result(timeout=5)
            else:
                assert result.result(timeout=5) == _upstream().content
    assert download.call_count == 1
    download.side_effect = None
    download.return_value = _upstream()
    assert load() == _upstream().content
    assert download.call_count == (2 if first_fails else 1)
