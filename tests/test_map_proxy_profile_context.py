import json
import shutil
import subprocess
from functools import wraps
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g

import map_request_proxy
from config_adapter import JsonConfigAdapter
from map_request_proxy import register_map_proxy_routes


ACTOR_A = "11111111-1111-4111-8111-111111111111"
ACTOR_B = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def runtime(tmp_path):
    config = JsonConfigAdapter.__new__(JsonConfigAdapter)
    config._data = {"Map": {
        "frontend_proxy_enabled": "true", "frontend_config_id": "front-one", "backend_config_id": "back-two",
        "configs": [
            {"id": "front-one", "name": "Front", "provider": "amap", "js_key": "front-secret",
             "backend_page_origin": "https://front-one.test"},
            {"id": "back-two", "name": "Back", "provider": "amap", "js_key": "back-secret",
             "backend_page_origin": "https://back-two.test"},
        ],
    }}
    actor = {"name": "alice", "session": ACTOR_A}
    app = Flask(__name__)
    app.testing = True
    app.secret_key = "map-profile-context-test-only"

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            g.user = actor["name"]
            g.session_id = actor["session"]
            return view(*args, **kwargs)
        return wrapped

    transport = Mock(side_effect=lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "application/javascript"}, content=b"window.fixture = true;", close=Mock(),
    ))
    authorize = Mock(return_value=True)
    proxy = register_map_proxy_routes(
        app, login_required, lambda: config, authorize, transport=transport,
        tile_cache_dir=tmp_path,
        dns_resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    client = app.test_client()
    client.set_cookie("auth_token", "alice-token")

    def bootstrap(profile="front-one", token=None, selected_client=None):
        return (selected_client or client).post("/api/map-proxy/context", headers={
            "Origin": "http://localhost", "X-Session-ID": actor["session"],
        }, json={"map_config_id": profile, **({"context_token": token} if token is not None else {})})

    def resource(token, selected_client=None, **kwargs):
        return (selected_client or client).get(
            "/map-proxy/amap/https/webapi.amap.com/maps?key=front-secret&__map_context=" + token,
            **kwargs,
        )

    return SimpleNamespace(config=config, app=app, actor=actor, client=client, transport=transport,
                           proxy=proxy, bootstrap=bootstrap, resource=resource, authorize=authorize)


@pytest.mark.parametrize("change", ["selection", "origin", "global_origin"])
def test_initialized_context_pins_origin_while_new_page_uses_updated_configuration(runtime, change):
    if change == "global_origin":
        runtime.config.get("Map", "configs")[0]["backend_page_origin"] = ""
        runtime.config.set("Map", "backend_page_origin", "https://initial-global.test")
    old = runtime.bootstrap()
    assert old.status_code == 200
    token = old.json["context_token"]
    old_origin = "https://initial-global.test" if change == "global_origin" else "https://front-one.test"
    if change == "selection":
        runtime.config.set("Map", "frontend_config_id", "back-two")
        new_id, new_origin = "back-two", "https://back-two.test"
    elif change == "origin":
        runtime.config.get("Map", "configs")[0]["backend_page_origin"] = "https://edited-origin.test"
        new_id, new_origin = "front-one", "https://edited-origin.test"
    else:
        runtime.config.set("Map", "backend_page_origin", "https://edited-global.test")
        new_id, new_origin = "front-one", "https://edited-global.test"
    assert runtime.resource(token).status_code == 200
    assert runtime.transport.call_args.kwargs["headers"]["Referer"] == old_origin + "/"
    assert "__map_context" not in runtime.transport.call_args.args[1]
    renewed = runtime.bootstrap(token=token)
    assert renewed.status_code == 200
    assert renewed.json["context_token"] == token
    fresh = runtime.bootstrap(profile=new_id)
    assert fresh.status_code == 200
    fresh_token = fresh.json["context_token"]
    assert fresh_token != token
    assert runtime.resource(fresh_token).status_code == 200
    assert runtime.transport.call_args.kwargs["headers"]["Origin"] == new_origin
    # Shared authentication cookies across tabs do not replace the URL snapshot.
    assert runtime.resource(token).status_code == 200
    assert runtime.transport.call_args.kwargs["headers"]["Origin"] == old_origin
    assert "origin" not in json.dumps(old.json)
    assert "secret" not in old.headers["Set-Cookie"]


def test_stale_initial_selection_cannot_silently_pin_the_new_origin(runtime):
    runtime.config.set("Map", "frontend_config_id", "back-two")
    response = runtime.bootstrap(profile="front-one")
    assert response.status_code == 409
    assert "Set-Cookie" not in response.headers
    assert runtime.proxy._profile_contexts == {}


@pytest.mark.parametrize("changed_identity", ["username", "auth_token"])
def test_opaque_profile_token_cannot_cross_authenticated_identity(runtime, changed_identity):
    original = runtime.bootstrap().json["context_token"]
    other = runtime.app.test_client()
    other.set_cookie("auth_token", "bob-token" if changed_identity == "auth_token" else "alice-token")
    if changed_identity == "username":
        runtime.actor["name"] = "bob"
    if changed_identity == "session":
        runtime.actor["session"] = ACTOR_B
    assert runtime.bootstrap(selected_client=other).status_code == 200
    runtime.transport.reset_mock()
    assert runtime.resource(original, selected_client=other).status_code == 401
    assert runtime.bootstrap(token=original, selected_client=other).status_code == 409
    runtime.transport.assert_not_called()


def test_same_user_tabs_keep_their_original_actor_authorization_after_shared_cookie_changes(runtime):
    first = runtime.bootstrap().json["context_token"]
    runtime.actor["session"] = ACTOR_B
    second = runtime.bootstrap().json["context_token"]
    runtime.authorize.side_effect = lambda username, token, actor, require_view_all: actor == ACTOR_A
    assert runtime.resource(first).status_code == 200
    runtime.authorize.assert_called_with("alice", "alice-token", ACTOR_A, False)
    assert runtime.resource(second).status_code == 401
    runtime.authorize.side_effect = lambda username, token, actor, require_view_all: actor == ACTOR_B
    assert runtime.resource(first).status_code == 401
    assert runtime.resource(second).status_code == 200


def test_new_proxy_script_can_pin_legacy_config_before_first_profile_migration(runtime):
    del runtime.config._data["Map"]["configs"]
    runtime.config.set("Map", "frontend_config_id", "legacy-amap")
    runtime.config.set("Map", "backend_config_id", "legacy-amap")
    runtime.config.set("Map", "providers", {"amap": {"js_key": "legacy", "backend_page_origin": "https://legacy.test"}})
    response = runtime.client.post("/api/map-proxy/context", headers={
        "Origin": "http://localhost", "X-Session-ID": ACTOR_A,
    }, json={"pin_context": True})
    assert response.status_code == 200
    assert response.json["map_config_id"] == "legacy-amap"
    token = response.json["context_token"]
    runtime.config.set("Map", "providers", {"amap": {"backend_page_origin": "https://migrated.test"}})
    assert runtime.resource(token).status_code == 200
    assert runtime.transport.call_args.kwargs["headers"]["Origin"] == "https://legacy.test"


def test_profile_tokens_expire_and_cannot_fall_back_to_current_configuration(runtime):
    token = runtime.bootstrap().json["context_token"]
    runtime.proxy._profile_contexts[token]["expires_at"] = 0
    assert runtime.resource(token).status_code == 401
    assert runtime.bootstrap(token=token).status_code == 409
    runtime.transport.assert_not_called()


def test_profile_context_memory_is_bounded_and_evicts_oldest_context(runtime, monkeypatch):
    monkeypatch.setattr(map_request_proxy, "PROXY_PROFILE_CONTEXT_LIMIT", 2)
    tokens = [runtime.bootstrap().json["context_token"] for _ in range(3)]
    assert len(runtime.proxy._profile_contexts) == 2
    assert runtime.resource(tokens[0]).status_code == 401
    assert runtime.resource(tokens[-1]).status_code == 200


def test_context_renewal_cannot_rebind_an_existing_token_to_another_profile(runtime):
    token = runtime.bootstrap().json["context_token"]
    assert runtime.bootstrap(profile="back-two", token=token).status_code == 409
    assert runtime.resource(token).status_code == 200
    assert runtime.transport.call_args.kwargs["headers"]["Origin"] == "https://front-one.test"


def test_worker_and_css_resources_carry_context_to_automatic_subresources(runtime):
    token = runtime.bootstrap().json["context_token"]
    runtime.transport.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "application/javascript"},
        content=b"fetch('https://webapi.amap.com/dependency.js')", close=Mock(),
    )
    worker = runtime.resource(token, headers={"Sec-Fetch-Dest": "worker", "Sec-Fetch-Mode": "same-origin"})
    assert worker.status_code == 200
    assert '"contextToken": "' + token + '"' in worker.get_data(as_text=True)
    runtime.transport.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "text/css"},
        content=b".map{background:url(https://webapi.amap.com/icon.png?x=1)}", close=Mock(),
    )
    css = runtime.resource(token)
    assert css.status_code == 200
    assert "icon.png?x=1&__map_context=" + token in css.get_data(as_text=True)


