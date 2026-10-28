"""Isolated real authentication with inert business task objects.

All accounts, permission groups and tokens live under pytest's temporary path.
Production authentication boundaries and initialization projection are executed
without starting the application, browser pool, or any campus client.
"""

import ast
import configparser
from copy import deepcopy
import functools
import json
import logging
from pathlib import Path
import re
import threading
import time
from types import SimpleNamespace

from flask import Flask, g, jsonify, make_response, request
import pytest

import auth_system as auth_module
from guest_token_store import GuestTokenStore
import runtime_models


ROOT = Path(__file__).resolve().parents[1]
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
C = "33333333-3333-4333-8333-333333333333"
MAIN_TREE = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
WEB_TREE = ast.parse((ROOT / "web_server.py").read_text(encoding="utf-8"))


def load_production_function(name, namespace, *, authentication_only=False):
    tree = MAIN_TREE if any(isinstance(node, ast.FunctionDef) and node.name == name for node in MAIN_TREE.body) else WEB_TREE
    node = deepcopy(next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name))
    node.decorator_list = []
    if authentication_only:
        stop = next(index for index, statement in enumerate(node.body)
                    if isinstance(statement, ast.If) and ast.unparse(statement.test) == "session_id"
                    and any(isinstance(child, ast.Call) and ast.unparse(child.func).endswith("update_session_activity") for child in ast.walk(statement)))
        node.body = node.body[:stop + 1] + [ast.Return(value=ast.Constant(value="authorized"))]
    ast.fix_missing_locations(node)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "web_server.py"), "exec"), namespace)
    return namespace[name]


class InertBusinessApi:
    def __init__(self, username, group, task_index):
        self.auth_username, self.auth_group = username, group
        self.is_authenticated, self.is_guest, self.login_success = True, False, True
        self.execution_count = 7 + task_index
        self.background_task = SimpleNamespace(running=True, worker=object(), stop_event=threading.Event())
        self.task_state = {"is_running": True, "current_task_index": task_index,
                           "current_point_index": 2, "run_coords": [[113.1, 23.1], [113.2, 23.2]]}

    def get_initial_data(self):
        return {"success": True, "is_authenticated": self.is_authenticated,
                "auth_username": self.auth_username, "auth_group": self.auth_group,
                "task_status": deepcopy(self.task_state)}


