import contextlib
import io
import logging
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestLogRotationResilience(unittest.TestCase):
    def test_single_instance_lock_rejects_a_second_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = str(Path(temp_dir) / "main.lock")
            holder_code = (
                "import main, sys, time; "
                "print('LOCK_RESULT=' + str(main._acquire_single_instance_lock(sys.argv[1])), flush=True); "
                "time.sleep(30)"
            )
            holder = subprocess.Popen(
                [sys.executable, "-c", holder_code, lock_path],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                holder_result = ""
                for _ in range(50):
                    line = holder.stdout.readline()
                    if line.startswith("LOCK_RESULT="):
                        holder_result = line.strip()
                        break
                self.assertEqual(holder_result, "LOCK_RESULT=True")
                contender_code = (
                    "import main, sys; "
                    "print('LOCK_RESULT=' + str(main._acquire_single_instance_lock(sys.argv[1])), flush=True)"
                )
                contender = subprocess.run(
                    [sys.executable, "-c", contender_code, lock_path],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(contender.returncode, 0)
                contender_result = [
                    line.strip()
                    for line in contender.stdout.splitlines()
                    if line.startswith("LOCK_RESULT=")
                ]
                self.assertEqual(contender_result, ["LOCK_RESULT=False"])
            finally:
                holder.terminate()
                try:
                    holder.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    holder.kill()
                    holder.wait(timeout=10)

    def test_failed_rollover_retries_are_backed_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = str(Path(temp_dir) / "test.log")
            handler = main.CustomLogHandler(log_path, max_bytes=1)
            handler.setFormatter(logging.Formatter("%(message)s"))
            record = logging.LogRecord(
                "rotation-test",
                logging.INFO,
                __file__,
                1,
                "payload",
                (),
                None,
            )
            try:
                with contextlib.redirect_stdout(io.StringIO()), patch(
                    "main.os.rename",
                    side_effect=PermissionError("locked"),
                ) as rename_mock:
                    handler.emit(record)
                    handler.emit(record)
                    handler.emit(record)
                    time.sleep(0.01)
                self.assertEqual(rename_mock.call_count, 1)
            finally:
                handler.close()


if __name__ == "__main__":
    unittest.main()
