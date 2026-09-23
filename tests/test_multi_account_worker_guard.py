import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import main as main_module


class FakeAccount:
    def __init__(self, username="account-1"):
        self.username = username
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.account_operation_lock = threading.Lock()
        self.user_data = SimpleNamespace(
            username=username,
            student_id=username,
        )


class TestMultiAccountWorkerGuard(unittest.TestCase):
    def setUp(self):
        with main_module.SCHOOL_ACCOUNT_EXECUTION_LOCK:
            main_module.SCHOOL_ACCOUNT_EXECUTION_CLAIMS.clear()

    def tearDown(self):
        with main_module.SCHOOL_ACCOUNT_EXECUTION_LOCK:
            main_module.SCHOOL_ACCOUNT_EXECUTION_CLAIMS.clear()

    def _new_api(self):
        api = object.__new__(main_module.Api)
        api.multi_execution_lock = threading.RLock()
        api.multi_active_executions = set()
        return api

    def test_concurrent_worker_starts_allow_only_one_execution(self):
        api = self._new_api()
        acc = FakeAccount()
        release_worker = threading.Event()

        def fake_worker(_acc, _delay, _run_only_incomplete):
            release_worker.wait(timeout=2)

        api._multi_account_worker = fake_worker
        start_barrier = threading.Barrier(8)
        results = []

        def start_worker():
            start_barrier.wait(timeout=2)
            results.append(
                main_module.Api._start_multi_account_worker(
                    api,
                    acc,
                    0,
                    True,
                )
            )

        starters = [
            threading.Thread(target=start_worker, daemon=True)
            for _ in range(8)
        ]
        for thread in starters:
            thread.start()
        for thread in starters:
            thread.join(timeout=2)

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 7)
        self.assertIn(acc.username, api.multi_active_executions)

        release_worker.set()
        worker = acc.worker_thread
        self.assertIsNotNone(worker)
        worker.join(timeout=2)

        deadline = time.time() + 2
        while time.time() < deadline and (
            acc.username in api.multi_active_executions
            or acc.worker_thread is not None
        ):
            time.sleep(0.01)

        self.assertNotIn(acc.username, api.multi_active_executions)
        self.assertIsNone(acc.worker_thread)
        self.assertTrue(acc.account_operation_lock.acquire(blocking=False))
        acc.account_operation_lock.release()

    def test_refresh_worker_skips_while_account_operation_is_locked(self):
        api = self._new_api()
        acc = FakeAccount()
        refresh_called = threading.Event()

        def fake_refresh(_acc, _preserve_status=False):
            refresh_called.set()

        api._multi_refresh_worker_unlocked = fake_refresh
        acc.account_operation_lock.acquire()
        try:
            main_module.Api._multi_refresh_worker(api, acc, False)
            self.assertFalse(refresh_called.is_set())
        finally:
            acc.account_operation_lock.release()

        main_module.Api._multi_refresh_worker(api, acc, False)
        self.assertTrue(refresh_called.is_set())

    def test_single_and_multi_execution_cannot_claim_same_school_account(self):
        api = self._new_api()
        acc = FakeAccount()
        single_execution_token = object()

        claimed, conflict = main_module._claim_school_account_execution(
            ["account-1"],
            single_execution_token,
        )
        self.assertTrue(claimed)
        self.assertIsNone(conflict)
        self.assertFalse(
            main_module.Api._start_multi_account_worker(
                api,
                acc,
                0,
                True,
            )
        )

        main_module._release_school_account_execution(single_execution_token)
        self.assertTrue(acc.account_operation_lock.acquire(blocking=False))
        acc.account_operation_lock.release()

    def test_adding_school_account_does_not_claim_execution_slot(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        add_account_block = source.split(
            "def multi_add_account(",
            1,
        )[1].split(
            "def multi_remove_account(",
            1,
        )[0]

        self.assertNotIn(
            "_claim_school_account_execution(",
            add_account_block,
        )

    def test_all_task_execution_entrypoints_use_execution_claims(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        single_run_block = source.split(
            "def start_single_run(",
            1,
        )[1].split(
            "def stop_run(",
            1,
        )[0]
        start_all_block = source.split(
            "def start_all_runs(",
            1,
        )[1].split(
            "def _run_all_tasks_manager(",
            1,
        )[0]
        background_block = source.split(
            "def start_background_task(",
            1,
        )[1].split(
            "def _execute_tasks_background(",
            1,
        )[0]

        self.assertIn(
            "_claim_single_school_account_execution(",
            single_run_block,
        )
        self.assertIn(
            "_claim_single_school_account_execution(",
            start_all_block,
        )
        self.assertIn(
            "_claim_school_account_execution(",
            background_block,
        )

    def test_refresh_worker_pushes_user_facing_executable_task_status(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        refresh_block = source.split(
            "def _multi_refresh_worker_unlocked(",
            1,
        )[1].split(
            "def multi_remove_selected_accounts(",
            1,
        )[0]

        self.assertIn(
            'final_status = f"有 {exe_cnt} 个任务可执行"',
            refresh_block,
        )
        self.assertIn(
            "status_text=final_status, summary=acc.summary",
            refresh_block,
        )
        self.assertNotIn("Have_Tasks", refresh_block)


if __name__ == "__main__":
    unittest.main()
