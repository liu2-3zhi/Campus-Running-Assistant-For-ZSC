"""多账号收尾状态文案的契约测试。

文案形式：`状态词 (成功/总数)`，例如 `全部完成 (3/3)`。
保留状态词是为了让前端着色逻辑（getMultiAccountStatusClass）继续可辨，
补上数量是为了让"全部完成"到底完成几个任务一目了然。
"""

import unittest

import main


class TestMultiAccountCompletionStatus(unittest.TestCase):
    def test_all_successful_tasks_report_all_complete(self):
        self.assertEqual(
            "全部完成 (3/3)",
            main._build_multi_account_completion_status(3, 3),
        )

    def test_all_failed_tasks_report_all_failed(self):
        self.assertEqual(
            "全部失败 (0/3)",
            main._build_multi_account_completion_status(3, 0),
        )

    def test_partial_success_reports_both_counts(self):
        self.assertEqual(
            "部分成功 (1/3)，2个任务失败",
            main._build_multi_account_completion_status(3, 1),
        )

    def test_single_task_success(self):
        self.assertEqual(
            "全部完成 (1/1)",
            main._build_multi_account_completion_status(1, 1),
        )

    def test_no_tasks_reports_no_executable_tasks(self):
        self.assertEqual(
            "无任务可执行",
            main._build_multi_account_completion_status(0, 0),
        )

    # ── 边界与健壮性 ────────────────────────────────────────
    def test_successful_cannot_exceed_total(self):
        """成功数超过总数时应被夹紧，不能出现 5/3 这种文案。"""
        self.assertEqual(
            "全部完成 (3/3)",
            main._build_multi_account_completion_status(3, 5),
        )

    def test_negative_inputs_are_clamped(self):
        self.assertEqual(
            "无任务可执行",
            main._build_multi_account_completion_status(-1, -1),
        )

    def test_none_inputs_do_not_crash(self):
        self.assertEqual(
            "无任务可执行",
            main._build_multi_account_completion_status(None, None),
        )

    def test_status_words_are_stable_for_frontend_colouring(self):
        """前端按状态词着色，因此这些词必须始终出现在文案里。"""
        cases = [
            (3, 3, "全部完成"),
            (3, 0, "全部失败"),
            (3, 1, "部分成功"),
            (0, 0, "无任务可执行"),
        ]
        for total, success, token in cases:
            with self.subTest(token=token):
                self.assertIn(
                    token,
                    main._build_multi_account_completion_status(total, success),
                )


if __name__ == "__main__":
    unittest.main()
