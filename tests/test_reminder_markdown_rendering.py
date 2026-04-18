import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


def _extract_js_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestReminderMarkdownRendering(unittest.TestCase):
    def test_render_markdown_to_html_stringifies_non_string_before_editormd(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        escape_html_source = _extract_js_section(
            source,
            "function escapeHtml(str) {",
            "\n\n/**",
        )
        render_source = _extract_js_section(
            source,
            "const renderMarkdownToHtml = async (md) => {",
            "\n\n    // 根据新提醒的数量",
        )

        node_script = f"""
const escapeHtmlSource = {json.dumps(escape_html_source)};
const renderSource = {json.dumps(render_source)};
const appendedNodes = [];
const noop = () => {{}};

globalThis.console = {{ log: noop, warn: noop, error: noop }};
globalThis.window = {{}};
globalThis.document = {{
  querySelector() {{
    return null;
  }},
  createElement(tag) {{
    return {{
      tagName: tag,
      style: {{}},
      innerHTML: "",
      rel: "",
      href: "",
      src: "",
      onload: null,
      onerror: null,
    }};
  }},
  body: {{
    appendChild(node) {{
      appendedNodes.push(node);
    }},
    removeChild(node) {{
      const index = appendedNodes.indexOf(node);
      if (index >= 0) appendedNodes.splice(index, 1);
    }},
  }},
  head: {{
    appendChild: noop,
  }},
}};

globalThis.editormd = {{
  markdownToHTML(_id, options) {{
    if (typeof options.markdown !== "string") {{
      throw new TypeError("markdown must be string");
    }}
    appendedNodes[appendedNodes.length - 1].innerHTML = `<p>${{options.markdown}}</p>`;
  }},
}};
window.editormd = globalThis.editormd;

eval(escapeHtmlSource);
const renderMarkdownToHtml = eval(`(function(){{${{renderSource}}; return renderMarkdownToHtml; }})()`);

(async () => {{
  const html = await renderMarkdownToHtml(123);
  process.stdout.write(JSON.stringify({{ html }}));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node reminder markdown regression failed\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["html"], "<p>123</p>")


if __name__ == "__main__":
    unittest.main()
