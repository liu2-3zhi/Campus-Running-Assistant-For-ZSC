"""多账号任务调度（Q2/Q3/Q4）的测试。

覆盖日志暴露的真实缺陷：
  "有 2 个待执行任务，但只完成了 1 个" —— 旧实现把启动时筛选出的任务列表
  固化成 tasks_to_run 一次性遍历，运行期间新发布的任务不会被追加。

同时覆盖：
  - 任务统计日志必须同时包含 可执行/未开始/已过期/共 四个要素；
  - 任务间隔等待必须发生在"已确认存在下一个任务"之后（用户明确要求）；
  - 退出前必须记录剩余待执行数量；
  - 同一任务不得在单次运行内被重复执行。
"""

import inspect
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


def _make_run(errand_id, schedule="s1", status=0, name=None):
    run = main_module.RunData()
    run.run_name = name or f"task-{errand_id}"
    run.errand_id = errand_id
    run.errand_schedule = schedule
    run.status = status
    run.start_time = ""
    run.end_time = ""
    return run


class _FakeAccount:
    def __init__(self, tasks):
        self.username = "school-1"
        self.user_data = SimpleNamespace(
            username="school-1", student_id="school-1", id="school-1", name="tester"
        )
        self.params = {
            "ignore_task_time": True,
            # 任务间隔压到 0，让"是否进入间隔等待"的日志可立即观察
            "task_gap_min_s": 0,
            "task_gap_max_s": 0,
        }
        self.all_run_data = list(tasks)
        self.summary = {}
        self.logs = []
        self.has_pending_tasks = False
        self.stop_event = mock.Mock()
        self.stop_event.is_set.return_value = False

    def log(self, message):
        self.logs.append(message)


class TestMultiTaskKeyAndSelection(unittest.TestCase):
    """_multi_task_key / _select_next_multi_task 的纯逻辑测试。"""

    def setUp(self):
        self.api = object.__new__(main_module.Api)

    def test_task_key_matches_summary_dedupe_fields(self):
        """去重键必须与 _multi_fetch_and_summarize_tasks 的口径一致。"""
        run = _make_run("e1", schedule="s2")
        run.start_time = "2026-01-01 08:00:00"
        run.end_time = "2026-01-01 09:00:00"

        self.assertEqual(
            self.api._multi_task_key(run),
            "e1|s2|2026-01-01 08:00:00|2026-01-01 09:00:00",
        )

    def test_task_key_distinguishes_same_errand_different_schedule(self):
        """同一 errandId 但不同 errandSchedule 必须视为不同任务。

        这正是日志中出现的场景：服务端对同一 errandId 返回了
        status=0 与 status=1 两条记录。
        """
        pending = _make_run("same", schedule="s-pending", status=0)
        done = _make_run("same", schedule="s-done", status=1)

        self.assertNotEqual(
            self.api._multi_task_key(pending),
            self.api._multi_task_key(done),
        )

    def test_selection_skips_attempted_tasks(self):
        acc = _FakeAccount([_make_run("e1"), _make_run("e2")])
        attempted = {self.api._multi_task_key(acc.all_run_data[0])}

        selected = self.api._select_next_multi_task(acc, attempted, True)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.errand_id, "e2")

    def test_selection_returns_none_when_all_attempted(self):
        acc = _FakeAccount([_make_run("e1"), _make_run("e2")])
        attempted = {self.api._multi_task_key(r) for r in acc.all_run_data}

        self.assertIsNone(self.api._select_next_multi_task(acc, attempted, True))

    def test_selection_respects_run_only_incomplete(self):
        acc = _FakeAccount([_make_run("e1", status=1)])

        self.assertIsNone(self.api._select_next_multi_task(acc, set(), True))
        self.assertIsNotNone(self.api._select_next_multi_task(acc, set(), False))

    def test_remaining_count_excludes_attempted_and_completed(self):
        acc = _FakeAccount(
            [
                _make_run("e1", status=0),
                _make_run("e2", status=0),
                _make_run("e3", status=1),
            ]
        )
        attempted = {self.api._multi_task_key(acc.all_run_data[0])}

        # e1 已尝试、e3 已完成，只剩 e2
        self.assertEqual(
            self.api._count_multi_remaining_tasks(acc, attempted, True), 1
        )


