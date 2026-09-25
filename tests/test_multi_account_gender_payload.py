import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class TestMultiAccountGenderPayload(unittest.TestCase):
    def test_account_status_payload_includes_gender_for_expanded_filters(self):
        api = object.__new__(main.Api)
        api.accounts = {
            "student-a": SimpleNamespace(
                username="student-a",
                user_data=SimpleNamespace(name="Alice", gender="女"),
                status_text="全部完成",
                summary={"total": 1, "completed": 1, "executable": 0},
                tag="",
                all_run_data=[],
                current_position=None,
            )
        }

        with patch.object(api, "_is_multi_account_execution_active", return_value=False):
            result = api.multi_get_all_accounts_status()

        self.assertEqual("女", result["accounts"][0]["gender"])


if __name__ == "__main__":
    unittest.main()
