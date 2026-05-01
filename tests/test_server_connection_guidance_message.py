import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = PROJECT_ROOT / "scripts" / "main.new.js"


class TestServerConnectionGuidanceMessage(unittest.TestCase):
    def test_guidance_message_uses_one_compact_card(self):
        source = MAIN_JS.read_text(encoding="utf-8")
        match = re.search(
            r"function\s+getServerConnectionGuidanceMessage\(\)\s*\{(?P<body>[\s\S]*?)\n\}",
            source,
        )
        self.assertIsNotNone(match, "getServerConnectionGuidanceMessage must exist")
        body = match.group("body")

        self.assertIn("rounded-xl border border-slate-200 bg-slate-50", body)
        self.assertIn('<ul class="mt-2 space-y-1', body)
        self.assertEqual(body.count("<li>"), 3)
        self.assertEqual(body.count("bg-"), 1)
        self.assertNotIn("space-y-4", body)


if __name__ == "__main__":
    unittest.main()
