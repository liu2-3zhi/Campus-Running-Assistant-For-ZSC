import tempfile
import unittest
from unittest import mock

from flask import Flask, jsonify, request as flask_request

import main as main_module


class TestHealthMonitoringTieredVisibility(unittest.TestCase):
    def test_health_helpers_exist(self):
        self.assertTrue(hasattr(main_module, "_aggregate_health_status"))
        self.assertTrue(hasattr(main_module, "_resolve_username_by_token"))
        self.assertTrue(hasattr(main_module, "_is_admin_health_view_from_token"))

    def test_core_error_should_escalate_to_error(self):
        components = [
            {"name": "running_core", "critical": True, "status": "error", "message": "broken"},
            {"name": "payment_system", "critical": False, "status": "ok", "message": "ok"},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok"},
        ]
        status, http_code, summary = main_module._aggregate_health_status(components)
        self.assertEqual(status, "error")
        self.assertEqual(http_code, 503)
        self.assertEqual(summary.get("critical_failed_count"), 1)

    def test_non_core_failure_should_be_degraded(self):
        components = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok"},
            {"name": "payment_system", "critical": False, "status": "degraded", "message": "missing config"},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok"},
        ]
        status, http_code, summary = main_module._aggregate_health_status(components)
        self.assertEqual(status, "degraded")
        self.assertEqual(http_code, 200)
        self.assertEqual(summary.get("non_critical_failed_count"), 1)

    def test_resolve_username_by_token(self):
        token = "test-token"
        fake_auth = mock.Mock()
        fake_auth.list_users.return_value = [
            {"auth_username": "u1"},
            {"auth_username": "admin"},
        ]

        fake_tm = mock.Mock()
        fake_tm.verify_token.side_effect = [
            (False, "token_mismatch"),
            (True, "valid"),
        ]

        with mock.patch.object(main_module, "auth_system", fake_auth, create=True), \
             mock.patch.object(main_module, "token_manager", fake_tm, create=True), \
             mock.patch.object(main_module, "_collect_auth_usernames_for_token_lookup", return_value=["u1", "admin"]):
            username = main_module._resolve_username_by_token(token)

        self.assertEqual(username, "admin")

    def test_resolve_username_by_token_uses_direct_token_index_first(self):
        token = "indexed-token"

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_tm = mock.Mock()
            fake_tm.tokens_dir = tmpdir
            fake_tm.verify_token.side_effect = AssertionError("should not scan all users")
            token_key = main_module._build_health_token_index_key(token)

            with mock.patch.object(main_module, "token_manager", fake_tm, create=True), \
                 mock.patch.object(main_module, "_read_health_token_index", return_value={token_key: "admin"}, create=True), \
                 mock.patch.object(main_module, "_validate_cached_health_token_owner", return_value=True, create=True), \
                 mock.patch.object(main_module, "_write_health_token_index", create=True):
                username = main_module._resolve_username_by_token(token)

        self.assertEqual(username, "admin")

    def test_write_health_token_index_should_preserve_prehashed_keys(self):
        token = "sensitive-token"

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_tm = mock.Mock()
            fake_tm.tokens_dir = tmpdir
            token_key = main_module._build_health_token_index_key(token)

            with mock.patch.object(main_module, "token_manager", fake_tm, create=True):
                main_module._write_health_token_index({token_key: "admin"})
                persisted_index = main_module._read_health_token_index()

        self.assertEqual(persisted_index, {token_key: "admin"})


    def test_health_route_returns_summary_for_public_and_details_for_admin(self):
        app = Flask(__name__)

        @app.route("/health")
        def _health_proxy():
            uptime_seconds = 12
            response_time_ms = 3.5
            payload = {
                "status": "degraded",
                "uptime_seconds": uptime_seconds,
                "response_time_ms": response_time_ms,
                "uptime_formatted": "12秒",
            }
            components = [
                {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
                {"name": "payment_system", "critical": False, "status": "degraded", "message": "bad", "checks": {}},
                {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
            ]
            summary = {"critical_failed_count": 0, "non_critical_failed_count": 1}
            is_admin = main_module._is_admin_health_view_from_token(flask_request.cookies.get("auth_token"))
            payload.update(main_module._build_health_comment_fields(is_admin=is_admin))
            if is_admin:
                payload["components"] = {c["name"]: c for c in components}
                payload["summary"] = summary
            return jsonify(payload), 200

        with app.test_client() as client:
            public_response = client.get("/health")
            public_payload = public_response.get_json()
            self.assertIn("_comment", public_payload)
            self.assertNotIn("components", public_payload)
            self.assertNotIn("summary", public_payload)

            client.set_cookie("auth_token", "admin-token")
            with mock.patch.object(main_module, "_is_admin_health_view_from_token", return_value=True):
                admin_response = client.get("/health")
            admin_payload = admin_response.get_json()
            self.assertIn("components", admin_payload)
            self.assertIn("summary", admin_payload)
            self.assertIn("_meta_zh", admin_payload)

    def test_register_health_route_exposes_public_and_admin_views(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "degraded", "message": "bad", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]

        fake_auth = mock.Mock()
        fake_auth.get_user_group.return_value = "admin"

        with mock.patch.object(main_module, "server_start_time", 0, create=True), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "auth_system", fake_auth, create=True), \
             mock.patch.object(main_module, "_resolve_username_by_token", return_value="admin", create=True), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                public_response = client.get("/health")
                public_payload = public_response.get_json()
                self.assertEqual(public_response.status_code, 200)
                self.assertEqual(public_payload.get("status"), "degraded")
                self.assertIn("_comment", public_payload)
                self.assertNotIn("components", public_payload)
                self.assertNotIn("summary", public_payload)

                client.set_cookie("auth_token", "admin-token")
                admin_response = client.get("/health")
                admin_payload = admin_response.get_json()
                self.assertEqual(admin_response.status_code, 200)
                self.assertIn("components", admin_payload)
                self.assertIn("summary", admin_payload)
                self.assertIn("_meta_zh", admin_payload)
                fake_auth.get_user_group.assert_called_with("admin")

    def test_register_health_route_hides_details_for_non_admin_token(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "degraded", "message": "bad", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]

        fake_auth = mock.Mock()
        fake_auth.get_user_group.return_value = "user"

        with mock.patch.object(main_module, "server_start_time", 0, create=True), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "auth_system", fake_auth, create=True), \
             mock.patch.object(main_module, "_resolve_username_by_token", return_value="normal-user", create=True), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                client.set_cookie("auth_token", "user-token")
                response = client.get("/health")
                payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload.get("status"), "degraded")
        self.assertIn("_comment", payload)
        self.assertNotIn("components", payload)
        self.assertNotIn("summary", payload)
        self.assertNotIn("_meta_zh", payload)
        fake_auth.get_user_group.assert_called_with("normal-user")

    def test_register_health_route_hides_details_for_invalid_token(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "degraded", "message": "bad", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]

        fake_auth = mock.Mock()

        with mock.patch.object(main_module, "server_start_time", 0, create=True), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "auth_system", fake_auth, create=True), \
             mock.patch.object(main_module, "_resolve_username_by_token", return_value=None, create=True), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                client.set_cookie("auth_token", "invalid-token")
                response = client.get("/health")
                payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("_comment", payload)
        self.assertNotIn("components", payload)
        self.assertNotIn("summary", payload)
        self.assertNotIn("_meta_zh", payload)
        fake_auth.get_user_group.assert_not_called()


    def test_register_health_route_returns_503_when_core_component_errors(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "error", "message": "broken", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]

        with mock.patch.object(main_module, "server_start_time", 0, create=True), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                response = client.get("/health")
                payload = response.get_json()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload.get("status"), "error")

        with mock.patch.object(main_module, "background_task_manager", mock.Mock(tasks={}, lock=mock.MagicMock()), create=True), \
             mock.patch.object(main_module, "chrome_pool", mock.Mock(_contexts={}), create=True), \
             mock.patch.object(main_module, "web_sessions", [], create=True):
            component = main_module._check_running_core_health()

        self.assertEqual(component.get("status"), "error")
        self.assertIn("会话", component.get("message", ""))

    def test_payment_should_be_degraded_when_qr_cache_index_is_corrupted(self):
        cfg = main_module.configparser.ConfigParser(strict=False)
        cfg.optionxform = str
        cfg["Payment_Settings"] = {"require_payment": "true"}
        cfg["Rainbow_YiPay"] = {
            "host": "https://example.com",
            "pid": "1001",
            "key": "secret",
            "payment_timeout_minutes": "900",
        }

        with mock.patch.object(main_module, "_safe_get_config_for_health", return_value=cfg), \
             mock.patch.object(main_module, "PAYMENT_ORDERS_DIR", ".", create=True), \
             mock.patch.object(main_module, "_load_qr_cache_index", side_effect=ValueError("bad json"), create=True):
            component = main_module._check_payment_system_health()

        self.assertEqual(component.get("status"), "degraded")
        self.assertIn("二维码", component.get("message", ""))

    def test_sms_should_be_degraded_when_rate_limit_config_invalid(self):
        cfg = main_module.configparser.ConfigParser(strict=False)
        cfg.optionxform = str
        cfg["Features"] = {"enable_sms_service": "true"}
        cfg["SMS_Service_SMSBao"] = {
            "username": "u",
            "api_key": "k",
            "signature": "sig",
            "template_register": "tpl",
            "send_interval_seconds": "abc",
            "code_expire_minutes": "-1",
        }

        with mock.patch.object(main_module, "_safe_get_config_for_health", return_value=cfg), \
             mock.patch.dict(main_module.__dict__, {"sms_verification_codes": {}}, clear=False):
            component = main_module._check_sms_system_health()

        self.assertEqual(component.get("status"), "degraded")
        self.assertIn("限流", component.get("message", ""))


if __name__ == "__main__":
    unittest.main()