@pytest.fixture
def isolated_business(tmp_path, monkeypatch):
    accounts = tmp_path / "system_accounts"
    accounts.mkdir()
    configuration = configparser.ConfigParser()
    configuration.read_dict({"Admin": {"super_admin": "isolated-supervisor"},
                             "Security": {"password_storage": "encrypted"}})
    config_file = tmp_path / "config.ini"
    with config_file.open("w", encoding="utf-8") as output:
        configuration.write(output)
    permissions_file = tmp_path / "permissions.json"
    permissions_file.write_text(json.dumps({"permission_groups": {
        "admin": {"is_system": False, "permissions": {"view_all_sessions": True, "view_map": True}},
        "user": {"is_system": False, "permissions": {"view_all_sessions": False, "view_map": True}},
        "super_admin": {"is_system": False, "permissions": {"view_all_sessions": True, "view_map": True}},
    }, "user_groups": {}}), encoding="utf-8")

    def read_configuration(path):
        loaded = configparser.ConfigParser()
        loaded.read(path, encoding="utf-8")
        return loaded

    def update_account_index(username, storage_key, action):
        path = accounts / "_index.json"
        entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entries[username] = storage_key
        path.write_text(json.dumps(entries), encoding="utf-8")

    runtime = SimpleNamespace(
        CONFIG_FILE=str(config_file), PERMISSIONS_FILE=str(permissions_file),
        SYSTEM_ACCOUNTS_DIR=str(accounts), LOGIN_LOG_FILE=str(tmp_path / "login.jsonl"),
        GuestTokenStore=GuestTokenStore, _create_config_ini=lambda: None,
        _read_config_ini=read_configuration, _update_system_accounts_index=update_account_index,
        request=request, jsonify=jsonify, make_response=make_response, g=g,
        ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
        _is_api_method_allowed=lambda method: method == "get_initial_data",
    )
    namespace = {"_main": lambda: runtime, "logging": logging, "functools": functools,
                 "time": time, "request": request, "args": None, "API_BLACKLIST_PREFIXES": (),
                 "SESSION_UUID_V4_PATTERN": re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$", re.I),
                 "PATH_SESSION_UUID_PATTERN": re.compile(r"/uuid=([a-f0-9-]{36})", re.I),
                 "MAX_USERNAME_LENGTH": 64, "USERNAME_PATTERN": re.compile(r"[A-Za-z0-9_-]+")}
    for name in ("normalize_session_uuid", "resolve_request_session_id", "_is_safe_auth_username"):
        setattr(runtime, name, load_production_function(name, namespace))
    monkeypatch.setattr(auth_module, "_main", lambda: runtime)
    monkeypatch.setattr(runtime_models, "_main", lambda: runtime)
    runtime.auth_system = auth_module.AuthSystem()
    runtime.token_manager = runtime_models.TokenManager(str(tmp_path / "tokens"))
    credentials = {}
    for username, group in (("isolated-manager", "admin"), ("isolated-second", "user"), ("isolated-third", "user")):
        password = "temporary-only-" + username
        assert runtime.auth_system.register_user(username, password, group=group)["success"]
        login = runtime.auth_system.authenticate(username, password, ip_address="127.0.0.1")
        assert login["success"] and login["group"] == group
        credentials[username] = runtime.token_manager.create_token(username)
    sessions = {A: InertBusinessApi("isolated-manager", "admin", 0),
                B: InertBusinessApi("isolated-second", "user", 1),
                C: InertBusinessApi("isolated-third", "user", 2)}
    namespace.update({"web_sessions": sessions, "web_sessions_lock": threading.RLock(),
                      "token_manager": runtime.token_manager, "auth_system": runtime.auth_system,
                      "session_activity": {}, "session_activity_lock": threading.Lock(),
                      "browsing_activity": {}, "browsing_activity_lock": threading.Lock(),
                      "admin_view_origin_activity": {}, "admin_view_origin_activity_lock": threading.Lock()})
    for name in ("update_session_activity", "touch_admin_view_origin_session",
                 "resolve_admin_origin_session_context", "resolve_admin_view_identity", "_verify_session_cookie_token"):
        setattr(runtime, name, load_production_function(name, namespace))
    project = load_production_function("_project_admin_view_context", namespace)
    authenticate = load_production_function("api_call", namespace, authentication_only=True)
    login_required = load_production_function("login_required", namespace)
    switch = load_production_function("auth_switch_session", namespace)
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.get("/api/get_initial_data")
    def initial_data():
        accepted = authenticate("get_initial_data")
        if accepted != "authorized":
            return accepted
        target = runtime.normalize_session_uuid(request.headers.get("X-Session-ID"))
        result = sessions[target].get_initial_data()
        projected = project(result, target, request.headers.get(runtime.ADMIN_ORIGIN_SESSION_HEADER, ""), request.cookies.get("auth_token"))
        assert "admin_view_context" not in result
        return jsonify(projected)

    app.add_url_rule("/auth/identity", "identity", login_required(lambda: jsonify({"user": g.user, "session_id": g.session_id})))
    app.add_url_rule("/auth/switch_session", "switch", switch, methods=["POST"])
    client = app.test_client()
    client.set_cookie("auth_token", credentials["isolated-manager"])
    return SimpleNamespace(runtime=runtime, sessions=sessions, namespace=namespace,
                           credentials=credentials, client=client, root=tmp_path)


def capture_business(environment):
    return {sid: {"api": api, "task": api.background_task, "worker": api.background_task.worker,
                  "login": (api.is_authenticated, api.is_guest, api.login_success, api.auth_username, api.auth_group),
                  "executions": api.execution_count, "state_object": api.task_state, "state": deepcopy(api.task_state)}
            for sid, api in environment.sessions.items() if sid in (B, C)}


def assert_business_unchanged(environment, before):
    for sid, previous in before.items():
        api = environment.sessions[sid]
        assert api is previous["api"] and api.background_task is previous["task"]
        assert api.background_task.worker is previous["worker"]
        assert not api.background_task.stop_event.is_set()
        assert api.background_task.running is True
        assert (api.is_authenticated, api.is_guest, api.login_success, api.auth_username, api.auth_group) == previous["login"]
        assert api.execution_count == previous["executions"]
        assert api.task_state is previous["state_object"] and api.task_state == previous["state"]


def token_files(environment):
    return {path.name: {"bytes": path.read_bytes(), "inode": path.stat().st_ino,
                        "data": json.loads(path.read_text(encoding="utf-8"))}
            for path in (environment.root / "tokens").glob("*.json")}


