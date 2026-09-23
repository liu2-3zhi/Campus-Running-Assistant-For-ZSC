import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class TestMultiAccountStartAllSkipOverdue(unittest.TestCase):
    def _api(self):
        api = object.__new__(main.Api)
        api.accounts = {
            "student-ok": SimpleNamespace(
                username="student-ok",
                summary={"total": 1, "expired": 0, "not_started": 0, "executable": 1},
                worker_thread=None,
            ),
            "student-overdue": SimpleNamespace(
                username="student-overdue",
                summary={"total": 1, "expired": 0, "not_started": 0, "executable": 1},
                worker_thread=None,
            ),
        }
        api.multi_run_stop_flag = threading.Event()
        api.multi_run_only_incomplete = True
        api.log = lambda _message: None
        return api

    def test_skip_overdue_excludes_overdue_accounts_from_batch_start(self):
        api = self._api()

        with patch.object(
            main,
            "_count_pending_bills_for_school",
            side_effect=lambda username: 1 if username == "student-overdue" else 0,
        ), patch.object(api, "_update_multi_global_buttons"), patch.object(
            api, "_start_multi_account_threads", return_value=1
        ) as start_threads:
            result = api.multi_start_all_accounts(
                0,
                0,
                False,
                True,
                skip_overdue=True,
            )

        self.assertTrue(result["success"])
        started_accounts = start_threads.call_args.args[0]
        self.assertEqual(["student-ok"], [acc.username for acc in started_accounts])
        self.assertEqual(
            ["student-overdue"],
            [item["school_username"] for item in result["skipped_overdue_accounts"]],
        )

    def test_all_overdue_accounts_cannot_be_skipped_into_an_empty_start(self):
        api = self._api()
        api.accounts.pop("student-ok")

        with patch.object(
            main,
            "_count_pending_bills_for_school",
            return_value=1,
        ), patch.object(api, "_update_multi_global_buttons"), patch.object(
            api, "_start_multi_account_threads"
        ) as start_threads:
            result = api.multi_start_all_accounts(
                0,
                0,
                False,
                True,
                skip_overdue=True,
            )

        self.assertFalse(result["success"])
        self.assertEqual("全部账号均存在欠费", result["message"])
        start_threads.assert_not_called()

    def test_batch_start_skips_accounts_that_are_already_running(self):
        api = self._api()
        api.accounts["student-running"] = SimpleNamespace(
            username="student-running",
            summary={"total": 1, "expired": 0, "not_started": 0, "executable": 1},
            worker_thread=None,
            log=lambda _message: None,
        )
        api.accounts["student-ok"].log = lambda _message: None
        api.accounts["student-overdue"].log = lambda _message: None

        with patch.object(
            main,
            "_count_pending_bills_for_school",
            return_value=0,
        ), patch.object(
            api,
            "_is_multi_account_execution_active",
            side_effect=lambda acc: acc.username == "student-running",
        ), patch.object(api, "_update_multi_global_buttons"), patch.object(
            api, "_start_multi_account_worker", return_value=True
        ) as start_worker:
            result = api.multi_start_all_accounts(0, 0, False, True)

        self.assertTrue(result["success"])
        started_usernames = [
            call.args[0].username for call in start_worker.call_args_list
        ]
        self.assertCountEqual(
            ["student-ok", "student-overdue"],
            started_usernames,
        )


if __name__ == "__main__":
    unittest.main()
