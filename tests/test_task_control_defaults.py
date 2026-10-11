"""「仅执行未完成的任务」与「自动生成路径」默认勾选的契约测试。

需求:
    这两个开关都应默认勾选，避免用户直接启动时
      - 重复执行已完成的任务；
      - 任务没有路线而无法执行（自动生成路径未勾选）。

覆盖两个前端：
    - legacy 界面（index.html）
    - Vue 界面（frontend/src）
"""

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
CONTROL_TABS_PATH = (
    PROJECT_ROOT / "frontend" / "src" / "components" / "main" / "ControlTabs.vue"
)
MULTI_ACCOUNT_VIEW_PATH = (
    PROJECT_ROOT / "frontend" / "src" / "views" / "MultiAccountView.vue"
)


def _input_tag_by_id(html: str, element_id: str) -> str:
    """返回指定 id 的 <input> 完整标签文本。"""
    pattern = re.compile(
        r"<input\b[^>]*?id=\"" + re.escape(element_id) + r"\"[^>]*?>",
        re.S,
    )
    match = pattern.search(html)
    if not match:
        raise AssertionError(f"index.html 中未找到 id={element_id} 的 input")
    return match.group(0)


def _is_checked(tag: str) -> bool:
    return re.search(r"\bchecked\b", tag) is not None


class TestLegacyCheckboxDefaults(unittest.TestCase):
    """legacy 界面（index.html）的默认勾选状态。"""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_PATH.read_text(encoding="utf-8")

    def _assert_checked(self, element_id):
        tag = _input_tag_by_id(self.html, element_id)
        self.assertTrue(
            _is_checked(tag),
            f"{element_id} 应默认勾选，实际未勾选：{tag.strip()}",
        )

    def test_desktop_auto_generate_path_is_checked(self):
        self._assert_checked("auto-gen-all-check")

    def test_mobile_auto_generate_path_is_checked(self):
        self._assert_checked("mobile-auto-gen-all-check")

    def test_desktop_run_only_incomplete_is_checked(self):
        self._assert_checked("multi-run-only-incomplete-check")

    def test_mobile_run_only_incomplete_is_checked(self):
        self._assert_checked("mobile-multi-only-incomplete-check")

    def test_both_auto_generate_controls_exist(self):
        """桌面与移动端都要有该开关，否则某一端会退回旧默认。"""
        for element_id in ("auto-gen-all-check", "mobile-auto-gen-all-check"):
            with self.subTest(element_id=element_id):
                _input_tag_by_id(self.html, element_id)

    def test_auto_generate_default_does_not_invert_existing_semantics(self):
        """「运行已完成任务」是相反语义的开关，默认必须保持不勾选。"""
        self.assertFalse(_is_checked(_input_tag_by_id(self.html, "run-completed-check")))
        self.assertFalse(
            _is_checked(_input_tag_by_id(self.html, "mobile-run-completed-check"))
        )


class TestVueCheckboxDefaults(unittest.TestCase):
    """Vue 界面的默认值（两个前端需保持一致）。"""

    def test_control_tabs_auto_generate_defaults_to_true(self):
        source = CONTROL_TABS_PATH.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"const\s+autoGenAll\s*=\s*ref\(\s*true\s*\)",
            "ControlTabs.vue 的「自动生成路径」应默认勾选（ref(true)）",
        )

    def test_multi_account_view_run_only_incomplete_defaults_to_true(self):
        source = MULTI_ACCOUNT_VIEW_PATH.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"runOnlyIncomplete:\s*true",
            "MultiAccountView.vue 的「仅执行未完成的任务」应默认勾选",
        )

    def test_vue_and_legacy_defaults_agree(self):
        """两个前端的默认值必须一致，否则切换界面时行为会漂移。"""
        control_tabs = CONTROL_TABS_PATH.read_text(encoding="utf-8")
        index_html = INDEX_PATH.read_text(encoding="utf-8")

        vue_auto_gen = re.search(
            r"const\s+autoGenAll\s*=\s*ref\(\s*(true|false)\s*\)", control_tabs
        )
        self.assertIsNotNone(vue_auto_gen)

        legacy_auto_gen = _is_checked(
            _input_tag_by_id(index_html, "auto-gen-all-check")
        )

        self.assertEqual(
            vue_auto_gen.group(1) == "true",
            legacy_auto_gen,
            "Vue 与 legacy 的「自动生成路径」默认值不一致",
        )


if __name__ == "__main__":
    unittest.main()
