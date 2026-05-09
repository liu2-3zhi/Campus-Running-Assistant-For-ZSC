import functools
import tempfile
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest import mock

from flask import Flask, g, jsonify, request

import main as main_module
from main import (
    _build_sms_verification_content,
    _normalize_sms_signature,
    _register_sms_routes,
)


class TestSmsTemplateSignatureRegressions(unittest.TestCase):
    def _build_test_app(self):
        app = Flask(__name__)
        session_store = {}

        def login_required(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                session_id = request.headers.get("X-Session-ID", "")
                api_instance = session_store.get(session_id)
                is_authenticated = getattr(api_instance, "is_authenticated", False)
                auth_username = getattr(api_instance, "auth_username", None)
                if not is_authenticated or not api_instance or not auth_username:
                    return jsonify({"success": False, "message": "未登录或会话无效"}), 401
                g.user = auth_username
                g.api_instance = api_instance
                g.session_id = session_id
                return f(*args, **kwargs)

            return decorated_function

        _register_sms_routes(app, login_required)
        return app, session_store

    def _register_authenticated_session(self, session_store, username="admin"):
        session_id = f"sms-test-session-{self._testMethodName}"
        session_store[session_id] = SimpleNamespace(
            is_authenticated=True,
            auth_username=username,
        )
        self.addCleanup(session_store.pop, session_id, None)
        return session_id

    def _make_sms_config(self, *, signature="跑步助手", enable_sms_service=True):
        config = main_module._get_default_config()
        config.set("Features", "enable_sms_service", str(enable_sms_service).lower())
        config.set("SMS_Service_SMSBao", "username", "demo-user")
        config.set("SMS_Service_SMSBao", "api_key", "demo-key")
        config.set("SMS_Service_SMSBao", "signature", signature)
        config.set(
            "SMS_Service_SMSBao",
            "template_register",
            "您的验证码是：{code}，{minutes}分钟内有效。",
        )
        config.set("SMS_Service_SMSBao", "code_expire_minutes", "5")
        return config

    def test_test_sms_content_uses_template_and_no_test_marker(self):
        content = _build_sms_verification_content(
            signature="跑步助手",
            template="您的验证码是：{code}，{minutes}分钟内有效。",
            code="551143",
            code_expire_minutes=5,
        )

        self.assertEqual(content, "【跑步助手】您的验证码是：551143，5分钟内有效。")
        self.assertNotIn("测试短信", content)

    def test_sms_signature_is_always_wrapped_in_full_width_brackets(self):
        self.assertEqual(_normalize_sms_signature("跑步助手"), "【跑步助手】")
        self.assertEqual(_normalize_sms_signature("【跑步助手】"), "【跑步助手】")
        self.assertEqual(_normalize_sms_signature("  【跑步助手】  "), "【跑步助手】")

    def test_verify_captcha_is_available_at_module_scope(self):
        self.assertTrue(callable(getattr(main_module, "verify_captcha", None)))

    def test_smsbao_error_message_includes_phone_format_failure_code(self):
        self.assertEqual(main_module._get_smsbao_error_message("51"), "手机号码不正确")

    def test_send_code_route_uses_template_with_normalized_signature(self):
        config = self._make_sms_config(signature="跑步助手")
        captured_urls = []
        app, _ = self._build_test_app()

        def fake_urlopen(url, timeout=10):
            captured_urls.append(url)
            return mock.Mock(read=mock.Mock(return_value=b"0"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "verify_captcha", return_value=(True, ""), create=True), \
             mock.patch.object(main_module.random, "randint", side_effect=[5, 5, 1, 1, 4, 3]), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "register",
                        "captcha": "123456",
                        "captcha_id": "captcha-login",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(captured_urls), 1)
        content = urllib.parse.parse_qs(urllib.parse.urlparse(captured_urls[0]).query)["c"][0]
        self.assertEqual(content, "【跑步助手】您的验证码是：551143，5分钟内有效。")
        self.assertNotIn("测试短信", content)

    def test_send_code_route_uses_module_scope_verify_captcha(self):
        config = self._make_sms_config(signature="跑步助手")
        app, _ = self._build_test_app()

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True), \
             mock.patch.object(main_module, "verify_captcha", return_value=(False, "图形验证码错误")) as verify_mock:
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "login",
                        "captcha": "bad-code",
                        "captcha_id": "captcha-login",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "图形验证码错误")
        verify_mock.assert_called_once_with("captcha-login", "bad-code")

    def test_send_code_route_preserves_smsbao_error_details(self):
        config = self._make_sms_config(signature="跑步助手")
        app, _ = self._build_test_app()

        def fake_urlopen(url, timeout=10):
            return mock.Mock(read=mock.Mock(return_value=b"43"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "verify_captcha", return_value=(True, ""), create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "register",
                        "captcha": "123456",
                        "captcha_id": "captcha-login",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "发送失败：IP地址限制")
        self.assertEqual(payload["error_code"], "43")

    def test_send_code_route_hides_internal_exception_details(self):
        config = self._make_sms_config(signature="跑步助手")
        app, _ = self._build_test_app()

        def fake_urlopen(url, timeout=10):
            raise RuntimeError("socket timeout")

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "verify_captcha", return_value=(True, ""), create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "register",
                        "captcha": "123456",
                        "captcha_id": "captcha-login",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "短信服务暂时不可用，请稍后重试")
        self.assertNotIn("socket timeout", payload["message"])

    def test_send_code_route_logs_smsbao_error_details(self):
        config = self._make_sms_config(signature="跑步助手")
        app, _ = self._build_test_app()

        def fake_urlopen(url, timeout=10):
            return mock.Mock(read=mock.Mock(return_value=b"43"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "verify_captcha", return_value=(True, ""), create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True), \
             mock.patch.object(main_module.logging, "error") as log_error:
            with app.test_client() as client:
                client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "register",
                        "captcha": "123456",
                        "captcha_id": "captcha-login",
                    },
                )

        log_error.assert_called_once()
        self.assertIn("[SMS] 验证码发送失败", log_error.call_args.args[0])
        self.assertIn("43", log_error.call_args.args[0])

    def test_send_code_route_enforces_send_interval_from_config(self):
        config = self._make_sms_config(signature="跑步助手")
        config.set("SMS_Service_SMSBao", "send_interval_seconds", "180")
        captured_urls = []
        app, _ = self._build_test_app()

        def fake_urlopen(url, timeout=10):
            captured_urls.append(url)
            return mock.Mock(read=mock.Mock(return_value=b"0"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "verify_captcha", return_value=(True, ""), create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir), \
             mock.patch.object(main_module, "cache", {"sms_last_send_13800000001": 1000.0}, create=True), \
             mock.patch.object(main_module, "sms_verification_codes", {}, create=True), \
             mock.patch.object(main_module, "sms_extended_once_keys", set(), create=True), \
             mock.patch.object(main_module.time, "time", return_value=1120.0):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/send_code",
                    json={
                        "phone": "13800000001",
                        "scene": "register",
                        "captcha": "123456",
                        "captcha_id": "captcha-login",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "发送过于频繁，请60秒后再试")
        self.assertEqual(payload["retry_after"], 60)
        self.assertEqual(captured_urls, [])

    def test_test_send_route_uses_template_with_normalized_signature(self):
        config = self._make_sms_config(signature="跑步助手")
        captured_urls = []
        app, session_store = self._build_test_app()
        session_id = self._register_authenticated_session(session_store)
        fake_auth_system = mock.Mock()
        fake_auth_system.get_user_group.return_value = "admin"

        def fake_urlopen(url, timeout=10):
            captured_urls.append(url)
            return mock.Mock(read=mock.Mock(return_value=b"0"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "auth_system", fake_auth_system, create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/test_send",
                    headers={"X-Session-ID": session_id},
                    json={"phone": "13800000002", "code": "551143"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(captured_urls), 1)
        content = urllib.parse.parse_qs(urllib.parse.urlparse(captured_urls[0]).query)["c"][0]
        self.assertEqual(content, "【跑步助手】您的验证码是：551143，5分钟内有效。")
        self.assertNotIn("测试短信", content)

    def test_test_send_route_preserves_smsbao_error_details(self):
        config = self._make_sms_config(signature="跑步助手")
        app, session_store = self._build_test_app()
        session_id = self._register_authenticated_session(session_store)
        fake_auth_system = mock.Mock()
        fake_auth_system.get_user_group.return_value = "admin"

        def fake_urlopen(url, timeout=10):
            return mock.Mock(read=mock.Mock(return_value=b"43"))

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "auth_system", fake_auth_system, create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/test_send",
                    headers={"X-Session-ID": session_id},
                    json={"phone": "13800000002", "code": "551143"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "发送失败：IP地址限制")
        self.assertEqual(payload["error_code"], "43")

    def test_test_send_route_hides_internal_exception_details(self):
        config = self._make_sms_config(signature="跑步助手")
        app, session_store = self._build_test_app()
        session_id = self._register_authenticated_session(session_store)
        fake_auth_system = mock.Mock()
        fake_auth_system.get_user_group.return_value = "admin"

        def fake_urlopen(url, timeout=10):
            raise RuntimeError("socket timeout")

        with tempfile.TemporaryDirectory() as temp_log_dir, \
             mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "auth_system", fake_auth_system, create=True), \
             mock.patch.object(main_module.urllib, "request", SimpleNamespace(urlopen=fake_urlopen), create=True), \
             mock.patch.object(main_module, "LOGIN_LOGS_DIR", temp_log_dir):
            with app.test_client() as client:
                response = client.post(
                    "/api/sms/test_send",
                    headers={"X-Session-ID": session_id},
                    json={"phone": "13800000002", "code": "551143"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["message"], "短信服务暂时不可用，请稍后重试")
        self.assertNotIn("socket timeout", payload["message"])

    def test_get_sms_config_normalizes_signature_in_response(self):
        config = self._make_sms_config(signature="跑步助手")
        app, session_store = self._build_test_app()
        session_id = self._register_authenticated_session(session_store)
        fake_auth_system = mock.Mock()
        fake_auth_system.check_permission.return_value = True

        with mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "auth_system", fake_auth_system, create=True):
            with app.test_client() as client:
                response = client.get(
                    "/api/admin/sms/config",
                    headers={"X-Session-ID": session_id},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["config"]["signature"], "【跑步助手】")

    def test_save_sms_config_normalizes_signature_before_persisting(self):
        config = self._make_sms_config(signature="旧签名")
        app, session_store = self._build_test_app()
        session_id = self._register_authenticated_session(session_store)
        fake_auth_system = mock.Mock()
        fake_auth_system.check_permission.return_value = True
        persisted = {}

        def capture_config(config_obj, filepath):
            persisted["signature"] = config_obj.get("SMS_Service_SMSBao", "signature")

        with mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch.object(main_module, "_write_config_with_comments", side_effect=capture_config), \
             mock.patch.object(main_module, "auth_system", fake_auth_system, create=True):
            with app.test_client() as client:
                response = client.post(
                    "/api/admin/sms/config",
                    headers={"X-Session-ID": session_id},
                    json={"signature": "  跑步助手  "},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(persisted["signature"], "【跑步助手】")


if __name__ == "__main__":
    unittest.main()
