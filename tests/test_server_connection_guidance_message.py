import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = PROJECT_ROOT / "scripts" / "main.js"


class TestServerConnectionGuidanceMessage(unittest.TestCase):
    def test_guidance_message_uses_structured_inline_cards(self):
        source = MAIN_JS.read_text(encoding="utf-8")
        match = re.search(
            r"function\s+getServerConnectionGuidanceMessage\(\)\s*\{(?P<body>[\s\S]*?)\n\}",
            source,
        )
        self.assertIsNotNone(match, "getServerConnectionGuidanceMessage must exist")
        body = match.group("body")

        self.assertIn("border-radius:10px", body)
        self.assertIn('<ul style="', body)
        self.assertEqual(body.count("<li>"), 3)
        self.assertGreaterEqual(body.count("background:"), 4)
        self.assertNotIn("space-y-4", body)


if __name__ == "__main__":
    unittest.main()