def test_duplicate_profile_tokens_are_rejected_without_upstream_request(runtime):
    token = runtime.bootstrap().json["context_token"]
    response = runtime.client.get(
        "/map-proxy/amap/https/webapi.amap.com/maps?__map_context=" + token + "&__map_context=" + token,
    )
    assert response.status_code == 400
    runtime.transport.assert_not_called()


def test_module_worker_dependencies_pin_static_and_dynamic_imports_without_altering_sdk_base_urls(runtime):
    token = runtime.bootstrap().json["context_token"]
    source = """
import { value } from './parts/one.js';
import './side-effect.js';
export { other } from '../two.js';
export * from 'https://webapi.amap.com/shared.js';
const base = 'https://webapi.amap.com';
const code = "import './not-a-dependency.js'";
const re = /import('unchanged')/;
if (ready) /import('unchanged')/.test(text);
while (ready) /import('unchanged')/.test(text);
for (;;) /import('unchanged')/.test(text);
const division = call() / import('./division.js') / 2;
const object = { import(value) { return value; } };
class Loader { import(value, options) { return value; } }
const dynamic = import('./dynamic.js');
const computed = name => import('./chunks/' + name + '.js');
const template = `${import('./template.js')}`;
"""
    runtime.transport.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "application/javascript"}, content=source.encode(), close=Mock(),
    )
    response = runtime.client.get(
        "/map-proxy/amap/https/webapi.amap.com/deep/worker.js?__map_context=" + token,
        headers={"Sec-Fetch-Dest": "worker", "Sec-Fetch-Mode": "cors"},
    )
    assert response.status_code == 200
    rewritten = response.get_data(as_text=True)
    assert rewritten.startswith('import "http://localhost/scripts/map-request-proxy.js";')
    for path in ("deep/parts/one.js", "deep/side-effect.js", "two.js", "shared.js"):
        assert f"http://localhost/map-proxy/amap/https/webapi.amap.com/{path}?__map_context={token}&__map_module=1" in rewritten
    assert "const base = 'http://localhost/map-proxy/amap/https/webapi.amap.com';" in rewritten
    assert 'const code = "import \'./not-a-dependency.js\'";' in rewritten
    assert "const re = /import('unchanged')/;" in rewritten
    for condition in ("if (ready)", "while (ready)", "for (;;)"):
        assert condition + " /import('unchanged')/.test(text);" in rewritten
    assert "call() / import(self.ZXMapRequestProxy.rewriteModuleUrl('./division.js', import.meta.url)) / 2" in rewritten
    assert "const object = { import(value) { return value; } };" in rewritten
    assert "class Loader { import(value, options) { return value; } }" in rewritten
    assert "import(self.ZXMapRequestProxy.rewriteModuleUrl('./dynamic.js', import.meta.url))" in rewritten
    assert "import(self.ZXMapRequestProxy.rewriteModuleUrl('./chunks/' + name + '.js', import.meta.url))" in rewritten
    assert "`${import(self.ZXMapRequestProxy.rewriteModuleUrl('./template.js', import.meta.url))}`" in rewritten
    node = shutil.which("node")
    if node:
        parsed = subprocess.run([node, "--input-type=module", "--check"], input=rewritten,
                                text=True, capture_output=True, timeout=10)
        assert parsed.returncode == 0, parsed.stderr
    child = runtime.client.get(
        "/map-proxy/amap/https/webapi.amap.com/deep/parts/one.js?__map_context=" + token + "&__map_module=1",
        headers={"Sec-Fetch-Dest": "script", "Sec-Fetch-Mode": "cors"},
    )
    assert child.get_data(as_text=True).startswith('import "http://localhost/scripts/map-request-proxy.js";')
    assert "__map_module" not in runtime.transport.call_args.args[1]


