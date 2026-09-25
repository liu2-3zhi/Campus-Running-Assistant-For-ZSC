import json
import tempfile
import unittest
from pathlib import Path
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

    def test_login_response_populates_gender_from_dept_info(self):
        user_data = SimpleNamespace()

        main.Api._apply_login_profile_to_user_data(
            user_data,
            {
                "userInfo": {"name": "Alice", "account": "student-a"},
                "deptInfo": {"sexValue": "女", "schoolName": "测试学校"},
            },
        )

        self.assertEqual("女", user_data.gender)
        self.assertEqual("测试学校", user_data.school_name)

    def test_login_response_maps_numeric_gender_when_text_is_missing(self):
        user_data = SimpleNamespace()

        main.Api._apply_login_profile_to_user_data(
            user_data,
            {
                "userInfo": {"name": "Bob", "account": "student-b", "sex": 1},
                "deptInfo": {},
            },
        )

        self.assertEqual("男", user_data.gender)

    def test_status_uses_flat_backup_when_session_gender_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "student-a_backup.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "userInfo": {"name": "Alice", "sex": 2},
                        "deptInfo": {"sexValue": "女"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            api = object.__new__(main.Api)
            api.user_dir = temp_dir
            api.accounts = {
                "student-a": SimpleNamespace(
                    username="student-a",
                    user_data=SimpleNamespace(
                        name="Alice",
                        gender="",
                        username="student-a",
                        student_id="student-a",
                    ),
                    status_text="无任务可执行",
                    summary={"total": 0, "completed": 0, "executable": 0},
                    tag="",
                    all_run_data=[],
                    current_position=None,
                )
            }

            with patch.object(
                api, "_is_multi_account_execution_active", return_value=False
            ):
                result = api.multi_get_all_accounts_status()

        self.assertEqual("女", result["accounts"][0]["gender"])

    def test_shared_backup_helper_writes_single_flat_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            api = object.__new__(main.Api)
            api.user_dir = temp_dir
            api._load_school_account_stats_from_ini = lambda _username: {
                "overdue_count": 2,
                "completed_count": 3,
            }

            backup_path = api._persist_school_account_backup(
                "student-a",
                {"name": "Alice"},
                {"sexValue": "女"},
                source="test",
            )

            self.assertEqual(
                str(Path(temp_dir) / "student-a_backup.json"),
                backup_path,
            )
            backup_data = json.loads(
                Path(backup_path).read_text(encoding="utf-8")
            )

        self.assertEqual("女", backup_data["deptInfo"]["sexValue"])
        self.assertEqual(2, backup_data["overdue_count"])
        self.assertEqual(3, backup_data["completed_count"])

    def test_multi_login_paths_share_profile_and_backup_helpers(self):
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
            encoding="utf-8"
        )
        execution_block = source.split(
            "def _multi_account_worker(", 1
        )[1].split(
            "def _run_all_multi_accounts_thread(", 1
        )[0]
        refresh_block = source.split(
            "def _multi_refresh_worker_unlocked(", 1
        )[1].split(
            "def multi_remove_selected_accounts(", 1
        )[0]

        for block in (execution_block, refresh_block):
            self.assertIn("_apply_login_profile_to_user_data(", block)
            self.assertIn("_persist_school_account_backup(", block)


if __name__ == "__main__":
    unittest.main()
