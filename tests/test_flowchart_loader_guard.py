import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = PROJECT_ROOT / "index.html"


class TestFlowchartLoaderGuard(unittest.TestCase):
    def test_flowchart_script_is_guarded_by_widget_ready_check(self):
        source = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn("window.__maybeLoadJqueryFlowchart", source)
        self.assertIn("jquery-ui-widget-js", source)
        self.assertIn("jquery-flowchart-js", source)
        self.assertIn("jQuery.widget", source)
        self.assertIn('typeof jQuery.widget === "function"', source)
        self.assertIn('onload="window.__maybeLoadJqueryFlowchart()"', source)
        self.assertNotIn('src="/api/cdn/jquery-flowchart-js"', source)

    def test_flowchart_loading_waits_until_window_load(self):
        source = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn('document.readyState !== "complete"', source)
        self.assertIn('window.addEventListener("load"', source)

    def test_flowchart_cdn_urls_stay_queryless(self):
        source = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn("jquery-ui-js?v=", source)
        self.assertNotIn("jquery-ui-widget-js?v=", source)
        self.assertNotIn("jquery-flowchart-js?v=", source)
        self.assertNotIn("jquery-flowchart-css?v=", source)


if __name__ == "__main__":
    unittest.main()
