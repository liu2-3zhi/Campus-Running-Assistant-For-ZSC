import gc
import tempfile
import threading
import time
import unittest
import weakref
from pathlib import Path
from unittest import mock

import main as main_module


class DummyUserData:
    username = "school-user"
    id = "account-1"


class DummyAccount:
    def __init__(self):
        self.user_data = DummyUserData()
        self.params = {"auto_attendance_refresh_s": 15}
        self.stop_event = threading.Event()
        self.worker_thread = None


class DummyApi:
    is_guest = True
    is_multi_account_mode = False

    def __init__(self):
        self._web_session_id = ""
        self.stop_run_flag = threading.Event()
        self.multi_run_stop_flag = threading.Event()
        self.stop_auto_refresh = threading.Event()
        self.stop_multi_auto_refresh = threading.Event()
        self.stop_account_monitor = threading.Event()
        self.threads_lock = threading.Lock()
        self.account_refresh_threads = {}
        self.accounts = {}
        self.account = DummyAccount()
        self.api_client = mock.Mock()

    def _get_account_by_id(self, account_id):
        return self.account

    def _get_session_stop_event(self):
        return main_module.Api._get_session_stop_event(self)

    def shutdown_session_runtime(self, reason="cleanup", timeout=3.0):
        return main_module.Api.shutdown_session_runtime(
            self,
            reason=reason,
            timeout=timeout,
        )


class TestSessionRuntimeCleanup(unittest.TestCase):
    def _patch_session_globals(self, temp_dir):
        return mock.patch.multiple(
            main_module,
            web_sessions={},
            web_sessions_lock=threading.Lock(),
            session_activity={},
            session_activity_lock=threading.Lock(),
            browsing_activity={},
            browsing_activity_lock=threading.Lock(),
            session_file_locks={},
            session_file_locks_lock=threading.Lock(),
            SESSION_STORAGE_DIR=str(Path(temp_dir) / "sessions"),
            SESSION_INDEX_FILE=str(Path(temp_dir) / "sessions" / "_index.json"),
            chrome_pool=None,
            create=True,
        )

    def test_cleanup_inactive_session_stops_account_refresh_thread(self):
        main_module._is_auto_attendance_enabled = lambda _username: False
        session_id = "11111111-1111-4111-8111-111111111111"

        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ):
            api = DummyApi()
            api._web_session_id = session_id
            main_module.web_sessions[session_id] = api

            stop_event = main_module.Api._get_session_stop_event(api)
            thread = threading.Thread(
                target=main_module.Api._account_refresh_worker,
                args=(api, "account-1", stop_event),
                daemon=True,
            )
            api.account_refresh_threads["account-1"] = thread
            thread.start()
            time.sleep(0.05)

            main_module.cleanup_inactive_session(session_id)
            thread.join(timeout=1.0)

            self.assertFalse(thread.is_alive())
            self.assertNotIn(session_id, main_module.web_sessions)
            api.api_client.session.close.assert_called_once()

    def test_cleanup_inactive_session_stops_multi_account_monitor(self):
        session_id = "22222222-2222-4222-8222-222222222222"

        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ):
            api = DummyApi()
            api._web_session_id = session_id
            api.is_multi_account_mode = True
            main_module.web_sessions[session_id] = api

            stop_event = main_module.Api._get_session_stop_event(api)
            thread = threading.Thread(
                target=main_module.Api._multi_account_monitor_worker,
                args=(api, stop_event),
                daemon=True,
            )
            api.account_monitor_thread = thread
            thread.start()
            time.sleep(0.05)

            main_module.cleanup_inactive_session(session_id)
            thread.join(timeout=1.0)

            self.assertFalse(thread.is_alive())

    def test_cleanup_inactive_session_closes_playwright_context(self):
        session_id = "33333333-3333-4333-8333-333333333333"
        pool = mock.Mock()

        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ):
            main_module.chrome_pool = pool
            main_module.web_sessions[session_id] = DummyApi()

            main_module.cleanup_inactive_session(session_id)

            pool.cleanup_context.assert_called_once_with(session_id)

    def test_auth_unlink_failure_does_not_skip_runtime_shutdown(self):
        session_id = "44444444-4444-4444-8444-444444444444"
        auth_system = mock.Mock()
        auth_system.get_user_sessions.return_value = []
        auth_system.unlink_session_from_user.side_effect = RuntimeError(
            "user already deleted"
        )
        token_manager = mock.Mock()

        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ), mock.patch.multiple(
            main_module,
            auth_system=auth_system,
            token_manager=token_manager,
            create=True,
        ):
            api = DummyApi()
            api.is_guest = False
            api.auth_username = "alice"
            api._web_session_id = session_id
            main_module.web_sessions[session_id] = api

            main_module.cleanup_inactive_session(session_id)

            self.assertNotIn(session_id, main_module.web_sessions)
            api.api_client.session.close.assert_called_once()

    def test_repeated_session_cleanup_releases_api_instances(self):
        main_module._is_auto_attendance_enabled = lambda _username: False

        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ):
            refs = []
            threads = []

            for index in range(10):
                session_id = f"session-{index}"
                account_id = f"account-{index}"
                api = DummyApi()
                api._web_session_id = session_id
                main_module.web_sessions[session_id] = api

                stop_event = main_module.Api._get_session_stop_event(api)
                thread = threading.Thread(
                    target=main_module.Api._account_refresh_worker,
                    args=(api, account_id, stop_event),
                    daemon=True,
                )
                api.account_refresh_threads[account_id] = thread
                thread.start()
                threads.append(thread)
                refs.append(weakref.ref(api))

                main_module.cleanup_inactive_session(session_id)

            api = None
            thread = None
            for thread in threads:
                thread.join(timeout=1.0)
            thread = None
            gc.collect()

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertTrue(all(ref() is None for ref in refs))

    def test_memory_diagnostics_snapshot_has_operational_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir, self._patch_session_globals(
            temp_dir
        ), self.assertLogs(level="INFO") as captured_logs:
            main_module._log_runtime_memory_diagnostics("unit-test")

        snapshot_logs = [
            line
            for line in captured_logs.output
            if "[内存诊断] 快照" in line
        ]
        self.assertEqual(len(snapshot_logs), 1)
        snapshot = snapshot_logs[0]
        for field in (
            "context=unit-test",
            "web_sessions=",
            "account_refresh_threads=",
            "multi_monitor_threads=",
            "playwright_contexts=",
            "ip_cache=",
            "phone_cache=",
            "sms_codes=",
            "rss_mb=",
            "max_rss_mb=",
        ):
            self.assertIn(field, snapshot)


if __name__ == "__main__":
    unittest.main()
