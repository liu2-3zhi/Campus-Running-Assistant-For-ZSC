"""“仅执行未完成的任务”开关必须立即影响任务统计文本。

真实缺陷:
    切换开关只改了后端 multi_run_only_incomplete 标志，但账号列表里的
    「总数/完成/未开始/可跑/过期」来自 acc.summary；summary 只有在下一次
    拉取任务列表时才重算，于是勾选/取消勾选后这些数字一动不动
    （典型现象: 完成 6 / 可跑 1 / 过期 5 在切换后完全不变）。

修复契约:
    1. set_multi_run_only_incomplete() 必须立即用缓存任务重算每个账号的
       summary，并按新规则刷新状态文案，同时把最新 accounts 返回给前端；
    2. 运行中的账号只刷新统计数字，进度文案不动；
    3. 已停止/已中止/已取消等终态文案不能被开关切换覆盖；
    4. 停止任务后状态文案必须停留在“已停止”，不能被停止看门狗覆盖成“待命”。
"""

import datetime
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main as main_module

PROJECT_ROOT = Path(main_module.__file__).resolve().parent


def _task(status=0, start_offset_days=None, end_offset_days=None):
    now = datetime.datetime.now()
    start_time = (
        (now + datetime.timedelta(days=start_offset_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if start_offset_days is not None
        else ""
    )
    end_time = (
        (now + datetime.timedelta(days=end_offset_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if end_offset_days is not None
        else ""
    )
    return SimpleNamespace(
        status=status,
        start_time=start_time,
        end_time=end_time,
    )


def _build_account(username="2024050101059", status_text="待命", tasks=None):
    return SimpleNamespace(
        username=username,
        all_run_data=list(tasks or []),
        params={"ignore_task_time": True},
        summary={
            "total": 0,
            "completed": 0,
            "pending": 0,
            "not_started": 0,
            "executable": 0,
            "expired": 0,
            "att_pending": 2,
            "att_completed": 1,
            "att_expired": 0,
        },
        status_text=status_text,
        worker_thread=None,
        stop_event=threading.Event(),
        account_operation_lock=threading.Lock(),
    )


class _BaseTest(unittest.TestCase):
    def _make_api(self, accounts):
        api = object.__new__(main_module.Api)
        api.accounts = {acc.username: acc for acc in accounts}
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        api.multi_run_only_incomplete = True
        api.log_and_notify_frontend = mock.Mock()
        api._update_multi_global_buttons = mock.Mock()
        api.multi_get_all_accounts_status = lambda addition=None: {
            "success": True,
            "accounts": [
                {
                    "username": account.username,
                    "summary": dict(account.summary),
                    "status_text": account.status_text,
                }
                for account in api.accounts.values()
            ],
        }
        return api


class RunOnlyIncompleteSummaryTests(_BaseTest):
    def _six_completed_tasks(self):
        # 与真实现象一致：6 个任务全部完成，其中 5 个已过期、1 个仍在窗口内。
        return [_task(status=1, start_offset_days=-2, end_offset_days=-1)] * 5 + [
            _task(status=1, start_offset_days=-2, end_offset_days=1)
        ]

    def test_toggle_recomputes_summary_and_status_text(self):
        acc = _build_account(tasks=self._six_completed_tasks())
        api = self._make_api([acc])

        result = api.set_multi_run_only_incomplete(False)
        self.assertTrue(result["success"])
        self.assertFalse(result["run_only_incomplete"])
        self.assertEqual(acc.summary["total"], 6)
        self.assertEqual(acc.summary["completed"], 6)
        self.assertEqual(acc.summary["executable"], 1)
        self.assertEqual(acc.summary["expired"], 5)
        self.assertEqual(acc.status_text, "有 1 个任务可执行")

        result = api.set_multi_run_only_incomplete(True)
        self.assertTrue(result["success"])
        self.assertEqual(acc.summary["completed"], 6)
        self.assertEqual(acc.summary["executable"], 0)
        self.assertEqual(acc.summary["expired"], 0)
        self.assertEqual(acc.summary["not_started"], 0)
        self.assertEqual(acc.status_text, "无任务可执行")

        # 返回给前端的 accounts 必须带新 summary，前端才能立即重渲染。
        payload = {item["username"]: item for item in result["accounts"]}
        self.assertEqual(
            payload[acc.username]["summary"]["executable"], 0
        )
        # 签到统计字段不能被任务统计重算清掉。
        self.assertEqual(acc.summary["att_pending"], 2)
        self.assertEqual(acc.summary["att_completed"], 1)

    def test_toggle_keeps_stopped_status_text(self):
        acc = _build_account(
            status_text="已停止", tasks=self._six_completed_tasks()
        )
        api = self._make_api([acc])

        api.set_multi_run_only_incomplete(False)
        self.assertEqual(acc.status_text, "已停止")
        self.assertEqual(acc.summary["executable"], 1)

        api.set_multi_run_only_incomplete(True)
        self.assertEqual(acc.status_text, "已停止")

    def test_toggle_keeps_running_progress_status_text(self):
        acc = _build_account(
            status_text="正在执行 1/1: 第四次2公里跑步30分...",
            tasks=self._six_completed_tasks(),
        )
        api = self._make_api([acc])
        api.multi_active_executions.add(acc.username)

        api.set_multi_run_only_incomplete(False)

        self.assertEqual(acc.status_text, "正在执行 1/1: 第四次2公里跑步30分...")
        self.assertEqual(acc.summary["executable"], 1)

    def test_toggle_does_not_fabricate_status_for_unfetched_account(self):
        acc = _build_account(status_text="首次验证中...", tasks=[])
        api = self._make_api([acc])

        api.set_multi_run_only_incomplete(False)

        self.assertEqual(acc.status_text, "首次验证中...")
        self.assertEqual(acc.summary["total"], 0)


class StopStatusTextTests(_BaseTest):
    def test_stop_single_account_keeps_stopped_status(self):
        acc = _build_account(status_text="正在执行 1/1: 任务A")

        def worker_body():
            # 模拟真实 worker 的收尾：收到停止信号后写入“已停止”再退出。
            acc.stop_event.wait(timeout=5)
            acc.status_text = "已停止"

        worker = threading.Thread(target=worker_body, daemon=True)
        worker.start()
        acc.worker_thread = worker

        api = self._make_api([acc])
        result = api.multi_stop_single_account(acc.username)

        self.assertTrue(result["success"])
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())

        # 停止看门狗会在 worker 退出后再刷一次状态；必须保持“已停止”。
        deadline = time.time() + 3
        while time.time() < deadline and acc.worker_thread is not None:
            time.sleep(0.05)
        time.sleep(0.3)

        self.assertEqual(acc.status_text, "已停止")


class FrontendWiringTests(unittest.TestCase):
    def test_backend_returns_accounts_after_toggle(self):
        acc = _build_account(tasks=[_task(status=1, end_offset_days=1)])
        api = _BaseTest()._make_api([acc])

        result = api.set_multi_run_only_incomplete(False)

        self.assertIn("accounts", result)
        self.assertEqual(len(result["accounts"]), 1)

    def test_legacy_toggle_handler_applies_returned_accounts(self):
        source = (PROJECT_ROOT / "scripts" / "main.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('"set_multi_run_only_incomplete"', source)
        self.assertIn("renderMultiAccountList(result.accounts)", source)

    def test_vue_toggle_applies_returned_accounts(self):
        source = (
            PROJECT_ROOT / "frontend" / "src" / "views" / "MultiAccountView.vue"
        ).read_text(encoding="utf-8")
        self.assertIn("set_multi_run_only_incomplete", source)
        self.assertIn("appStore.multiAccounts = result.accounts", source)

    def test_stop_watcher_preserves_stopped_status_source(self):
        source = (
            PROJECT_ROOT / "api_runtime.py"
        ).read_text(encoding="utf-8")
        watcher_block = source.split("def _watch_stop():", 1)[1].split(
            "threading.Thread(target=_watch_stop", 1
        )[0]
        self.assertIn('status_text="已停止"', watcher_block)
        self.assertNotIn('status_text="待命"\n                    self._update_multi_global_buttons()', watcher_block)


if __name__ == "__main__":
    unittest.main()
