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

        jquery_flowchart_anchor = 'src="/api/cdn/jquery-flowchart-js"'
        self.assertIn(jquery_flowchart_anchor, source)

        jquery_ui_anchors = [
            'src="/api/cdn/jquery-ui-js"',
            'src="https://cdn.jsdelivr.net/npm/jquery-ui-dist/jquery-ui.min.js"',
            'src="https://cdn.jsdelivr.net/npm/jquery-ui/ui/widget.js"',
        ]
        present_anchors = [anchor for anchor in jquery_ui_anchors if anchor in source]
        self.assertTrue(
            present_anchors,
            "index.html must load a jQuery UI widget factory script before jquery-flowchart-js",
        )

        jquery_flowchart_index = source.index(jquery_flowchart_anchor)
        jquery_ui_index = min(source.index(anchor) for anchor in present_anchors)
        self.assertLess(jquery_ui_index, jquery_flowchart_index)
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
        navigate_guard_index = source.index("if (event.request.mode === 'navigate')")
        static_cache_first_index = source.index("caches.match(event.request)")
        self.assertLess(
            navigate_guard_index,
            static_cache_first_index,
            "navigation handling must happen before generic static asset cache-first logic",
        )


if __name__ == "__main__":
    unittest.main()
