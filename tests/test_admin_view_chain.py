import ast
import functools
import logging
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from flask import Flask, jsonify, make_response, request


SOURCE = Path(__file__).resolve().parents[1] / "web_server.py"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def load_function(name, runtime, sessions=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        raise AssertionError(f"missing production function {name}")
    node.decorator_list = []
    namespace = {
        "_main": lambda: runtime,
        "web_sessions": sessions or {},
        "web_sessions_lock": threading.Lock(),
        "logging": logging,
        "functools": functools,
        "args": None,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


def load_api_authentication(runtime, sessions):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "api_call")
    node.decorator_list = []
    # Run the real authentication boundary without dispatching unrelated business code.
    stop = next(i for i, statement in enumerate(node.body)
                if isinstance(statement, ast.If) and ast.unparse(statement.test) == "session_id"
                and any(isinstance(child, ast.Call) and ast.unparse(child.func).endswith("update_session_activity")
                        for child in ast.walk(statement)))
    node.body = node.body[:stop + 1] + [ast.Return(value=ast.Constant(value="authorized"))]
    ast.fix_missing_locations(node)
    namespace = {"_main": lambda: runtime, "web_sessions": sessions,
                 "web_sessions_lock": threading.Lock(), "logging": logging,
                 "API_BLACKLIST_PREFIXES": (), "args": None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["api_call"]


def load_origin_resolver(runtime, sessions, touch):
    source = SOURCE.with_name("main.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "resolve_admin_origin_session_context")
    namespace = {
        "normalize_session_uuid": runtime.normalize_session_uuid,
        "web_sessions": sessions, "web_sessions_lock": threading.Lock(),
        "token_manager": runtime.token_manager, "auth_system": runtime.auth_system,
        "touch_admin_view_origin_session": touch, "logging": logging,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[node.name]


class AdminViewChainTests(unittest.TestCase):
    def request_runtime(self, origin_valid=True):
        target = SimpleNamespace(is_authenticated=True, is_guest=False,
                                 auth_username="manager", auth_group="admin")
        sessions = {B: target, A: target}
        touch_origin = mock.Mock()

        def resolve_origin(target_id, origin_id, token, **_kwargs):
            if origin_valid and target_id == B and origin_id == A and token == "cookie":
                touch_origin(origin_id)
                return {"session_id": A, "username": "manager", "group": "admin", "api_instance": target}
            return None

        runtime = SimpleNamespace(
            request=request, jsonify=jsonify, g=SimpleNamespace(),
            ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
            normalize_session_uuid=lambda value: value,
            _is_api_method_allowed=lambda _method: True,
            _is_safe_auth_username=lambda _username: True,
            token_manager=SimpleNamespace(verify_token=mock.Mock(return_value=(True, "valid")), refresh_token=mock.Mock()),
            _verify_session_cookie_token=mock.Mock(return_value=True),
            resolve_admin_origin_session_context=mock.Mock(side_effect=resolve_origin),
            resolve_admin_view_identity=mock.Mock(return_value={"username": "manager"}),
            auth_system=SimpleNamespace(get_account_cancellation_status=mock.Mock(return_value=None)),
            update_session_activity=mock.Mock(),
        )
        return runtime, sessions, touch_origin

    def test_every_same_owner_business_request_validates_and_keeps_origin_active(self):
        runtime, sessions, touch = self.request_runtime()
        runtime.auth_system.check_permission = mock.Mock(return_value=True)
        runtime.resolve_admin_origin_session_context = mock.Mock(wraps=load_origin_resolver(runtime, sessions, touch))
        authenticate = load_api_authentication(runtime, sessions)
        app = Flask(__name__)
        with app.test_request_context("/api/get_run_status", headers={
            "X-Session-ID": B, "X-Admin-Origin-Session-ID": A, "Cookie": "auth_token=cookie",
        }):
            for _ in range(2):
                self.assertEqual(authenticate("get_run_status"), "authorized")
        self.assertEqual(touch.call_count, 2)
        self.assertEqual(runtime.resolve_admin_origin_session_context.call_count, 2)

    def test_expired_origin_and_revoked_permission_reject_even_valid_owner_cookie(self):
        for expired, revoked in ((True, False), (False, True)):
            with self.subTest(expired=expired, revoked=revoked):
                runtime, sessions, touch = self.request_runtime()
                runtime.token_manager.verify_token.side_effect = lambda _user, sid, _token: (
                    (False, "token_expired") if sid == A and expired else (True, "valid")
                )
                runtime.auth_system.check_permission = mock.Mock(return_value=not revoked)
                runtime.resolve_admin_origin_session_context = mock.Mock(wraps=load_origin_resolver(runtime, sessions, touch))
                authenticate = load_api_authentication(runtime, sessions)
                app = Flask(__name__)
                with app.test_request_context("/api/get_run_status", headers={
                    "X-Session-ID": B, "X-Admin-Origin-Session-ID": A, "Cookie": "auth_token=cookie",
                }):
                    response = make_response(authenticate("get_run_status"))
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.get_json()["need_login"])
                runtime.token_manager.verify_token.assert_called_once_with("manager", A, "cookie")
                runtime.resolve_admin_view_identity.assert_not_called()
                runtime.token_manager.refresh_token.assert_not_called()
                touch.assert_not_called()

    def test_invalid_explicit_origin_never_falls_back_to_target_identity(self):
        for entry in ("api_call", "login_required", "admin_required"):
            with self.subTest(entry=entry):
                runtime, sessions, touch = self.request_runtime(origin_valid=False)
                if entry == "api_call":
                    invoke = lambda: load_api_authentication(runtime, sessions)("get_run_status")
                else:
                    invoke = load_function(entry, runtime, sessions)(lambda: "authorized")
                app = Flask(__name__)
                with app.test_request_context("/api/get_run_status", headers={
                    "X-Session-ID": B, "X-Admin-Origin-Session-ID": A, "Cookie": "auth_token=cookie",
                }):
                    response = make_response(invoke())
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.get_json()["need_login"])
                self.assertEqual(response.headers.getlist("Set-Cookie"), [])
                runtime.resolve_admin_view_identity.assert_not_called()
                runtime.token_manager.verify_token.assert_not_called()
                runtime._verify_session_cookie_token.assert_not_called()
                touch.assert_not_called()

    def test_verified_actor_projection_does_not_replace_target_identity(self):
        runtime = SimpleNamespace(resolve_admin_origin_session_context=mock.Mock(return_value={
            "session_id": A, "username": "manager", "group": "admin",
        }))
        project = load_function("_project_admin_view_context", runtime)
        original = {"success": True, "auth_username": "viewed", "auth_group": "user"}
        result = project(original, B, A, "cookie")
        self.assertEqual(result["auth_username"], "viewed")
        self.assertEqual(result["admin_view_context"]["auth_username"], "manager")
        self.assertNotIn("admin_view_context", original)
        runtime.resolve_admin_origin_session_context.assert_called_once_with(B, A, "cookie")

    def test_same_owner_target_still_verifies_explicit_origin(self):
        runtime = SimpleNamespace(resolve_admin_origin_session_context=mock.Mock(return_value=None))
        project = load_function("_project_admin_view_context", runtime)
        result = project({"success": True, "auth_username": "manager"}, B, A, "cookie")
        runtime.resolve_admin_origin_session_context.assert_called_once_with(B, A, "cookie")
        self.assertNotIn("admin_view_context", result)

    def switch(self, target_owner, target_in_memory=True, viewed_current=False):
        app = Flask(__name__)
        current = SimpleNamespace(is_authenticated=True, is_guest=False,
                                  auth_username="viewed" if viewed_current else "manager")
        target = SimpleNamespace(is_authenticated=True, is_guest=False, auth_username=target_owner)
        sessions = {A: current}
        if target_in_memory:
            sessions[B] = target
        tokens = SimpleNamespace(
            verify_token=mock.Mock(return_value=(not viewed_current, "valid")),
            create_token=mock.Mock(return_value="new-token"),
        )
        runtime = SimpleNamespace(
            resolve_request_session_id=lambda: A,
            normalize_session_uuid=lambda value: value,
            request=request, jsonify=jsonify, make_response=make_response,
            token_manager=tokens,
            resolve_admin_view_identity=mock.Mock(return_value={"username": "manager"}),
            load_session_state=mock.Mock(return_value={"auth_username": target_owner}),
            Api=mock.Mock(return_value=SimpleNamespace()),
            restore_session_to_api_instance=mock.Mock(),
        )
        switch = load_function("auth_switch_session", runtime, sessions)
        with app.test_request_context("/auth/switch_session", method="POST",
                                      json={"target_session_id": B}, headers={"Cookie": "auth_token=cookie"}):
            response = make_response(switch())
        return response, tokens, target, sessions

    def test_cross_owner_switch_rejected_before_token_or_cookie_mutation(self):
        for persisted in (False, True):
            with self.subTest(persisted=persisted):
                response, tokens, target, sessions = self.switch("other", not persisted)
                self.assertEqual(response.status_code, 403)
                tokens.create_token.assert_not_called()
                self.assertEqual(response.headers.getlist("Set-Cookie"), [])
                self.assertEqual(target.auth_username, "other")

    def test_viewer_identity_controls_owner_guard_and_own_switch_still_works(self):
        response, tokens, _, _ = self.switch("manager", viewed_current=True)
        self.assertEqual(response.status_code, 200)
        tokens.create_token.assert_called_once_with("manager", B)


if __name__ == "__main__":
    unittest.main()
