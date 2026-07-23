import re
import unittest
from pathlib import Path
from unittest import mock

import main as main_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
MAIN_PATH = PROJECT_ROOT / "main.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"
VUE_ADMIN_CAPTCHA_PATH = PROJECT_ROOT / "frontend" / "src" / "components" / "admin" / "AdminCaptcha.vue"


def _extract_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestCaptchaBehaviorGenerationChain(unittest.TestCase):
    def test_verify_captcha_calls_behavior_check2_with_saved_key(self):
        config = main_module._get_default_config()
        config.set("Captcha", "provider", "behavior")
        config.set("Captcha", "behavior_base_url", "http://127.0.0.1:8080/")
        config.set("Captcha", "behavior_api_key", "secret-key")
        config.set("Captcha", "behavior_type", "SLIDER")
        captured = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured.update(
                {
                    "url": url,
                    "params": params,
                    "headers": headers,
                    "timeout": timeout,
                }
            )
            return mock.Mock(status_code=200, text="true")

        with mock.patch.object(main_module, "_read_config_ini", return_value=config), \
             mock.patch("requests.get", side_effect=fake_get):
            passed, message = main_module.verify_captcha("captcha-id-1", "")

        self.assertTrue(passed)
        self.assertEqual(message, "")
        self.assertEqual(captured["url"], "http://127.0.0.1:8080/check2")
        self.assertEqual(captured["params"], {"id": "captcha-id-1"})
        self.assertEqual(captured["headers"], {"X-Captcha-Key": "secret-key"})
        self.assertEqual(captured["timeout"], 5)

    def test_legacy_html_auth_loads_behavior_captcha_through_backend_proxy(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_source = _extract_section(
            source,
            "async function loadCaptcha(formType) {",
            "\nfunction refreshCaptcha(formType) {",
        )

        self.assertIn("async function fetchRuntimeCaptchaProviderConfig()", source)
        self.assertIn('"/api/captcha/provider"', source)
        self.assertIn('"/api/captcha/behavior/loader.js"', source)
        self.assertIn("async function loadBehaviorCaptcha(formType)", source)
        self.assertIn("window.initTAC", source)
        self.assertIn('"/api/captcha/behavior/tac/"', source)
        self.assertIn('"/api/captcha/behavior/gen?type="', source)
        self.assertIn('validCaptchaUrl: "/api/captcha/behavior/check"', source)
        self.assertIn("if (await isBehaviorCaptchaProvider()) {", load_source)
        self.assertIn("return loadBehaviorCaptcha(formType);", load_source)

    def test_legacy_html_behavior_success_id_is_sent_to_business_apis(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        behavior_source = _extract_section(
            source,
            "async function loadBehaviorCaptcha(formType) {",
            "\nfunction refreshCaptcha(formType) {",
        )
        modal_source = _extract_section(
            source,
            "async function loadBehaviorCaptchaModal() {",
            "\nasync function loadCaptchaModal(requestedWidth) {",
        )

        self.assertRegex(
            behavior_source,
            r"const captchaId = res && res\.data \? res\.data\.id : \"\";",
        )
        self.assertIn("setCaptchaIdForForm(formType, captchaId);", behavior_source)
        self.assertIn(
            'setCaptchaInputValueForForm(formType, "behavior-verified");',
            behavior_source,
        )
        self.assertIn("captchaIds_modal = captchaId;", modal_source)
        self.assertIn('modalInput.value = "behavior-verified";', modal_source)
        self.assertIn("return loadBehaviorCaptchaModal();", source)

    def test_backend_behavior_proxy_matches_captcha_local_contract(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('@app.route("/api/captcha/provider", methods=["GET"])', source)
        self.assertIn('@app.route("/api/captcha/behavior/loader.js", methods=["GET"])', source)
        self.assertIn('@app.route("/api/captcha/behavior/gen", methods=["GET"])', source)
        self.assertIn('@app.route("/api/captcha/behavior/check", methods=["POST"])', source)
        self.assertIn('headers["X-Captcha-Key"] = conf["behavior_api_key"]', source)
        self.assertIn('params={"id": captcha_id}', source)
        self.assertIn('resp.text.strip().lower() == "true"', source)

        provider_source = _extract_section(
            source,
            'def get_captcha_provider():',
            '\n    def _behavior_base_or_error():',
        )
        self.assertNotIn("behavior_base_url", provider_source)
        self.assertNotIn("behavior_api_key", provider_source)

        verify_source = _extract_section(
            source,
            "def verify_captcha(captcha_id, user_input):",
            "\n\ndef _register_payment_verify_probe_route(app):",
        )
        self.assertIn('get_captcha_provider_config().get("provider") == "behavior"', verify_source)
        self.assertIn("return _verify_behavior_captcha(captcha_id.strip())", verify_source)

    def test_admin_test_generate_can_hit_unsaved_behavior_server_config(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        route_source = _extract_section(
            source,
            "def test_generate_captcha():",
            "\n    # ==============================================================================",
        )

        self.assertIn('str(data.get("provider") or "").strip().lower() == "behavior"', route_source)
        self.assertIn('str(data.get("behavior_base_url") or "").strip().rstrip("/")', route_source)
        self.assertIn('str(data.get("behavior_api_key") or "").strip()', route_source)
        self.assertIn('str(data.get("behavior_type") or "SLIDER").strip() or "SLIDER"', route_source)
        self.assertIn('headers["X-Captcha-Key"] = behavior_api_key', route_source)
        self.assertIn("_requests.get(", route_source)
        self.assertIn('f"{behavior_base_url}/gen"', route_source)
        self.assertIn('"provider": "behavior"', route_source)

    def test_legacy_admin_test_generate_sends_provider_fields_and_renders_behavior_result(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        html = INDEX_PATH.read_text(encoding="utf-8")
        pc_source = _extract_section(
            source,
            "async function testGenerateCaptcha() {",
            "\ndocument.addEventListener(\"DOMContentLoaded\", function () {",
        )
        mobile_source = _extract_section(
            source,
            "async function mobileTestCaptcha() {",
            "\n// 切换移动端验证码面板视图",
        )

        for section in (pc_source, mobile_source):
            self.assertIn("readCaptchaProviderForm", section)
            self.assertIn("...providerConfig", section)
            self.assertIn("renderCaptchaTestPreview", section)
            self.assertIn('result.provider === "behavior"', section)
        self.assertIn("captcha-preview-answer-label", html)
        self.assertIn("mobile-captcha-preview-answer-label", html)

    def test_vue_admin_test_generate_sends_provider_fields_and_renders_behavior_result(self):
        source = VUE_ADMIN_CAPTCHA_PATH.read_text(encoding="utf-8")
        test_source = _extract_section(
            source,
            "async function testGenerate() {",
            "\nasync function loadHistory() {",
        )

        self.assertIn("provider: provider.value", test_source)
        self.assertIn("behavior_base_url: behaviorBaseUrl.value.trim()", test_source)
        self.assertIn("behavior_api_key: behaviorApiKey.value", test_source)
        self.assertIn("behavior_type: behaviorType.value", test_source)
        self.assertIn("result.provider === 'behavior'", test_source)
        self.assertIn("previewProvider.value", source)
        self.assertIn("previewCaptcha.value", source)
        self.assertIn("验证码 ID", source)


if __name__ == "__main__":
    unittest.main()
