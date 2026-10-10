"""计费优先级（Q5）的测试。

口径（已与需求方确认）：
  第一优先级：平台（系统）账号 system_accounts/{auth}.json 的 available_runs
  第二优先级：仅当系统账号次数不足时，学校账号 overdue_count +1 并生成账单

同时覆盖日志中暴露的账号映射矛盾：
  _finalize_run 打印 "学校账号=（游客或未设置）"，而同一秒的多账号路径却
  打印了正确的学校账号，说明多账号下回退链取到了空值。
"""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


class TestBillingDeductionPriority(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.user_file = os.path.join(self._tmp.name, "zhangzhi.json")

        # 提供可用的付费配置：require_payment=true, single_run_cost=1
        config = main_module._get_default_config()
        config.set("Payment_Settings", "require_payment", "true")
        config.set("Payment_Settings", "single_run_cost", "1")

        self._patches = [
            mock.patch.object(
                main_module, "_read_config_ini", return_value=config
            ),
            # main.auth_system 由运行时装配，测试进程里可能尚未创建，
            # 因此用 create=True 补上。
            mock.patch.object(main_module, "auth_system", mock.Mock(), create=True),
            mock.patch.object(main_module, "CONFIG_JSON_FILE", "configs/config.json"),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        main_module.auth_system.get_user_file_path.return_value = self.user_file

        self.api = object.__new__(main_module.Api)
        self.api.is_offline_mode = False
        # 学校账号列表由 _load_user_school_accounts 提供，这里直接打桩
        self.school_accounts = {
            "2024080403024": {"password": "x", "overdue_count": 0}
        }
        self.api._load_user_school_accounts = mock.Mock(
            return_value=self.school_accounts
        )
        self.api._save_user_school_accounts = mock.Mock(return_value=True)

        self.billing = mock.Mock()
        self._billing_patch = mock.patch.object(
            main_module, "_create_user_billing_record", self.billing
        )
        self._billing_patch.start()
        self.addCleanup(self._billing_patch.stop)

    def _write_user(self, available_runs):
        with open(self.user_file, "w", encoding="utf-8") as fp:
            json.dump({"available_runs": available_runs}, fp)

    def _read_user(self):
        with open(self.user_file, encoding="utf-8") as fp:
            return json.load(fp)

    def test_first_priority_deducts_system_account_only(self):
        """系统账号有次数时：只扣系统账号，不产生任何欠费与账单。"""
        self._write_user(3)

        self.api._deduct_available_runs_or_increment_overdue_unlocked(
            "zhangzhi", "2024080403024"
        )

        self.assertEqual(self._read_user()["available_runs"], 2)
        self.assertEqual(
            self.school_accounts["2024080403024"]["overdue_count"],
            0,
            "第一优先级命中时不得增加学校账号欠费",
        )
        self.billing.assert_not_called()
        self.api._save_user_school_accounts.assert_not_called()

    def test_second_priority_charges_school_account_when_system_exhausted(self):
        """系统账号次数用尽：不扣系统账号，改为学校账号欠费 +1 并生成账单。"""
        self._write_user(0)

        self.api._deduct_available_runs_or_increment_overdue_unlocked(
            "zhangzhi", "2024080403024"
        )

        self.assertEqual(
            self._read_user()["available_runs"], 0, "系统账号次数已为 0，不应变成负数"
        )
        self.assertEqual(
            self.school_accounts["2024080403024"]["overdue_count"],
            1,
            "系统账号次数不足时学校账号欠费必须 +1",
        )
        self.api._save_user_school_accounts.assert_called_once()
        self.billing.assert_called_once()

    def test_unlimited_account_skips_everything(self):
        """available_runs == -1 表示无限：不扣减、不欠费、不生成账单。"""
        self._write_user(-1)

        self.api._deduct_available_runs_or_increment_overdue_unlocked(
            "zhangzhi", "2024080403024"
        )

        self.assertEqual(self._read_user()["available_runs"], -1)
        self.assertEqual(self.school_accounts["2024080403024"]["overdue_count"], 0)
        self.billing.assert_not_called()

    def test_free_mode_skips_everything(self):
        config = main_module._get_default_config()
        config.set("Payment_Settings", "require_payment", "false")
        self._write_user(0)

        with mock.patch.object(main_module, "_read_config_ini", return_value=config):
            self.api._deduct_available_runs_or_increment_overdue_unlocked(
                "zhangzhi", "2024080403024"
            )

        self.assertEqual(self.school_accounts["2024080403024"]["overdue_count"], 0)
        self.billing.assert_not_called()

    def test_offline_mode_skips_everything(self):
        self._write_user(0)
        self.api.is_offline_mode = True

        self.api._deduct_available_runs_or_increment_overdue_unlocked(
            "zhangzhi", "2024080403024"
        )

        self.assertEqual(self.school_accounts["2024080403024"]["overdue_count"], 0)
        self.billing.assert_not_called()
        self.assertEqual(self._read_user()["available_runs"], 0)

    def test_unknown_school_account_does_not_silently_succeed(self):
        """学校账号不在配置中时必须告警，而不是静默当作已扣费。"""
        self._write_user(0)

        with self.assertLogs(level="WARNING") as captured:
            self.api._deduct_available_runs_or_increment_overdue_unlocked(
                "zhangzhi", "not-in-config"
            )

        joined = "\n".join(captured.output)
        self.assertIn("not-in-config", joined)
        self.billing.assert_not_called()


class TestFinalizeRunSchoolUsernameResolution(unittest.TestCase):
    """_finalize_run 必须使用调用方显式传入的学校账号。"""

    def test_finalize_run_accepts_explicit_school_username(self):
        source = __import__("inspect").getsource(
            main_module.Api._finalize_run
        )

        self.assertIn("school_username: str = None", source)
        self.assertIn("auth_username: str = None", source)
        # 显式传参必须优先于 client.app.user_data 回退链
        self.assertIn("resolved_school_username = school_username", source)
        self.assertIn("if not resolved_school_username:", source)

    def test_skip_log_distinguishes_reason(self):
        source = __import__("inspect").getsource(
            main_module.Api._finalize_run
        )
        # 只看代码体，避免命中解释性 docstring
        body = source.split('"""', 2)[-1]

        # 旧文案把所有情况都归因于"游客或未设置"，掩盖了真实原因
        self.assertNotIn("（游客或未设置）", body)
        self.assertIn("missing_fields", body)


if __name__ == "__main__":
    unittest.main()
