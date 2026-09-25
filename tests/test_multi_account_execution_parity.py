import datetime
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import main


class _FakeRunInfoClient:
    def __init__(self, status):
        self._status = status
        self.app = SimpleNamespace(
            log=lambda _message: None,
            user_data=SimpleNamespace(username="student-a"),
        )

    def get_run_info_by_trid(self, _trid):
        return {
            "success": True,
            "data": {"recordMap": {"status": self._status}},
        }


class TestMultiAccountExecutionParity(unittest.TestCase):
    def _new_api(self):
        api = object.__new__(main.Api)
        api.auth_username = "owner"
        api.user_data = SimpleNamespace(username="wrong-account")
        api.params = {"ignore_task_time": True}
        api._deduct_available_runs_or_increment_overdue = Mock()
        api._increment_completed_count = Mock()
        return api

    def _free_mode_config(self):
        config = MagicMock()
        config.getboolean.return_value = False
        return config

    def test_finalize_run_returns_confirmation_and_settles_bound_school_account(self):
        api = self._new_api()
        run_data = main.RunData()
        run_data.run_name = "task-a"
        run_data.trid = "trid-a"

        with patch.object(main, "socketio", None, create=True), patch.object(
            main.time, "sleep"
        ):
            confirmed = api._finalize_run(
                run_data,
                -1,
                _FakeRunInfoClient(status=1),
            )

        self.assertTrue(confirmed)
        self.assertEqual(1, run_data.status)
        api._deduct_available_runs_or_increment_overdue.assert_called_once_with(
            "owner",
            "student-a",
        )
        api._increment_completed_count.assert_called_once_with(
            "owner",
            "student-a",
        )

    def test_finalize_run_does_not_settle_unconfirmed_run(self):
        api = self._new_api()
        run_data = main.RunData()
        run_data.run_name = "task-a"
        run_data.trid = "trid-a"

        with patch.object(main, "socketio", None, create=True), patch.object(
            main.time, "sleep"
        ):
            confirmed = api._finalize_run(
                run_data,
                -1,
                _FakeRunInfoClient(status=0),
            )

        self.assertFalse(confirmed)
        self.assertEqual(0, run_data.status)
        api._deduct_available_runs_or_increment_overdue.assert_not_called()
        api._increment_completed_count.assert_not_called()

    def test_billing_settlement_serializes_shared_system_account_runs(self):
        api = object.__new__(main.Api)
        first_entered = threading.Event()
        release_first = threading.Event()
        call_order = []

        def fake_unlocked(_auth_username, school_username):
            call_order.append(school_username)
            if len(call_order) == 1:
                first_entered.set()
                release_first.wait(timeout=2)

        api._deduct_available_runs_or_increment_overdue_unlocked = fake_unlocked

        first = threading.Thread(
            target=api._deduct_available_runs_or_increment_overdue,
            args=("owner", "student-a"),
        )
        second = threading.Thread(
            target=api._deduct_available_runs_or_increment_overdue,
            args=("owner", "student-b"),
        )
        first.start()
        self.assertTrue(first_entered.wait(timeout=1))
        second.start()
        time.sleep(0.05)

        self.assertEqual(["student-a"], call_order)
        release_first.set()
        first.join(timeout=2)
        second.join(timeout=2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(["student-a", "student-b"], call_order)

    def test_multi_worker_uses_finalize_result_without_duplicate_settlement(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        worker_block = source.split(
            "def _multi_account_worker(",
            1,
        )[1].split(
            "def _run_all_multi_accounts_thread(",
            1,
        )[0]

        self.assertIn("if self._finalize_run(", worker_block)
        self.assertNotIn("_deduct_available_runs_or_increment_overdue(", worker_block)
        self.assertNotIn("_increment_completed_count(", worker_block)
        self.assertNotIn("run_data.status = 1", worker_block)

    def test_multi_worker_and_summary_use_shared_task_time_evaluator(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        worker_block = source.split(
            "def _multi_account_worker(",
            1,
        )[1].split(
            "def _run_all_multi_accounts_thread(",
            1,
        )[0]
        summary_block = source.split(
            "def _multi_fetch_and_summarize_tasks(",
            1,
        )[1].split(
            "def _multi_fetch_attendance_stats(",
            1,
        )[0]

        self.assertIn("_get_task_time_state(", worker_block)
        self.assertIn("_get_task_time_state(", summary_block)
        self.assertNotIn('strptime(\n                            r.start_time, "%Y-%m-%d %H:%M:%S"', worker_block)
        self.assertNotIn('strptime(\n                        r.start_time, "%Y-%m-%d %H:%M:%S"', summary_block)

    def test_multi_worker_persists_progress_and_tracks_distance(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        worker_block = source.split(
            "def _multi_account_worker(",
            1,
        )[1].split(
            "def _run_all_multi_accounts_thread(",
            1,
        )[0]

        self.assertIn("distance_covered_m +=", worker_block)
        self.assertIn("save_session_state(", worker_block)

    def test_multi_session_state_round_trip_preserves_progress_and_position(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        save_block = source.split(
            "def save_session_state(",
            1,
        )[1].split(
            "def restore_session_to_api_instance(",
            1,
        )[0]
        restore_block = source.split(
            "def restore_session_to_api_instance(",
            1,
        )[1].split(
            "@app.route",
            1,
        )[0]

        for field in (
            "progress_pct",
            "progress_text",
            "progress_extra",
            "current_position",
        ):
            self.assertIn(field, save_block)
            self.assertIn(field, restore_block)

    def test_task_time_state_accepts_single_account_time_formats(self):
        api = self._new_api()
        now = datetime.datetime(2026, 9, 25, 12, 0, 0)

        self.assertEqual(
            "expired",
            api._get_task_time_state(
                SimpleNamespace(start_time="2026-09-24", end_time="2026-09-24"),
                now=now,
            ),
        )
        self.assertEqual(
            "not_started",
            api._get_task_time_state(
                SimpleNamespace(start_time="2026-09-26", end_time="2026-09-27"),
                now=now,
            ),
        )
        self.assertEqual(
            "active",
            api._get_task_time_state(
                SimpleNamespace(start_time="2026-09-25T08:00:00", end_time="2026-09-25T20:00:00"),
                now=now,
            ),
        )

    def test_free_mode_single_run_skips_overdue_gate(self):
        api = self._new_api()
        api.stop_run_flag = threading.Event()
        api.stop_run_flag.set()
        api.single_execution_lock = threading.Lock()
        api.all_run_data = []
        api.current_run_idx = -1

        with patch.object(
            main, "_read_config_ini", return_value=self._free_mode_config()
        ), patch.object(
            main,
            "_count_pending_bills_for_school",
            side_effect=AssertionError("free mode must not query school bills"),
        ):
            result = api.start_single_run()

        self.assertEqual("请选择任务并生成路线", result["message"])

    def test_free_mode_single_start_all_skips_overdue_gate(self):
        api = self._new_api()
        api.stop_run_flag = threading.Event()
        api.stop_run_flag.set()
        api.all_run_data = []

        with patch.object(
            main, "_read_config_ini", return_value=self._free_mode_config()
        ), patch.object(
            main,
            "_count_pending_bills_for_school",
            side_effect=AssertionError("free mode must not query school bills"),
        ):
            result = api.start_all_runs(False, False)

        self.assertTrue(result["message"].startswith("没有符合条件的可执行任务。"))

    def test_free_mode_multi_single_start_skips_overdue_gate(self):
        api = self._new_api()
        acc = SimpleNamespace(username="student-a")
        api.accounts = {"student-a": acc}
        api.multi_run_stop_flag = threading.Event()
        api._is_multi_account_execution_active = lambda _acc: False

        with patch.object(
            main, "_read_config_ini", return_value=self._free_mode_config()
        ), patch.object(
            main,
            "_count_pending_bills_for_school",
            side_effect=AssertionError("free mode must not query school bills"),
        ), patch.object(
            api, "_start_multi_account_worker", return_value=True
        ), patch.object(
            api, "_update_account_status_js"
        ), patch.object(
            api, "_update_multi_global_buttons"
        ):
            result = api.multi_start_single_account("student-a")

        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
