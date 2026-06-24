import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


class TestMobileAdminScrollRegressions(unittest.TestCase):
    def test_scroll_guard_helpers_exist_for_mobile_admin_unified_panel(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("const mobileAdminUnifiedScrollState =", source)
        self.assertIn("function captureMobileAdminUnifiedScrollState(", source)
        self.assertIn("function restoreMobileAdminUnifiedScrollState(", source)
        self.assertIn("function withMobileAdminUnifiedScrollGuard(", source)
        self.assertIn("function syncMobileAdminUnifiedPanelScroll(", source)

    def test_copy_admin_content_to_multi_panel_uses_scroll_guard(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("withMobileAdminUnifiedScrollGuard(tabType,", source)
        self.assertIn("mobileContainer.innerHTML = pcContainer.innerHTML;", source)
        self.assertIn("restoreMode: \"replace\"", source)

    def test_mobile_admin_unified_tab_switches_preserve_scroll_context(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"))', source)
        self.assertIn('loadMobileMultiAdminBillingList()', source)
        self.assertIn('captureMobileAdminUnifiedScrollState(', source)

    def test_scroll_guard_restores_scroll_top_after_replace_render(self):
        node_script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const source = fs.readFileSync({str(SCRIPT_PATH)!r}, 'utf8');

            const helperStart = source.indexOf('const mobileAdminUnifiedScrollState =');
            if (helperStart === -1) throw new Error('missing mobileAdminUnifiedScrollState');
            const helperEnd = source.indexOf('// let captchaIds = {{', helperStart);
            if (helperEnd === -1) throw new Error('missing helper section end marker');
            const helperSource = source.slice(helperStart, helperEnd);

            const panel = {{
              scrollTop: 180,
              scrollHeight: 1200,
              clientHeight: 400,
              dataset: {{}},
            }};
            const mobileContainer = {{ innerHTML: '<div>before</div>' }};
            const pcContainer = {{ innerHTML: '<div>after</div>' }};

            global.document = {{
              getElementById(id) {{
                if (id === 'mobile-admin-panel-unified') return panel;
                if (id === 'mobile-multi-admin-users-list') return mobileContainer;
                if (id === 'admin-users-list_modal') return pcContainer;
                return null;
              }},
            }};
            global.window = global;
            global.requestAnimationFrame = (callback) => callback();
            global.logMessage_Error = () => {{}};

            eval(helperSource);

            withMobileAdminUnifiedScrollGuard('users', () => {{
              mobileContainer.innerHTML = pcContainer.innerHTML;
              panel.scrollTop = 999;
            }}, {{ restoreMode: 'replace' }});

            process.stdout.write(JSON.stringify({{
              scrollTop: panel.scrollTop,
              html: mobileContainer.innerHTML,
            }}));
            """
        )

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node mobile admin scroll regression failed\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        self.assertIn('"scrollTop":180', result.stdout)
        self.assertIn('"html":"<div>after</div>"', result.stdout)


if __name__ == "__main__":
    unittest.main()
