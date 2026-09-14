import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestFrontendJavascriptHardening(unittest.TestCase):
    def test_js_anti_debug_switch_defaults_off(self):
        self.assertIs(main.ENABLE_FRONTEND_JS_ANTI_DEBUG, False)

    def test_hardening_strips_comments_compacts_and_preserves_literals(self):
        sample = """
        // top-level comment
        const url = "https://example.com/a//b";
        const tpl = `keep // inside template`;
        /* block comment */
        const rx = /https?:\\/\\/example\\.com/;
        console.log(url, tpl, rx); //# sourceMappingURL=demo.js.map
        """

        with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", True):
            hardened = main._harden_frontend_javascript_for_response(sample)

        self.assertIn("__FRONTEND_JS_ANTI_DEBUG__", hardened)
        self.assertIn("debugger", hardened)
        self.assertIn("https://example.com/a//b", hardened)
        self.assertIn("keep // inside template", hardened)
        self.assertIn("/https?:\\/\\/example\\.com/", hardened)
        self.assertNotIn("top-level comment", hardened)
        self.assertNotIn("block comment", hardened)
        self.assertNotIn("sourceMappingURL", hardened)
        self.assertLessEqual(hardened.count("\n"), 1)

    def test_hardening_handles_nested_template_interpolations(self):
        sample = r"""
        const nested = `outer ${String.raw`inner // ${/https?:\/\//.test(url) ? "yes" : "no"}`} end`;
        const evaluated = `${(() => {
          // expression comment
          return /https?:\/\//.test(url);
        })()}`;
        function codeAfterTemplate() {
          return nested + evaluated;
        }
        """

        with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", True):
            hardened = main._harden_frontend_javascript_for_response(sample)

        self.assertIn("function codeAfterTemplate()", hardened)
        self.assertIn("inner //", hardened)
        self.assertIn("/https?:\\/\\//.test(url)", hardened)
        self.assertNotIn("expression comment", hardened)
        self.assertLessEqual(hardened.count("\n"), 1)

    def test_hardening_removes_shebang_after_prepending_guard(self):
        sample = "#!/usr/bin/env node\nconst value = 1;\n"

        with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", True):
            hardened = main._harden_frontend_javascript_for_response(sample)

        self.assertIn("const value=1;", hardened)
        self.assertNotIn("#!", hardened)

    def test_hardening_preserves_asi_between_statement_lines(self):
        sample = """
        fs.mkdirSync("dist/", { recursive: true })
        fs.writeFileSync("dist/out.js", "ok");
        """

        with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", True):
            hardened = main._harden_frontend_javascript_for_response(sample)

        self.assertIn('fs.mkdirSync("dist/",{recursive:true})\nfs.writeFileSync', hardened)

    def test_js_response_routes_use_hardening_helpers(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn("def _make_frontend_javascript_response(", source)
        self.assertIn("def _send_frontend_static_file(", source)
        self.assertIn("def _harden_frontend_javascript_response_if_needed(", source)

        cdn_block = source[
            source.index('@app.route("/api/cdn/<file_key>")'):
            source.index('@app.route("/api/map_key_runtime.js")')
        ]
        map_runtime_block = source[
            source.index('@app.route("/api/map_key_runtime.js")'):
            source.index('@app.route("/api/map_provider_keys/decrypt"')
        ]
        scripts_block = source[
            source.index('@app.route("/scripts/<path:filename>")'):
            source.index('@app.route("/styles/<path:filename>")')
        ]
        styles_block = source[
            source.index('@app.route("/styles/<path:filename>")'):
            source.index('@app.route("/theme-assets/<path:filename>")')
        ]
        theme_assets_block = source[
            source.index('@app.route("/theme-assets/<path:filename>")'):
            source.index("# ========== 新增路由：Twemoji")
        ]
        twemoji_block = source[
            source.index('@app.route("/twemoji/<path:filename>")'):
            source.index('@app.route("/Github_emojis/<path:filename>")')
        ]
        github_emojis_block = source[
            source.index('@app.route("/Github_emojis/<path:filename>")'):
            source.index('@app.route("/editor.md/<path:filename>")')
        ]
        service_worker_block = source[
            source.index('@app.route("/sw.js")'):
            source.index('@app.route("/icon-<int:size>x<int:size2>.png")')
        ]
        frontend_config_block = source[
            source.index('@app.route("/api/frontend_config.js")'):
            source.index("# Vue 前端自动构建")
        ]
        vue_asset_block = source[
            source.index('@app.route("/assets/<path:filename>")'):
            source.index("def _serve_vue_index(")
        ]
        behavior_block = source[
            source.index('@app.route("/api/captcha/behavior/loader.js"'):
            source.index('@app.route("/api/captcha/behavior/gen"')
        ]

        self.assertIn("_make_frontend_javascript_response(", cdn_block)
        self.assertIn("_make_frontend_javascript_response(", map_runtime_block)
        self.assertIn("_send_frontend_static_file(script_dir, filename", scripts_block)
        self.assertIn("_send_frontend_static_file(style_dir, filename", styles_block)
        self.assertIn("_send_frontend_static_file(assets_dir, filename", theme_assets_block)
        self.assertIn('startswith(("scripts/", "src/"))', twemoji_block)
        self.assertIn("_send_frontend_static_file(twemoji_dir, filename", twemoji_block)
        self.assertIn("_send_frontend_static_file(gh_dir, filename", github_emojis_block)
        self.assertIn("_send_frontend_static_file(", service_worker_block)
        self.assertIn('os.path.join(root_dir, "PWA")', service_worker_block)
        self.assertIn('"sw.js"', service_worker_block)
        self.assertIn("_make_frontend_javascript_response(config_script", frontend_config_block)
        self.assertIn("_send_frontend_static_file(assets_dir, filename", vue_asset_block)
        self.assertIn("_make_frontend_javascript_response(", behavior_block)

    def test_after_request_hardens_javascript_response_fallback(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        after_request_block = source[
            source.index("@app.after_request"):
            source.index("# ============================================================================", source.index("@app.after_request"))
        ]

        self.assertIn(
            "response = _harden_frontend_javascript_response_if_needed(response)",
            after_request_block,
        )

    def test_after_request_helper_hardens_javascript_response(self):
        app = Flask(__name__)
        with app.app_context():
            response = main.make_response("const answer = 42; // readable comment\n")
            response.mimetype = "application/javascript"

            with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", True):
                hardened = main._harden_frontend_javascript_response_if_needed(response)

        body = hardened.get_data(as_text=True)
        self.assertEqual(hardened.headers.get("X-JS-Hardened"), "1")
        self.assertIn("__FRONTEND_JS_ANTI_DEBUG__", body)
        self.assertNotIn("readable comment", body)
        self.assertLessEqual(body.count("\n"), 1)

    def test_after_request_helper_leaves_javascript_unchanged_when_disabled(self):
        app = Flask(__name__)
        with app.app_context():
            response = main.make_response("const answer = 42; // keep comment\n")
            response.mimetype = "application/javascript"

            with patch.object(main, "ENABLE_FRONTEND_JS_ANTI_DEBUG", False):
                untouched = main._harden_frontend_javascript_response_if_needed(response)

        self.assertIs(untouched, response)
        self.assertNotIn("X-JS-Hardened", untouched.headers)
        self.assertIn("keep comment", untouched.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
