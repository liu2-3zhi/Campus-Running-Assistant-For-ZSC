import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


class TestBillingTimeDisplay(unittest.TestCase):
    def test_billing_time_formatter_converts_legacy_utc_to_beijing_time(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")

        formatter_match = re.search(
            r"function\s+_fmtBillTime\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\n\}",
            source,
        )
        self.assertIsNotNone(formatter_match, "scripts/main.new.js must define _fmtBillTime")
        formatter_body = formatter_match.group("body")

        self.assertIn("Date.UTC", formatter_body)
        self.assertIn("8 * 60 * 60 * 1000", formatter_body)
        self.assertNotIn('replace("T", " ").replace("Z", "")', formatter_body)

    def test_billing_rendering_prefers_beijing_keys(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn('r.created_at.replace("T", " ").replace("Z", "")', source)
        self.assertNotIn('r.paid_at.replace("T", " ").replace("Z", "")', source)
        self.assertIn("_getBillingTime(r, \"created_at\")", source)
        self.assertIn("_getBillingTime(r, \"paid_at\")", source)
        self.assertIn("_getBillingTime(r, \"admin_cleared_at\")", source)


if __name__ == "__main__":
    unittest.main()
