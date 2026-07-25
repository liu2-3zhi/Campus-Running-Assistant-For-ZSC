import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"
MAIN_PATH = PROJECT_ROOT / "main.py"
VUE_ADMIN_CAPTCHA_PATH = PROJECT_ROOT / "frontend" / "src" / "components" / "admin" / "AdminCaptcha.vue"
VUE_AUTH_PANEL_PATH = PROJECT_ROOT / "frontend" / "src" / "components" / "login" / "AuthPanel.vue"


def _extract_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestCaptchaProviderHtmlUi(unittest.TestCase):
    def test_pc_and_mobile_captcha_panels_expose_server_provider_controls(self):
        html = INDEX_PATH.read_text(encoding="utf-8")
        pc_panel = _extract_section(
            html,
            'id="admin-captcha-panel_modal"',
            'id="admin-captcha-history-panel_modal"',
        )
        mobile_panel = _extract_section(
            html,
            'id="mobile-multi-admin-captcha-panel"',
            'id="mobile-multi-admin-reminders-panel"',
        )

        for panel, prefix in ((pc_panel, ""), (mobile_panel, "mobile-")):
            self.assertIn("验证码服务器", panel)
            self.assertIn(f'id="{prefix}captcha-provider-image"', panel)
            self.assertIn(f'id="{prefix}captcha-provider-behavior"', panel)
            self.assertIn(f'id="{prefix}captcha-behavior-fields"', panel)
            self.assertIn(f'id="{prefix}captcha-behavior-base-url"', panel)
            self.assertIn(f'id="{prefix}captcha-behavior-api-key"', panel)
            self.assertIn(f'id="{prefix}captcha-behavior-type"', panel)

    def test_captcha_provider_switch_shows_only_matching_input_fields(self):
        html = INDEX_PATH.read_text(encoding="utf-8")
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        for fields_id in ("captcha-image-fields", "mobile-captcha-image-fields"):
            fields_tag_match = re.search(
                rf'<div\s+id="{fields_id}"\s+class="([^"]*)"',
                html,
            )
            self.assertIsNotNone(fields_tag_match, fields_id)
            class_names = fields_tag_match.group(1).split()
            self.assertNotIn("hidden", class_names, fields_id)

        for fields_id in ("captcha-behavior-fields", "mobile-captcha-behavior-fields"):
            fields_tag_match = re.search(
                rf'<div\s+id="{fields_id}"\s+class="([^"]*)"',
                html,
            )
            self.assertIsNotNone(fields_tag_match, fields_id)
            class_names = fields_tag_match.group(1).split()
            self.assertIn("hidden", class_names, fields_id)

        self.assertIn('serverFields.classList.toggle("hidden", provider !== "behavior");', source)
        self.assertIn('imageFields.classList.toggle("hidden", provider === "behavior");', source)

    def test_local_captcha_fields_have_white_parameter_containers(self):
        html = INDEX_PATH.read_text(encoding="utf-8")

        for fields_id in ("captcha-image-fields", "mobile-captcha-image-fields"):
            fields_tag_match = re.search(
                rf'<div\s+id="{fields_id}"\s+class="([^"]*)"',
                html,
            )
            self.assertIsNotNone(fields_tag_match, fields_id)
            class_names = fields_tag_match.group(1).split()
            for expected_class in ("bg-white", "border", "border-slate-200", "rounded-lg"):
                self.assertIn(expected_class, class_names, fields_id)
            self.assertTrue(
                any(name.startswith("p-") for name in class_names),
                f"{fields_id} should include padding on the white container",
            )

    def test_captcha_provider_switch_updates_card_state_and_test_button_text(self):
        html = INDEX_PATH.read_text(encoding="utf-8")
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertGreaterEqual(html.count('data-captcha-provider-card="image"'), 2)
        self.assertGreaterEqual(html.count('data-captcha-provider-card="behavior"'), 2)
        self.assertIn("captcha-provider-segmented", html)
        self.assertNotIn("grid grid-cols-1 sm:grid-cols-2 gap-3", html)
        self.assertIn("function setCaptchaProviderCardStates", source)
        self.assertIn('radio.closest("[data-captcha-provider-card]")', source)
        self.assertIn('card.classList.toggle("border-sky-400", active);', source)
        self.assertIn("function setCaptchaProviderActionText", source)
        self.assertIn('provider === "behavior" ? "🔄 测试服务器" : "🔄 测试生成"', source)

    def test_behavior_captcha_types_follow_captcha_local_api_contract(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        options_source = _extract_section(
            source,
            "const BEHAVIOR_CAPTCHA_TYPES = [",
            "];",
        )

        expected_api_types = {
            "SLIDER",
            "SLIDER2",
            "ROTATE",
            "CONCAT",
            "WORD_IMAGE_CLICK",
            "GESTURE",
            "CURVE",
            "CURVE2",
            "CURVE3",
            "WORD_ORDER_CLICK",
            "POW",
            "MATH",
            "ICON_CLICK",
            "DIRECTION_CLICK",
            "RANDOM",
        }
        actual_values = set(re.findall(r'value: "([A-Z0-9_]+)"', options_source))
        self.assertEqual(expected_api_types, actual_values)
        self.assertIsNone(re.search(r"[A-Za-z]:[/\\]Users[/\\]", source))

    def test_captcha_provider_sources_do_not_embed_local_reference_paths(self):
        api_doc_name = "API" + ".md"
        repo_segment_pattern = "Documents" + r"[/\\]" + "GitHub"
        sources = {
            "index.html": INDEX_PATH.read_text(encoding="utf-8"),
            "scripts/main.new.js": SCRIPT_PATH.read_text(encoding="utf-8"),
            "main.py": MAIN_PATH.read_text(encoding="utf-8"),
            "AdminCaptcha.vue": VUE_ADMIN_CAPTCHA_PATH.read_text(encoding="utf-8"),
            "AuthPanel.vue": VUE_AUTH_PANEL_PATH.read_text(encoding="utf-8"),
        }

        for name, source_text in sources.items():
            self.assertIsNone(re.search(r"[A-Za-z]:[/\\]Users[/\\]", source_text), name)
            self.assertIsNone(re.search(repo_segment_pattern, source_text), name)
            self.assertNotIn(api_doc_name, source_text, name)
            self.assertIsNone(
                re.search(r"captcha-local[^\n]*(API\s*文档|API\.md)", source_text),
                name,
            )

    def test_captcha_provider_fields_load_save_and_sync_between_pc_and_mobile(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_source = _extract_section(
            source,
            "async function loadCaptchaSettings(ShowSwalFire = true) {",
            "\nasync function saveCaptchaSettings() {",
        )
        save_source = _extract_section(
            source,
            "async function saveCaptchaSettings() {",
            "\nasync function testGenerateCaptcha() {",
        )
        mobile_update_source = _extract_section(
            source,
            "function mobileUpdateCaptchaForm(settings) {",
            "\n/**\n * 保存移动端验证码设置",
        )
        mobile_save_source = _extract_section(
            source,
            "async function mobileSaveCaptchaSettings() {",
            "\n/**\n * 移动端测试验证码生成",
        )

        self.assertIn('applyCaptchaProviderSettings(settings, "");', load_source)
        self.assertIn('applyCaptchaProviderSettings(settings, "mobile-");', load_source)
        self.assertIn('const providerConfig = readCaptchaProviderForm("");', save_source)
        self.assertIn("...providerConfig", save_source)
        self.assertIn("behavior_base_url", save_source)
        self.assertIn("behavior_api_key", save_source)
        self.assertIn("behavior_type", save_source)

        self.assertIn('applyCaptchaProviderSettings(settings, "mobile-");', mobile_update_source)
        self.assertIn('const providerConfig = readCaptchaProviderForm("mobile-");', mobile_save_source)
        self.assertIn("...providerConfig", mobile_save_source)
        self.assertIn('applyCaptchaProviderSettings(providerConfig, "");', mobile_save_source)


if __name__ == "__main__":
    unittest.main()
