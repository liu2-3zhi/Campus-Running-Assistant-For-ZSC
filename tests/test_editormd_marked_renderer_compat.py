import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDITORMD_PATH = PROJECT_ROOT / "editor.md" / "editormd.js"
MARKED_PATH = PROJECT_ROOT / "cache" / "cdn" / "marked.js"
MESSAGES_PATH = PROJECT_ROOT / "messages.json"


def _extract_js_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _function_body(source: str, name: str) -> str:
    start_match = re.search(
        rf"markedRenderer\.{name}\s*=\s*function\s*\([^)]*\)\s*\{{",
        source,
    )
    if not start_match:
        raise AssertionError(f"markedRenderer.{name} must be defined")

    start = start_match.end()
    depth = 1
    index = start
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
        index += 1

    raise AssertionError(f"markedRenderer.{name} body was not closed")


class TestEditormdMarkedRendererCompat(unittest.TestCase):
    def test_renderer_text_is_normalized_before_string_methods(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")

        self.assertIn("function normalizeMarkedRendererText", source)
        self.assertIn("function normalizeMarkedRendererInlineText", source)
        self.assertIn("value.text", source)
        self.assertIn("value.raw", source)

        for name in ("emoji", "atLink", "pageBreak", "paragraph"):
            body = _function_body(source, name)
            self.assertIn("normalizeMarkedRendererText", body, f"{name} must normalize token objects")

        emoji_body = _function_body(source, "emoji")
        self.assertRegex(
            emoji_body,
            re.compile(
                r"text\s*=\s*normalizeMarkedRendererText\(text,\s*this\);[\s\S]*?text\s*=\s*text\.replace",
                re.MULTILINE,
            ),
        )

        paragraph_body = _function_body(source, "paragraph")
        self.assertRegex(
            paragraph_body,
            re.compile(
                r"text\s*=\s*normalizeMarkedRendererText\(text,\s*this\);[\s\S]*?text\.replace",
                re.MULTILINE,
            ),
        )

    def test_heading_renderer_accepts_marked_token_object(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        heading_body = _function_body(source, "heading")

        self.assertRegex(
            heading_body,
            re.compile(
                r"if\s*\(\s*text\s*&&\s*typeof\s+text\s*===\s*[\"']object[\"']\s*\)\s*\{[\s\S]*?level\s*=\s*text\.depth",
                re.MULTILINE,
            ),
        )
        self.assertRegex(
            heading_body,
            re.compile(
                r"text\s*=\s*normalizeMarkedRendererText\(text,\s*this\);[\s\S]*?text\s*=\s*trim\(text\)",
                re.MULTILINE,
            ),
        )

    def test_renderer_methods_adapt_marked_token_signatures(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")

        self.assertIn("function normalizeMarkedRendererLinkArgs", source)
        self.assertIn("function normalizeMarkedRendererCodeArgs", source)
        self.assertIn("function normalizeMarkedRendererTablecellArgs", source)
        self.assertIn("function normalizeMarkedRendererListitemArgs", source)

        link_body = _function_body(source, "link")
        self.assertIn("var linkArgs = normalizeMarkedRendererLinkArgs", link_body)
        self.assertIn("linkArgs.href", link_body)
        self.assertIn("linkArgs.title", link_body)
        self.assertIn("linkArgs.text", link_body)

        code_body = _function_body(source, "code")
        self.assertIn("var codeArgs = normalizeMarkedRendererCodeArgs", code_body)
        self.assertIn("codeArgs.code", code_body)
        self.assertIn("codeArgs.lang", code_body)

        tablecell_body = _function_body(source, "tablecell")
        self.assertIn("var cellArgs = normalizeMarkedRendererTablecellArgs", tablecell_body)
        self.assertIn("cellArgs.content", tablecell_body)
        self.assertIn("cellArgs.flags", tablecell_body)

        listitem_body = _function_body(source, "listitem")
        self.assertIn("var itemArgs = normalizeMarkedRendererListitemArgs", listitem_body)
        self.assertIn("itemArgs.text", listitem_body)
        self.assertIn("itemArgs.task", listitem_body)

    def test_parse_inline_tokens_are_preserved(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "function isMarkedInlineTokens(tokens)",
            "markedRenderer.emoji = function(text)",
        )

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
const calls = [];
const renderer = {{
  parser: {{
    parseInline(tokens) {{
      calls.push(tokens);
      return "<strong>bold</strong>";
    }}
  }}
}};

eval(helperSource);
const output = normalizeMarkedRendererText({{ tokens: [{{ type: "strong", text: "bold" }}] }}, renderer);
process.stdout.write(JSON.stringify({{ output, calls: calls.length }}));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node markdown compatibility check failed\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["output"], "<strong>bold</strong>")
        self.assertEqual(payload["calls"], 1)

    def test_plain_markdown_bold_falls_back_to_marked_parse_inline(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "function isMarkedInlineTokens(tokens)",
            "markedRenderer.emoji = function(text)",
        )

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
const calls = [];
globalThis.marked = {{
  parseInline(text) {{
    calls.push(text);
    return "<strong>本网站今天正式开通啦，欢迎大家使用！</strong>";
  }}
}};
const renderer = {{
  parser: {{
    parseInline(tokens) {{
      throw new Error("parseInline should not be used for raw text fallback");
    }},
    parse(tokens) {{
      throw new Error("parse should not be used for raw text fallback");
    }}
  }}
}};

eval(helperSource);
const output = normalizeMarkedRendererText({{ text: "**本网站今天正式开通啦，欢迎大家使用！**" }}, renderer);
process.stdout.write(JSON.stringify({{ output, calls }}));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node markdown bold compatibility check failed\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["output"], "<strong>本网站今天正式开通啦，欢迎大家使用！</strong>")
        self.assertEqual(payload["calls"], ["**本网站今天正式开通啦，欢迎大家使用！**"])

    def test_blockquote_markdown_bold_is_preserved_with_real_marked_renderer(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "editormd.markedRenderer = function(markdownToC, options) {",
            "    /**\n     * 将Markdown文档解析为HTML用于前台显示",
        )
        marked_source = MARKED_PATH.read_text(encoding="utf-8")

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
const markedSource = {json.dumps(marked_source)};
const projectRoot = {json.dumps(str(PROJECT_ROOT.as_posix()))};
const path = require('path');
const markedModule = require(path.join(projectRoot, 'cache/cdn/marked.js'));
const marked = markedModule.marked || markedModule;
const g = globalThis;
const trim = function(str) {{
  return (!String.prototype.trim)
    ? str.replace(/^[\s﻿\xA0]+|[\s﻿\xA0]+$/g, "")
    : str.trim();
}};

g.window = g;
g.marked = marked;
g.$ = {{
  extend: function () {{
    const args = Array.from(arguments);
    let deep = false;
    let target = args[0];
    let index = 1;
    if (typeof target === 'boolean') {{
      deep = target;
      target = args[1] || {{}};
      index = 2;
    }}
    for (; index < args.length; index++) {{
      const src = args[index] || {{}};
      for (const key of Object.keys(src)) {{
        const value = src[key];
        if (deep && value && typeof value === 'object' && !Array.isArray(value)) {{
          target[key] = g.$.extend(true, Array.isArray(target[key]) ? [] : (target[key] || {{}}), value);
        }} else {{
          target[key] = value;
        }}
      }}
    }}
    return target;
  }},
  inArray: function (item, arr) {{
    return arr.indexOf(item);
  }}
}};

g.editormd = {{
  $marked: marked.parse.bind(marked),
  regexs: {{
    atLink: /(@[\\w-]+)/,
    emoji: /:[^:]+:/g,
    email: /([\\w.+-]+@[\\w.-]+\\.[A-Za-z]{{2,}})/,
    emailLink: /([\\w.+-]+@[\\w.-]+\\.[A-Za-z]{{2,}})/,
    twemoji: /tw-[\\w-]+/,
    fontAwesome: /fa-[\\w-]+/,
    editormdLogo: /editormd-logo[\\w-]*/,
    pageBreak: /^\\[=+\\]$/
  }},
  classNames: {{ tex: 'tex' }},
  urls: {{ atLinkBase: '/user/' }},
  emoji: {{ path: '', ext: '' }},
  twemoji: {{ path: '', ext: '' }},
  rand: () => 1
}};

eval(helperSource);
const renderer = g.editormd.markedRenderer([], {{
  toc: false,
  tocm: false,
  tocStartLevel: 1,
  taskList: false,
  emoji: false,
  tex: false,
  pageBreak: true,
  atLink: true,
  emailLink: true,
  flowChart: false,
  sequenceDiagram: false,
  previewCodeHighlight: true
}});
const output = marked.parse(
  '> **重要提示：**校园跑执行时间通常限制在 **08:00 ~ 22:00**。',
  {{
    renderer,
    gfm: true,
    breaks: true,
    pedantic: false,
    smartLists: true,
    smartypants: true
  }}
);
process.stdout.write(output);
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(node_script)
            temp_script = handle.name

        try:
            result = subprocess.run(
                ["node", temp_script],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        finally:
            os.unlink(temp_script)

        if result.returncode != 0:
            self.fail(
                "Node markdown blockquote compatibility check failed\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        output = result.stdout
        self.assertIn("<blockquote>", output)
        self.assertIn("<strong>重要提示：</strong>", output)
        self.assertIn("<strong>08:00 ~ 22:00</strong>", output)

    def test_messages_json_blockquote_leading_bold_is_preserved(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "editormd.markedRenderer = function(markdownToC, options) {",
            "    /**\n     * 将Markdown文档解析为HTML用于前台显示",
        )
        marked_source = MARKED_PATH.read_text(encoding="utf-8")
        markdown_sample = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))[0]["content"]

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
const markedSource = {json.dumps(marked_source)};
const markdown = {json.dumps(markdown_sample)};
const projectRoot = {json.dumps(str(PROJECT_ROOT.as_posix()))};
const path = require('path');
const markedModule = require(path.join(projectRoot, 'cache/cdn/marked.js'));
const marked = markedModule.marked || markedModule;
const g = globalThis;
const trim = function(str) {{
  return (!String.prototype.trim)
    ? str.replace(/^[\s﻿\xA0]+|[\s﻿\xA0]+$/g, "")
    : str.trim();
}};

g.window = g;
g.marked = marked;
g.$ = {{
  extend: function () {{
    const args = Array.from(arguments);
    let deep = false;
    let target = args[0];
    let index = 1;
    if (typeof target === 'boolean') {{
      deep = target;
      target = args[1] || {{}};
      index = 2;
    }}
    for (; index < args.length; index++) {{
      const src = args[index] || {{}};
      for (const key of Object.keys(src)) {{
        const value = src[key];
        if (deep && value && typeof value === 'object' && !Array.isArray(value)) {{
          target[key] = g.$.extend(true, Array.isArray(target[key]) ? [] : (target[key] || {{}}), value);
        }} else {{
          target[key] = value;
        }}
      }}
    }}
    return target;
  }},
  inArray: function (item, arr) {{
    return arr.indexOf(item);
  }}
}};

g.editormd = {{
  $marked: marked.parse.bind(marked),
  regexs: {{
    atLink: /(@[\\w-]+)/,
    emoji: /:[^:]+:/g,
    email: /([\\w.+-]+@[\\w.-]+\\.[A-Za-z]{{2,}})/,
    emailLink: /([\\w.+-]+@[\\w.-]+\\.[A-Za-z]{{2,}})/,
    twemoji: /tw-[\\w-]+/,
    fontAwesome: /fa-[\\w-]+/,
    editormdLogo: /editormd-logo[\\w-]*/,
    pageBreak: /^\\[=+\\]$/
  }},
  classNames: {{ tex: 'tex' }},
  urls: {{ atLinkBase: '/user/' }},
  emoji: {{ path: '', ext: '' }},
  twemoji: {{ path: '', ext: '' }},
  rand: () => 1
}};

eval(helperSource);
const renderer = g.editormd.markedRenderer([], {{
  toc: false,
  tocm: false,
  tocStartLevel: 1,
  taskList: false,
  emoji: false,
  tex: false,
  pageBreak: true,
  atLink: true,
  emailLink: true,
  flowChart: false,
  sequenceDiagram: false,
  previewCodeHighlight: true
}});
const output = marked.parse(markdown, {{
  renderer,
  gfm: true,
  breaks: true,
  pedantic: false,
  smartLists: true,
  smartypants: true
}});
const start = output.indexOf('<blockquote');
const end = output.indexOf('</blockquote>', start) + '</blockquote>'.length;
process.stdout.write(output.slice(start, end));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(node_script)
            temp_script = handle.name

        try:
            result = subprocess.run(
                ["node", temp_script],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        finally:
            os.unlink(temp_script)

        if result.returncode != 0:
            self.fail(
                "Node messages.json blockquote compatibility check failed\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        output = result.stdout
        self.assertIn("<blockquote>", output)
        self.assertIn("<strong>08:00 ~ 22:00</strong>", output)
        self.assertIn("<strong>重要提示：</strong>", output)
        self.assertNotIn("**重要提示：**", output)

    def test_listitem_block_tokens_use_block_parser(self):
        source = EDITORMD_PATH.read_text(encoding="utf-8")
        helper_source = _extract_js_section(
            source,
            "function isMarkedInlineTokens(tokens)",
            "markedRenderer.emoji = function(text)",
        )

        node_script = f"""
const helperSource = {json.dumps(helper_source)};
const calls = [];
const renderer = {{
  parser: {{
    parse(tokens, loose) {{
      calls.push({{ method: "parse", tokens, loose }});
      return "<p><strong>bold</strong></p>\\n";
    }},
    parseInline(tokens) {{
      calls.push({{ method: "parseInline", tokens }});
      throw new Error('Token with "paragraph" type was not found.');
    }}
  }}
}};

eval(helperSource);
const result = normalizeMarkedRendererListitemArgs({{
  type: "list_item",
  task: false,
  loose: false,
  text: "**bold**",
  tokens: [{{ type: "paragraph", text: "**bold**", tokens: [{{ type: "strong", text: "bold" }}] }}]
}}, false, renderer);
process.stdout.write(JSON.stringify({{ text: result.text, task: result.task, calls }}));
"""

        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "Node listitem token compatibility check failed\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["text"], "<p><strong>bold</strong></p>\n")
        self.assertFalse(payload["task"])
        self.assertEqual([call["method"] for call in payload["calls"]], ["parse"])


if __name__ == "__main__":
    unittest.main()
