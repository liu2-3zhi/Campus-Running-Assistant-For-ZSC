"""multi_import_accounts 的汇总契约。

要点:
    1. `already_exists` 不得被算作"导入成功"（旧代码 `imported += 1` 无条件自增）；
    2. 返回体必须带前端读取的 `imported_count` / `skipped_count` / `message`
       （旧代码返回 `multi_get_all_accounts_status()`，这些字段一个都没有，
       于是前端永远显示"成功导入 0 个"）；
    3. 缺密码账号清单**不得截断**（旧代码后端 alert 只列前 20 个）；
    4. 后端不得再用 `window.evaluate_js` 弹窗——缺密码提示只由前端阶段 1 负责，
       否则和后端弹窗形成两套提示。
"""

import base64
import unittest
from unittest import mock

import main as main_module


class _FakeAccount:
    def __init__(self, username):
        self.username = username
        self.password = "pw"
        self.tag = ""
        self.params = {}
        self.device_ua = "ua"
        self.user_data = mock.Mock()
        self.is_first_login_verified = True


class _ImportTestBase(unittest.TestCase):
    def _make_api(self, existing=()):
        api = object.__new__(main_module.Api)
        api.accounts = {u: _FakeAccount(u) for u in existing}
        api.auth_username = "zhangzhi"
        api.log = mock.Mock()
        api._save_account_tag = mock.Mock()
        api._update_multi_global_buttons = mock.Mock()
        api._update_account_status_js = mock.Mock()
        api._multi_refresh_worker = mock.Mock()
        api._load_user_school_accounts = mock.Mock(return_value={})
        api.multi_get_all_accounts_status = mock.Mock(
            return_value={"success": True, "accounts": []}
        )

        api._is_multi_account_execution_active = mock.Mock(return_value=False)

        # 真正的 multi_add_account 会碰会话/线程；这里只关心分类结果，
        # 用真实实现的判定规则做一个等价桩。
        def fake_add(
            username, password, tag=None, params=None, *, only_if_missing=False
        ):
            if username in api.accounts:
                return {
                    "success": False,
                    "reason": "already_exists",
                    "message": f"账号 {username} 已存在，未重复添加。",
                    "username": username,
                }
            api.accounts[username] = _FakeAccount(username)
            return {"success": True, "accounts": []}

        api.multi_add_account = fake_add
        return api

    @staticmethod
    def _csv_b64(rows):
        text = "账号,密码,标记\n" + "\n".join(rows) + "\n"
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")


class TestImportSummary(_ImportTestBase):
    def test_mixed_file_counts_each_bucket(self):
        api = self._make_api(existing=("existing1",))
        result = api.multi_import_accounts(
            "t.csv",
            self._csv_b64(
                [
                    "newA,pwA,tagA",   # 新增
                    "existing1,pw1,",  # 已存在
                    "missA,",          # 缺密码
                ]
            ),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["already_exists_count"], 1)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["total_rows"], 3)

    def test_already_exists_is_not_counted_as_imported(self):
        """核心回归：已存在的账号旧代码会被算作"成功导入"。"""
        api = self._make_api(existing=("e1", "e2", "e3"))
        result = api.multi_import_accounts(
            "t.csv",
            self._csv_b64(
                ["e1,pw", "e2,pw", "e3,pw"],
            ),
        )

        self.assertEqual(result["imported_count"], 0, "已存在账号被算成导入成功了")
        self.assertEqual(result["already_exists_count"], 3)

    def test_duplicate_rows_counted_once(self):
        api = self._make_api()
        result = api.multi_import_accounts(
            "t.csv",
            self._csv_b64(["dup,pw", "dup,pw", "dup,pw"]),
        )

        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["duplicate_in_file_count"], 2)
        self.assertEqual(result["total_rows"], 3)

    def test_frontend_fields_present(self):
        """缺了这些字段前端就永远显示 0。"""
        api = self._make_api()
        result = api.multi_import_accounts("t.csv", self._csv_b64(["a,pw"]))

        for key in (
            "success",
            "message",
            "imported_count",
            "already_exists_count",
            "skipped_count",
            "accounts",
        ):
            with self.subTest(key=key):
                self.assertIn(key, result)

    def test_unsupported_format_rejected(self):
        api = self._make_api()
        result = api.multi_import_accounts("t.txt", self._csv_b64(["a,pw"]))

        self.assertFalse(result["success"])
        self.assertIn("不支持的导入格式", result["message"])


class TestMissingPasswordListIsNotTruncated(_ImportTestBase):
    """缺密码账号**不限数量**：不得截断、不得只列前 N 个。"""

    def test_thirty_missing_accounts_all_returned(self):
        api = self._make_api()
        rows = [f"miss{i:03d}," for i in range(30)]

        result = api.multi_import_accounts("t.csv", self._csv_b64(rows))

        self.assertEqual(result["skipped_count"], 30)
        self.assertEqual(
            len(result["accounts_missing_password"]),
            30,
            "缺密码清单被截断了",
        )
        self.assertEqual(
            [item["username"] for item in result["accounts_missing_password"]],
            [f"miss{i:03d}" for i in range(30)],
            "清单顺序或内容不完整",
        )

    def test_two_hundred_missing_accounts_all_returned(self):
        """旧代码 [:20] 截断的边界之外也要完整返回。"""
        api = self._make_api()
        rows = [f"bulk{i:03d}," for i in range(200)]

        result = api.multi_import_accounts("t.csv", self._csv_b64(rows))

        self.assertEqual(result["skipped_count"], 200)
        self.assertEqual(len(result["accounts_missing_password"]), 200)

    def test_missing_entries_carry_username_and_tag(self):
        api = self._make_api()
        result = api.multi_import_accounts(
            "t.csv", self._csv_b64(["missA,,A组", "missB,,"])
        )

        by_name = {i["username"]: i for i in result["accounts_missing_password"]}
        self.assertEqual(len(by_name), 2)
        self.assertEqual(by_name["missA"]["tag"], "A组")
        self.assertIsNone(by_name["missB"]["tag"])


class TestNoBackendAlert(_ImportTestBase):
    """后端不得再弹窗：提示统一由前端负责。"""

    def test_window_evaluate_js_is_not_called(self):
        api = self._make_api()
        api.window = mock.Mock()

        api.multi_import_accounts(
            "t.csv", self._csv_b64(["a,pw", "missA,"])
        )

        api.window.evaluate_js.assert_not_called()

    def test_source_has_no_alert_for_missing_password(self):
        """源码级兜底：导入路径里不得再出现 alert 拼装。"""
        import inspect

        source = inspect.getsource(
            main_module.Api.multi_import_accounts
        ) + inspect.getsource(main_module.Api._build_import_summary)

        self.assertNotIn("evaluate_js", source)
        self.assertNotIn("skipped_no_password[:20]", source)


class TestImportRunsAlongsideRunningAccount(_ImportTestBase):
    """账号执行中时导入不得覆盖它，应单独归类。"""

    def test_running_account_is_not_overwritten_nor_counted_as_added(self):
        api = self._make_api()
        api.multi_add_account = mock.Mock(
            return_value={
                "success": False,
                "reason": "account_running",
                "message": "正在执行任务",
            }
        )

        result = api.multi_import_accounts("t.csv", self._csv_b64(["busy,pw"]))

        self.assertEqual(result["imported_count"], 0)
        self.assertEqual(result["skipped_running_count"], 1)
        self.assertEqual(result["skipped_running"], ["busy"])
        self.assertIn("执行中跳过", result["message"])


if __name__ == "__main__":
    unittest.main()
