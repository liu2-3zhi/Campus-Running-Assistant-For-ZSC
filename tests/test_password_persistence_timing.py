"""密码落盘时机契约：**只有登录成功才更新配置里的密码**。

用户要求（本轮）:
    "正常但用户显式给了不同密码，只有登录成功了才更新数据库的密码。"

真实缺陷（修复前）:
    1. `_multi_refresh_worker_unlocked` 在"账号早已验证过"的分支调用
       `self._save_config(acc.username)`，而 `_save_config` 的语义是
       "password=None 时保留现有密码" —— 于是新密码**永远写不进去**，
       成功登录也不落盘；
    2. 反过来，新增账号与改参数两条路径却把**尚未验证**的密码提前写进配置，
       一个输错的密码会覆盖原本可用的凭据。

正确行为:
    - 新密码先只在内存里，用它去登录；
    - 登录成功 → 落盘并清掉暂存；
    - 登录失败 → 回滚成原密码，配置里的密码始终是**已验证过的那个**。
"""

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main as main_module


class _FakeAccount:
    def __init__(self, username="2024090101001", password="old-pw"):
        self.username = username
        self.password = password
        self.tag = ""
        self.params = {}
        self.device_ua = "ua"
        self.user_data = SimpleNamespace(
            id="uid-1",
            username=username,
            student_id=username,
            name="tester",
        )
        self.is_first_login_verified = True
        self.is_verifying = False
        self.status_text = "待命"
        self.account_operation_lock = threading.Lock()
        self.api_client = mock.Mock()
        self.worker_thread = None
        self.logs = []

    def log(self, message):
        self.logs.append(str(message))


class _PendingPasswordBase(unittest.TestCase):
    def _make_api(self):
        api = object.__new__(main_module.Api)
        api.accounts = {}
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        api._save_config = mock.Mock()
        api._save_account_tag = mock.Mock()
        api._update_multi_global_buttons = mock.Mock()
        api._update_account_status_js = mock.Mock()
        api._multi_refresh_worker = mock.Mock()
        api._is_multi_account_execution_active = mock.Mock(return_value=False)
        api.log = mock.Mock()
        api.multi_get_all_accounts_status = mock.Mock(
            return_value={"success": True, "accounts": []}
        )
        return api


class TestStagingAndCommit(_PendingPasswordBase):
    def test_stage_keeps_previous_password_for_rollback(self):
        api = self._make_api()
        acc = _FakeAccount(password="old-pw")

        main_module.Api._stage_pending_account_password(api, acc, "new-pw")

        self.assertEqual(acc.password, "new-pw", "登录要用新密码")
        self.assertEqual(
            getattr(acc, "_password_before_change"), "old-pw", "必须记住旧密码"
        )
        self.assertIsNotNone(main_module.Api._pending_account_password(api, acc))

    def test_commit_writes_password_and_clears_pending(self):
        api = self._make_api()
        acc = _FakeAccount(password="old-pw")
        main_module.Api._stage_pending_account_password(api, acc, "new-pw")

        main_module.Api._commit_pending_account_password(api, acc)

        api._save_config.assert_called_once_with(acc.username, "new-pw", "ua")
        self.assertIsNone(main_module.Api._pending_account_password(api, acc))

    def test_rollback_restores_previous_password(self):
        api = self._make_api()
        acc = _FakeAccount(password="old-pw")
        main_module.Api._stage_pending_account_password(api, acc, "typo-pw")

        main_module.Api._rollback_pending_account_password(api, acc)

        self.assertEqual(
            acc.password, "old-pw", "登录失败必须恢复成原来可用的密码"
        )
        self.assertIsNone(main_module.Api._pending_account_password(api, acc))
        api._save_config.assert_not_called()

    def test_commit_is_noop_without_pending(self):
        """没有待验证密码时不得顺手覆盖配置（保留原有 password=None 语义）。"""
        api = self._make_api()
        acc = _FakeAccount()

        main_module.Api._commit_pending_account_password(api, acc)

        api._save_config.assert_not_called()

    def test_rollback_is_noop_without_pending(self):
        api = self._make_api()
        acc = _FakeAccount(password="keep")

        main_module.Api._rollback_pending_account_password(api, acc)

        self.assertEqual(acc.password, "keep")