class TestTaskSummaryLogging(unittest.TestCase):
    """Q2/Q4：任务统计日志的四个要素。"""

    def setUp(self):
        self.api = object.__new__(main_module.Api)

    def test_summary_contains_all_four_elements(self):
        acc = _FakeAccount([])
        acc.summary = {
            "executable": 1,
            "not_started": 3,
            "expired": 2,
            "total": 6,
        }

        text = self.api._format_multi_task_summary(acc)

        self.assertIn("可执行 1 个", text)
        self.assertIn("未开始 3 个", text)
        self.assertIn("已过期 2 个", text)
        self.assertIn("共 6 个", text)

    def test_summary_is_logged_to_account_and_system_log(self):
        acc = _FakeAccount([])
        acc.summary = {"executable": 0, "not_started": 0, "expired": 0, "total": 0}

        with mock.patch.object(main_module.logging, "log") as log_mock:
            message = self.api._log_multi_task_summary(acc, prefix="任务统计")

        self.assertEqual(len(acc.logs), 1)
        self.assertIn("任务统计", message)
        log_mock.assert_called_once()


class TestWorkerLoopOrdering(unittest.TestCase):
    """Q3：调度循环的结构性契约（源码级断言）。"""

    @classmethod
    def setUpClass(cls):
        # 单任务执行体已抽成 _run_single_multi_account_task，
        # 调度段 + 执行体拼接才是完整的多账号执行路径
        worker = inspect.getsource(main_module.Api._multi_account_worker)
        task_body = inspect.getsource(
            main_module.Api._run_single_multi_account_task
        )
        cls.worker = worker
        cls.combined = worker + "\n" + task_body

    def test_worker_refetches_tasks_each_round(self):
        self.assertIn("while True:", self.worker)
        self.assertIn("self._multi_fetch_and_summarize_tasks(acc)", self.worker)
        self.assertIn("_select_next_multi_task(", self.worker)
        # 不得再固化任务列表后一次性遍历
        self.assertNotIn("enumerate(tasks_to_run)", self.worker)
        self.assertNotIn("for i, run_data in", self.worker)

    def test_wait_happens_only_after_next_task_is_confirmed(self):
        """先确定有新任务，再进入任务间隔等待。"""
        select_index = self.worker.index("run_data = self._select_next_multi_task(")
        none_guard_index = self.worker.index("if run_data is None:")
        gap_index = self.worker.index("if has_completed_any:")

        self.assertLess(
            select_index,
            none_guard_index,
            "必须先挑选任务再判断是否为空",
        )
        self.assertLess(
            none_guard_index,
            gap_index,
            "任务间隔等待必须位于'无任务则退出'之后，否则最后一个任务"
            "跑完还要白等一轮",
        )

    def test_worker_has_runaway_guard(self):
        self.assertIn("MULTI_WORKER_MAX_TASKS", self.worker)

    def test_worker_logs_remaining_tasks_before_exit(self):
        self.assertIn("剩余待执行", self.worker)
        self.assertIn("_count_multi_remaining_tasks(", self.worker)

    def test_worker_keeps_shared_time_evaluator_and_finalize(self):
        self.assertIn("_get_task_time_state(", self.worker)
        self.assertIn("if self._finalize_run(", self.combined)

    def test_worker_does_not_duplicate_settlement(self):
        self.assertNotIn(
            "_deduct_available_runs_or_increment_overdue(", self.combined
        )
        self.assertNotIn("_increment_completed_count(", self.combined)
        self.assertNotIn("run_data.status = 1", self.combined)

    def test_worker_passes_school_username_to_finalize(self):
        """结算必须显式传入学校账号，避免结算与计数口径矛盾的日志。"""
        self.assertIn("school_username=acc.user_data.username", self.combined)
        self.assertIn("auth_username=", self.combined)


