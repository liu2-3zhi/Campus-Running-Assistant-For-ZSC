import unittest
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


if __name__ == "__main__":
    unittest.main()
