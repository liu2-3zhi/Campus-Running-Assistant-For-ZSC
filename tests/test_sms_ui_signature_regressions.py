import json
import re
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML_PATH = PROJECT_ROOT / "index.html"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


def _extract_js_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestSmsUiSignatureRegressions(unittest.TestCase):
    def test_normalize_sms_signature_wraps_full_width_brackets(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("function normalizeSmsSignature(signature)", source)
        normalize_source = _extract_js_section(
            source,
            "function normalizeSmsSignature(signature) {",
            "\n\nfunction getSmsSignatureInnerValue(signature) {",
        )

        node_script = f"""
const normalizeSource = {json.dumps(normalize_source)};
eval(normalizeSource);
const payload = [
  normalizeSmsSignature('跑步助手'),
  normalizeSmsSignature('【跑步助手】'),
  normalizeSmsSignature('  【跑步助手】  '),
  normalizeSmsSignature(''),
];
process.stdout.write(JSON.stringify(payload));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=False,
            check=False,
        )

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        if result.returncode != 0:
            self.fail(
                "Node SMS signature normalization regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload, ["【跑步助手】", "【跑步助手】", "【跑步助手】", ""])

    def test_get_sms_signature_inner_value_strips_fixed_brackets(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "function normalizeSmsSignature(signature) {",
            "\n\nasync function loadSMSConfig() {",
        )

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
eval(helperSource);
const payload = [
  getSmsSignatureInnerValue('【跑步助手】'),
  getSmsSignatureInnerValue('跑步助手'),
  getSmsSignatureInnerValue('  【跑步助手】  '),
  getSmsSignatureInnerValue(''),
];
process.stdout.write(JSON.stringify(payload));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=False,
            check=False,
        )

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        if result.returncode != 0:
            self.fail(
                "Node SMS signature inner value regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload, ["跑步助手", "跑步助手", "跑步助手", ""])

    def test_strip_sms_signature_fixed_brackets_removes_full_width_brackets_during_input(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "function normalizeSmsSignature(signature) {",
            "\n\nasync function loadSMSConfig() {",
        )

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
eval(helperSource);
const mockInput = {{
  value: '【跑步助手】',
  dataset: {{}},
  handlers: {{}},
  addEventListener(type, handler) {{
    this.handlers[type] = handler;
  }},
}};

bindSmsSignatureInputSanitization(mockInput);
const payload = [
  mockInput.value,
  stripSmsSignatureFixedBrackets('【跑步助手】'),
];

mockInput.value = '跑【步】助【手】';
mockInput.handlers.input();
payload.push(mockInput.value);

process.stdout.write(JSON.stringify(payload));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=False,
            check=False,
        )

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        if result.returncode != 0:
            self.fail(
                "Node SMS signature input sanitization regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload, ["跑步助手", "跑步助手", "跑步助手"])

    def test_sms_signature_inputs_bind_shared_sanitization_logic(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_sms_config_source = _extract_js_section(
            source,
            "async function loadSMSConfig() {",
            "\nasync function saveSMSConfig() {",
        )
        self.assertIn(
            'bindSmsSignatureInputSanitization($("sms-signature"));',
            load_sms_config_source,
        )

        mobile_load_sms_config_source = _extract_js_section(
            source,
            "async function mobileLoadSMSConfig() {",
            "\n\n/**\n * 移动端短信服务主开关变更处理",
        )
        self.assertIn(
            'bindSmsSignatureInputSanitization(document.getElementById("mobile-sms-signature"));',
            mobile_load_sms_config_source,
        )

        html_source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_sms_config_source = _extract_js_section(
            source,
            "async function loadSMSConfig() {",
            "\nasync function saveSMSConfig() {",
        )
        save_sms_config_source = _extract_js_section(
            source,
            "async function saveSMSConfig() {",
            "\nfunction handleSmsMainSwitchChange() {",
        )

        self.assertRegex(
            html_source,
            re.compile(
                r'<span[^>]*>【</span>\s*<input[^>]*id="sms-signature"[^>]*>\s*<span[^>]*>】</span>',
                re.MULTILINE | re.DOTALL,
            ),
        )
        self.assertIn(
            '$("sms-signature").value = getSmsSignatureInnerValue(result.config.signature || "")',
            load_sms_config_source,
        )
        self.assertIn(
            'signature: normalizeSmsSignature($("sms-signature").value),',
            save_sms_config_source,
        )

    def test_mobile_sms_signature_uses_fixed_brackets_in_markup_and_load_save(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        mobile_load_sms_config_source = _extract_js_section(
            source,
            "async function mobileLoadSMSConfig() {",
            "\n\n/**\n * 移动端短信服务主开关变更处理",
        )
        mobile_save_sms_config_source = _extract_js_section(
            source,
            "async function mobileSaveSMSConfig() {",
            "\n\n/**\n * 移动端查询短信余额",
        )

        self.assertIn('>【</span>', mobile_load_sms_config_source)
        self.assertIn('id="mobile-sms-signature" value="${getSmsSignatureInnerValue(config.signature || "")}"', mobile_load_sms_config_source)
        self.assertIn('>】</span>', mobile_load_sms_config_source)
        self.assertIn(
            'signature: normalizeSmsSignature(',
            mobile_save_sms_config_source,
        )


if __name__ == "__main__":
    unittest.main()