class TestWorkerReloopBehavior(unittest.TestCase):
    """Q3 行为测试：运行期间新出现的任务必须也被执行。

    直接驱动 _multi_account_worker，把任务拉取与单任务执行体替换成桩，
    模拟"启动时只有 1 个可执行任务，跑完第 1 个之后服务端又出现 1 个"。
    旧实现（固化 tasks_to_run）只会执行第 1 个。
    """

    def setUp(self):
        self.api = object.__new__(main_module.Api)
        self.api._init_state_variables()
        self.api.is_multi_account_mode = True
        # _init_state_variables 默认把停止标志置为已设置，正常启动流程会 clear()
        self.api.multi_run_stop_flag.clear()
        # 把任务间隔压到最小，让"是否进入间隔等待"的日志可以立即观察到
        self.api.global_params["task_gap_min_s"] = 0
        self.api.global_params["task_gap_max_s"] = 0

        self.executed = []
        self.fetch_calls = 0

        # 模拟"服务端任务状态随时间变化"：
        #   phase 0: 启动时只有 1 个可执行任务
        #   phase 1: 第 1 个任务完成后，服务端发布了第 2 个可执行任务
        #   phase 2: 两个都已完成
        # 注意：worker 在一次执行中会多次拉取（每轮一次 + 结束时一次），
        # 因此拉取必须是"无副作用"的——服务端状态只能由任务完成来推进。
        self.acc = _FakeAccount([])
        self.phase = 0
        self._apply_phase()

        def fake_fetch(acc):
            self.fetch_calls += 1
            acc.all_run_data = [
                _make_run(errand_id, status=status)
                for errand_id, status in self._phase_tasks[self.phase]
            ]
            acc.summary = {
                "total": len(acc.all_run_data),
                "executable": sum(1 for r in acc.all_run_data if r.status == 0),
                "not_started": 0,
                "expired": 0,
            }

        self.api._multi_fetch_and_summarize_tasks = fake_fetch
        self.status_calls = []
        self.api._update_account_status_js = mock.Mock(
            side_effect=lambda acc, **kwargs: self.status_calls.append(kwargs)
        )
        self.api._update_multi_global_buttons = mock.Mock()

        def fake_run_task(
            acc,
            run_data,
            task_index,
            task_name_short,
            attempted_count=1,
            planned_total=None,
        ):
            self.executed.append(run_data.errand_id)
            # 任务完成后服务端状态推进
            self.phase = min(self.phase + 1, len(self._phase_tasks) - 1)
            self._apply_phase()
            return "success"

        self.api._run_single_multi_account_task = fake_run_task

    def _apply_phase(self):
        """把当前阶段的服务端任务状态写入账号对象。"""
        self.acc.all_run_data = [
            _make_run(errand_id, status=status)
            for errand_id, status in self._phase_tasks[self.phase]
        ]
        self.acc.summary = {
            "total": len(self.acc.all_run_data),
            "executable": sum(1 for r in self.acc.all_run_data if r.status == 0),
            "not_started": 0,
            "expired": 0,
        }
        # 设成"刚刚刷新过"，让 worker 直接走任务调度分支（跳过登录前置流程）
        self.acc.last_refresh_time = time.time()
        self.acc.api_client = mock.Mock()
        self.acc.device_ua = "ua"
        self.acc.is_first_login_verified = True
        self.acc.status_text = ""
        self.acc.summary = self.acc.summary

    _phase_tasks = [
        [("e1", 0)],
        [("e1", 1), ("e2", 0)],
        [("e1", 1), ("e2", 1)],
    ]

    def test_newly_published_task_is_also_executed(self):
        self.api._multi_account_worker(self.acc, 0, True)

        self.assertEqual(
            self.executed,
            ["e1", "e2"],
            "运行期间新出现的可执行任务必须也被执行（旧实现只跑启动时的快照）",
        )

    def test_exit_summary_reports_success_and_remaining(self):
        self.api._multi_account_worker(self.acc, 0, True)

        joined = "\n".join(self.acc.logs)
        self.assertIn("任务执行流程结束", joined)
        self.assertIn("成功 2", joined)
        self.assertIn("剩余待执行 0", joined)

    def test_task_gap_is_applied_only_between_tasks(self):
        """任务间隔只能在"已确认还有下一个任务"之后发生。

        统计"进入任务间隔等待"的日志条数：第 1 个任务前不等待，
        两个任务之间等待 1 次，全部跑完后不再等待。
        """
        gap_logs = []
        original_log = self.acc.log

        def capture(message):
            if "进入任务间隔等待" in message:
                gap_logs.append(message)
            original_log(message)

        self.acc.log = capture
        self.api._multi_account_worker(self.acc, 0, True)

        self.assertEqual(self.executed, ["e1", "e2"])
        self.assertEqual(
            len(gap_logs),
            1,
            "只应在'已确认存在下一个任务'时等待一次；第一任务前与结束后都不等待",
        )

    def test_no_wait_when_no_next_task(self):
        """只有一个任务时不得进入间隔等待。"""
        self._phase_tasks = [[("only", 0)], [("only", 1)]]
        self.phase = 0
        self._apply_phase()

        gap_logs = []
        original_log = self.acc.log

        def capture(message):
            if "进入任务间隔等待" in message:
                gap_logs.append(message)
            original_log(message)

        self.acc.log = capture
        self.api._multi_account_worker(self.acc, 0, True)

        self.assertEqual(self.executed, ["only"])
        self.assertEqual(
            gap_logs, [], "没有下一个任务时不得等待（否则最后一个任务跑完还要白等）"
        )

    def test_no_executable_tasks_sets_terminal_status(self):
        """跳过已完成任务后没有可执行项时，不能把状态留在待命。"""
        self._phase_tasks = [[("already-done", 1)]]
        self.phase = 0
        self._apply_phase()
        self.acc.status_text = "待命"

        def update_status(acc, status_text=None, **kwargs):
            if status_text is not None:
                acc.status_text = status_text

        self.api._update_account_status_js = mock.Mock(side_effect=update_status)

        self.api._multi_account_worker(self.acc, 0, True)

        self.assertEqual(self.acc.status_text, "无任务可执行")

    def test_aborted_task_stops_scheduling(self):
        def abort_task(
            acc,
            run_data,
            task_index,
            task_name_short,
            attempted_count=1,
            planned_total=None,
        ):
            self.executed.append(run_data.errand_id)
            return "aborted"

        self.api._run_single_multi_account_task = abort_task
        self.api._multi_account_worker(self.acc, 0, True)

        self.assertEqual(
            self.executed, ["e1"], "被中止后不得继续挑下一个任务"
        )

    def test_task_start_sets_running_status_with_task_name(self):
        """任务真正开始执行时必须改写状态文案。

        否则状态栏会停留在启动延迟/任务间隔的旧文案（例如"延迟 0s"），
        管理员查看他人会话时看到的也是这个字段，会误以为任务没在跑。
        """
        self.api._multi_account_worker(self.acc, 0, True)

        status_updates = [
            call.kwargs.get("status_text")
            for call in self.api._update_account_status_js.call_args_list
            if call.kwargs.get("status_text")
        ]
        running_updates = [
            text for text in status_updates if text.startswith("正在执行")
        ]

        self.assertEqual(
            len(running_updates),
            len(self.executed),
            "每个被调度的任务都要先进入'正在执行'状态",
        )
        for name in ("task-e1", "task-e2"):
            self.assertTrue(
                any(name in text for text in running_updates),
                f"状态文案必须带上任务名 {name}: {running_updates}",
            )

    def test_running_status_includes_planned_sequence(self):
        """计划执行多个任务时，状态栏显示"正在执行 i/n: 任务名"。"""
        self._phase_tasks = [
            [("e1", 0), ("e2", 0), ("e3", 0)],
            [("e1", 1), ("e2", 0), ("e3", 0)],
            [("e1", 1), ("e2", 1), ("e3", 0)],
            [("e1", 1), ("e2", 1), ("e3", 1)],
        ]
        self.phase = 0
        self._apply_phase()

        self.api._multi_account_worker(self.acc, 0, True)

        running_updates = [
            call.kwargs.get("status_text")
            for call in self.api._update_account_status_js.call_args_list
            if str(call.kwargs.get("status_text") or "").startswith("正在执行")
        ]

        self.assertEqual(self.executed, ["e1", "e2", "e3"])
        self.assertEqual(running_updates[0], "正在执行 1/3: task-e1")
        self.assertEqual(running_updates[1], "正在执行 2/3: task-e2")
        self.assertEqual(running_updates[2], "正在执行 3/3: task-e3")

    def test_running_progress_text_uses_planned_total(self):
        """进度文案的分母用计划任务数，而不是恒等于当前序号。"""
        self._phase_tasks = [
            [("e1", 0), ("e2", 0)],
            [("e1", 1), ("e2", 0)],
            [("e1", 1), ("e2", 1)],
        ]
        self.phase = 0
        self._apply_phase()

        self.api._multi_account_worker(self.acc, 0, True)

        progress_texts = [
            call.kwargs.get("progress_text")
            for call in self.api._update_account_status_js.call_args_list
            if call.kwargs.get("progress_text")
        ]

        self.assertTrue(
            any(text.startswith("运行 1/2:") for text in progress_texts),
            progress_texts,
        )

    def test_status_update_works_without_socketio(self):
        """没有 socketio 时也必须更新内存状态：轮询接口读的就是它。"""
        self.acc.status_text = "延迟 0s"

        with mock.patch.object(main_module, "socketio", None, create=True):
            main_module.Api._update_account_status_js(
                self.api, self.acc, status_text="正在执行: x"
            )

        self.assertEqual(self.acc.status_text, "正在执行: x")

    def test_task_start_clears_stale_delay_status(self):
        """启动延迟结束后不得把"延迟 0s"留在状态栏。"""
        self.acc.status_text = "延迟 0s"

        self.api._multi_account_worker(self.acc, 0, True)

        final_status = self.acc.status_text
        self.assertNotIn("延迟", final_status)


