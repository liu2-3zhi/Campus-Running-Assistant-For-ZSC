import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"
LOAD_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "load_amap_watermark.js"


class TestAmapDialogGuardrails(unittest.TestCase):
    def test_backend_keeps_no_cache_response_helper(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def _apply_no_cache_headers(response):', source)
        self.assertIn('response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"', source)
        self.assertIn('response.headers["Pragma"] = "no-cache"', source)
        self.assertIn('response.headers["Expires"] = "0"', source)
        self.assertIn('return _apply_no_cache_headers(response)', source)

    def test_frontend_loader_installs_native_dialog_guard(self):
        source = LOAD_SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("window.__amapNativeDialogGuardInstalled", source)
        self.assertIn("window.alert = function", source)
        self.assertIn("window.confirm = function", source)
        self.assertIn("window.prompt = function", source)
        self.assertIn("installAmapNativeDialogGuard();", source)

    def test_backend_amap_context_installs_dialog_dismiss_handler(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def _install_amap_dialog_guard(page, guard_label="AMap"):', source)
        self.assertIn('page.on("dialog", _handle_dialog)', source)
        self.assertIn('dialog.dismiss()', source)
        self.assertGreaterEqual(source.count('_install_amap_dialog_guard(page,'), 2)


if __name__ == "__main__":
    unittest.main()
