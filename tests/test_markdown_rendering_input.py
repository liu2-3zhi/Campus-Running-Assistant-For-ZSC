import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


class TestMarkdownRenderingInput(unittest.TestCase):
    def test_markdown_renderer_normalizes_non_string_values(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("function normalizeMarkdownText", source)
        self.assertIn("JSON.stringify(value)", source)

        self.assertNotIn("markdown: m.content || \"\"", source)
        self.assertNotIn("markdown: reminder.message || \"\"", source)
        self.assertNotIn("escapeHtml(m.content || \"\")", source)
        self.assertNotIn("escapeHtml(reminder.message || \"\")", source)

    def test_message_renderers_pass_normalized_strings_to_editormd(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(
                r"const\s+markdownText\s*=\s*normalizeMarkdownText\(m\.content\);[\s\S]*?markdown:\s*markdownText",
                re.MULTILINE,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"const\s+markdownText\s*=\s*normalizeMarkdownText\(reminder\.message\);[\s\S]*?markdown:\s*markdownText",
                re.MULTILINE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
