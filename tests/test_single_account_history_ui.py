import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = PROJECT_ROOT / "scripts" / "main.js"
STYLE_CSS = PROJECT_ROOT / "styles" / "style.css"


class TestSingleAccountHistoryUi(unittest.TestCase):
    def test_history_items_keep_the_loaded_record_selected(self):
        source = MAIN_JS.read_text(encoding="utf-8")
        history_source = source[
            source.index("async function loadHistory("):
            source.index("async function showHistoricalTrack(")
        ]

        self.assertIn("selectedHistoryTrid", history_source)
        self.assertIn("item.classList.add(\"selected\")", history_source)
        self.assertIn("showHistoricalTrack(rec.trid)", history_source)

    def test_leaving_history_restores_the_task_map(self):
        source = MAIN_JS.read_text(encoding="utf-8")
        show_tab_source = source[
            source.index("function showTab("):
            source.index("function autoLogin(", source.index("function showTab("))
        ]

        self.assertIn("clearHistoricalTrack()", show_tab_source)
        self.assertIn("if (tabName !== \"history\")", show_tab_source)
        self.assertIn("if (hasHistoricalTrack) drawOnMap();", source)

    def test_history_selection_has_a_desktop_selected_style(self):
        source = STYLE_CSS.read_text(encoding="utf-8")
        self.assertIn("#history-list > div.selected", source)


if __name__ == "__main__":
    unittest.main()
