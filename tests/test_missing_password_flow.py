"""缺密码补全四阶段流程的测试。

分两层：
    - 源码级契约（本文件 TestMissingPasswordFlowContract）：断言结构与文案；
    - **行为级**（TestMissingPasswordFlowBehavior）：用 Node + 最小 DOM 桩
      真正把流程跑起来，观察它做什么。

为什么必须有行为层:
    源码级断言抓不到控制流错误。本会话已经栽过一次——测试"通过"了，
    但函数在到达待测分支之前就提前 return 了，属于假通过。
    尤其"选『补全部分』但一个都不勾选"这条边界，只能靠行为测试证明。

用户明确要求（本轮）:
    1. 缺密码账号**不限数量**，清单做成卡片可滚动，完整显示，绝不截断；
    2. 阶段 1 版式：`发现以下账号缺少密码，是否要补密码？`
       + `共 N 个账号缺少密码` + 卡片列表 + 三个按钮；
    3. 阶段 2 是勾选表格：第一列勾选框、第二列账号；
    4. 阶段 3 密码弹窗显示进度，第一个账号显示"放弃所有"、后续显示"放弃剩余 N 个"；
    5. 阶段 2 一个都不勾选要正常收尾（不得卡死、不得弹密码框）；
    6. 导入结果弹窗必须等补密码流程结束后才弹，且汇总成功/跳过/失败全部结果。
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from extract_missing_flow import (
    MAIN_JS,
    ROOT,
    extract_import_result_source,
    extract_missing_flow_source,
)


HARNESS = ROOT / "tests" / "frontend" / "missing_flow_harness.mjs"

#: 场景名 -> 说明（与 harness 中的键一一对应）
SCENARIOS = [
    "list-shows-all-without-truncation",
    "list-message-shows-exact-count",
    "fill-some-requires-selection",
    "zero-selection-flows-to-done",
    "zero-selection-fires-done-callback-exactly-once",
    "done-callback-fires-after-full-queue",
    "done-callback-fires-on-abandon",
    "done-callback-is-consumed-not-repeated",
    "no-selection-then-back-still-works",
    "selected-subset-honors-choices",
    "fill-all-enters-password-stage-with-progress",
    "second-account-abandon-label-changes",
    "abandon-all-ends-flow",
    "last-account-advance-finishes-flow",
    "empty-list-finishes-immediately",
]


class TestMissingPasswordFlowContract(unittest.TestCase):
    """源码级契约：结构、文案、关键调用。"""

    @classmethod
    def setUpClass(cls):
        cls.flow = extract_missing_flow_source()
        cls.main_js = MAIN_JS.read_text(encoding="utf-8")
        cls.index_html = (ROOT / "index.html").read_text(encoding="utf-8")

    # ── 阶段 1 ────────────────────────────────────────────────
    def test_stage1_has_three_buttons(self):
        for btn in (
            "missing-pass-abandon-all-btn",
            "missing-pass-fill-all-btn",
            "missing-pass-fill-some-btn",
        ):
            with self.subTest(btn=btn):
                self.assertIn(btn, self.flow, f"阶段 1 缺少按钮 {btn}")

    def test_stage1_title_matches_required_wording(self):
        self.assertIn(
            "发现以下账号缺少密码，是否要补密码？", self.index_html
        )

    def test_stage1_lists_all_accounts_in_scrollable_container(self):
        # 卡片列表容器 + 可滚动
        self.assertIn('id="missing-password-list"', self.index_html)
        idx = self.index_html.index('id="missing-password-list"')
        snippet = self.index_html[idx : idx + 400]
        self.assertIn("overflow-y-auto", snippet)

    def test_stage1_renders_every_account_without_cap(self):
        """不得出现"只列前 N 个"的逻辑。"""
        self.assertIn("missingQueue.forEach", self.flow)
        self.assertNotIn(".slice(0, 10)", self.flow)
        self.assertNotIn(".slice(0, 20)", self.flow)

    # ── 阶段 2 ────────────────────────────────────────────────
    def test_stage2_selection_table_has_checkbox_and_account_columns(self):
        for element in (
            'id="missing-password-select-modal"',
            'id="missing-pass-select-tbody"',
        ):
            with self.subTest(element=element):
                self.assertIn(element, self.index_html)

        # 表头两列：勾选 + 账号（用正则匹配，避免依赖换行与缩进）
        header_idx = self.index_html.index('id="missing-pass-select-tbody"')
        header_block = self.index_html[header_idx - 1200 : header_idx]
        self.assertIn("<thead", header_block)
        headers = re.findall(r"<th[^>]*>\s*([^<\s][^<]*?)\s*</th>", header_block)
        self.assertEqual(
            headers,
            ["选择", "账号"],
            f"勾选表格应有两列「选择」「账号」，实际: {headers}",
        )

    def test_every_element_flow_looks_up_exists_in_html(self):
        """流程里 $("...") 查的每个 id 都必须真的存在于 index.html。

        这里踩过坑：harness 用了错的 id（missing-password-select-tbody），
        导致表格永远渲染不出行，而契约断言却全绿——属于假通过。
        所以把"源码里引用的 id"与"HTML 里定义的 id"对起来。
        """
        referenced = set(re.findall(r'\$\("([a-z0-9-]+)"\)', self.flow))
        self.assertTrue(referenced, "未从流程源码里解析到任何 $() 引用")

        missing = sorted(
            element_id
            for element_id in referenced
            if f'id="{element_id}"' not in self.index_html
        )
        self.assertEqual(
            missing,
            [],
            f"流程引用了 index.html 中不存在的 id: {missing}",
        )

    def test_stage2_builds_checkbox_rows(self):
        self.assertIn('createElement("tr")', self.flow)
        self.assertIn('createElement("td")', self.flow)
        self.assertIn('cb.type = "checkbox"', self.flow)

    def test_stage2_select_all_and_counter(self):
        self.assertIn("missing-pass-select-all", self.flow)
        self.assertIn("missing-pass-select-count", self.flow)

    def test_stage2_confirm_reads_only_checked_accounts(self):
        self.assertIn("missingSelectSet", self.flow)
        self.assertIn("missingSelectSet.has(", self.flow)

    # ── 阶段 3 ────────────────────────────────────────────────
    def test_stage3_shows_progress_and_remaining(self):
        self.assertIn("当前进度 ", self.flow)
        self.assertIn("还有 ", self.flow)
        self.assertIn(" 个账号待补密码", self.flow)

    def test_stage3_abandon_label_switches_on_first_account(self):
        """第一个账号显示"放弃所有无密码账号"，后续显示"放弃剩余 N 个账号"。"""
        self.assertIn("放弃所有无密码账号", self.flow)
        self.assertIn("放弃剩余 ", self.flow)
        self.assertIn("missingIndex === 0", self.flow)

    # ── 收尾 ──────────────────────────────────────────────────
    def test_all_exit_paths_funnel_into_single_flush(self):
        """所有出口都必须调用 flushMissingFlowDone，否则导入结果弹窗会丢。"""
        flush_calls = len(re.findall(r"flushMissingFlowDone\(\)", self.flow))
        self.assertGreaterEqual(
            flush_calls,
            5,
            "补完/跳过到队尾/放弃剩余/放弃所有/取消 等出口都要收尾",
        )
        # 收尾函数自身要消费回调，避免重复弹出
        self.assertIn("missingFlowDoneCallback = null", self.flow)

    # ── 不限数量 ──────────────────────────────────────────────
    def test_no_truncation_anywhere_in_flow(self):
        """用户明确要求：缺密码账号不限数量，任何展示都不得截断。"""
        forbidden = [
            r"\[:20\]",
            r"\.slice\(0,\s*\d+\)",
            r"等 \$\{",
            r"等\$\{",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    re.search(pattern, self.flow),
                    f"流程里出现了截断/省略模式 {pattern}",
                )

    def test_no_such_word_as_truncation_in_import_result(self):
        result_src = extract_import_result_source()
        self.assertNotIn("等 ", result_src)
        self.assertNotIn("slice(0,", result_src)


class TestImportResultModalContract(unittest.TestCase):
    """导入结果弹窗：汇总成功/跳过/失败全部结果，且不截断。"""

    @classmethod
    def setUpClass(cls):
        cls.src = extract_import_result_source()
        cls.index_html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_renders_success_section(self):
        self.assertIn("【成功导入】", self.src)
        self.assertIn("result.added", self.src)

    def test_renders_skip_sections(self):
        self.assertIn("【已存在，未重复添加】", self.src)
        self.assertIn("【缺少密码，已跳过】", self.src)
        self.assertIn("accounts_missing_password", self.src)

    def test_renders_duplicate_and_failure_sections(self):
        self.assertIn("【文件内重复行】", self.src)
        self.assertIn("【失败】", self.src)

    def test_sections_are_scrollable_and_uncapped(self):
        self.assertIn('id="import-result-sections"', self.index_html)
        idx = self.index_html.index('id="import-result-sections"')
        self.assertIn("overflow-y-auto", self.index_html[idx : idx + 200])

    def test_import_defers_result_until_password_flow_done(self):
        main_js = MAIN_JS.read_text(encoding="utf-8")
        idx = main_js.index("async function multi_importFromExcel(")
        block = main_js[idx : idx + 2600]

        # 必须登记回调，再由流程收尾时触发；不得立刻弹
        self.assertIn("missingFlowDoneCallback = () =>", block)
        self.assertIn("startMissingPasswordFlow(", block)
        self.assertIn("flushMissingFlowDone()", block)


class TestMissingPasswordFlowBehavior(unittest.TestCase):
    """行为级：真的把流程跑起来。"""

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node:
            cls.flow_source = extract_missing_flow_source()

    def _run(self, scenario):
        if not self.node:
            self.skipTest("未找到 node")

        proc = subprocess.run(
            [self.node, str(HARNESS), self.flow_source, scenario],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertTrue(
            proc.stdout and proc.stdout.strip(),
            f"harness 无输出: rc={proc.returncode} err={(proc.stderr or '')[:400]}",
        )
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_all_scenarios_pass(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                result = self._run(scenario)
                self.assertTrue(
                    result["ok"],
                    f"{scenario} 失败：{result['detail']}",
                )

    def test_zero_selection_does_not_open_password_modal(self):
        """选「补全部分」但一个都不勾选：不得进入阶段 3。"""
        result = self._run("zero-selection-fires-done-callback-exactly-once")
        self.assertTrue(result["ok"], result["detail"])
        self.assertEqual(result["calls"]["done"], 1)

    def test_zero_selection_fires_done_callback_once(self):
        result = self._run("zero-selection-fires-done-callback-exactly-once")
        self.assertEqual(
            result["calls"]["done"],
            1,
            "收尾回调必须恰好触发一次，否则导入结果弹窗会丢失或重复",
        )

    def test_progress_text_includes_remaining(self):
        result = self._run("fill-all-enters-password-stage-with-progress")
        self.assertTrue(result["ok"], result["detail"])
        self.assertIn("还有 3 个账号待补密码", result["detail"])

    def test_second_account_uses_remaining_label(self):
        result = self._run("second-account-abandon-label-changes")
        self.assertTrue(result["ok"], result["detail"])
        self.assertIn("放弃剩余 2 个账号", result["detail"])


if __name__ == "__main__":
    unittest.main()
