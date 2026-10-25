import ast
import datetime
import json
import logging
import os
import re
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request

from guest_token_store import GuestTokenStore


WEB_SERVER_PATH = Path(__file__).resolve().parents[1] / "web_server.py"
USER_SESSION = "11111111-1111-4111-8111-111111111111"
GUEST_SESSION = "22222222-2222-4222-8222-222222222222"
ORIGIN_SESSION = "33333333-3333-4333-8333-333333333333"


class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 25, 12, 0, tzinfo=tz)


def load_reminder_routes(main_stub, sessions):
    module = ast.parse(WEB_SERVER_PATH.read_text(encoding="utf-8"))
    server = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "start_web_server"
    )
    names = {"get_reminders_list", "add_reminder", "update_reminder", "check_reminders", "_is_time_in_range"}
    routes = [
        node for node in server.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    for route in routes:
        route.decorator_list = []
    namespace = {
        "_main": lambda: main_stub,
        "datetime": SimpleNamespace(datetime=FixedDateTime),
        "json": json,
        "logging": logging,
        "os": os,
        "re": re,
        "threading": threading,
        "time": time,
        "uuid": uuid,
        "web_sessions": sessions,
        "web_sessions_lock": threading.Lock(),
    }
    exec(compile(ast.Module(body=routes, type_ignores=[]), str(WEB_SERVER_PATH), "exec"), namespace)
    return namespace


class TestReminderAccessControl(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        old_directory = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, old_directory)
        self.sessions = {
            USER_SESSION: SimpleNamespace(is_authenticated=True, auth_username="alice", is_guest=False),
            GUEST_SESSION: SimpleNamespace(is_authenticated=True, auth_username="guest", is_guest=True),
        }
        self.guest_store = GuestTokenStore(str(Path(self.directory.name) / "guest_tokens"))
        self.guest_token = self.guest_store.create(GUEST_SESSION)
        self.guest_record = {
            "is_guest": True,
            "auth_username": "guest",
            "last_accessed": time.time(),
        }

        def admin_origin(target, origin, token):
            if target == GUEST_SESSION and origin == ORIGIN_SESSION and token == "admin-token":
                return {"username": "admin", "session_id": ORIGIN_SESSION}
            return None

        def admin_view(target, token, owner):
            if target == GUEST_SESSION and token == "admin-token":
                return {"username": "admin", "session_id": ORIGIN_SESSION}
            return None

        self.main_stub = SimpleNamespace(
            request=request,
            jsonify=jsonify,
            normalize_session_uuid=lambda value: str(value or "").strip(),
            ADMIN_ORIGIN_SESSION_HEADER="X-Admin-Origin-Session-ID",
            resolve_admin_origin_session_context=admin_origin,
            resolve_admin_view_identity=admin_view,
            _verify_session_cookie_token=lambda sid, username, token: (
                sid == USER_SESSION and username == "alice" and token == "valid-alice"
            ),
            _load_guest_session_record=lambda sid: self.guest_record if sid == GUEST_SESSION else None,
            _get_guest_config=lambda config: {"guest_session_inactivity_timeout": 300},
            _read_config_ini=lambda path: None,
            _get_default_config=lambda: {},
            CONFIG_FILE="unused.ini",
            _touch_guest_session=lambda sid: True,
            token_manager=SimpleNamespace(guest_store=self.guest_store),
            auth_system=SimpleNamespace(check_permission=lambda username, permission: True),
        )
        routes = load_reminder_routes(self.main_stub, self.sessions)
        self.app = Flask(__name__)
        self.app.testing = True
        for path, method, name in (
            ("/api/reminders/check", "GET", "check_reminders"),
            ("/api/reminders/add", "POST", "add_reminder"),
            ("/api/reminders/update", "POST", "update_reminder"),
        ):
            self.app.add_url_rule(path, endpoint=name, view_func=routes[name], methods=[method])

    def write_reminders(self, reminders):
        Path("reminders.json").write_text(
            json.dumps({"reminders": reminders}, ensure_ascii=False), encoding="utf-8"
        )

    def read_reminders(self):
        return json.loads(Path("reminders.json").read_text(encoding="utf-8"))["reminders"]

    def check(self, session_id="", token="", origin=""):
        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id
        if origin:
            headers["X-Admin-Origin-Session-ID"] = origin
        with self.app.test_client() as client:
            if token:
                client.set_cookie("auth_token", token)
            return client.get("/api/reminders/check", headers=headers)

    def post(self, path, payload):
        with self.app.test_client() as client:
            return client.post(path, json=payload, headers={"X-Session-ID": USER_SESSION})

    def test_check_rejects_missing_session_and_unverified_tokens(self):
        self.write_reminders([self.reminder("visible", allow_guest_view=True)])
        for session_id, token in (
            ("", ""),
            ("unknown", "valid-alice"),
            (USER_SESSION, ""),
            (USER_SESSION, "bad-token"),
            (GUEST_SESSION, ""),
            (GUEST_SESSION, "bad-token"),
        ):
            with self.subTest(session_id=session_id, token=token):
                response = self.check(session_id, token)
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.json["success"])
                self.assertNotIn("reminders", response.json)

    def test_check_filters_guest_without_hiding_reminders_from_users_or_admin_view(self):
        self.write_reminders([
            self.reminder("guest-visible", allow_guest_view=True),
            self.reminder("user-only", allow_guest_view=False),
            self.reminder("legacy"),
            self.reminder("disabled", allow_guest_view=True, enabled=False),
        ])
        user = self.check(USER_SESSION, "valid-alice")
        guest = self.check(GUEST_SESSION, self.guest_token)
        admin = self.check(GUEST_SESSION, "admin-token", ORIGIN_SESSION)
        self.assertEqual(user.status_code, 200)
        self.assertEqual({item["id"] for item in user.json["reminders"]}, {"guest-visible", "user-only", "legacy"})
        self.assertEqual(guest.status_code, 200)
        self.assertEqual([item["id"] for item in guest.json["reminders"]], ["guest-visible"])
        self.assertEqual(admin.status_code, 200)
        self.assertEqual({item["id"] for item in admin.json["reminders"]}, {"guest-visible", "user-only", "legacy"})

    def test_check_rejects_expired_guest_session(self):
        self.write_reminders([self.reminder("guest-visible", allow_guest_view=True)])
        self.guest_record["last_accessed"] = time.time() - 1000
        response = self.check(GUEST_SESSION, self.guest_token)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("reminders", response.json)

    def test_guest_marked_session_cannot_use_regular_user_token(self):
        self.write_reminders([self.reminder("user-only")])
        self.sessions[USER_SESSION].is_guest = True
        response = self.check(USER_SESSION, "valid-alice")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("reminders", response.json)

    def test_add_defaults_to_user_only_and_rejects_non_boolean_flag(self):
        required = {"title": "提醒", "message": "内容", "start_time": "00:00", "end_time": "23:59"}
        default_response = self.post("/api/reminders/add", required)
        explicit_response = self.post("/api/reminders/add", {**required, "allow_guest_view": True})
        invalid_response = self.post("/api/reminders/add", {**required, "allow_guest_view": "false"})
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(explicit_response.status_code, 200)
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual([item["allow_guest_view"] for item in self.read_reminders()], [False, True])

    def test_partial_update_preserves_flag_and_rejects_non_boolean_value(self):
        self.write_reminders([self.reminder("existing")])
        partial = self.post("/api/reminders/update", {"id": "existing", "enabled": False})
        self.assertEqual(partial.status_code, 200)
        self.assertNotIn("allow_guest_view", self.read_reminders()[0])
        enabled = self.post("/api/reminders/update", {"id": "existing", "allow_guest_view": True})
        invalid = self.post("/api/reminders/update", {"id": "existing", "allow_guest_view": "false"})
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(invalid.status_code, 400)
        self.assertIs(self.read_reminders()[0]["allow_guest_view"], True)

    @staticmethod
    def reminder(reminder_id, **fields):
        return {
            "id": reminder_id,
            "title": reminder_id,
            "message": "content",
            "start_time": "00:00",
            "end_time": "23:59",
            "enabled": True,
            **fields,
        }


if __name__ == "__main__":
    unittest.main()
