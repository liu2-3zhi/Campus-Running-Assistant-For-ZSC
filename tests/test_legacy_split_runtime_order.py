import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestLegacySplitRuntimeOrder(unittest.TestCase):
    def test_legacy_reminders_has_no_dangling_async_token(self):
        source = (PROJECT_ROOT / "scripts" / "legacy-reminders.js").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(source, r"(?m)^\s*async\s*$")

    def test_multi_account_list_binding_waits_for_dom_and_core_helpers(self):
        source = (
            PROJECT_ROOT / "scripts" / "legacy-multi-accounts.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            '$("multi-account-list").addEventListener',
            source,
        )
        self.assertIn(
            "function bindMultiAccountListChangeHandler()",
            source,
        )
        self.assertRegex(
            source,
            r"document\.getElementById\(\"multi-account-list\"\)[\s\S]*"
            r"addEventListener\(\"change\"",
        )


if __name__ == "__main__":
    unittest.main()
