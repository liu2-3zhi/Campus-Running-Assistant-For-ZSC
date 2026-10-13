"""multi_run_stop_flag 生命周期回归测试。

背景（真实故障）:
    多账号会话此前不会自动销毁。根因是 multi_run_stop_flag 只在
    multi_stop_all_accounts() 里置位：账号 worker 自然跑完后标志一直保持
    clear，会话不活跃监控把它永久当成“多账号任务执行中”，不会按空闲超时
    回收。

期望语义:
    multi_run_stop_flag 必须真实反映“是否还有多账号任务在跑”：
    - 启动账号 worker 时清空；
    - 最后一个账号 worker 退出后恢复置位；
    - 启动尝试里一个账号都没跑起来（worker.start 失败 / 全部账号都没启动）
      时同样要恢复置位，不能留下“假运行”。
"""

import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import api_runtime
import main


class _StartFailingThread(threading.Thread):
    """start() 直接失败的真实 Thread 子类，用于覆盖启动异常分支。"""

    def start(self):
        raise RuntimeError("worker start failed")


def _new_api():
    api = object.__new__(main.Api)
    api.auth_username = "owner"
    api.accounts = {}
    api.multi_execution_lock = threading.RLock()
    api.multi_active_executions = set()
    api.multi_run_stop_flag = threading.Event()
    api.multi_run_stop_flag.set()
    api.multi_login_lock = threading.Semaphore(20)
    api.log = mock.Mock()
    api._update_multi_global_buttons = mock.Mock()
    api._payment_required_for_overdue_gate = mock.Mock(return_value=False)
    return api


def _new_account(api, username):
    acc = SimpleNamespace(
        username=username,
        user_data=SimpleNamespace(
            username=f"school-{username}",
            student_id=f"sid-{username}",
        ),
        account_operation_lock=threading.Lock(),
        stop_event=threading.Event(),
        worker_thread=None,
        has_pending_tasks=False,
        summary={},
        status_text="待命",
    )
    api.accounts[username] = acc
    return acc


class MultiRunStopFlagLifecycleTests(unittest.TestCase):
    def _start_blocking_worker(self, api, acc, release_event):
        api._multi_account_worker = (
            lambda _acc, _delay, _run_only_incomplete: release_event.wait(
                timeout=5
            )
        )
        started = api._start_multi_account_worker(acc, 0, True)
        self.assertTrue(started)
        worker = acc.worker_thread
        self.assertIsNotNone(worker)
        self.assertTrue(worker.is_alive())

        def _cleanup():
            release_event.set()
            worker.join(timeout=5)

        self.addCleanup(_cleanup)
        return worker

    def test_flag_returns_to_stopped_after_last_worker_finishes(self):
        """worker 自然跑完后 multi_run_stop_flag 必须恢复置位。"""
        api = _new_api()
        acc = _new_account(api, "student-a")
        release_event = threading.Event()

        worker = self._start_blocking_worker(api, acc, release_event)
        self.assertFalse(
            api.multi_run_stop_flag.is_set(),
            "启动账号 worker 后 multi_run_stop_flag 必须清空",
        )

        release_event.set()
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertTrue(
            api.multi_run_stop_flag.is_set(),
            "最后一个账号 worker 退出后 multi_run_stop_flag 必须恢复置位",
        )
        self.assertEqual(set(), set(api.multi_active_executions))
        self.assertIsNone(acc.worker_thread)

    def test_flag_stays_clear_until_last_worker_finishes(self):
        """还有账号 worker 存活时不能恢复“已停止”。"""
        api = _new_api()
        acc_a = _new_account(api, "student-a")
        acc_b = _new_account(api, "student-b")
        release_a = threading.Event()
        release_b = threading.Event()
        release_events = {
            "student-a": release_a,
            "student-b": release_b,
        }
        api._multi_account_worker = (
            lambda acc, _delay, _done: release_events[acc.username].wait(
                timeout=5
            )
        )

        self.assertTrue(api._start_multi_account_worker(acc_a, 0, True))
        self.assertTrue(api._start_multi_account_worker(acc_b, 0, True))
        workers = [acc_a.worker_thread, acc_b.worker_thread]

        def _cleanup():
            release_a.set()
            release_b.set()
            for worker in workers:
                if worker is not None:
                    worker.join(timeout=5)

        self.addCleanup(_cleanup)
        self.assertFalse(api.multi_run_stop_flag.is_set())

        release_a.set()
        acc_a.worker_thread.join(timeout=5)
        self.assertFalse(
            api.multi_run_stop_flag.is_set(),
            "还有账号 worker 在跑时不能把标志恢复成“已停止”",
        )

        release_b.set()
        acc_b.worker_thread.join(timeout=5)
        self.assertTrue(api.multi_run_stop_flag.is_set())

    def test_failed_worker_start_restores_stopped_flag(self):
        """worker.start 抛异常时不能留下已清空的“假运行”标志。"""
        api = _new_api()
        acc = _new_account(api, "student-a")
        api._multi_account_worker = mock.Mock()

        with mock.patch.object(
            api_runtime.threading, "Thread", _StartFailingThread
        ):
            with self.assertRaises(RuntimeError):
                api._start_multi_account_worker(acc, 0, True)

        self.assertTrue(api.multi_run_stop_flag.is_set())
        self.assertEqual(set(), set(api.multi_active_executions))
        self.assertIsNone(acc.worker_thread)

    def test_zero_started_start_all_restores_stopped_flag(self):
        """“全部开始”一个账号都没启动时必须恢复置位。"""
        api = _new_api()
        _new_account(api, "student-a")
        api._start_multi_account_threads = mock.Mock(return_value=0)

        result = api.multi_start_all_accounts(0, 0, False, True)

        self.assertFalse(result["success"])
        self.assertTrue(
            api.multi_run_stop_flag.is_set(),
            "没有任何账号真正启动时 multi_run_stop_flag 必须恢复置位",
        )

    def test_zero_started_start_all_keeps_flag_clear_while_other_worker_runs(self):
        """已有账号 worker 在跑时，“没启动新账号”不能把标志置位。"""
        api = _new_api()
        running_acc = _new_account(api, "student-a")
        _new_account(api, "student-b")
        release_event = threading.Event()

        worker = self._start_blocking_worker(api, running_acc, release_event)
        api._start_multi_account_threads = mock.Mock(return_value=0)

        result = api.multi_start_all_accounts(0, 0, False, True)

        self.assertFalse(result["success"])
        self.assertFalse(
            api.multi_run_stop_flag.is_set(),
            "仍有账号 worker 在跑时不能把标志恢复成“已停止”",
        )

        release_event.set()
        worker.join(timeout=5)
        self.assertTrue(api.multi_run_stop_flag.is_set())
