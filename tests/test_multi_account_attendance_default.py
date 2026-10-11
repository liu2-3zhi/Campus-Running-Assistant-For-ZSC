"""多账号「完成指定次数后自动关闭」默认勾选的行为验证。

用户关心的问题:
    多账号界面的这个开关是否默认勾选。

这里不满足于"HTML 里有 checked 字样"，而是把 legacy-admin-config.js 里
真正操作该控件的代码段抽出来，在 Node 里配一个最小 DOM 桩真实执行，
覆盖三种参数状态，确认最终 checkbox 状态符合预期。
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADMIN_CONFIG_JS = ROOT / "scripts" / "legacy-admin-config.js"
INDEX_HTML = ROOT / "index.html"

MULTI_ACCOUNT_CHECKBOX_ID = "mobile-multi-auto_attendance_stop_after_success"
DATA_KEY = "auto_attendance_stop_after_success"


def _extract_binding_block() -> str:
    """抽出操作多账号自动关闭开关的完整 `if (autoAttendanceStopAfterSuccess) {...}` 块。

    用花括号配平定位结束位置，而不是匹配某个固定结尾字符串——
    后者会随代码格式微调而失效（第一次写就踩到了）。
    """
    source = ADMIN_CONFIG_JS.read_text(encoding="utf-8")
    anchor = f'const autoAttendanceStopAfterSuccess = document.getElementById('
    start = source.index(anchor)

    # 找到 `if (autoAttendanceStopAfterSuccess) {` 之后的第一个 '{'
    if_marker = "if (autoAttendanceStopAfterSuccess) {"
    if_index = source.index(if_marker, start)
    brace_start = if_index + len(if_marker) - 1  # 指向 '{'

    depth = 0
    end = brace_start
    for offset, char in enumerate(source[brace_start:], start=brace_start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = offset + 1
                break
    else:
        raise AssertionError("未找到绑定块的结束花括号")

    return source[start:end]


class TestMultiAccountAutoCloseDefaultChecked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")
        cls.block = _extract_binding_block()
        cls.node = shutil.which("node")
        cls.tmp = tempfile.mkdtemp(prefix="attendance_default_")
        cls.block_path = os.path.join(cls.tmp, "block.js")
        with open(cls.block_path, "w", encoding="utf-8") as fp:
            fp.write(cls.block)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    # ── 静态契约 ────────────────────────────────────────────
    def test_html_checkbox_has_checked_attribute(self):
        match = re.search(
            r'<input\b[^>]*?id="' + re.escape(MULTI_ACCOUNT_CHECKBOX_ID) + r'"[^>]*?>',
            self.html,
            re.S,
        )
        self.assertIsNotNone(match, "未找到多账号自动关闭控件")
        self.assertIn(
            "checked",
            match.group(0),
            "多账号「完成指定次数后自动关闭」缺少 checked 默认属性",
        )

    def test_binding_block_uses_the_same_data_key(self):
        self.assertIn(f'"{DATA_KEY}"', self.block)
        self.assertIn("mobile-multi-auto_attendance_stop_after_success", self.block)

    def test_backend_default_is_true(self):
        source = (ROOT / "api_runtime.py").read_text(encoding="utf-8")
        match = re.search(r'"auto_attendance_stop_after_success":\s*([^,\n]+)', source)
        self.assertIsNotNone(match, "后端 global_params 未定义该键")
        self.assertEqual(match.group(1).strip(), "True")

    def test_config_file_does_not_disable_it(self):
        """配置文件不得把该开关显式设为 False（那会覆盖默认勾选）。

        注意 configs/config.json 是 JSON 格式，由 config_adapter 转成
        configparser 视图，不能直接用 ConfigParser.read() 读。
        """
        import json

        config_path = ROOT / "configs" / "config.json"
        if not config_path.exists():
            self.skipTest("无 configs/config.json")

        raw = json.loads(config_path.read_text(encoding="utf-8"))
        section = raw.get("Config", {})
        if "auto_attendance_stop_after_success" not in section:
            # 未显式设置 -> 由后端默认值 True 生效，也是允许的
            return

        value = str(section["auto_attendance_stop_after_success"]).strip().lower()
        self.assertIn(
            value,
            ("true", "1", "yes", "on"),
            f"配置文件把该开关设为 {value!r}，会覆盖默认勾选",
        )

    # ── 行为验证 ────────────────────────────────────────────
    def _run_block(self, params_js):
        """在最小 DOM 桩上执行真实代码段，返回 checkbox 最终状态。"""
        if not self.node:
            self.skipTest("未找到 node")

        harness = f"""
// ── 最小 DOM 桩 ──────────────────────────────────────────
const elements = {{}};
function makeEl(id, tag) {{
  const listeners = {{}};
  return {{
    id,
    tagName: tag,
    checked: undefined,
    value: undefined,
    addEventListener(type, fn) {{ listeners[type] = fn; }},
    dispatch(type) {{ if (listeners[type]) listeners[type].call(this); }},
    _listeners: listeners,
  }};
}}

// 控件：按 index.html 的真实形态初始化（带 checked）
const checkbox = makeEl("{MULTI_ACCOUNT_CHECKBOX_ID}", "INPUT");
checkbox.type = "checkbox";
checkbox.checked = true;        // 来自 HTML 的 checked 属性
elements["{MULTI_ACCOUNT_CHECKBOX_ID}"] = checkbox;

globalThis.document = {{
  getElementById: (id) => elements[id] || null,
}};

// 其它被同一段代码引用的控件（可能不存在，代码里有 null 判断）
let updateCalls = [];
globalThis.callPythonAPI = async (method, key, value) => {{
  updateCalls.push([method, key, value]);
}};
globalThis.console = console;

// 参数对象
globalThis.pythonParams = {params_js};

// ── 执行真实代码段 ──────────────────────────────────────
{self.block}

console.log(JSON.stringify({{
  checked: checkbox.checked,
  hasChangeListener: typeof checkbox._listeners.change === "function",
}}));
"""
        harness_path = os.path.join(self.tmp, "harness.mjs")
        with open(harness_path, "w", encoding="utf-8") as fp:
            fp.write(harness)

        proc = subprocess.run(
            [self.node, harness_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        self.assertTrue(
            proc.stdout and proc.stdout.strip(),
            f"无输出: rc={proc.returncode} err={(proc.stderr or '')[:500]}",
        )
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_checked_when_params_empty_object(self):
        """pythonParams 为空对象（页面刚加载）：必须保持勾选。"""
        result = self._run_block("{}")

        self.assertTrue(
            result["checked"],
            "pythonParams 为空时不得取消勾选（undefined !== false 应为 true）",
        )

    def test_checked_when_backend_sends_true(self):
        """后端下发 True（正常路径）：必须勾选。"""
        result = self._run_block('{"auto_attendance_stop_after_success": true}')

        self.assertTrue(result["checked"])

    def test_unchecked_only_when_explicitly_false(self):
        """只有用户显式设为 False 时才取消勾选。"""
        result = self._run_block('{"auto_attendance_stop_after_success": false}')

        self.assertFalse(
            result["checked"],
            "显式 False 时必须取消勾选，否则用户无法关闭该功能",
        )

    def test_change_listener_is_registered(self):
        result = self._run_block('{"auto_attendance_stop_after_success": true}')

        self.assertTrue(
            result["hasChangeListener"],
            "必须注册 change 事件，用户切换后才会保存到后端",
        )


if __name__ == "__main__":
    unittest.main()
