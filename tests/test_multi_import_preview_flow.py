"""多账号导入的预览/确认两阶段契约。"""

import base64
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


class _PreviewAccount:
    def __init__(self, username, password="stored"):
        self.username = username
        self.password = password
        self.tag = ""
        self.params = {}
        self.user_data = mock.Mock(id="session-id")
        self.is_first_login_verified = True


class _PreviewBase(unittest.TestCase):
    def _api(self):
        api = object.__new__(main_module.Api)
        api.auth_username = "alice"
        api.accounts = {}
        api._load_user_school_accounts = mock.Mock(return_value={})
        api.multi_add_account = mock.Mock(return_value={"success": True})
        api.log_and_notify_frontend = mock.Mock()
        api.multi_get_all_accounts_status = mock.Mock(
            return_value={"success": True, "accounts": []}
        )
        return api

    @staticmethod
    def _csv(rows):
        text = "账号,密码,标记\n" + "\n".join(rows) + "\n"
        return base64.b64encode(text.encode("utf-8")).decode("ascii")


class ImportPreviewTests(_PreviewBase):
    def test_preview_lists_unique_rows_and_only_checks_empty_password(self):
        api = self._api()

        result = api.multi_preview_import_accounts(
            "accounts.csv",
            self._csv([
                "10001,pwA,A组",
                "10002,,B组",
                "10001,姓名,重复",
            ]),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["detected_count"], 2)
        self.assertEqual(result["total_rows"], 3)
        self.assertEqual(
            [row["username"] for row in result["records"]],
            ["10001", "10002"],
        )
        self.assertEqual(result["records"][0]["password"], "pwA")
        self.assertTrue(result["records"][0]["password_present"])
        self.assertFalse(result["records"][1]["password_present"])
        self.assertEqual(result["missing_password"], ["10002"])
        self.assertEqual(result["duplicate_in_file"], ["10001"])
        api.multi_add_account.assert_not_called()
        api._load_user_school_accounts.assert_not_called()

    def test_preview_does_not_reject_password_before_confirmation(self):
        api = self._api()

        result = api.multi_preview_import_accounts(
            "accounts.csv", self._csv(["10001,中文密码,"])
        )

        self.assertEqual(result["detected_count"], 1)
        self.assertEqual(result["records"][0]["password"], "中文密码")
        self.assertTrue(result["records"][0]["password_present"])
        self.assertNotIn("invalid_password", result)


class ConfirmedImportTests(_PreviewBase):
    def test_confirmed_import_waits_for_login_verification(self):
        api = self._api()
        account = _PreviewAccount("10001", password="new-password")
        account.user_data.id = ""
        account.is_first_login_verified = False
        account.is_verifying = True
        api.accounts = {"10001": account}

        result = api.multi_import_account(
            username="10001", password="new-password", tag="A组"
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["pending_verification"])
        self.assertFalse(result["login_verified"])

    def test_import_status_exposes_verified_and_verifying_states(self):
        api = object.__new__(main_module.Api)
        api._is_multi_account_execution_active = mock.Mock(return_value=False)
        api._get_school_account_gender_from_backup = mock.Mock(return_value="")
        account = SimpleNamespace(
            username="10001",
            user_data=SimpleNamespace(id="", name="", gender=""),
            all_run_data=[],
            summary={},
            status_text="首次验证中...",
            tag="",
            current_position=None,
            progress_pct=0,
            progress_text="",
            progress_extra="",
            is_first_login_verified=False,
            is_verifying=True,
        )
        api.accounts = {"10001": account}

        pending = api.multi_get_all_accounts_status()
        self.assertFalse(pending["accounts"][0]["login_verified"])
        self.assertTrue(pending["accounts"][0]["login_verifying"])
        self.assertEqual(
            pending["accounts"][0]["login_verification_status"], "verifying"
        )

        account.user_data.id = "student-id"
        account.is_first_login_verified = True
        account.is_verifying = False
        account.status_text = "获取数据..."
        verified = api.multi_get_all_accounts_status()
        self.assertTrue(verified["accounts"][0]["login_verified"])
        self.assertFalse(verified["accounts"][0]["login_verifying"])
        self.assertEqual(
            verified["accounts"][0]["login_verification_status"], "verified"
        )

        account.user_data.id = ""
        account.is_first_login_verified = False
        account.status_text = "验证失败: 密码错误"
        failed = api.multi_get_all_accounts_status()
        self.assertFalse(failed["accounts"][0]["login_verified"])
        self.assertFalse(failed["accounts"][0]["login_verifying"])
        self.assertEqual(
            failed["accounts"][0]["login_verification_status"], "failed"
        )
        self.assertEqual(
            failed["accounts"][0]["login_verification_message"],
            "验证失败: 密码错误",
        )

    def test_confirmed_import_falls_back_to_saved_password_and_allows_override(self):
        api = self._api()
        api._load_user_school_accounts.return_value = {
            "10001": {"password": "system-password"}
        }

        blank_result = api.multi_import_account(
            username="10001", password="", tag="A组"
        )
        explicit_result = api.multi_import_account(
            username="10001", password="new-password", tag="B组"
        )

        self.assertTrue(blank_result["success"])
        self.assertTrue(explicit_result["success"])
        self.assertEqual(
            api.multi_add_account.call_args_list[0].kwargs,
            {
                "tag": "A组",
                "only_if_missing": False,
            },
        )
        self.assertEqual(
            api.multi_add_account.call_args_list[0].args,
            ("10001", "system-password"),
        )
        self.assertEqual(
            api.multi_add_account.call_args_list[1].args,
            ("10001", "new-password"),
        )
        self.assertFalse(api.multi_add_account.call_args_list[1].kwargs["only_if_missing"])

    def test_confirmed_import_reports_missing_password_without_mutation(self):
        api = self._api()

        result = api.multi_import_account(username="10001", password="")

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "skipped_no_password")
        self.assertEqual(result["action"], "request_password")
        api.multi_add_account.assert_not_called()


if __name__ == "__main__":
    unittest.main()
