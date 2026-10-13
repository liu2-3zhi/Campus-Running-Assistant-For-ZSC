"""密码可见权限（Q6）的测试。

权限分两层（高 → 低）：
  auto_fill_password              —— 可看所有认证用户的所有学校账号密码
  view_school_account_passwords   —— 只看当前登录系统账号自己关联的学校账号密码
  两者皆无                        —— 不下发任何密码
"""

import inspect
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module
import auth_system as auth_system_module


class TestResolvePasswordVisibility(unittest.TestCase):
    def _make_auth_system(self, group="user", permissions=None):
        system = object.__new__(auth_system_module.AuthSystem)
        system.permissions = {"permission_groups": {}, "user_groups": {}}
        system.get_user_group = mock.Mock(return_value=group)
        system.check_permission = mock.Mock(
            side_effect=lambda _user, perm: bool((permissions or {}).get(perm, False))
        )
        return system

    def test_admin_group_gets_all(self):
        system = self._make_auth_system(group="admin")

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_ALL,
        )

    def test_super_admin_group_gets_all(self):
        system = self._make_auth_system(group="super_admin")

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_ALL,
        )

    def test_auto_fill_password_gets_all(self):
        system = self._make_auth_system(
            group="user", permissions={"auto_fill_password": True}
        )

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_ALL,
        )

    def test_new_permission_gets_own_scope(self):
        system = self._make_auth_system(
            group="user", permissions={"view_school_account_passwords": True}
        )

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_OWN,
        )

    def test_no_permission_gets_none(self):
        system = self._make_auth_system(group="user")

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_NONE,
        )

    def test_auto_fill_takes_precedence_over_own_permission(self):
        system = self._make_auth_system(
            group="user",
            permissions={
                "auto_fill_password": True,
                "view_school_account_passwords": True,
            },
        )

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_ALL,
        )

    def test_error_falls_back_to_none(self):
        system = object.__new__(auth_system_module.AuthSystem)
        system.permissions = {"permission_groups": {}, "user_groups": {}}
        system.get_user_group = mock.Mock(side_effect=RuntimeError("boom"))

        self.assertEqual(
            system.resolve_password_visibility("someone"),
            auth_system_module.PASSWORD_VISIBILITY_NONE,
        )


class TestBuiltinPermissionBackfill(unittest.TestCase):
    def test_missing_key_is_backfilled_per_group(self):
        system = object.__new__(auth_system_module.AuthSystem)
        system.permissions = {
            "permission_groups": {
                "guest": {"is_system": True, "permissions": {}},
                "user": {"is_system": True, "permissions": {}},
                "admin": {"is_system": True, "permissions": {}},
                "super_admin": {"is_system": True, "permissions": {}},
            },
            "user_groups": {},
        }
        system._save_permissions = mock.Mock()

        system._ensure_builtin_permissions()

        groups = system.permissions["permission_groups"]
        self.assertFalse(groups["guest"]["permissions"]["view_school_account_passwords"])
        self.assertFalse(groups["user"]["permissions"]["view_school_account_passwords"])
        self.assertTrue(groups["admin"]["permissions"]["view_school_account_passwords"])
        self.assertTrue(
            groups["super_admin"]["permissions"]["view_school_account_passwords"]
        )
        self.assertFalse(groups["guest"]["permissions"]["bypass_overdue"])
        self.assertFalse(groups["user"]["permissions"]["bypass_overdue"])
        self.assertTrue(groups["admin"]["permissions"]["bypass_overdue"])
        self.assertTrue(groups["super_admin"]["permissions"]["bypass_overdue"])
        system._save_permissions.assert_called_once()

    def test_existing_value_is_never_overwritten(self):
        system = object.__new__(auth_system_module.AuthSystem)
        system.permissions = {
            "permission_groups": {
                "user": {
                    "is_system": True,
                    "permissions": {
                        "view_school_account_passwords": True,
                        "bypass_overdue": True,
                    },
                }
            },
            "user_groups": {},
        }
        system._save_permissions = mock.Mock()

        system._ensure_builtin_permissions()

        self.assertTrue(
            system.permissions["permission_groups"]["user"]["permissions"][
                "view_school_account_passwords"
            ],
            "已存在的用户自定义取值不得被回填覆盖",
        )
        self.assertTrue(
            system.permissions["permission_groups"]["user"]["permissions"][
                "bypass_overdue"
            ],
            "已存在的 bypass_overdue 取值不得被回填覆盖",
        )
        system._save_permissions.assert_not_called()

    def test_custom_group_is_not_touched(self):
        system = object.__new__(auth_system_module.AuthSystem)
        system.permissions = {
            "permission_groups": {
                "my_custom_group": {"is_system": False, "permissions": {}}
            },
            "user_groups": {},
        }
        system._save_permissions = mock.Mock()

        system._ensure_builtin_permissions()

        self.assertNotIn(
            "view_school_account_passwords",
            system.permissions["permission_groups"]["my_custom_group"]["permissions"],
        )


class TestPasswordRedactionContract(unittest.TestCase):
    """web_server 层的结构性契约。"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.source = (
            Path(__file__).resolve().parents[1] / "web_server.py"
        ).read_text(encoding="utf-8")

    def test_helper_exists_and_handles_three_levels(self):
        block = self.source.split("def _apply_password_visibility(", 1)[1].split(
            "def _sync_runtime_state(", 1
        )[0]

        self.assertIn('if visibility == "all"', block)
        self.assertIn('if visibility == "own" and target_username == auth_username', block)
        # 敏感字段置空
        self.assertIn('sanitized["password"] = ""', block)
        self.assertIn('sanitized["ua"] = ""', block)

    def test_both_school_account_endpoints_apply_redaction(self):
        count = self.source.count(
            "filtered_accounts = _apply_password_visibility("
        )

        self.assertEqual(
            count, 2, "两个 school_account 接口都必须应用密码脱敏"
        )

    def test_admin_full_dump_requires_all_level(self):
        block = self.source.split(
            "def auth_admin_get_all_users_school_accounts(", 1
        )[1].split("@app.route", 1)[0]

        self.assertIn('!= "all"', block)
        self.assertIn("auto_fill_password", block)

    def test_on_user_selected_gate_uses_visibility_levels(self):
        block = self.source.split(
            'if method == "on_user_selected"', 1
        )[1].split("auto_save_methods = [", 1)[0]

        self.assertIn('visibility == "all"', block)
        self.assertIn('visibility == "own"', block)
        self.assertIn('result["password"] = ""', block)


class TestNewPermissionWiredEverywhere(unittest.TestCase):
    def test_permission_template_contains_new_key(self):
        source = inspect.getsource(main_module._create_permissions_json)

        self.assertIn('"view_school_account_passwords"', source)
        # 内置组：guest/user 为 False，admin/super_admin 为 True
        self.assertEqual(source.count('"view_school_account_passwords": False'), 2)
        self.assertEqual(source.count('"view_school_account_passwords": True'), 2)

    def test_frontend_has_label_for_new_permission(self):
        from pathlib import Path

        main_js = (
            Path(__file__).resolve().parents[1] / "scripts" / "main.js"
        ).read_text(encoding="utf-8")

        self.assertIn("view_school_account_passwords:", main_js)

    def test_get_initial_data_grants_own_scope(self):
        source = inspect.getsource(main_module.Api.get_initial_data)

        self.assertIn('password_visibility == "all"', source)
        self.assertIn('password_visibility == "own"', source)
        self.assertIn("has_view_own_permission", source)


if __name__ == "__main__":
    unittest.main()