class TestMultiAddAccountStagesInsteadOfCommitting(_PendingPasswordBase):
    """改密码必须走"暂存 → 验证 → 落盘"，不能提前写配置。"""

    def _make_api_with(self, acc):
        api = self._make_api()
        api.accounts = {acc.username: acc}
        api._reset_account_session_for_relogin = mock.Mock()
        return api

    def test_password_change_is_staged_not_saved(self):
        acc = _FakeAccount(password="old-pw")
        api = self._make_api_with(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "new-pw", None
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(acc.password, "new-pw", "内存里要用新密码去试")
        self.assertEqual(
            getattr(acc, "_password_before_change"), "old-pw"
        )
        api._save_config.assert_not_called()
        api._reset_account_session_for_relogin.assert_called_once()

    def test_same_password_does_not_stage(self):
        acc = _FakeAccount(password="same")
        api = self._make_api_with(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "same", None
        )

        self.assertEqual(result["reason"], "already_exists")
        self.assertIsNone(
            main_module.Api._pending_account_password(api, acc)
        )
        api._save_config.assert_not_called()

    def test_broken_account_with_saved_password_is_staged(self):
        """会话失效但本地存过密码：新密码同样要走"暂存 → 验证 → 落盘"。

        注意：只要传入的密码与 `acc.password` 不同就会暂存，
        因此不存在"异常账号直接用新密码"的旁路 —— 旧密码照样要保住。
        """
        acc = _FakeAccount(password="saved-pw")
        acc.user_data.id = ""
        acc.is_first_login_verified = False
        api = self._make_api_with(acc)

        result = main_module.Api.multi_add_account(
            api, acc.username, "fresh-pw", None
        )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(acc.password, "fresh-pw", "内存里用新密码去试")
        self.assertEqual(
            getattr(acc, "_password_before_change"),
            "saved-pw",
            "必须记住原来的密码以便失败回滚",
        )
        api._save_config.assert_not_called()
        api._reset_account_session_for_relogin.assert_called_once()

    def test_rollback_after_broken_account_restores_saved_password(self):
        acc = _FakeAccount(password="saved-pw")
        acc.user_data.id = ""
        acc.is_first_login_verified = False
        api = self._make_api_with(acc)

        main_module.Api.multi_add_account(api, acc.username, "typo-pw", None)
        main_module.Api._rollback_pending_account_password(api, acc)

        self.assertEqual(acc.password, "saved-pw")


class TestUnverifiedPasswordIsNotPersisted(unittest.TestCase):
    """新增账号与改参数都不得把未验证的密码写进配置。"""

    def test_new_account_does_not_save_password_before_login(self):
        import inspect

        source = inspect.getsource(main_module.Api.multi_add_account)
        # 新增账号分支里那次 _save_config 必须显式传 password=None
        self.assertIn(
            "password=None, ua=self.accounts[username].device_ua", source
        )
        self.assertNotIn(
            "self._save_config(\n                    username, password, ",
            source,
        )

    def test_param_update_does_not_save_password(self):
        import inspect

        source = inspect.getsource(
            main_module.Api.multi_update_account_param
        )
        self.assertNotIn(
            "_save_config(username, self.accounts[username].password)", source
        )


class TestLoginOutcomeDrivesPersistence(unittest.TestCase):
    """真正驱动登录成功 / 失败两条分支，检查落盘与回滚。"""

    def _make_api(self):
        api = object.__new__(main_module.Api)
        api.accounts = {}
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        api._save_config = mock.Mock()
        api._save_account_tag = mock.Mock()
        api._update_account_status_js = mock.Mock()
        api._multi_fetch_and_summarize_tasks = mock.Mock()
        api._persist_school_account_backup = mock.Mock()
        api.log = mock.Mock()
        # 登录成功分支会拼 user/<username>.ini 路径，缺这个属性会直接抛异常，
        # 让测试在"落盘"之前就断掉（曾经造成"没落盘"的假失败）。
        api.user_dir = str(Path(tempfile.gettempdir()) / "dsh_pw_test")
        return api

    def _run_refresh(self, api, acc, login_response):
        api._queued_login = mock.Mock(return_value=login_response)
        with mock.patch.object(main_module.time, "sleep", return_value=None):
            main_module.Api._multi_refresh_worker_unlocked(api, acc)

    def test_successful_relogin_commits_new_password(self):
        api = self._make_api()
        acc = _FakeAccount(password="old-pw")
        acc.user_data.id = ""  # 触发重新登录
        main_module.Api._stage_pending_account_password(api, acc, "new-pw")

        self._run_refresh(
            api,
            acc,
            {"success": True, "data": {"userInfo": {"id": "1"}}},
        )

        # 落盘时必须带上新密码
        saved_passwords = [
            call.args[1]
            for call in api._save_config.call_args_list
            if len(call.args) > 1
        ]
        self.assertIn("new-pw", saved_passwords, "登录成功后新密码没落盘")
        self.assertIsNone(main_module.Api._pending_account_password(api, acc))

    def test_failed_relogin_rolls_back_and_does_not_save(self):
        api = self._make_api()
        acc = _FakeAccount(password="old-pw")
        acc.user_data.id = ""
        main_module.Api._stage_pending_account_password(api, acc, "typo-pw")

        self._run_refresh(
            api,
            acc,
            {"success": False, "message": "密码错误"},
        )

        self.assertEqual(acc.password, "old-pw", "失败后必须恢复旧密码")
        api._save_config.assert_not_called()
        self.assertIsNone(main_module.Api._pending_account_password(api, acc))

    def test_failed_relogin_never_overwrites_stored_password(self):
        """核心回归：错误的新密码不得覆盖配置里已验证的密码。"""
        api = self._make_api()
        acc = _FakeAccount(password="good-pw")
        acc.user_data.id = ""
        main_module.Api._stage_pending_account_password(api, acc, "bad-pw")

        self._run_refresh(api, acc, {"success": False, "message": "密码错误"})

        for call in api._save_config.call_args_list:
            with self.subTest(call=str(call)):
                if len(call.args) > 1 and call.args[1] is not None:
                    self.assertNotEqual(
                        call.args[1], "bad-pw", "错误密码被写进了配置"
                    )


if __name__ == "__main__":
    unittest.main()
