"""“绕过欠费（强制执行）”权限与计费豁免的回归测试。

需求:
    1. 新增 bypass_overdue 权限，默认仅管理员/超级管理员拥有，可单独授予普通用户；
    2. 有权限时欠费弹窗出现“强制执行”；点击后校验可用执行次数，
       不足则弹警告；管理员在警告里额外有“此次不计费”；
    3. 强制执行仍然照常扣次数/生成欠费账单（次数不足也生成）；
       只有“此次不计费”才跳过扣减与账单生成（服务端仅管理员可用）；
    4. 前端三个入口（legacy 多账号、legacy 后台任务、Vue）都要把
       bypass_overdue/waive_charge 传给后端。
"""

import inspect
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import auth_system as auth_module
import main as main_module

PROJECT_ROOT = Path(main_module.__file__).resolve().parent


class PermissionDefaultsTests(unittest.TestCase):
    def test_builtin_defaults_only_admin_groups(self):
        defaults = auth_module.BUILTIN_PERMISSION_DEFAULTS["bypass_overdue"]
        self.assertEqual(
            defaults,
            {
                "guest": False,
                "user": False,
                "admin": True,
                "super_admin": True,
            },
        )

    def test_permissions_template_contains_bypass_overdue(self):
        source = inspect.getsource(main_module._create_permissions_json)
        self.assertEqual(source.count('"bypass_overdue": True'), 2)
        self.assertEqual(source.count('"bypass_overdue": False'), 2)

    def test_existing_permissions_file_is_backfilled(self):
        system = object.__new__(auth_module.AuthSystem)
        system.permissions = {
            "permission_groups": {
                group: {"name": group, "permissions": {}}
                for group in ("guest", "user", "admin", "super_admin")
            },
            "user_groups": {},
        }
        system._save_permissions = mock.Mock()

        system._ensure_builtin_permissions()

        for group, expected in (
            ("guest", False),
            ("user", False),
            ("admin", True),
            ("super_admin", True),
        ):
            self.assertEqual(
                system.permissions["permission_groups"][group]["permissions"][
                    "bypass_overdue"
                ],
                expected,
            )

    def test_get_available_runs_reads_user_file(self):
        system = object.__new__(auth_module.AuthSystem)
        with tempfile.TemporaryDirectory() as temp_dir:
            user_file = Path(temp_dir) / "user.json"
            user_file.write_text(
                json.dumps({"available_runs": 7}), encoding="utf-8"
            )
            system.get_user_file_path = lambda _u: str(user_file)
            self.assertEqual(system.get_available_runs("alice"), 7)

            user_file.write_text(
                json.dumps({"available_runs": -1}), encoding="utf-8"
            )
            self.assertEqual(system.get_available_runs("alice"), -1)

        system.get_user_file_path = lambda _u: str(
            Path(temp_dir) / "missing.json"
        )
        self.assertEqual(system.get_available_runs("alice"), 0)


class BypassPermissionResolutionTests(unittest.TestCase):
    def _api(self, group="user"):
        api = object.__new__(main_module.Api)
        api.auth_username = "alice"
        return api, group

    def test_user_without_permission_cannot_bypass(self):
        api, _ = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = False
        auth.get_user_group.return_value = "user"
        with mock.patch.multiple(
            main_module, auth_system=auth, create=True
        ):
            self.assertFalse(api._user_can_bypass_overdue())
            self.assertFalse(api._overdue_bypass_allowed(True))
            self.assertFalse(api._resolve_waive_charge(True))

    def test_non_admin_user_with_permission_can_bypass_but_not_waive(self):
        api, _ = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = True
        auth.get_user_group.return_value = "user"
        with mock.patch.multiple(
            main_module, auth_system=auth, create=True
        ):
            self.assertTrue(api._user_can_bypass_overdue())
            self.assertTrue(api._overdue_bypass_allowed(True))
            # 普通用户即使拿到绕过权限，也不能免单。
            self.assertFalse(api._resolve_waive_charge(True))

    def test_admin_can_waive_charge(self):
        api, _ = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = True
        auth.get_user_group.return_value = "admin"
        with mock.patch.multiple(
            main_module, auth_system=auth, create=True
        ):
            self.assertTrue(api._resolve_waive_charge(True))
            self.assertFalse(api._resolve_waive_charge(False))


