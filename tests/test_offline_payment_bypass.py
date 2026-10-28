"""离线 / 免费模式必须跳过欠费检查与支付订单结算。

覆盖四处门禁：
1. ``Api._payment_required_for_overdue_gate``（单任务 / 全部任务 / 多账号共用）
2. ``Api._deduct_available_runs_or_increment_overdue_unlocked``（任务完成后扣次数/记欠费）
3. ``BackgroundTaskManager.start_background_task``（后台任务启动）
4. ``web_server`` 接口级欠费校验
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import api_runtime  # noqa: E402
from api_runtime import Api  # noqa: E402


def _make_runtime(offline=False):
    runtime = Api.__new__(Api)
    runtime.params = {}
    runtime.is_offline_mode = offline
    runtime.log_and_notify_frontend = lambda *args, **kwargs: None
    return runtime


class _ConfigStub:
    def __init__(self, require_payment=True, single_run_cost=1.0):
        self._require_payment = str(require_payment).lower()
        self._single_run_cost = str(single_run_cost)

    def getboolean(self, section, option, fallback=True):
        if option == "require_payment":
            return self._require_payment == "true"
        return fallback

    def getfloat(self, section, option, fallback=1.0):
        if option == "single_run_cost":
            return float(self._single_run_cost)
        return fallback


class TestOfflinePaymentBypass(unittest.TestCase):
    def test_offline_mode_disables_overdue_gate(self):
        runtime = _make_runtime(offline=True)
        with mock.patch.object(
            api_runtime._main(), "_read_config_ini", return_value=_ConfigStub(True)
        ):
            self.assertFalse(runtime._payment_required_for_overdue_gate())

    def test_online_paid_mode_keeps_overdue_gate(self):
        runtime = _make_runtime(offline=False)
        with mock.patch.object(
            api_runtime._main(), "_read_config_ini", return_value=_ConfigStub(True)
        ):
            self.assertTrue(runtime._payment_required_for_overdue_gate())

    def test_free_mode_disables_overdue_gate(self):
        runtime = _make_runtime(offline=False)
        with mock.patch.object(
            api_runtime._main(), "_read_config_ini", return_value=_ConfigStub(False)
        ):
            self.assertFalse(runtime._payment_required_for_overdue_gate())

    def test_offline_mode_skips_billing_settlement(self):
        """离线模式不得读取/修改用户账户文件（即不产生订单与欠费）。"""
        runtime = _make_runtime(offline=True)
        with mock.patch.object(
            api_runtime._main(), "auth_system", None, create=True
        ), mock.patch.object(
            api_runtime._main(), "_read_config_ini", return_value=_ConfigStub(True)
        ):
            # 离线模式应在读取 auth_system 之前直接返回；若未短路会走到
            # "auth_system 未初始化" 分支，这里通过断言不抛异常且无副作用即可
            runtime._deduct_available_runs_or_increment_overdue_unlocked("admin", "2024030101054")

    def test_offline_settlement_returns_before_touching_user_file(self):
        runtime = _make_runtime(offline=True)
        opened = []
        real_open = open

        def _tracking_open(path, *args, **kwargs):
            opened.append(str(path))
            return real_open(path, *args, **kwargs)

        with mock.patch.object(
            api_runtime._main(), "_read_config_ini", return_value=_ConfigStub(True)
        ), mock.patch("builtins.open", _tracking_open):
            runtime._deduct_available_runs_or_increment_overdue_unlocked(
                "admin", "2024030101054"
            )
        self.assertEqual(opened, [], f"离线模式不应打开任何文件: {opened}")

    def test_background_task_manager_skips_overdue_check_when_offline(self):
        import background_task_manager as btm

        source = Path(btm.__file__).read_text(encoding="utf-8")
        block = source.split("def start_background_task(", 1)[1].split(
            "def _execute_tasks_background(", 1
        )[0]
        self.assertIn('getattr(api_instance, "is_offline_mode", False)', block)
        self.assertIn("离线测试模式，跳过欠费拦截", block)

    def test_web_server_skips_overdue_check_when_offline(self):
        import web_server as ws

        source = Path(ws.__file__).read_text(encoding="utf-8")
        route_index = source.index("def start_background_task():")
        block = source[route_index : route_index + 4000]
        self.assertIn('getattr(api_instance, "is_offline_mode", False)', block)
        self.assertIn("require_payment = False", block)

    def test_background_start_explicit_empty_scope_does_not_expand_to_all_accounts(self):
        import web_server as ws

        source = Path(ws.__file__).read_text(encoding="utf-8")
        route_index = source.index("def start_background_task():")
        block = source[route_index : route_index + 5000]
        self.assertIn('"school_username" in data or "school_usernames" in data', block)
        self.assertIn("if not target_usernames and not scope_supplied", block)
        self.assertIn("if target_usernames", block)

    def test_frontend_overdue_check_short_circuits_when_offline(self):
        source = (
            PROJECT_ROOT / "scripts" / "legacy-payment-user.js"
        ).read_text(encoding="utf-8")
        block = source.split("async function _isPaymentRequiredForOverdueCheck()", 1)[1]
        block = block.split("\n}", 1)[0]
        self.assertIn('await ensureLegacyBusinessMode()', block)
        self.assertIn("return false", block)
        # Runtime behavior, NULL scopes and stale-session responses are covered
        # by tests/offline_frontend_state.test.mjs for both frontends.


if __name__ == "__main__":
    unittest.main()
