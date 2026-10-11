"""多账号状态文案 -> 颜色映射的契约测试。

为什么需要:
    `getMultiAccountStatusClass` 原本用整串相等判断 `"全部完成"` / `"全部失败"`。
    状态文案补上数量后（`全部完成 (3/3)`），整串相等会失配，
    绿色/红色/琥珀色语义静默丢失，全部掉进默认的天蓝色。

    这里抽出真实函数在 Node 里执行，而不是在 Python 里复刻一份判断逻辑——
    复刻的那份不会随前端代码一起改变，等于没测。
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MULTI_ACCOUNTS_JS = ROOT / "scripts" / "legacy-multi-accounts.js"

# (状态文案, 期望包含的颜色类)
CASES = [
    ("全部完成 (3/3)", "text-emerald-700"),
    ("全部完成 (1/1)", "text-emerald-700"),
    ("全部失败 (0/3)", "text-red-700"),
    ("部分成功 (1/3)，2个任务失败", "text-amber-700"),
    ("无任务可执行", "text-slate-500"),
    ("开始前等待 45s: 待执行 1/3 个任务", "text-amber-700"),
    ("任务间等待 300s: 下一个 2/3 · 第四次2公里跑步30分...", "text-amber-700"),
    ("正在执行 1/3: 第四次2公里跑步30分钟内完成", "text-sky-600"),
    ("正在执行: 单任务", "text-sky-600"),
    ("运行 2/3: 第四次2公里...", "text-sky-600"),
    ("已中止", "text-amber-700"),
    ("执行出错", "text-amber-700"),
]


def _extract_status_class_function() -> str:
    """抽出 getMultiAccountStatusClass 的真实函数体。"""
    source = MULTI_ACCOUNTS_JS.read_text(encoding="utf-8")
    anchor = "function getMultiAccountStatusClass"
    start = source.index(anchor)
    # 用花括号配平找到函数结束，避免依赖后续函数的写法
    brace = source.index("{", start)
    depth = 0
    for offset in range(brace, len(source)):
        char = source[offset]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError("未找到 getMultiAccountStatusClass 的结束花括号")


class TestMultiAccountStatusClassMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        cls.function_source = _extract_status_class_function()

    def _evaluate(self, texts):
        if not self.node:
            self.skipTest("未找到 node")

        script = (
            f"{self.function_source}\n"
            f"const texts = {json.dumps(texts, ensure_ascii=False)};\n"
            "console.log(JSON.stringify(texts.map((t) => getMultiAccountStatusClass(t))));\n"
        )
        proc = subprocess.run(
            [self.node, "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        self.assertTrue(
            proc.stdout and proc.stdout.strip(),
            f"node 无输出: rc={proc.returncode} err={(proc.stderr or '')[:400]}",
        )
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_function_uses_contains_not_exact_match(self):
        """必须用 includes/contains 匹配，否则带数量的文案会失配。"""
        self.assertIn("includes(", self.function_source)
        self.assertNotIn('=== "全部完成"', self.function_source)
        self.assertNotIn('=== "全部失败"', self.function_source)

    def test_all_status_texts_map_to_expected_colour(self):
        texts = [text for text, _ in CASES]
        classes = self._evaluate(texts)

        self.assertEqual(len(classes), len(texts))
        for (text, expected), actual in zip(CASES, classes):
            with self.subTest(text=text):
                self.assertIn(
                    expected,
                    actual,
                    f"'{text}' 应包含 {expected}，实际 {actual}",
                )

    def test_every_status_text_gets_a_class(self):
        """任何文案都必须返回完整的基础类，不能返回空值。"""
        texts = [text for text, _ in CASES]
        classes = self._evaluate(texts)

        for text, actual in zip(texts, classes):
            with self.subTest(text=text):
                self.assertIn("status-text", actual)
                self.assertTrue(actual.strip())


if __name__ == "__main__":
    unittest.main()