class OverdueGateTests(unittest.TestCase):
    def _api(self, accounts=("2024050101059",)):
        api = object.__new__(main_module.Api)
        api.auth_username = "alice"
        api.log_and_notify_frontend = mock.Mock()
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        api.multi_run_stop_flag = threading.Event()
        api.multi_run_stop_flag.set()
        api._update_multi_global_buttons = mock.Mock()
        api.accounts = {
            name: mock.Mock(
                username=name, worker_thread=None, summary={}
            )
            for name in accounts
        }
        return api

    def test_multi_single_blocks_without_permission(self):
        api = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = False
        with mock.patch.multiple(
            main_module,
            auth_system=auth,
            _count_pending_bills_for_school=mock.Mock(return_value=1),
            create=True,
        ), mock.patch.object(
            api, "_payment_required_for_overdue_gate", return_value=True
        ):
            result = main_module.Api.multi_start_single_account(
                api, "2024050101059", True, True, False
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "OVERDUE_PAYMENT")

    def test_multi_single_allows_when_permission_and_force(self):
        api = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = True
        auth.get_user_group.return_value = "user"
        with mock.patch.multiple(
            main_module,
            auth_system=auth,
            _count_pending_bills_for_school=mock.Mock(return_value=1),
            create=True,
        ), mock.patch.object(
            api, "_payment_required_for_overdue_gate", return_value=True
        ), mock.patch.object(
            api, "_start_multi_account_worker", return_value=True
        ):
            result = main_module.Api.multi_start_single_account(
                api, "2024050101059", True, True, False
            )

        self.assertTrue(result["success"])
        # 普通用户有绕过权限但未申请豁免：照常扣费（不设置豁免标志）。
        self.assertFalse(api.waive_charge_active)

    def test_multi_single_admin_waive_sets_flag(self):
        api = self._api()
        auth = mock.Mock()
        auth.check_permission.return_value = True
        auth.get_user_group.return_value = "admin"
        with mock.patch.multiple(
            main_module,
            auth_system=auth,
            _count_pending_bills_for_school=mock.Mock(return_value=1),
            create=True,
        ), mock.patch.object(
            api, "_payment_required_for_overdue_gate", return_value=True
        ), mock.patch.object(
            api, "_start_multi_account_worker", return_value=True
        ):
            result = main_module.Api.multi_start_single_account(
                api, "2024050101059", True, True, True
            )

        self.assertTrue(result["success"])
        self.assertTrue(api.waive_charge_active)

    def test_multi_all_allows_when_force_authorized(self):
        api = self._api(("2024050101059", "2024050104038"))
        auth = mock.Mock()
        auth.check_permission.return_value = True
        auth.get_user_group.return_value = "admin"
        with mock.patch.multiple(
            main_module,
            auth_system=auth,
            _count_pending_bills_for_school=mock.Mock(return_value=1),
            create=True,
        ), mock.patch.object(
            api, "_payment_required_for_overdue_gate", return_value=True
        ), mock.patch.object(
            api, "_start_multi_account_threads", return_value=2
        ):
            result = main_module.Api.multi_start_all_accounts(
                api, 0, 0, False, True, False, True, True
            )

        self.assertTrue(result["success"])
        self.assertTrue(api.waive_charge_active)

    def test_multi_all_blocks_when_force_without_permission(self):
        api = self._api(("2024050101059",))
        auth = mock.Mock()
        auth.check_permission.return_value = False
        with mock.patch.multiple(
            main_module,
            auth_system=auth,
            _count_pending_bills_for_school=mock.Mock(return_value=1),
            create=True,
        ), mock.patch.object(
            api, "_payment_required_for_overdue_gate", return_value=True
        ):
            result = main_module.Api.multi_start_all_accounts(
                api, 0, 0, False, True, False, True, False
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "OVERDUE_PAYMENT")


class WaiveChargeSettlementTests(unittest.TestCase):
    def test_waive_skips_deduction_and_billing(self):
        api = object.__new__(main_module.Api)
        api.waive_charge_active = True
        api.is_offline_mode = False
        billing = mock.Mock()
        with mock.patch.multiple(
            main_module, _create_user_billing_record=billing, create=True
        ):
            main_module.Api._deduct_available_runs_or_increment_overdue_unlocked(
                api, "alice", "2024050101059"
            )
        billing.assert_not_called()


class BackendWiringTests(unittest.TestCase):
    def test_check_overdue_exposes_permission_fields(self):
        source = (PROJECT_ROOT / "web_server.py").read_text(encoding="utf-8")
        block = source.split("def check_overdue():", 1)[1].split(
            '@app.route("/api/school_account/stats"', 1
        )[0]
        self.assertIn("can_bypass_overdue", block)
        self.assertIn("is_admin", block)
        self.assertIn("available_runs", block)
        self.assertGreaterEqual(block.count('"can_bypass_overdue"'), 3)

    def test_background_route_forwards_bypass_flags(self):
        source = (PROJECT_ROOT / "web_server.py").read_text(encoding="utf-8")
        block = source.split("def start_background_task():", 1)[1].split(
            '@app.route("/api/background_task/status"', 1
        )[0]
        self.assertIn("bypass_overdue", block)
        self.assertIn("waive_charge", block)
        self.assertIn("_user_can_bypass_overdue()", block)

    def test_background_manager_supports_bypass(self):
        source = (
            PROJECT_ROOT / "background_task_manager.py"
        ).read_text(encoding="utf-8")
        block = source.split("def start_background_task(", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("bypass_overdue", block)
        self.assertIn("waive_charge", block)
        self.assertIn("_user_can_bypass_overdue()", block)


class FrontendWiringTests(unittest.TestCase):
    def _read(self, relative):
        return (PROJECT_ROOT / relative).read_text(encoding="utf-8")

    def test_legacy_modal_has_force_and_waive(self):
        payment = self._read("scripts/legacy-payment-user.js")
        self.assertIn("强制执行", payment)
        self.assertIn("此次不计费", payment)
        self.assertIn("_consumeOverdueForceOverride", payment)

        multi = self._read("scripts/legacy-multi-accounts.js")
        self.assertIn("overdueOverride.bypass_overdue", multi)
        self.assertIn("overdueOverride.waive_charge", multi)

        main_js = self._read("scripts/main.js")
        self.assertIn("_consumeOverdueForceOverride()", main_js)
        self.assertIn("...overdueOverride", main_js)

    def test_vue_modal_has_force_and_waive(self):
        payment = self._read("frontend/src/composables/usePayment.js")
        self.assertIn("强制执行", payment)
        self.assertIn("此次不计费", payment)
        self.assertIn("export function consumeOverdueForceOverride", payment)

        multi_view = self._read("frontend/src/views/MultiAccountView.vue")
        self.assertIn("consumeOverdueForceOverride", multi_view)
        self.assertIn("bypass_overdue", multi_view)
        self.assertIn("waive_charge", multi_view)

        control_tabs = self._read("frontend/src/components/main/ControlTabs.vue")
        self.assertIn("consumeOverdueForceOverride", control_tabs)
        self.assertIn("...overdueOverride", control_tabs)


if __name__ == "__main__":
    unittest.main()
