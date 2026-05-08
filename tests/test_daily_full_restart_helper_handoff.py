import json
import os
import tempfile
import unittest
from unittest import mock

import main as main_module


class TestDailyFullRestartHelperHandoff(unittest.TestCase):
    def test_daily_restart_marker_round_trip_and_same_day_guard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = os.path.join(tmpdir, "daily_restart_marker.json")
            now_dt = main_module.datetime.datetime(2026, 5, 7, 0, 0, 5)

            self.assertFalse(
                main_module._has_daily_full_restart_marker_for_date(
                    now_dt.date(), marker_path
                )
            )

            main_module._write_daily_full_restart_marker(marker_path, now_dt)

            self.assertTrue(
                main_module._has_daily_full_restart_marker_for_date(
                    now_dt.date(), marker_path
                )
            )
            self.assertFalse(
                main_module._has_daily_full_restart_marker_for_date(
                    main_module.datetime.date(2026, 5, 8), marker_path
                )
            )

    def test_build_daily_restart_helper_command_preserves_forwarded_args(self):
        command = main_module._build_daily_restart_helper_command(
            old_pid=4321,
            python_executable=r"C:\Python\python.exe",
            main_script_path=r"C:\repo\main.py",
            cwd=r"C:\repo",
            restart_log_path=r"C:\repo\logs\daily_restart.log",
            restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            forwarded_argv=["--port", "5055", "--log-level", "info"],
        )

        self.assertEqual(
            command[:2], [r"C:\Python\python.exe", r"C:\repo\main.py"]
        )
        self.assertIn("--daily-restart-helper", command)
        self.assertIn("--daily-restart-parent-pid", command)
        self.assertIn("4321", command)
        payload = json.loads(
            command[command.index("--daily-restart-forward-args-json") + 1]
        )
        self.assertEqual(payload, ["--port", "5055", "--log-level", "info"])

    def test_build_main_arg_parser_accepts_hidden_daily_restart_flags(self):
        parser = main_module._build_main_arg_parser()
        args = parser.parse_args(
            [
                "--daily-restart-helper",
                "--daily-restart-parent-pid",
                "4321",
                "--daily-restart-python-executable",
                r"C:\Python\python.exe",
                "--daily-restart-main-script-path",
                r"C:\repo\main.py",
                "--daily-restart-cwd",
                r"C:\repo",
                "--daily-restart-log-path",
                r"C:\repo\logs\daily_restart.log",
                "--daily-restart-marker-path",
                r"C:\repo\logs\daily_restart_marker.json",
                "--daily-restart-forward-args-json",
                '["--port", "5055"]',
            ]
        )

        self.assertTrue(args.daily_restart_helper)
        self.assertEqual(args.daily_restart_parent_pid, 4321)
        self.assertEqual(
            args.daily_restart_python_executable, r"C:\Python\python.exe"
        )
        self.assertEqual(args.daily_restart_main_script_path, r"C:\repo\main.py")
        self.assertEqual(args.daily_restart_cwd, r"C:\repo")

    def test_wait_for_process_exit_polls_until_process_stops(self):
        checks = []
        running_states = iter([True, True, False])

        finished = main_module._wait_for_process_exit(
            4321,
            timeout_seconds=10,
            poll_interval=0.01,
            is_running_func=lambda pid: checks.append(pid) or next(running_states),
            sleep_func=lambda seconds: None,
            monotonic_func=iter([0.0, 0.01, 0.02]).__next__,
        )

        self.assertTrue(finished)
        self.assertEqual(checks, [4321, 4321, 4321])

    def test_run_daily_restart_helper_relaunches_main_after_parent_exits(self):
        args = main_module.argparse.Namespace(
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=r"C:\Python\python.exe",
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json='["--port", "5055", "--log-level", "info"]',
        )

        with mock.patch.object(
            main_module, "_wait_for_process_exit", return_value=True
        ) as wait_for_exit, mock.patch.object(
            main_module.subprocess, "Popen", return_value=mock.Mock(pid=9876)
        ) as popen, mock.patch.object(
            main_module, "_append_daily_full_restart_log"
        ) as append_log:
            result = main_module._run_daily_restart_helper(args)

        self.assertTrue(result)
        wait_for_exit.assert_called_once_with(4321)
        popen.assert_called_once_with(
            [
                r"C:\Python\python.exe",
                r"C:\repo\main.py",
                "--port",
                "5055",
                "--log-level",
                "info",
            ],
            cwd=r"C:\repo",
        )
        self.assertGreaterEqual(append_log.call_count, 2)

    def test_run_daily_restart_helper_timeout_does_not_relaunch_main(self):
        args = main_module.argparse.Namespace(
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=r"C:\Python\python.exe",
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json="[]",
        )

        with mock.patch.object(
            main_module, "_wait_for_process_exit", return_value=False
        ) as wait_for_exit, mock.patch.object(
            main_module.subprocess, "Popen"
        ) as popen, mock.patch.object(
            main_module, "_append_daily_full_restart_log"
        ) as append_log:
            result = main_module._run_daily_restart_helper(args)

        self.assertFalse(result)
        wait_for_exit.assert_called_once_with(4321)
        popen.assert_not_called()
        self.assertGreaterEqual(append_log.call_count, 2)

    def test_trigger_daily_full_restart_skips_same_day_repeat(self):
        now_dt = main_module.datetime.datetime(2026, 5, 7, 0, 0, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = os.path.join(tmpdir, "daily_restart_marker.json")
            log_path = os.path.join(tmpdir, "daily_restart.log")
            main_module._write_daily_full_restart_marker(marker_path, now_dt)

            with mock.patch.object(
                main_module,
                "_get_daily_full_restart_marker_path",
                return_value=marker_path,
            ), mock.patch.object(
                main_module,
                "_get_daily_full_restart_log_path",
                return_value=log_path,
            ), mock.patch.object(
                main_module.subprocess, "Popen"
            ) as popen:
                result = main_module._trigger_daily_full_restart(
                    now_dt=now_dt,
                    exit_func=lambda code: (_ for _ in ()).throw(AssertionError(code)),
                )

        self.assertFalse(result)
        popen.assert_not_called()

    def test_trigger_daily_full_restart_helper_failure_does_not_exit(self):
        now_dt = main_module.datetime.datetime(2026, 5, 7, 0, 0, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = os.path.join(tmpdir, "daily_restart_marker.json")
            log_path = os.path.join(tmpdir, "daily_restart.log")
            exit_calls = []

            with mock.patch.object(
                main_module,
                "_get_daily_full_restart_marker_path",
                return_value=marker_path,
            ), mock.patch.object(
                main_module,
                "_get_daily_full_restart_log_path",
                return_value=log_path,
            ), mock.patch.object(
                main_module.subprocess,
                "Popen",
                side_effect=RuntimeError("spawn failed"),
            ):
                result = main_module._trigger_daily_full_restart(
                    now_dt=now_dt,
                    exit_func=lambda code: exit_calls.append(code),
                )

        self.assertFalse(result)
        self.assertEqual(exit_calls, [])
        self.assertFalse(os.path.exists(marker_path))

    def test_trigger_daily_full_restart_writes_marker_and_exits_after_helper_spawn(self):
        now_dt = main_module.datetime.datetime(2026, 5, 7, 0, 0, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            marker_path = os.path.join(tmpdir, "daily_restart_marker.json")
            log_path = os.path.join(tmpdir, "daily_restart.log")
            exit_calls = []

            with mock.patch.object(
                main_module,
                "_get_daily_full_restart_marker_path",
                return_value=marker_path,
            ), mock.patch.object(
                main_module,
                "_get_daily_full_restart_log_path",
                return_value=log_path,
            ), mock.patch.object(
                main_module.subprocess, "Popen", return_value=mock.Mock(pid=9876)
            ) as popen:
                result = main_module._trigger_daily_full_restart(
                    now_dt=now_dt,
                    exit_func=lambda code: exit_calls.append(code),
                )

                self.assertTrue(result)
                self.assertEqual(exit_calls, [0])
                self.assertTrue(
                    main_module._has_daily_full_restart_marker_for_date(now_dt.date(), marker_path)
                )
                popen.assert_called_once()

    def test_run_daily_restart_helper_rejects_missing_launch_metadata(self):
        args = main_module.argparse.Namespace(
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=None,
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json="[]",
        )

        with mock.patch.object(
            main_module, "_wait_for_process_exit"
        ) as wait_for_exit, mock.patch.object(
            main_module.subprocess, "Popen"
        ) as popen, mock.patch.object(
            main_module, "_append_daily_full_restart_log"
        ) as append_log:
            result = main_module._run_daily_restart_helper(args)

        self.assertFalse(result)
        wait_for_exit.assert_not_called()
        popen.assert_not_called()
        self.assertGreaterEqual(append_log.call_count, 1)

    def test_run_daily_restart_helper_drops_helper_only_forwarded_flags(self):
        args = main_module.argparse.Namespace(
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=r"C:\Python\python.exe",
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json=(
                '["--port", "5055", "--daily-restart-helper", '
                '"--daily-restart-parent-pid", "4321", '
                '"--daily-restart-python-executable", "C:/Python/python.exe", '
                '"--daily-restart-main-script-path", "C:/repo/main.py", '
                '"--daily-restart-cwd", "C:/repo", '
                '"--daily-restart-log-path", "C:/repo/logs/daily_restart.log", '
                '"--daily-restart-marker-path", "C:/repo/logs/daily_restart_marker.json", '
                '"--daily-restart-forward-args-json", "[]", '
                '"--log-level", "info"]'
            ),
        )

        with mock.patch.object(
            main_module, "_wait_for_process_exit", return_value=True
        ), mock.patch.object(
            main_module.subprocess, "Popen", return_value=mock.Mock(pid=9876)
        ) as popen, mock.patch.object(
            main_module, "_append_daily_full_restart_log"
        ):
            result = main_module._run_daily_restart_helper(args)

        self.assertTrue(result)
        popen.assert_called_once_with(
            [
                r"C:\Python\python.exe",
                r"C:\repo\main.py",
                "--port",
                "5055",
                "--log-level",
                "info",
            ],
            cwd=r"C:\repo",
        )

    def test_run_daily_restart_helper_drops_helper_only_equals_forwarded_flags(self):
        args = main_module.argparse.Namespace(
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=r"C:\Python\python.exe",
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json=(
                '["--port=5055", "--daily-restart-helper", '
                '"--daily-restart-parent-pid=4321", '
                '"--daily-restart-python-executable=C:/Python/python.exe", '
                '"--daily-restart-main-script-path=C:/repo/main.py", '
                '"--daily-restart-cwd=C:/repo", '
                '"--daily-restart-log-path=C:/repo/logs/daily_restart.log", '
                '"--daily-restart-marker-path=C:/repo/logs/daily_restart_marker.json", '
                '"--daily-restart-forward-args-json=[]", '
                '"--log-level=info"]'
            ),
        )

        with mock.patch.object(
            main_module, "_wait_for_process_exit", return_value=True
        ), mock.patch.object(
            main_module.subprocess, "Popen", return_value=mock.Mock(pid=9876)
        ) as popen, mock.patch.object(
            main_module, "_append_daily_full_restart_log"
        ):
            result = main_module._run_daily_restart_helper(args)

        self.assertTrue(result)
        popen.assert_called_once_with(
            [
                r"C:\Python\python.exe",
                r"C:\repo\main.py",
                "--port=5055",
                "--log-level=info",
            ],
            cwd=r"C:\repo",
        )

    def test_main_dispatches_daily_restart_helper_before_web_startup(self):
        helper_args = main_module.argparse.Namespace(
            daily_restart_helper=True,
            daily_restart_parent_pid=4321,
            daily_restart_python_executable=r"C:\Python\python.exe",
            daily_restart_main_script_path=r"C:\repo\main.py",
            daily_restart_cwd=r"C:\repo",
            daily_restart_log_path=r"C:\repo\logs\daily_restart.log",
            daily_restart_marker_path=r"C:\repo\logs\daily_restart_marker.json",
            daily_restart_forward_args_json="[]",
            port=5000,
            host="127.0.0.1",
            headless=True,
            log_level="debug",
            debug=False,
        )
        parser_mock = mock.Mock(parse_args=mock.Mock(return_value=helper_args))

        with mock.patch.object(
            main_module, "_build_main_arg_parser", return_value=parser_mock
        ), mock.patch.object(
            main_module, "setup_logging"
        ), mock.patch.object(
            main_module, "_run_daily_restart_helper", return_value=True
        ) as run_helper, mock.patch.object(
            main_module, "import_standard_libraries"
        ) as import_standard_libraries, mock.patch.object(
            main_module, "check_and_import_dependencies"
        ) as check_and_import_dependencies, mock.patch.object(
            main_module, "start_web_server"
        ) as start_web_server:
            result = main_module.main()

        self.assertTrue(result)
        run_helper.assert_called_once_with(helper_args)
        import_standard_libraries.assert_not_called()
        check_and_import_dependencies.assert_not_called()
        start_web_server.assert_not_called()


if __name__ == "__main__":
    unittest.main()

