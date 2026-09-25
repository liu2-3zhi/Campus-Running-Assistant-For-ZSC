import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main


class TestSharedSubmissionRetry(unittest.TestCase):
    def _new_api(self):
        api = object.__new__(main.Api)
        api.is_offline_mode = False
        return api

    def _submit_with_retries(self, api, stop_event=None, log_func=None):
        return api._submit_chunk_with_retries(
            object(),
            [],
            0,
            False,
            0,
            object(),
            SimpleNamespace(student_id="account-1"),
            stop_event=stop_event or threading.Event(),
            log_func=log_func or (lambda _message: None),
        )

    def test_shared_retry_succeeds_after_transient_failures(self):
        api = self._new_api()
        api._submit_chunk = mock.Mock(side_effect=[False, False, True])

        result = self._submit_with_retries(api)

        self.assertTrue(result)
        self.assertEqual(3, api._submit_chunk.call_count)

    def test_shared_retry_stops_after_ten_failures(self):
        api = self._new_api()
        api._submit_chunk = mock.Mock(return_value=False)

        result = self._submit_with_retries(api)

        self.assertFalse(result)
        self.assertEqual(10, api._submit_chunk.call_count)

    def test_shared_retry_cancels_backoff_when_stop_event_is_set(self):
        api = self._new_api()
        stop_event = threading.Event()

        def fail_and_stop(*_args, **_kwargs):
            stop_event.set()
            return False

        api._submit_chunk = mock.Mock(side_effect=fail_and_stop)

        result = self._submit_with_retries(api, stop_event=stop_event)

        self.assertFalse(result)
        self.assertEqual(1, api._submit_chunk.call_count)

    def test_single_and_multi_submission_loops_reuse_shared_retry(self):
        source = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")
        single_loop = source.split(
            "def _run_submission_thread(",
            1,
        )[1].split(
            "def _submit_chunk_with_retries(",
            1,
        )[0]
        multi_loop = source.split(
            "def _multi_account_worker(",
            1,
        )[1].split(
            "def _multi_refresh_worker(",
            1,
        )[0]

        self.assertIn("_submit_chunk_with_retries(", single_loop)
        self.assertIn("_submit_chunk_with_retries(", multi_loop)


if __name__ == "__main__":
    unittest.main()
