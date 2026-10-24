import ast
import configparser
import json
import logging
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask, jsonify, request

import api_runtime
import runtime_models
import theme_background_legacy
from theme_background_state import BACKGROUND_FILES_LOCK


WEB_SERVER_PATH = Path(__file__).resolve().parents[1] / "web_server.py"


def load_login_route(function_name, main_stub):
    module = ast.parse(WEB_SERVER_PATH.read_text(encoding="utf-8"))
    server = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "start_web_server")
    route = next(node for node in server.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
    route.decorator_list = []
    namespace = {
        "_main": lambda: main_stub,
        "configparser": configparser,
        "json": json,
        "logging": logging,
        "os": os,
        "threading": threading,
        "time": time,
        "uuid": uuid,
        "web_sessions": {},
        "web_sessions_lock": threading.Lock(),
        "args": None,
        "sms_verification_codes": {},
    }
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(WEB_SERVER_PATH), "exec"), namespace)
    return namespace[function_name]


class TestBackgroundRouteTransactions(unittest.TestCase):
    def test_consume_keeps_selection_and_binding_atomic_and_refreshes_after_unlock(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory) / "random_background_image"
            cache_dir.mkdir()
            image_path = cache_dir / "pc_selected.jpg"
            image_path.write_bytes(b"selected-image")
            image_url = "/theme-assets/random_background_image/pc_selected.jpg"
            cleanup_started = threading.Event()
            cleanup_completed = threading.Event()
            observed = {}
            workers = []
            main_stub = SimpleNamespace(
                RANDOM_BACKGROUND_IMAGE_DIR="random_background_image",
                _normalize_theme_background_target=theme_background_legacy._normalize_theme_background_target,
                _resolve_theme_background_binding_decision=theme_background_legacy._resolve_theme_background_binding_decision,
                _load_random_background_index=theme_background_legacy._load_random_background_index,
                _save_random_background_index=theme_background_legacy._save_random_background_index,
                _mark_random_background_file_expired=theme_background_legacy._mark_random_background_file_expired,
                _reset_random_background_file_expired=theme_background_legacy._reset_random_background_file_expired,
                _extract_background_image_url_from_value=theme_background_legacy._extract_background_image_url_from_value,
            )

            def cleanup():
                cleanup_started.set()
                runtime_models._cleanup_random_background_cache(str(cache_dir), 1)
                cleanup_completed.set()

            def get_theme_config(*args, **kwargs):
                worker = threading.Thread(target=cleanup)
                workers.append(worker)
                worker.start()
                self.assertTrue(cleanup_started.wait(1))
                observed["cleanup_blocked_during_selection"] = not cleanup_completed.wait(0.05)
                return {"global_environment_variables": {
                    "auth_login_container_background": f'url("{image_url}")',
                }}

            main_stub.auth_system = SimpleNamespace(get_theme_config=get_theme_config)
            api = api_runtime.Api.__new__(api_runtime.Api)
            api._web_session_id = "session-selecting"

            def refresh(image_types):
                self.assertFalse(BACKGROUND_FILES_LOCK._is_owned())
                self.assertEqual(image_types, ["pc"])

            api._refresh_default_theme_background_cache_async = Mock(side_effect=refresh)
            with patch.object(api_runtime, "_main", return_value=main_stub), patch.object(
                runtime_models, "_main", return_value=main_stub
            ), patch.object(api_runtime, "__file__", str(Path(directory) / "api_runtime.py")):
                result = api.mark_theme_background_consumed(image_url="")
                for worker in workers:
                    worker.join(2)
            self.assertTrue(observed["cleanup_blocked_during_selection"])
            self.assertTrue(cleanup_completed.is_set())
            self.assertTrue(image_path.exists())
            binding = theme_background_legacy._get_session_theme_background_binding(
                str(cache_dir), "session-selecting", "pc"
            )
            self.assertEqual(binding["image_url"], image_url)
            self.assertTrue(result["success"])
            api._refresh_default_theme_background_cache_async.assert_called_once()

    def _assert_empty_login_payload(self, function_name, route_path, request_data):
        for empty_bundle in (None, {}):
            with self.subTest(bundle=empty_bundle), tempfile.TemporaryDirectory() as directory:
                empty_payload = {
                    "bundle_id": "", "revision": 0,
                    "pc": {"image_url": ""}, "mobile": {"image_url": ""},
                }
                config = configparser.ConfigParser()
                config.add_section("Config")
                auth = Mock()
                auth.authenticate.return_value = {
                    "success": True, "auth_username": "alice", "group": "user", "is_guest": False,
                }
                auth.get_user_sessions.return_value = []
                auth.get_user_details.return_value = {"max_sessions": 1}
                auth.get_account_cancellation_status.return_value = None
                auth.get_user_group.return_value = "user"
                auth.get_user_file_path.return_value = str(Path(directory) / "missing-user.json")
                tokens = Mock()
                tokens.create_token.return_value = "test-token"
                tokens.detect_multi_device_login.return_value = []
                convert_payload = Mock(return_value=empty_payload)
                main_stub = SimpleNamespace(
                    CONFIG_FILE=str(Path(directory) / "config.json"),
                    _read_config_ini=Mock(return_value=config),
                    request=request,
                    jsonify=jsonify,
                    _normalize_phone=Mock(return_value=""),
                    _normalize_sms_code=Mock(return_value=""),
                    verify_captcha=Mock(return_value=(True, "")),
                    normalize_session_uuid=Mock(return_value=""),
                    _consume_two_fa_challenge=Mock(return_value=(True, "")),
                    auth_system=auth,
                    token_manager=tokens,
                    Api=Mock(side_effect=lambda args: SimpleNamespace()),
                    _bind_login_bundle_for_user=Mock(return_value=empty_bundle),
                    _bundle_to_public_payload=convert_payload,
                )
                app = Flask(__name__)
                app.testing = True
                app.add_url_rule(route_path, view_func=load_login_route(function_name, main_stub), methods=["POST"])
                response = app.test_client().post(route_path, json=request_data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json["success"])
                self.assertEqual(response.json.get("theme_background"), empty_payload)
                convert_payload.assert_called_once_with(empty_bundle)

    def test_password_login_returns_structured_empty_background(self):
        self._assert_empty_login_payload("auth_login", "/auth/login", {
            "auth_username": "alice", "auth_password": "test-password",
        })

    def test_two_factor_login_returns_structured_empty_background(self):
        self._assert_empty_login_payload("auth_2fa_verify_login", "/auth/2fa/verify_login", {
            "auth_username": "alice", "code": "123456", "challenge": "test-challenge",
        })


if __name__ == "__main__":
    unittest.main()