class TestMultiAccountStatusTextContract(unittest.TestCase):
    """状态文案契约：两种等待必须可区分，且带上进度与下一个任务名。

    旧文案只有裸的 `延迟 12s` 与 `等待 300s`：
    分不清是"开跑前等"还是"两个任务之间等"，也看不出后面还有没有任务、
    点的是第几个任务。
    """

    @classmethod
    def setUpClass(cls):
        cls.source = inspect.getsource(main_module.Api._multi_account_worker)

    def test_two_wait_texts_are_distinct(self):
        self.assertIn("开始前等待", self.source)
        self.assertIn("任务间等待", self.source)

    def test_bare_wait_texts_are_gone(self):
        self.assertNotIn('status_text=f"延迟 {delay_remaining', self.source)
        self.assertNotIn('status_text=f"等待 {remaining', self.source)

    def test_wait_texts_carry_progress_and_next_task(self):
        self.assertIn("待执行 {next_task_index}/", self.source)
        self.assertIn("下一个 {next_task_index}/", self.source)
        self.assertIn("next_task_name", self.source)

    def test_running_status_reuses_shared_name_shortening(self):
        """等待态与执行态必须显示同一个任务名。"""
        self.assertIn(
            "next_task_name = self._shorten_task_name_for_status(", self.source
        )
        self.assertIn("task_name_for_status = next_task_name", self.source)

    def test_shorten_helper(self):
        api = object.__new__(main_module.Api)

        self.assertEqual(api._shorten_task_name_for_status("短任务"), "短任务")
        self.assertEqual(
            api._shorten_task_name_for_status("a" * 30), "a" * 24 + "..."
        )
        self.assertEqual(api._shorten_task_name_for_status(None), "")


