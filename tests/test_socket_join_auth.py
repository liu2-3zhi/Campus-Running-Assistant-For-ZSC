import ast
import json
import logging
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import uuid


class SocketJoinAuthenticationTests(unittest.TestCase):
    target_id = "11111111-1111-4111-8111-111111111111"
    origin_id = "22222222-2222-4222-8222-222222222222"

    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "web_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        handler = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "handle_join"
        )
        handler.decorator_list = []
        cls.handler_code = compile(
            ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[])),
            str(source), "exec",
        )

    def setUp(self):
        self.api = SimpleNamespace(
            auth_username="admin-owner", is_authenticated=True, is_guest=False
        )
        self.runtime = SimpleNamespace(
            web_sessions={self.target_id: self.api},
            web_sessions_lock=threading.Lock(),
            request=SimpleNamespace(cookies={"auth_token": "ordinary-token"}, sid="client-1"),
            normalize_session_uuid=self.normalize_uuid,
            _verify_session_cookie_token=Mock(return_value=False),
            resolve_admin_origin_session_context=Mock(return_value=None),
            resolve_admin_view_identity=Mock(return_value=None),
            join_room=Mock(), emit=Mock(),
        )
        namespace = {
            "_main": lambda: self.runtime, "json": json,
            "logging": logging, "request": self.runtime.request,
        }
        exec(self.handler_code, namespace)
        self.handle_join = namespace["handle_join"]

    @staticmethod
    def normalize_uuid(value):
        try:
            parsed = uuid.UUID(str(value or "").strip())
            return str(parsed) if parsed.version == 4 else ""
        except (ValueError, AttributeError):
            return ""

    def assert_denied(self):
        self.runtime.join_room.assert_not_called()
        for call in self.runtime.emit.call_args_list:
            self.assertNotEqual(call.kwargs.get("room"), self.target_id)
            self.assertNotEqual(call.kwargs.get("to"), self.target_id)

    def test_unknown_and_unauthenticated_sessions_are_denied(self):
        for api in (None, SimpleNamespace(
            auth_username="admin-owner", is_authenticated=False, is_guest=False
        ), SimpleNamespace(auth_username="", is_authenticated=True, is_guest=False)):
            with self.subTest(api=api):
                self.runtime.web_sessions = {} if api is None else {self.target_id: api}
                self.handle_join({"session_id": self.target_id})
                self.assert_denied()

    def test_ordinary_cookie_cannot_join_an_admin_uuid(self):
        self.handle_join({"session_id": self.target_id})
        self.runtime._verify_session_cookie_token.assert_called_once_with(
            self.target_id, "admin-owner", "ordinary-token"
        )
        self.runtime.resolve_admin_view_identity.assert_called_once_with(
            self.target_id, "ordinary-token", "admin-owner"
        )
        self.assert_denied()

    def test_owner_with_verified_cookie_can_join(self):
        self.runtime._verify_session_cookie_token.return_value = True
        self.handle_join(json.dumps({"session_id": self.target_id}))
        self.runtime.join_room.assert_called_once_with(self.target_id)
        self.runtime.resolve_admin_view_identity.assert_not_called()

    def test_explicit_admin_origin_is_verified(self):
        self.runtime.resolve_admin_origin_session_context.return_value = {"username": "admin"}
        self.handle_join({
            "session_id": self.target_id, "admin_origin_session_id": self.origin_id
        })
        self.runtime.resolve_admin_origin_session_context.assert_called_once_with(
            self.target_id, self.origin_id, "ordinary-token"
        )
        self.runtime._verify_session_cookie_token.assert_not_called()
        self.runtime.join_room.assert_called_once_with(self.target_id)

    def test_invalid_explicit_origin_does_not_fall_back_to_owner(self):
        self.runtime._verify_session_cookie_token.return_value = True
        self.handle_join({
            "session_id": self.target_id, "admin_origin_session_id": "invalid"
        })
        self.runtime._verify_session_cookie_token.assert_not_called()
        self.assert_denied()

    def test_failed_explicit_origin_does_not_fall_back_to_admin_identity(self):
        self.runtime.resolve_admin_view_identity.return_value = {"username": "admin"}
        self.handle_join({
            "session_id": self.target_id, "admin_origin_session_id": self.origin_id
        })
        self.runtime.resolve_admin_view_identity.assert_not_called()
        self.assert_denied()

    def test_admin_view_without_origin_remains_compatible(self):
        self.runtime.resolve_admin_view_identity.return_value = {"username": "admin"}
        self.handle_join({"session_id": self.target_id})
        self.runtime.join_room.assert_called_once_with(self.target_id)

    def test_active_guest_can_join_without_an_account_cookie(self):
        self.api.auth_username = "guest"
        self.api.is_guest = True
        self.runtime.request.cookies = {}
        self.handle_join({"session_id": self.target_id})
        self.runtime.join_room.assert_called_once_with(self.target_id)
        self.runtime._verify_session_cookie_token.assert_not_called()

    def test_guest_flag_cannot_bypass_authenticated_owner_validation(self):
        self.api.is_guest = True
        self.handle_join({"session_id": self.target_id})
        self.assert_denied()

    def test_authentication_errors_fail_closed(self):
        self.runtime._verify_session_cookie_token.side_effect = RuntimeError("unavailable")
        self.handle_join({"session_id": self.target_id})
        self.assert_denied()


if __name__ == "__main__":
    unittest.main()
