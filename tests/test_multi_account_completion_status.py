import unittest

import main


class TestMultiAccountCompletionStatus(unittest.TestCase):
    def test_all_successful_tasks_report_all_complete(self):
        self.assertEqual(
            "全部完成",
            main._build_multi_account_completion_status(3, 3),
        )

    def test_all_failed_tasks_report_all_failed(self):
        self.assertEqual(
            "全部失败",
            main._build_multi_account_completion_status(3, 0),
        )

    def test_partial_success_reports_failed_task_count(self):
        self.assertEqual(
            "部分成功，2个任务失败",
            main._build_multi_account_completion_status(3, 1),
        )

    def test_no_tasks_reports_no_executable_tasks(self):
        self.assertEqual(
            "无任务可执行",
            main._build_multi_account_completion_status(0, 0),
        )


if __name__ == "__main__":
    unittest.main()
