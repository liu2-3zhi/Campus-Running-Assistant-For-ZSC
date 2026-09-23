import unittest
import threading
from types import SimpleNamespace
from unittest import mock

import requests

import main


class TestNetworkRetryCount(unittest.TestCase):
    def test_api_requests_retry_ten_times(self):
        api_client = object.__new__(main.ApiClient)
        api_client.session = mock.Mock()
        api_client.session.get.side_effect = requests.exceptions.Timeout(
            "request timed out"
        )
        api_client.app = SimpleNamespace(
            log=lambda _message: None,
            is_offline_mode=False,
        )

        with mock.patch.object(
            api_client, "_get_headers", return_value={}
        ), mock.patch.object(main.time, "sleep"), mock.patch.object(
            main, "requests", requests, create=True
        ):
            result = api_client._request("GET", "https://example.invalid/test")

        self.assertIsNone(result)
        self.assertEqual(10, api_client.session.get.call_count)

    def test_account_stop_event_aborts_retry_loop_immediately(self):
        api_client = object.__new__(main.ApiClient)
        api_client.session = mock.Mock()
        stop_event = threading.Event()

        def fail_once(*_args, **_kwargs):
            stop_event.set()
            raise requests.exceptions.Timeout("request timed out")

        api_client.session.get.side_effect = fail_once
        api_client._execution_cancel_event = stop_event
        api_client.app = SimpleNamespace(
            log=lambda _message: None,
            is_offline_mode=False,
        )

        with mock.patch.object(
            api_client, "_get_headers", return_value={}
        ), mock.patch.object(main.time, "sleep"), mock.patch.object(
            main, "requests", requests, create=True
        ):
            result = api_client._request("GET", "https://example.invalid/test")

        self.assertIsNone(result)
        self.assertEqual(1, api_client.session.get.call_count)

    def test_background_refresh_ignores_old_account_and_global_stop_flags(self):
        api_client = object.__new__(main.ApiClient)
        stop_event = threading.Event()
        stop_event.set()
        global_stop = threading.Event()
        global_stop.set()
        api_client.app = SimpleNamespace(
            log=lambda _message: None,
            is_offline_mode=False,
            stop_event=stop_event,
            api_bridge=SimpleNamespace(multi_run_stop_flag=global_stop),
        )
        api_client._execution_cancel_event = None

        self.assertFalse(api_client._request_cancelled_by_stop())


if __name__ == "__main__":
    unittest.main()
