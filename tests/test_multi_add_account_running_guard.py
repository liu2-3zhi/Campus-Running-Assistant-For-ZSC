"""multi_add_account 对"已存在账号"的处置契约。

三档行为（真实事故 2026-10-11 19:07 催生）:
    1. 状态正常 + 没给新密码      → `already_exists`，无操作，绝不动会话；
    2. 状态异常（首次验证未通过 / 会话已失效）→ **允许覆盖**，覆盖密码并重登。
       否则"密码填错了想改对"永远无法恢复，只能删掉再加回；
    3. 状态正常 + 用户给了新密码  → 允许覆盖（用户明确要改密码），但仅限
       该账号没有在执行任务时。

事故链路:
    任务跑到 250/411 时前端对同一账号又提交了一次 `multi_add_account`，
    旧代码无条件清空 `session.cookies` 并置空 `user_data.id`，4 秒后下一次
    提交变成"0 个 Cookie、无 shiroCookie、无 Authorization"的裸请求，
    被学校服务器拒绝为 400 `userId不能为空`
    （这是**认证失败**的表象，不是业务字段缺失），重试 10 次后任务中止。
"""

import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


class _FakeAccount:
    def __init__(
        self,
        username="2024090101001",
        uid="uid-original",
        verified=True,
        password="pw",
    ):
        self.username = username
        self.password = password
        self.tag = ""
        self.params = {"alpha": 1}
        self.device_ua = "ua"
        self.user_data = SimpleNamespace(
            id=uid,
            username=username,
            student_id=username,
            name="tester",
        )
        self.is_first_login_verified = verified
        self.is_verifying = False
        self.status_text = "待命"
        self.account_operation_lock = threading.Lock()
        self.api_client = mock.Mock()
        self.worker_thread = None


class _TestBase(unittest.TestCase):
    def _make_api(self, acc):
        api = object.__new__(main_module.Api)
        api.accounts = {acc.username: acc}
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        api._update_account_status_js = mock.Mock()
        api._update_multi_global_buttons = mock.Mock()
        api.multi_get_all_accounts_status = mock.Mock(
            return_value={"success": True, "accounts": []}
        )
        api._save_account_tag = mock.Mock()
        api._load_accounts_by_permission = mock.Mock(
            return_value={acc.username: {"password": "pw", "ua": "ua"}}
        )
        api._get_auth_user_and_check_admin = mock.Mock(
            return_value=("zhangzhi", False)
        )
        api.log_and_notify_frontend = mock.Mock()
        api._multi_refresh_worker = mock.Mock()
        return api

    def _mark_running(self, acc):
        """让 _is_multi_account_execution_active 判定为"正在执行"。"""
        worker = mock.Mock()
        worker.is_alive.return_value = True
        acc.worker_thread = worker


class TestHealthyAccountIsSkipped(_TestBase):
    """状态正常的账号：跳过重复添加，会话分毫不动。"""

    def test_returns_already_exists(self):
        acc = _FakeAccount()
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(api, acc.username, "", None)

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "already_exists")
        self.assertIn(acc.username, result["message"])
        self.assertIn("accounts", result)

    def test_session_is_not_touched(self):
        acc = _FakeAccount()
        api = self._make_api(acc)

        with mock.patch.object(main_module.threading, "Thread") as thread_mock:
            main_module.Api.multi_add_account(api, acc.username, "", None)

        acc.api_client.session.cookies.clear.assert_not_called()
        self.assertEqual(
            acc.user_data.id,
            "uid-original",
            "状态正常的账号不得被置空 user_data.id（会导致 userId不能为空）",
        )
        thread_mock.assert_not_called()

    def test_password_is_not_rewritten_when_not_provided(self):
        acc = _FakeAccount(password="keep-me")
        api = self._make_api(acc)

        main_module.Api.multi_add_account(api, acc.username, "", None)

        self.assertEqual(acc.password, "keep-me")

    def test_tag_and_params_are_still_updated(self):
        """守卫只跳过"清会话"，元数据仍应更新。"""
        acc = _FakeAccount()
        api = self._make_api(acc)

        main_module.Api.multi_add_account(
            api, acc.username, "", "my-tag", {"alpha": 99, "unknown": 1}
        )

        self.assertEqual(acc.tag, "my-tag")
        api._save_account_tag.assert_called_once()
        self.assertEqual(acc.params["alpha"], 99)
        self.assertNotIn("unknown", acc.params, "不应写入未定义的参数键")