def assert_tokens_not_rotated(environment, before, *, allow_admin_refresh):
    after = token_files(environment)
    assert after.keys() == before.keys()
    for name, previous in before.items():
        assert after[name]["inode"] == previous["inode"]
        assert after[name]["data"]["token"] == previous["data"]["token"]
        assert after[name]["data"]["created_at"] == previous["data"]["created_at"]
        if not allow_admin_refresh or name != "isolated-manager.json":
            assert after[name]["bytes"] == previous["bytes"]


def headers_for(target):
    return {"X-Session-ID": target, **({"X-Admin-Origin-Session-ID": A} if target != A else {})}


@pytest.mark.parametrize("third_owned_by_admin", [False, True])
def test_real_authentication_chain_keeps_credentials_and_business_isolated(isolated_business, third_owned_by_admin):
    env = isolated_business
    if third_owned_by_admin:
        env.sessions[C].auth_username, env.sessions[C].auth_group = "isolated-manager", "admin"
    tasks_before, tokens_before = capture_business(env), token_files(env)
    for target in (A, B, C, A):
        response = env.client.get("/api/get_initial_data", headers=headers_for(target))
        assert response.status_code == 200 and response.headers.getlist("Set-Cookie") == []
        payload = response.get_json()
        assert payload["auth_username"] == env.sessions[target].auth_username
        if target != A:
            assert payload["admin_view_context"]["session_id"] == A
            assert payload["admin_view_context"]["auth_username"] == "isolated-manager"
        else:
            assert "admin_view_context" not in payload
        identity = env.client.get("/auth/identity", headers=headers_for(target))
        assert identity.status_code == 200
        assert identity.get_json() == {"user": "isolated-manager", "session_id": A}
        assert_tokens_not_rotated(env, tokens_before, allow_admin_refresh=True)
        assert_business_unchanged(env, tasks_before)
    assert env.namespace["admin_view_origin_activity"][A] > 0


@pytest.mark.parametrize("invalidity", ["removed", "expired", "revoked"])
@pytest.mark.parametrize("third_owned_by_admin", [False, True])
def test_real_origin_invalidation_never_logs_out_or_restarts_target(isolated_business, invalidity, third_owned_by_admin):
    env = isolated_business
    if third_owned_by_admin:
        env.sessions[C].auth_username, env.sessions[C].auth_group = "isolated-manager", "admin"
    tasks_before = capture_business(env)
    if invalidity == "removed":
        del env.sessions[A]
    elif invalidity == "expired":
        path = env.root / "tokens" / "isolated-manager.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["expires_at"] = 0
        path.write_text(json.dumps(record), encoding="utf-8")
    else:
        assert env.runtime.auth_system.set_user_custom_permission("isolated-manager", "view_all_sessions", False)["success"]
        assert env.runtime.auth_system.check_permission("isolated-manager", "view_all_sessions") is False
    tokens_before = token_files(env)
    for target in (B, C):
        for path in ("/api/get_initial_data", "/auth/identity"):
            response = env.client.get(path, headers=headers_for(target))
            assert response.status_code == 401 and response.get_json()["need_login"]
            assert response.headers.getlist("Set-Cookie") == []
    assert_tokens_not_rotated(env, tokens_before, allow_admin_refresh=False)
    assert_business_unchanged(env, tasks_before)
    env.client.set_cookie("auth_token", env.credentials["isolated-second"])
    own_response = env.client.get("/auth/identity", headers={"X-Session-ID": B})
    assert own_response.status_code == 200 and own_response.get_json()["user"] == "isolated-second"
    if not third_owned_by_admin:
        env.client.set_cookie("auth_token", env.credentials["isolated-third"])
        assert env.client.get("/auth/identity", headers={"X-Session-ID": C}).status_code == 200
    assert_business_unchanged(env, tasks_before)


@pytest.mark.parametrize("current", [A, B])
def test_real_cross_account_switch_rejects_before_token_cookie_or_task_mutation(isolated_business, current):
    env = isolated_business
    tasks_before, tokens_before = capture_business(env), token_files(env)
    response = env.client.post("/auth/switch_session", json={"target_session_id": C}, headers=headers_for(current))
    assert response.status_code == 403 and response.get_json()["success"] is False
    assert response.headers.getlist("Set-Cookie") == []
    assert_tokens_not_rotated(env, tokens_before, allow_admin_refresh=False)
    assert_business_unchanged(env, tasks_before)
