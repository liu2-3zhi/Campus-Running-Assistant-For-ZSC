import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML_PATH = PROJECT_ROOT / "index.html"
MAIN_PY_PATH = PROJECT_ROOT / "main.py"
SERVICE_WORKER_PATH = PROJECT_ROOT / "PWA" / "sw.js"


def _extract_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestFlowchartScriptDependencies(unittest.TestCase):
    def test_jquery_ui_widget_factory_loads_before_jquery_flowchart(self):
        source = INDEX_HTML_PATH.read_text(encoding="utf-8")

        self.assertIn("window.__maybeLoadJqueryFlowchart", source)
        self.assertIn("jquery-ui-widget-js", source)
        self.assertIn("jquery-flowchart-js", source)
        self.assertIn("jQuery.widget", source)
        self.assertIn('typeof jQuery.widget === "function"', source)
        self.assertIn('onload="window.__maybeLoadJqueryFlowchart()"', source)
        self.assertNotIn('src="/api/cdn/jquery-flowchart-js"', source)

    def test_jquery_is_loaded_only_once(self):
        source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count('src="/api/cdn/jquery"'), 1)

    def test_index_route_reads_index_html_per_request_instead_of_startup_snapshot(self):
        source = MAIN_PY_PATH.read_text(encoding="utf-8")
        index_route_source = _extract_section(
            source,
            "    @app.route(\"/\")",
            "    # @app.route(\"/\")",
        )

        self.assertIn('with open("index.html", "r", encoding="utf-8") as file:', index_route_source)
        self.assertIn("current_html_content = file.read()", index_route_source)
        self.assertIn("return render_template_string(current_html_content)", index_route_source)
        self.assertNotIn("render_template_string(html_content)", index_route_source)

    def test_editor_md_route_disables_browser_cache(self):
        source = MAIN_PY_PATH.read_text(encoding="utf-8")
        editor_route_source = _extract_section(
            source,
            '    @app.route("/editor.md/<path:filename>")',
            '    # ========== IE 浏览器拦截页面路由 ==========',
        )

        self.assertIn('response = send_from_directory(ed_dir, filename)', editor_route_source)
        self.assertIn('response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"', editor_route_source)
        self.assertIn('response.headers["Pragma"] = "no-cache"', editor_route_source)
        self.assertIn('response.headers["Expires"] = "0"', editor_route_source)

    def test_service_worker_uses_network_first_for_navigation_requests(self):
        source = SERVICE_WORKER_PATH.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            re.compile(r"event\.request\.mode\s*===?\s*['\"]navigate['\"]"),
        )
        self.assertRegex(
            source,
            re.compile(r"if\s*\([^\)]*event\.request\.mode\s*===?\s*['\"]navigate['\"][^\)]*\)\s*\{[\s\S]*?fetch\(event\.request\)[\s\S]*?caches\.match\('/'\)", re.MULTILINE),
        )
        self.assertIn("'/editor.md/'", source)
        navigate_guard_index = source.index("if (event.request.mode === 'navigate')")
        static_cache_first_index = source.index("caches.match(event.request)")
        self.assertLess(
            navigate_guard_index,
            static_cache_first_index,
            "navigation handling must happen before generic static asset cache-first logic",
        )

    def test_service_worker_does_not_serve_legacy_main_script_from_static_cache(self):
        source = SERVICE_WORKER_PATH.read_text(encoding="utf-8")

        self.assertNotIn("'/scripts/main.new.js'", source)
        self.assertNotIn('"/scripts/main.new.js"', source)
        self.assertRegex(
            source,
            re.compile(
                r"if\s*\(\s*url\.pathname\.startsWith\(\s*['\"]\/scripts\/['\"]\s*\)\s*\)\s*\{[\s\S]*?fetch\(event\.request\)",
                re.MULTILINE,
            ),
        )

    def test_legacy_main_script_bypasses_old_worker_and_http_caches(self):
        index_source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        main_source = MAIN_PY_PATH.read_text(encoding="utf-8")
        scripts_route_source = _extract_section(
            main_source,
            '    @app.route("/scripts/<path:filename>")',
            '    @app.route("/styles/<path:filename>")',
        )

        self.assertRegex(
            index_source,
            re.compile(
                r'<script\s+src="/scripts/main\.new\.js\?v=[^"]+"\s+defer',
            ),
        )
        self.assertIn(
            "return _send_frontend_static_file(script_dir, filename, no_cache=True)",
            scripts_route_source,
        )


if __name__ == "__main__":
    unittest.main()
