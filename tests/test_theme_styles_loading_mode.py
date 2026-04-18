import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


def _extract_js_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestThemeStylesLoadingMode(unittest.TestCase):
    def test_theme_styles_uses_public_fetch_before_auth_is_confirmed(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        resolve_source = _extract_js_section(
            source,
            "function resolveThemeRequestSessionUUID(sessionId = sessionUUID, pathname = window.location.pathname) {",
            "\n\nfunction buildPublicThemeStylesUrl",
        )
        build_url_source = _extract_js_section(
            source,
            "function buildPublicThemeStylesUrl(styleId, backgroundTarget, sessionId = sessionUUID, pathname = window.location.pathname) {",
            "\n\nfunction shouldApplyThemeConfigImmediately",
        )
        should_apply_source = _extract_js_section(
            source,
            "function shouldApplyThemeConfigImmediately(params) {",
            "\n\nasync function ensureThemeStylesLoaded",
        )
        ensure_source = _extract_js_section(
            source,
            "async function ensureThemeStylesLoaded(force = false, options = {}) {",
            "\n\nfunction applyTheme",
        )

        node_script = f"""
const resolveSource = {json.dumps(resolve_source)};
const buildUrlSource = {json.dumps(build_url_source)};
const shouldApplySource = {json.dumps(should_apply_source)};
const ensureSource = {json.dumps(ensure_source)};

let sessionUUID = '11111111-1111-4111-8111-111111111111';
let themeBackgroundAuthStateResolved = false;
let themeBackgroundAuthenticatedSession = false;
let availableThemeStyles = [];
let currentThemeConfig = null;
let window = {{ location: {{ pathname: '/uuid=11111111-1111-4111-8111-111111111111' }} }};
let fetchCalls = [];
let pythonCalls = [];

function normalizeThemeStyle(value) {{
  return value || 'default';
}}
function getCachedThemeStyle() {{
  return 'default';
}}
function getCurrentThemeBackgroundTarget() {{
  return 'pc';
}}
function applyThemeGlobalEnvironmentVariables(_config) {{}}
async function callPythonAPI(method, ...args) {{
  pythonCalls.push([method, ...args]);
  return {{ success: true, theme_styles: [{{ id: 'private' }}], theme_config: {{}} }};
}}
async function fetch(url, options) {{
  fetchCalls.push([url, options && options.method ? options.method : 'GET']);
  return {{
    ok: true,
    json: async () => ({{ success: true, theme_styles: [{{ id: 'public' }}], theme_config: {{}} }}),
  }};
}}

eval(resolveSource);
eval(buildUrlSource);
eval(shouldApplySource);
eval(ensureSource);

(async () => {{
  const result = await ensureThemeStylesLoaded(true, {{ applyThemeConfig: false }});
  process.stdout.write(JSON.stringify({{ result, fetchCalls, pythonCalls }}));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node theme styles mode regression failed\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["pythonCalls"], [])
        self.assertEqual(payload["fetchCalls"][0][0], "/api/public/theme_styles?style_id=default&background_target=pc&uuid=11111111-1111-4111-8111-111111111111")
        self.assertEqual(payload["result"], [{"id": "public"}])


if __name__ == "__main__":
    unittest.main()
