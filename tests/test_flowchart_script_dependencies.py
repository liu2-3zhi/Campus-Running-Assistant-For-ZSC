import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML_PATH = PROJECT_ROOT / "index.html"


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


if __name__ == "__main__":
    unittest.main()