def test_css_relative_imports_and_urls_pin_origin_without_rewriting_comments_or_external_urls(runtime):
    token = runtime.bootstrap().json["context_token"]
    source = """
@import './nested.css';
@import url(../shared.css);
.a { background: url(./icon.png?x=1); }
.b { background: url(https://webapi.amap.com/absolute.png); }
.c { background: url(data:image/png;base64,abc); mask: url(#symbol); }
.d { background: url(https://outside.test/image.png); }
.e::after { content: "url(./literal.png)"; }
/* url(./comment.png) */
"""
    runtime.transport.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "text/css"}, content=source.encode(), close=Mock(),
    )
    response = runtime.client.get("/map-proxy/amap/https/webapi.amap.com/css/style.css?__map_context=" + token)
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    for path in ("css/nested.css", "shared.css", "absolute.png"):
        assert f"http://localhost/map-proxy/amap/https/webapi.amap.com/{path}?__map_context={token}" in text
    assert f"css/icon.png?x=1&__map_context={token}" in text
    for untouched in ("url(data:image/png;base64,abc)", "url(#symbol)", "url(https://outside.test/image.png)",
                      'content: "url(./literal.png)"', "/* url(./comment.png) */"):
        assert untouched in text


def test_module_and_css_pin_urls_on_non_default_application_ports():
    token = "A" * 43
    app_origin = "http://127.0.0.1:4177"
    for source, rewrite in (
        ("import './child.js'; import 'https://webapi.amap.com/shared.js';", map_request_proxy._rewrite_module_specifiers),
        ("@import './nested.css'; .a{background:url(https://webapi.amap.com/icon.png)}", map_request_proxy._rewrite_css_specifiers),
    ):
        proxied = map_request_proxy._rewrite_vendor_urls(source, "amap", app_origin, "https://front.test")
        pinned = rewrite(proxied, "https://webapi.amap.com/deep/resource.js", app_origin, token)
        assert pinned.count("__map_context=" + token) == 2
        assert app_origin + "/map-proxy/amap/https/webapi.amap.com/" in pinned


def test_with_condition_regex_is_not_mistaken_for_dynamic_import_in_legacy_script():
    source = "with (scope) /import('unchanged')/.test(text); obj.if(ready) / value / 2;"
    assert map_request_proxy._rewrite_module_specifiers(
        source, "https://webapi.amap.com/worker.js", "http://localhost", "A" * 43,
    ) == source