class TestUnhealthyAccountIsOverwritten(_TestBase):
    """状态异常的账号：必须允许覆盖，否则无法恢复。"""

    def test_failed_first_login_is_overwritten(self):
        acc = _FakeAccount(uid="", verified=False, password="wrong")
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "correct-pw", None
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(acc.password, "correct-pw")
        acc.api_client.session.cookies.clear.assert_called_once()
        self.assertEqual(acc.user_data.id, "")

    def test_missing_session_id_is_overwritten_even_without_new_password(self):
        """会话已失效（id 为空）但保留过验证标记：仍应重建会话。"""
        acc = _FakeAccount(uid="", verified=True)
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(api, acc.username, "", None)

        self.assertTrue(result.get("success"), result)
        acc.api_client.session.cookies.clear.assert_called_once()


class TestPasswordChange(_TestBase):
    """用户显式给出不同密码 = 要改密码。"""

    def test_new_password_overwrites_healthy_account(self):
        acc = _FakeAccount(password="old")
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "new-pw", None
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(acc.password, "new-pw")
        acc.api_client.session.cookies.clear.assert_called_once()

    def test_same_password_is_treated_as_skip(self):
        acc = _FakeAccount(password="same")
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "same", None
        )

        self.assertEqual(result["reason"], "already_exists")
        acc.api_client.session.cookies.clear.assert_not_called()


class TestRunningAccountIsProtected(_TestBase):
    """正在执行任务的账号不得被覆盖（否则重演线上事故）。"""

    def test_password_change_is_refused_while_running(self):
        acc = _FakeAccount(password="old")
        api = self._make_api(acc)
        self._mark_running(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "new-pw", None
        )

        self.assertEqual(result["reason"], "account_running")
        self.assertEqual(acc.password, "old", "运行中不得改密码")
        acc.api_client.session.cookies.clear.assert_not_called()
        self.assertIn("请先停止", result["message"])

    def test_unhealthy_but_running_is_also_refused(self):
        acc = _FakeAccount(uid="", verified=False, password="wrong")
        api = self._make_api(acc)
        self._mark_running(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "correct-pw", None
        )

        self.assertEqual(result["reason"], "account_running")
        acc.api_client.session.cookies.clear.assert_not_called()

    def test_skip_still_works_while_running(self):
        """运行中的正常账号被重复"添加"时仍走 already_exists，不能报错。"""
        acc = _FakeAccount()
        api = self._make_api(acc)
        self._mark_running(acc)

        result = main_module.Api.multi_add_account(api, acc.username, "", None)

        self.assertEqual(result["reason"], "already_exists")
        acc.api_client.session.cookies.clear.assert_not_called()


class TestOnlyIfMissing(_TestBase):
    """批量导入不得用文件里的密码覆盖正常账号。"""

    def test_import_does_not_overwrite_healthy_account(self):
        acc = _FakeAccount(password="stored-pw")
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "file-pw", None, only_if_missing=True
        )

        self.assertEqual(result["reason"], "already_exists")
        self.assertEqual(
            acc.password, "stored-pw", "导入覆盖了正常账号的密码"
        )
        acc.api_client.session.cookies.clear.assert_not_called()

    def test_import_still_recovers_unhealthy_account(self):
        acc = _FakeAccount(uid="", verified=False, password="wrong")
        api = self._make_api(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "file-pw", None, only_if_missing=True
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(acc.password, "file-pw")


class TestValidationStillApplies(_TestBase):
    """安全校验不能被这次改动破坏。"""

    def test_invalid_username_is_rejected(self):
        acc = _FakeAccount()
        api = self._make_api(acc)

        for bad in (None, "", 123, "has space", "a" * 500):
            with self.subTest(bad=str(bad)[:20]):
                result = main_module.Api.multi_add_account(api, bad, "pw", None)
                self.assertFalse(result.get("success"))
                self.assertNotIn("reason", result, "校验失败不应走 already_exists")

    def test_too_many_params_rejected(self):
        acc = _FakeAccount()
        api = self._make_api(acc)
        many = {f"k{i}": 1 for i in range(main_module.MAX_PARAMS_COUNT + 1)}

        result = main_module.Api.multi_add_account(
            api, acc.username, "", None, many
        )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "参数过多")


if __name__ == "__main__":
    unittest.main()
