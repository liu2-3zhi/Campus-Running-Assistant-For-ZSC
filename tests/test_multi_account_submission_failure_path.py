"""多账号单任务执行体的失败路径回归测试。

背景（真实事故，来自线上 ERROR 日志）:
    提交重试全部失败时，worker 抛
    `UnboundLocalError: cannot access local variable 'task_succeeded'`
    导致整个 worker 崩溃 —— 而"提交失败"本来是一个**正常可处理**的分支，
    应该返回 "failed" 让主循环继续挑下一个任务。

    根因是把任务执行体从 _multi_account_worker 抽成
    _run_single_multi_account_task 时，结果标记 `task_succeeded` 只在
    `if submission_successful:` 的 if/else 两个分支里赋值，
    提交失败的路径会绕过整个块直达末尾的 return。

这类缺陷的判定标准：**必须真正驱动那条分支**。
只断言源码里存在 `task_succeeded = False` 是抓不到的。
"""

import inspect
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


def _make_run():
    run = main_module.RunData()
    run.run_name = "测试任务"
    run.errand_id = "e1"
    run.errand_schedule = "s1"
    run.status = 0
    run.run_coords = [(113.1, 22.1, 1000), (113.2, 22.2, 1000)]
    run.target_points = [(113.1, 22.1)]
    run.target_sequence = 0
    return run


class _FakeAcc:
    def __init__(self):
        self.username = "school-1"
        self.user_data = SimpleNamespace(
            username="school-1",
            student_id="school-1",
            id="uid-1",
            name="tester",
        )
        self.params = {
            "ignore_task_time": True,
            "interval_ms": 3000,
            "location_random_m": 1.5,
            "min_time_m": 20,
            "max_time_m": 30,
            "min_dist_m": 2000,
        }
        self.logs = []
        self.summary = {}
        self.api_client = mock.Mock()
        self.stop_event = mock.Mock()
        self.stop_event.is_set.return_value = False
        self.stop_event.wait.return_value = False
        self.current_position = None

    def log_and_notify_frontend(self, message):
        self.logs.append(str(message))


class TestFailingSubmissionPath(unittest.TestCase):
    """提交失败必须返回 "failed"，不得让 worker 崩溃。"""

    def setUp(self):
        self.api = object.__new__(main_module.Api)
        self.api._init_state_variables()
        self.api.is_multi_account_mode = True
        # 必须给一个会话 ID：路径规划前的分支会在缺它时直接 return "failed"，
        # 那样测试就永远走不到提交环节（会变成假通过）。
        self.api._web_session_id = "test-session-0001"
        self.api.multi_run_stop_flag.clear()

        self.acc = _FakeAcc()
        self.run = _make_run()

        # 让任务体拿到可用的详情与路线，快速走到提交环节
        self.acc.api_client.get_run_details.return_value = {
            "success": True,
            "data": {
                "errandDetail": {
                    "geoCoorList": [
                        {"lon": 113.1, "lat": 22.1},
                        {"lon": 113.2, "lat": 22.2},
                    ]
                }
            },
        }

        self.api._update_account_status_js = mock.Mock()
        self.api._update_multi_global_buttons = mock.Mock()
        self.api._multi_fetch_and_summarize_tasks = mock.Mock()
        self.api.check_target_reached_during_run = mock.Mock()
        self.api._finalize_run = mock.Mock(return_value=False)

        # 路线规划直接给一条可用路径
        self.api._build_route_path_with_random_detours = mock.Mock(
            return_value=[(113.1, 22.1), (113.2, 22.2)]
        )

        # 关掉提交前的真实等待
        self._sleep_patcher = mock.patch.object(
            main_module.time, "sleep", return_value=None
        )
        self._sleep_patcher.start()
        self.addCleanup(self._sleep_patcher.stop)

        # 位置推送走 socketio；测试进程里没有该对象，补一个空壳
        self._socketio_patcher = mock.patch.object(
            main_module, "socketio", mock.Mock(), create=True
        )
        self._socketio_patcher.start()
        self.addCleanup(self._socketio_patcher.stop)

    def _run_with_submission_result(self, submit_ok):
        self.api._submit_chunk_with_retries = mock.Mock(return_value=submit_ok)

        # 规划 provider 返回成功
        with mock.patch.object(
            main_module,
            "_plan_route_path_with_provider_runtime",
            return_value={"path": [{"lng": 113.1, "lat": 22.1}, {"lng": 113.2, "lat": 22.2}]},
        ), mock.patch.object(main_module, "chrome_pool", object(), create=True):
            return self.api._run_single_multi_account_task(
                self.acc, self.run, 1, "测试任务", attempted_count=1, planned_total=1
            )

    def test_failing_submission_returns_failed_instead_of_crashing(self):
        """核心回归：提交失败时不得抛 UnboundLocalError。"""
        try:
            outcome = self._run_with_submission_result(False)
        except UnboundLocalError as exc:  # pragma: no cover - 命中即为回归
            self.fail(
                f"提交失败路径仍然抛 UnboundLocalError（task_succeeded 未初始化）: {exc}"
            )

        self.assertEqual(
            outcome,
            "failed",
            "提交失败应返回 'failed' 交给主循环，而不是崩溃",
        )

    def test_failing_submission_does_not_call_finalize(self):
        """提交都没成功，不应再去向服务器确认完成。"""
        self._run_with_submission_result(False)

        self.api._finalize_run.assert_not_called()

    def test_failing_submission_logs_task_failure(self):
        self._run_with_submission_result(False)

        joined = "\n".join(self.acc.logs)
        self.assertIn("执行失败", joined)

    def test_successful_submission_still_returns_success(self):
        """成功路径不能被这次改动破坏。"""
        self.api._finalize_run = mock.Mock(return_value=True)

        outcome = self._run_with_submission_result(True)

        self.assertEqual(outcome, "success")

    def test_task_succeeded_is_initialized_before_first_use(self):
        """结构性兜底：声明必须出现在函数早期，而不是只在 if 分支里。"""
        source = inspect.getsource(
            main_module.Api._run_single_multi_account_task
        )
        # 去掉 docstring 后看代码体
        body = source.split('"""', 2)[-1]

        first_assign = body.index("task_succeeded = ")
        first_branch = body.index("if submission_successful:")

        self.assertLess(
            first_assign,
            first_branch,
            "task_succeeded 必须在进入提交结果分支之前就初始化",
        )


if __name__ == "__main__":
    unittest.main()