class TestWaitStatusTextsBehavior(unittest.TestCase):
    """真正驱动 worker，抓取它发出的等待文案。"""

    def setUp(self):
        self.api = object.__new__(main_module.Api)
        self.api._init_state_variables()
        self.api.is_multi_account_mode = True
        self.api.multi_run_stop_flag.clear()
        # 间隔取极小正数：等待循环至少执行一轮以便观察文案，又几乎不耗时
        self.api.global_params["task_gap_min_s"] = 0.4
        self.api.global_params["task_gap_max_s"] = 0.4
        self.api._update_multi_global_buttons = mock.Mock()

    def _run(self, phases, delay=0.0):
        acc = _FakeAccount([])
        acc.params.update({"task_gap_min_s": 0.4, "task_gap_max_s": 0.4})
        acc.api_client = mock.Mock()
        acc.device_ua = "ua"
        acc.is_first_login_verified = True
        acc.status_text = ""
        # 满足 skip_refresh：刚刷新过 + 已有任务数据，
        # 否则 worker 会先走去登录流程，而不是直接进入任务调度。
        acc.last_refresh_time = time.time()
        acc.all_run_data = [_make_run("placeholder", status=1)]

        state = {"phase": 0}

        def fake_fetch(target):
            target.all_run_data = [
                _make_run(eid, status=status)
                for eid, status in phases[state["phase"]]
            ]
            target.summary = {
                "total": len(target.all_run_data),
                "executable": sum(
                    1 for r in target.all_run_data if r.status == 0
                ),
                "not_started": 0,
                "expired": 0,
            }

        self.api._multi_fetch_and_summarize_tasks = fake_fetch

        def fake_task(target, rd, ti, tn, attempted_count=1, planned_total=None):
            state["phase"] = min(state["phase"] + 1, len(phases) - 1)
            fake_fetch(target)
            return "success"

        self.api._run_single_multi_account_task = fake_task

        seen = []
        self.api._update_account_status_js = mock.Mock(
            side_effect=lambda _acc, **kw: seen.append(kw.get("status_text"))
        )
        self.api._multi_account_worker(acc, delay, True)
        return seen

    def test_gap_wait_text_is_specific(self):
        texts = self._run(
            [
                [("e1", 0)],
                [("e1", 1), ("e2", 0)],
                [("e1", 1), ("e2", 1)],
            ]
        )

        gap_texts = [t for t in texts if t and "任务间等待" in t]
        self.assertTrue(gap_texts, f"未出现任务间等待文案；实际: {texts}")
        self.assertIn(
            "下一个 2/", gap_texts[0], f"应指明下一个是第 2 个任务: {gap_texts[0]}"
        )
        self.assertIn("·", gap_texts[0], f"应带上任务名: {gap_texts[0]}")

    def test_delay_wait_text_is_specific(self):
        texts = self._run([[("e1", 0)], [("e1", 1)]], delay=1.4)

        delay_texts = [t for t in texts if t and "开始前等待" in t]
        self.assertTrue(delay_texts, f"未出现开始前等待文案；实际: {texts}")
        self.assertIn("待执行 1/", delay_texts[0])

    def test_no_gap_wait_text_when_no_next_task(self):
        texts = self._run([[("only", 0)], [("only", 1)]])

        self.assertFalse(
            [t for t in texts if t and "任务间等待" in t],
            "没有下一个任务时不应出现任务间等待文案",
        )



if __name__ == "__main__":
    unittest.main()
