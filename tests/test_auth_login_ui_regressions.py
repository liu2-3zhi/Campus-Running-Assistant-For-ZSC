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


class TestAuthLoginUiRegressions(unittest.TestCase):
    def test_pc_personal_info_contains_auth_username_field_and_binding(self):
        html_source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        script_source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_personal_info_source = _extract_js_section(
            script_source,
            "async function loadPersonalInfo() {",
            "\n\nasync function updateAvatar()",
        )

        self.assertIn('id="profile-auth-username"', html_source)
        self.assertIn("profile-auth-username", load_personal_info_source)
        self.assertRegex(load_personal_info_source, re.compile(r"user\.auth_username"))

    def test_mobile_personal_info_contains_auth_username_field_and_binding(self):
        html_source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        script_source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_mobile_profile_source = _extract_js_section(
            script_source,
            "async function loadMobileUnifiedProfile() {",
            "\n\n// 【移动端统一面板】处理头像文件选择",
        )

        self.assertIn('id="mobile-unified-profile-auth-username"', html_source)
        self.assertIn("mobile-unified-profile-auth-username", load_mobile_profile_source)
        self.assertRegex(load_mobile_profile_source, re.compile(r"data\.auth_username"))

    def test_login_mode_toggle_buttons_do_not_submit_forms(self):
        html_source = INDEX_HTML_PATH.read_text(encoding="utf-8")

        def assert_button_uses_button_type(button_id: str):
            pattern = re.compile(
                rf'<button[^>]*(?:type="button"[^>]*id="{re.escape(button_id)}"|id="{re.escape(button_id)}"[^>]*type="button")[^>]*>',
                re.MULTILINE | re.DOTALL,
            )
            self.assertRegex(html_source, pattern)

        assert_button_uses_button_type("auth-login-username-btn")
        assert_button_uses_button_type("auth-login-phone-btn")
        assert_button_uses_button_type("mobile-login-username-btn")
        assert_button_uses_button_type("mobile-login-phone-btn")

    def test_password_validation_failure_refreshes_login_captcha(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        handle_auth_login_source = _extract_js_section(
            source,
            "async function handleAuthLogin(isMobile_use = false) {",
            "\n\n/**\n * 处理手机号未注册时跳转到注册页面",
        )

        node_script = f"""
const handleAuthLoginSource = {json.dumps(handle_auth_login_source)};
const elements = new Map();
const refreshCalls = [];
const swalCalls = [];

globalThis.console = {{ log() {{}}, info() {{}}, warn() {{}}, error() {{}} }};

function createElement(id, value = '') {{
  const classes = new Set();
  return {{
    id,
    value,
    textContent: '',
    dataset: {{}},
    disabled: false,
    innerHTML: '',
    classList: {{
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
    }},
  }};
}}

function $(id) {{
  return elements.get(id);
}}

const authLoginBtn = createElement('auth-login-btn');
authLoginBtn.textContent = 'login';
const authUsername = createElement('auth-username', 'demo-user');
const authPassword = createElement('auth-password', '');
const authSmsCode = createElement('auth-sms-code', '');
const authLoginCaptcha = createElement('auth-login-captcha', '123456');
const authLoginPhoneBtn = createElement('auth-login-phone-btn');
const authSmsSection = createElement('auth-sms-section');
authSmsSection.classList.add('hidden');

[
  authLoginBtn,
  authUsername,
  authPassword,
  authSmsCode,
  authLoginCaptcha,
  authLoginPhoneBtn,
  authSmsSection,
].forEach((element) => elements.set(element.id, element));

globalThis.document = {{
  getElementById(id) {{
    return elements.get(id) || null;
  }},
}};
globalThis.Swal = {{
  fire(payload) {{
    swalCalls.push(payload);
    return Promise.resolve({{ isConfirmed: false }});
  }},
}};
globalThis.capturePreLoginBackgroundSnapshot = () => {{}};
globalThis.validateInput = () => ({{ valid: true }});
globalThis.refreshCaptcha = (formType) => refreshCalls.push(formType);
globalThis.setButtonLoading = () => {{}};
globalThis.showButtonError = () => {{}};
globalThis.showButtonSuccess = () => {{}};
globalThis.showAuthSuccess = () => {{}};
globalThis.syncThemeFromServer = async () => {{}};
globalThis.initializeInlineAdminPanel = async () => {{}};
globalThis.showSessionPicker = () => {{}};
globalThis.showMobileSessionPicker = () => {{}};
globalThis.logMessage_Info = () => {{}};
globalThis.logMessage_Error = () => {{}};
globalThis.escapeHtml = (value) => String(value);
globalThis.fetch = async () => {{ throw new Error('fetch should not be called on validation failure'); }};
globalThis.window = {{}};
globalThis.currentUserData = {{}};
globalThis.isMobileMode = false;
globalThis.sessionUUID = '';
globalThis.captchaIds_login = 'captcha-login';
globalThis.captchaIds_mobile_login = 'captcha-mobile';
globalThis.themeBackgroundLoginSyncInFlight = false;

eval(handleAuthLoginSource);

(async () => {{
  await handleAuthLogin(false);
  process.stdout.write(JSON.stringify({{ refreshCalls, swalCalls, captchaValue: authLoginCaptcha.value }}));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
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
                "Node auth login validation regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload["refreshCalls"], ["login"])
        self.assertEqual(payload["captchaValue"], "")
        self.assertEqual(payload["swalCalls"][0]["text"], "请输入密码")

    def test_auth_login_uuid_resolver_does_not_generate_new_business_session(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        resolver_source = _extract_js_section(
            source,
            "function isUsableClientSessionUUID(value) {",
            "\n\nfunction shouldSuppressLoggedOutElsewhereNotice",
        )

        node_script = f"""
const resolverSource = {json.dumps(resolver_source)};
let sessionUUID = null;
let generated = false;
function generateUUID() {{
  generated = true;
  return '22222222-2222-4222-8222-222222222222';
}}
function getUUIDFromURL() {{
  return '';
}}
eval(resolverSource);
const resolved = ensureAuthLoginSessionUUID();
process.stdout.write(JSON.stringify({{ resolved, sessionUUID, generated }}));
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
                "Node auth login UUID resolver regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertIsNone(payload["resolved"])
        self.assertIsNone(payload["sessionUUID"])
        self.assertFalse(payload["generated"])

    def test_pc_login_request_omits_session_header_before_business_session_exists(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        resolver_source = _extract_js_section(
            source,
            "function isUsableClientSessionUUID(value) {",
            "\n\nfunction shouldSuppressLoggedOutElsewhereNotice",
        )
        handle_auth_login_source = _extract_js_section(
            source,
            "async function handleAuthLogin(isMobile_use = false) {",
            "\n\n/**\n * 处理手机号未注册时跳转到注册页面",
        )

        node_script = f"""
const resolverSource = {json.dumps(resolver_source)};
const handleAuthLoginSource = {json.dumps(handle_auth_login_source)};
const elements = new Map();
let capturedHeaders = null;

function createElement(id, value = '') {{
  const classes = new Set();
  return {{
    id,
    value,
    textContent: '',
    disabled: false,
    classList: {{
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
    }},
  }};
}}

function $(id) {{ return elements.get(id) || null; }}

[
  createElement('auth-login-btn'),
  createElement('auth-username', 'demo-user'),
  createElement('auth-password', 'secret123'),
  createElement('auth-sms-code', ''),
  createElement('auth-login-captcha', '123456'),
  createElement('auth-login-phone-btn'),
  createElement('auth-sms-section'),
  createElement('auth-login-container'),
].forEach((element) => elements.set(element.id, element));
elements.get('auth-sms-section').classList.add('hidden');

globalThis.document = {{ getElementById(id) {{ return elements.get(id) || null; }} }};
globalThis.window = {{}};
globalThis.console = {{ log() {{}}, info() {{}}, warn() {{}}, error() {{}} }};
globalThis.Swal = {{ fire() {{ return Promise.resolve({{ isConfirmed: false }}); }} }};
globalThis.capturePreLoginBackgroundSnapshot = () => {{}};
globalThis.validateInput = () => ({{ valid: true }});
globalThis.refreshCaptcha = () => {{}};
globalThis.setButtonLoading = () => {{}};
globalThis.showButtonError = () => {{}};
globalThis.showButtonSuccess = () => {{}};
globalThis.showAuthSuccess = () => {{}};
globalThis.syncThemeFromServer = async () => {{}};
globalThis.initializeInlineAdminPanel = async () => {{}};
globalThis.showSessionPicker = () => {{}};
globalThis.showMobileSessionPicker = () => {{}};
globalThis.logMessage_Info = () => {{}};
globalThis.logMessage_Error = () => {{}};
globalThis.escapeHtml = (value) => String(value);
globalThis.fetch = async (_url, options) => {{
  capturedHeaders = options.headers;
  return {{
    json: async () => ({{
      success: true,
      auth_session_id: '33333333-3333-4333-8333-333333333333',
      auth_username: 'demo-user',
      group: 'user',
      is_guest: false,
      theme: 'light',
    }}),
  }};
}};
globalThis.currentUserData = {{}};
globalThis.isMobileMode = false;
globalThis.sessionUUID = null;
globalThis.authSessionUUID = null;
globalThis.authRequestGeneration = 0;
globalThis.authLoginInProgress = false;
globalThis.captchaIds_login = 'captcha-login';
globalThis.captchaIds_mobile_login = 'captcha-mobile';
globalThis.themeBackgroundLoginSyncInFlight = false;
function generateUUID() {{ return '22222222-2222-4222-8222-222222222222'; }}
function getUUIDFromURL() {{ return ''; }}

eval(resolverSource);
eval(handleAuthLoginSource);

(async () => {{
  await handleAuthLogin(false);
  process.stdout.write(JSON.stringify({{ capturedHeaders }}));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
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
                "Node auth login request header regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload["capturedHeaders"], {"Content-Type": "application/json"})

    def test_initial_data_api_uses_auth_session_when_business_session_missing(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        resolver_source = _extract_js_section(
            source,
            "function isUsableClientSessionUUID(value) {",
            "\n\nfunction shouldSuppressLoggedOutElsewhereNotice",
        )
        call_python_api_source = _extract_js_section(
            source,
            "async function callPythonAPI(method, ...args) {",
            "\n\nasync function callPythonAPI_raw",
        )

        node_script = f"""
const resolverSource = {json.dumps(resolver_source)};
const callPythonAPISource = {json.dumps(call_python_api_source)};
const fetchCalls = [];
globalThis.console = {{ log() {{}}, info() {{}}, warn() {{}}, error() {{}} }};
globalThis.window = {{ location: {{ pathname: '/' }} }};
globalThis.document = {{ getElementById() {{ return null; }} }};
globalThis.Swal = {{ fire() {{ return Promise.resolve({{ isConfirmed: true }}); }} }};
globalThis.logMessage_Info = () => {{}};
globalThis.logMessage_Warning = () => {{}};
globalThis.logMessage_Error = () => {{}};
globalThis.getServerConnectionGuidanceMessage = () => '';
globalThis.showMobileMessage = () => {{}};
globalThis.setInterval = () => 1;
globalThis.clearInterval = () => {{}};
globalThis.isInNetworkErrorState = false;
globalThis.refreshUserListInterval = null;
globalThis.socket = null;
globalThis.isMobileMode = false;
globalThis.sessionUUID = null;
globalThis.authSessionUUID = '44444444-4444-4444-8444-444444444444';
globalThis.authRequestGeneration = 1;
globalThis.authLoginInProgress = false;
globalThis.fetch = async (url, options) => {{
  fetchCalls.push({{ url, headers: options.headers }});
  return {{
    ok: true,
    json: async () => ({{ success: true }}),
  }};
}};
function getUUIDFromURL() {{ return ''; }}

eval(resolverSource);
eval(callPythonAPISource);

(async () => {{
  await callPythonAPI('get_initial_data', {{}});
  await callPythonAPI('load_tasks', {{}});
  process.stdout.write(JSON.stringify(fetchCalls));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
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
                "Node initial data auth session header regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(
            payload[0]["headers"],
            {
                "Content-Type": "application/json",
                "X-Session-ID": "44444444-4444-4444-8444-444444444444",
            },
        )
        self.assertEqual(payload[1]["headers"], {"Content-Type": "application/json"})

    def test_registration_avatar_preview_object_urls_are_revoked_after_preview_load(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        crop_registration_source = _extract_js_section(
            source,
            "function closeCropModal() {",
            "\n\nasync function confirmCropAndUpload()",
        )

        node_script = f"""
const cropRegistrationSource = {json.dumps(crop_registration_source)};
const elements = new Map();
const createCalls = [];
const revokeCalls = [];

function createElement(id, value = '') {{
  return {{
    id,
    value,
    src: '',
    onload: null,
    onerror: null,
  }};
}}

function $(id) {{
  return elements.get(id) || null;
}}

[
  'auth-reg-avatar-preview',
  'mobile-reg-avatar-preview',
  'profile-avatar-file',
  'auth-reg-avatar',
  'mobile-reg-avatar',
].forEach((id) => elements.set(id, createElement(id)));

globalThis.document = {{
  getElementById(id) {{
    return elements.get(id) || null;
  }},
}};
globalThis.$ = $;
globalThis.File = class File {{
  constructor(parts, name, options = {{}}) {{
    this.parts = parts;
    this.name = name;
    this.type = options.type || '';
  }}
}};
globalThis.URL = {{
  createObjectURL(value) {{
    const url = `blob:${{createCalls.length + 1}}`;
    createCalls.push(url);
    return url;
  }},
  revokeObjectURL(url) {{
    revokeCalls.push(url);
  }},
}};
globalThis.Swal = {{
  fire() {{
    return Promise.resolve();
  }},
}};
globalThis.hideModal = () => {{}};
globalThis.avatarCropper = {{
  destroy() {{}},
  getCroppedCanvas() {{
    return {{
      toBlob(callback) {{
        callback({{ size: 1, type: 'image/jpeg' }});
      }},
    }};
  }},
}};
globalThis.registrationCroppedAvatarBlob = null;
globalThis.isRegistrationCrop = true;

eval(cropRegistrationSource);

(async () => {{
  await confirmCropForRegistration();
  const previewImg = elements.get('auth-reg-avatar-preview');
  const mobilePreviewImg = elements.get('mobile-reg-avatar-preview');
  if (typeof previewImg.onload === 'function') previewImg.onload();
  if (typeof mobilePreviewImg.onload === 'function') mobilePreviewImg.onload();
  process.stdout.write(JSON.stringify({{
    createCalls,
    revokeCalls,
    previewSrc: previewImg.src,
    mobilePreviewSrc: mobilePreviewImg.src,
  }}));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
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
                "Node registration avatar preview cleanup regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(payload["createCalls"], ["blob:1", "blob:2"])
        self.assertEqual(payload["previewSrc"], "blob:1")
        self.assertEqual(payload["mobilePreviewSrc"], "blob:2")
        self.assertEqual(payload["revokeCalls"], ["blob:1", "blob:2"])

    def test_pc_login_mode_uses_mode_drafts_and_digit_sanitizers(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("const pcLoginModeDrafts =", source)
        self.assertIn("function sanitizePhoneDigits(value)", source)
        self.assertIn("function sanitizeSmsCodeDigits(value)", source)
        self.assertIn("function savePcLoginModeDraft()", source)
        self.assertIn("function restorePcLoginModeDraft(mode)", source)
        self.assertIn("function clearPcLoginModeDraftFields(mode)", source)
        self.assertIn("replace(/\\D/g, \"\")", source)
        self.assertIn("slice(0, 11)", source)

    def test_pc_login_mode_rebinds_digit_sanitizers_after_dynamic_switch(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("bindAuthPhoneLoginInput();", source)
        self.assertIn("bindAuthSmsCodeInput();", source)
        self.assertIn("bindRegistrationDigitInputs();", source)
        self.assertIn("applyDigitSanitizer(phoneInput, sanitizePhoneDigits);", source)
        self.assertIn("applyDigitSanitizer(smsInput, sanitizeSmsCodeDigits);", source)
        self.assertIn('document.getElementById("auth-sms-code")', source)
        self.assertIn('document.getElementById("auth-reg-phone")', source)
        self.assertIn('document.getElementById("auth-reg-sms-code")', source)

    def test_backend_normalizes_phone_and_sms_digits_before_validation(self):
        main_path = PROJECT_ROOT / "main.py"
        source = main_path.read_text(encoding="utf-8")

        self.assertIn("def _digits_only(value):", source)
        self.assertIn("def _normalize_phone(value):", source)
        self.assertIn("def _normalize_sms_code(value):", source)
        self.assertIn("auth_phone = _normalize_phone(data.get(\"auth_phone\"))", source)
        self.assertIn("sms_code = _normalize_sms_code(data.get(\"auth_sms_code\"))", source)
        self.assertIn("phone = _normalize_phone(data.get(\"phone\", \"\"))", source)
        self.assertIn("sms_code = _normalize_sms_code(data.get(\"sms_code\", \"\"))", source)


if __name__ == "__main__":
    unittest.main()
