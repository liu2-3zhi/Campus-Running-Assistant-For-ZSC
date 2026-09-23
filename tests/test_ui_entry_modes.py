import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestUiEntryModes(unittest.TestCase):
    def test_backend_registers_fixed_new_and_old_entries(self):
        source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        for route in (
            '@app.route("/frontend")',
            '@app.route("/frontend/")',
            '@app.route("/frontend/<path:path>")',
            '@app.route("/old")',
            '@app.route("/old/")',
            '@app.route("/old/<path:path>")',
        ):
            self.assertIn(route, source)
        self.assertIn('runtime_config.get("Config", "default_ui"', source)
        self.assertIn('config.set("Config", "default_ui", default_ui)', source)
        self.assertIn('return redirect("/frontend/")', source)

    def test_vue_build_and_router_use_frontend_base(self):
        vite_config = (PROJECT_ROOT / "frontend/vite.config.js").read_text(
            encoding="utf-8"
        )
        router = (PROJECT_ROOT / "frontend/src/router/index.js").read_text(
            encoding="utf-8"
        )
        main_js = (PROJECT_ROOT / "frontend/src/main.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("base: '/frontend/'", vite_config)
        self.assertIn("createWebHistory(import.meta.env.BASE_URL)", router)
        self.assertIn("window.__RUNNING_UI_BASE__ = import.meta.env.BASE_URL", main_js)

    def test_legacy_entry_keeps_old_prefix_for_session_navigation(self):
        source = (PROJECT_ROOT / "scripts/main.js").read_text(encoding="utf-8")
        self.assertIn("function buildLegacyUiPath(path = \"/\")", source)
        self.assertIn(
            "window.location.href = buildLegacyUiPath(`/uuid=${originSession}`)",
            source,
        )
        self.assertIn(
            "window.location.replace(buildLegacyUiPath(`/uuid=${sessionUUID}`))",
            source,
        )
        self.assertNotIn('window.location.href = "/";', source)
        self.assertNotIn('window.location.replace("/")', source)

    def test_nginx_proxies_prefixed_ui_entries(self):
        source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("location ^~ /frontend/", source)
        self.assertIn("location ^~ /old/", source)


if __name__ == "__main__":
    unittest.main()
