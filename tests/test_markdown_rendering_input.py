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

    def test_message_markdown_renderer_uses_container_element_not_id_string(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")
        message_section = source[source.index("(function renderMessagesMarkdown(msgs) {") : source.index(
            "async function postMessage() {"
        )]

        self.assertIn("const container = document.getElementById(id);", message_section)
        self.assertIn("container.innerHTML =", message_section)
        self.assertNotIn("id.innerHTML =", message_section)
        self.assertNotIn("id.innerHTML =\n", message_section)

    def test_mobile_message_markdown_renderer_uses_container_element_not_id_string(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")
        mobile_section = source[
            source.index("(function renderMobileMessagesMarkdown(msgs) {") : source.index(
                "async function submitMobileMultiMessage() {"
            )
        ]

        self.assertIn("const container = document.getElementById(id);", mobile_section)
        self.assertIn("container.innerHTML =", mobile_section)
        self.assertNotIn("id.innerHTML =", mobile_section)
        self.assertNotIn("id.innerHTML =\n", mobile_section)

    def test_messages_are_rerendered_after_editormd_initializes(self):
        source = MAIN_JS_PATH.read_text(encoding="utf-8")
        init_marker = "window._messageEditorInitialized = true;"
        reminder_marker = "// 为 reminder-editor 也注册相同的对话框移动与遮罩可见性控制逻辑"
        init_start = source.index(init_marker)
        init_end = source.index(reminder_marker, init_start)
        post_init_section = source[init_start:init_end]

        self.assertRegex(
            post_init_section,
            re.compile(r"window\._messageEditorInitialized\s*=\s*true;[\s\S]*?loadMessages\(\);", re.MULTILINE),
        )


if __name__ == "__main__":
    unittest.main()
