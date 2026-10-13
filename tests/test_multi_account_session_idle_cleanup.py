"""多账号会话空闲自动销毁的回归测试。

背景（真实故障）:
    会话不活跃监控把 multi_run_stop_flag 当成“多账号任务执行中”的标志。
    该标志只在“全部停止”时置位，账号 worker 自然跑完后不会复位，于是任何
    启动过一次任务的多账号会话都会被永久保活，不再按空闲超时销毁。

期望语义:
    多账号会话只有在“还有账号任务在进行”时才保活；“开始前等待 / 任务间
    等待”都发生在账号 worker 线程内部，因此 worker 存活即代表任务流程
    （含两种等待）仍在进行。账号 worker 全部结束后，会话按
    session_inactivity_timeout 正常空闲回收。

    不能用 has_pending_tasks 判断：该字段只表示“还有可执行任务”，账号没在
    跑时同样可能为 True，会把空闲会话永久保活。
"""

import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module

SESSION_ID = "44444444-4444-4444-8444-444444444444"
SCHOOL_USERNAME = "2024080402005"


class _FakeWorker:
    def __init__(self, alive):
        self._alive = bool(alive)

    def is_alive(self):
        return self._alive


def _build_account(
    worker=None,
    status_text="无任务可执行",
    has_pending_tasks=False,
    school_username=None,
):
    return SimpleNamespace(
        username=SCHOOL_USERNAME,
        user_data=SimpleNamespace(
            username=school_username,
            id="account-1",
            name="测试账号",
        ),
        status_text=status_text,
        worker_thread=worker,
        has_pending_tasks=has_pending_tasks,
        stop_event=threading.Event(),
        summary={},
    )


def _build_multi_session(accounts):
    session = SimpleNamespace(
        _web_session_id=SESSION_ID,
        is_authenticated=True,
        is_guest=False,
        auth_username="alice",
        auth_group="user",
        is_multi_account_mode=True,
        accounts=accounts,
        stop_run_flag=threading.Event(),
        multi_run_stop_flag=threading.Event(),
        shutdown_session_runtime=mock.Mock(),
    )
    # 多账号模式下单账号运行标志应为“已停止”；multi_run_stop_flag 模拟
    # “曾经点过全部开始”后的历史遗留状态：保持 clear 且不会自动复位。
    session.stop_run_flag.set()
    session.multi_run_stop_flag.clear()
    return session


class MultiAccountSessionIdleCleanupTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

    def _run_monitor_once(
        self,
        session,
        *,
        auto_attendance=False,
        background_task_status=None,
    ):
        """跑一轮 monitor_session_inactivity，返回清理调用与活跃时间表。"""
        cleanup_calls = []
        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                # 让 while True 循环在完成一轮检查后退出。
                raise SystemExit

        config = main_module.configparser.ConfigParser(strict=False)
        config.add_section("System")
        config.set("System", "session_monitor_check_interval", "1")
        config.set("System", "session_inactivity_timeout", "1")

        sessions = {SESSION_ID: session}
        session_activity = {SESSION_ID: time.time() - 10_000}

        manager = None
        if background_task_status is not None:
            manager = mock.Mock()
            manager.get_task_status.return_value = {
                "status": background_task_status
            }

        with mock.patch.multiple(
            main_module,
            web_sessions=sessions,
            web_sessions_lock=threading.Lock(),
            session_activity=session_activity,
            session_activity_lock=threading.Lock(),
            browsing_activity={},
            browsing_activity_lock=threading.Lock(),
            admin_view_origin_activity={},
            admin_view_origin_activity_lock=threading.Lock(),
            session_file_locks={},
            session_file_locks_lock=threading.Lock(),
            background_task_manager=manager,
            _is_auto_attendance_enabled=mock.Mock(
                return_value=auto_attendance
            ),
            cleanup_inactive_session=mock.Mock(
                side_effect=lambda sid, reason="manual": cleanup_calls.append(sid)
            ),
            _read_config_ini=mock.Mock(return_value=config),
            create=True,
        ), mock.patch.object(
            main_module.os.path, "exists", return_value=True
        ), mock.patch.object(main_module.time, "sleep", fake_sleep):
            with self.assertRaises(SystemExit):
                main_module.monitor_session_inactivity()

        self.assertEqual(sleep_calls[0], 1)
        return cleanup_calls, session_activity

    def test_workers_finished_multi_session_is_cleaned_after_idle_timeout(self):
        """账号 worker 全部结束后，多账号会话必须按空闲超时回收。"""
        session = _build_multi_session(
            {
                SCHOOL_USERNAME: _build_account(
                    worker=_FakeWorker(alive=False),
                    status_text="全部完成 (1/1)",
                    # 还有可执行任务不等于“正在进行任务”，不能让会话永久保活。
                    has_pending_tasks=True,
                )
            }
        )

        cleanup_calls, _ = self._run_monitor_once(session)

        self.assertEqual([SESSION_ID], cleanup_calls)

    def test_task_gap_wait_counts_as_running_task(self):
        """任务间等待在 worker 内进行，必须被视为进行中的任务。"""
        session = _build_multi_session(
            {
                SCHOOL_USERNAME: _build_account(
                    worker=_FakeWorker(alive=True),
                    status_text="任务间等待 300s: 下一个 2/3 · 第四次2公里跑步30分...",
                )
            }
        )

        cleanup_calls, session_activity = self._run_monitor_once(session)

        self.assertEqual([], cleanup_calls)
        self.assertGreater(session_activity[SESSION_ID], time.time() - 60)

    def test_pre_start_wait_counts_as_running_task(self):
        """开始前等待同样必须被视为进行中的任务。"""
        session = _build_multi_session(
            {
                SCHOOL_USERNAME: _build_account(
                    worker=_FakeWorker(alive=True),
                    status_text="开始前等待 45s: 待执行 1/3 个任务",
                )
            }
        )

        cleanup_calls, _ = self._run_monitor_once(session)

        self.assertEqual([], cleanup_calls)

    def test_stopping_worker_keeps_session_alive_until_thread_exits(self):
        """用户点过“全部停止”但 worker 还在收尾时，不能提前回收会话。"""
        session = _build_multi_session(
            {
                SCHOOL_USERNAME: _build_account(
                    worker=_FakeWorker(alive=True),
                    status_text="正在执行 2/3: 第四次2公里跑步30分...",
                )
            }
        )
        session.multi_run_stop_flag.set()

        cleanup_calls, _ = self._run_monitor_once(session)

        self.assertEqual([], cleanup_calls)

    def test_running_background_task_keeps_session_alive(self):
        """会话级后台任务仍在执行时不能按空闲回收。"""
        session = _build_multi_session(
            {SCHOOL_USERNAME: _build_account(worker=_FakeWorker(alive=False))}
        )

        cleanup_calls, _ = self._run_monitor_once(
            session, background_task_status="running"
        )

        self.assertEqual([], cleanup_calls)

    def test_completed_background_task_does_not_keep_session_alive(self):
        """后台任务已结束后只剩残留状态，不应继续保活。"""
        session = _build_multi_session(
            {SCHOOL_USERNAME: _build_account(worker=_FakeWorker(alive=False))}
        )

        cleanup_calls, _ = self._run_monitor_once(
            session, background_task_status="completed"
        )

        self.assertEqual([SESSION_ID], cleanup_calls)

    def test_auto_attendance_keeps_multi_session_alive(self):
        """启用自动签到的账号有常驻后台刷新线程，仍需保活。"""
        session = _build_multi_session(
            {
                SCHOOL_USERNAME: _build_account(
                    worker=_FakeWorker(alive=False),
                    school_username=SCHOOL_USERNAME,
                )
            }
        )

        cleanup_calls, _ = self._run_monitor_once(
            session, auto_attendance=True
        )

        self.assertEqual([], cleanup_calls)
