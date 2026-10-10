"""自动签到后台线程退出行为（Q1）与多账号监控回收（Q1）的测试。

覆盖"线程在自动签到关闭后永久驻留空转"这一根因：
  - _account_refresh_worker 连续多轮确认未启用后必须退出；
  - _auto_refresh_worker 同样必须退出（旧实现是 `else: pass` 后继续循环）；
  - _multi_account_monitor_worker 必须调用权威清理入口。
"""

import inspect
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import main as main_module


class _FakeUserData:
    def __init__(self, username="school-user", user_id="user-1"):
        self.username = username
        self.id = user_id
        self.name = "tester"


class TestAutoAttendanceThreadExit(unittest.TestCase):
    def test_account_refresh_worker_exits_when_attendance_disabled(self):
        """未启用自动签到时，账号刷新线程必须在有限轮次内退出。"""
        api = object.__new__(main_module.Api)
        api._init_state_variables()

        stop_event = threading.Event()
        # 让等待立即返回，避免测试真的 sleep 30 秒
        with mock.patch.object(
            main_module, "_is_auto_attendance_enabled", return_value=False
        ), mock.patch.object(
            main_module.Api,
            "_get_account_by_id",
            return_value=mock.Mock(user_data=_FakeUserData()),
        ), mock.patch.object(
            stop_event, "wait", side_effect=lambda timeout=None: False
        ):
            worker = threading.Thread(
                target=api._account_refresh_worker,
                args=("user-1", stop_event),
                daemon=True,
            )
            worker.start()
            worker.join(timeout=5)

        self.assertFalse(
            worker.is_alive(),
            "自动签到未启用时刷新线程必须退出，而不是永久驻留空转",
        )

    def test_auto_refresh_worker_exits_when_attendance_disabled(self):
        """单账号旧版刷新线程同样必须在未启用时退出。"""
        api = object.__new__(main_module.Api)
        api._init_state_variables()
        api.user_data = _FakeUserData()
        api.is_multi_account_mode = False
        api.log = mock.Mock()

        with mock.patch.object(
            main_module, "_is_auto_attendance_enabled", return_value=False
        ), mock.patch.object(
            api.stop_auto_refresh, "wait", side_effect=lambda timeout=None: False
        ):
            worker = threading.Thread(
                target=api._auto_refresh_worker, daemon=True
            )
            worker.start()
            worker.join(timeout=5)

        self.assertFalse(
            worker.is_alive(),
            "单账号刷新线程在未启用自动签到时必须退出",
        )

    def test_exit_threshold_is_greater_than_one(self):
        """阈值必须 > 1，避免配置读写瞬时抖动导致线程误退。"""
        self.assertGreater(
            main_module.AUTO_ATTENDANCE_DISABLED_ROUNDS_BEFORE_EXIT, 1
        )

    def test_monitor_worker_calls_authoritative_sweep(self):
        """多账号监控线程必须调用与登录状态无关的清理入口。"""
        source = inspect.getsource(main_module.Api._multi_account_monitor_worker)

        self.assertIn(
            "expire_stale_auto_attendance_accounts(",
            source,
            "监控线程必须调用权威清理入口，否则不在会话中的账号记录会永久驻留",
        )

    def test_session_restore_does_not_start_attendance_thread_when_disabled(self):
        """会话恢复时若没有任何账号启用自动签到，不得启动该线程。"""
        source = (
            Path(__file__).resolve().parents[1] / "session_state.py"
        ).read_text(encoding="utf-8")
        restore_block = source.split(
            "恢复多账号自动签到线程", 1
        )[1].split("logging.info(\n            f\"会话状态恢复完成", 1)[0]

        self.assertIn("if has_auto_attendance:", restore_block)
        # 线程创建必须位于 if has_auto_attendance 之内
        thread_create_index = restore_block.index(
            "api_instance.multi_auto_refresh_thread = threading.Thread("
        )
        guard_index = restore_block.index("if has_auto_attendance:")
        self.assertGreater(
            thread_create_index,
            guard_index,
            "线程创建必须在 has_auto_attendance 守卫之内",
        )


if __name__ == "__main__":
    unittest.main()
