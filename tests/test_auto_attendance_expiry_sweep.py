"""自动签到记录超时回收（Q1）的单元测试。

覆盖"自动签到账号无限期存在"的根因：
  1. 记录超时后必须被移除，且不依赖该账号当前是否登录；
  2. enabled_at 缺失/损坏/位于未来时不再豁免，一律按过期回收；
  3. 写盘失败时不留下"内存已删、磁盘仍在"的不一致；
  4. 清理必须幂等。
"""

import datetime
import json
import tempfile
import unittest
from unittest import mock

import main as main_module
import auto_attendance_config as auto_attendance_module


def _iso(minutes_ago):
    """生成 N 分钟前的 enabled_at（UTC，与 _enable_auto_attendance 同格式）。"""
    moment = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=minutes_ago
    )
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestAutoAttendanceExpirySweep(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = f"{self._tmp.name}/auto_attendance.json"
        patcher = mock.patch.object(
            main_module, "AUTO_ATTENDANCE_CONFIG_FILE", self.config_path
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_config(self, enabled_accounts):
        with open(self.config_path, "w", encoding="utf-8") as fp:
            json.dump({"enabled_accounts": enabled_accounts}, fp)

    def _read_config(self):
        with open(self.config_path, encoding="utf-8") as fp:
            return json.load(fp)

    def test_expired_record_is_removed_regardless_of_login_state(self):
        """超时记录必须被回收，即使该账号从未出现在任何会话中。"""
        self._write_config(
            {
                "orphan-account": {
                    "session_uuid": "session-x",
                    "enabled_at": _iso(60 * 24),  # 一天前，远超 120 分钟
                    "auth_username": "someone",
                }
            }
        )

        result = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["removed"], ["orphan-account"])
        self.assertTrue(result["save_ok"])
        self.assertNotIn("orphan-account", self._read_config()["enabled_accounts"])

    def test_record_within_limit_is_kept(self):
        self._write_config(
            {
                "fresh-account": {
                    "session_uuid": "session-y",
                    "enabled_at": _iso(5),
                    "auth_username": "someone",
                }
            }
        )

        result = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["removed"], [])
        self.assertIn("fresh-account", self._read_config()["enabled_accounts"])

    def test_missing_enabled_at_is_treated_as_expired(self):
        """缺少 enabled_at 不得再豁免超时检查（旧实现会永久驻留）。"""
        self._write_config({"legacy-account": {"session_uuid": "session-z"}})

        result = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(result["removed"], ["legacy-account"])
        self.assertNotIn("legacy-account", self._read_config()["enabled_accounts"])

    def test_malformed_enabled_at_is_treated_as_expired(self):
        """enabled_at 格式损坏同样按过期回收，而不是跳过检查。"""
        self._write_config(
            {"broken-account": {"session_uuid": "s", "enabled_at": "not-a-timestamp"}}
        )

        result = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(result["removed"], ["broken-account"])

    def test_future_enabled_at_is_treated_as_expired(self):
        """时间落在未来无法确认时长，同样回收（防时钟回拨导致的永久记录）。"""
        future = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_config(
            {"future-account": {"session_uuid": "s", "enabled_at": future}}
        )

        result = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(result["removed"], ["future-account"])

    def test_sweep_is_idempotent(self):
        self._write_config({"gone": {"session_uuid": "s", "enabled_at": _iso(9999)}})

        first = main_module.expire_stale_auto_attendance_accounts()
        second = main_module.expire_stale_auto_attendance_accounts()

        self.assertEqual(first["removed"], ["gone"])
        self.assertEqual(second["removed"], [])
        self.assertEqual(second["checked"], 0)

    def test_save_failure_does_not_report_removal(self):
        """写盘失败时必须报告失败并保留磁盘记录，便于下次启动重试。"""
        self._write_config({"stuck": {"session_uuid": "s", "enabled_at": _iso(9999)}})

        # 注意：必须 patch auto_attendance_config 模块内的名字，
        # main.py 里的是 re-export 的副本，patch 它不会影响实际调用点。
        with mock.patch.object(
            auto_attendance_module, "_save_auto_attendance_config", return_value=False
        ):
            result = main_module.expire_stale_auto_attendance_accounts()

        self.assertFalse(result["save_ok"])
        self.assertEqual(result["removed"], [])
        # 磁盘上的记录仍在，下次启动会重试
        self.assertIn("stuck", self._read_config()["enabled_accounts"])

    def test_disabled_event_is_emitted_to_owning_session(self):
        self._write_config(
            {
                "notify-me": {
                    "session_uuid": "session-notify",
                    "enabled_at": _iso(9999),
                }
            }
        )
        socketio = mock.Mock()

        with mock.patch.object(main_module, "socketio", socketio, create=True):
            main_module.expire_stale_auto_attendance_accounts()

        socketio.emit.assert_called_once()
        args, kwargs = socketio.emit.call_args
        self.assertEqual(args[0], "auto_attendance_updated")
        self.assertFalse(args[1]["enabled"])
        self.assertEqual(kwargs.get("room"), "session-notify")

    def test_is_auto_attendance_enabled_shares_the_same_expiry_rule(self):
        """读路径与批量回收必须使用同一套超时口径。"""
        self._write_config({"shared-rule": {"session_uuid": "s"}})  # 缺 enabled_at

        self.assertFalse(main_module._is_auto_attendance_enabled("shared-rule"))
        self.assertNotIn(
            "shared-rule", self._read_config()["enabled_accounts"]
        )

    def test_is_auto_attendance_enabled_keeps_fresh_record(self):
        self._write_config(
            {"fresh": {"session_uuid": "s", "enabled_at": _iso(1)}}
        )

        self.assertTrue(main_module._is_auto_attendance_enabled("fresh"))


if __name__ == "__main__":
    unittest.main()
