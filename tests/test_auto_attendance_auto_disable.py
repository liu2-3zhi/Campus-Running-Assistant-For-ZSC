import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import main as main_module


class FakeAttendanceClient:
    def __init__(self, notices):
        self.notices = notices
        self.info_calls = []

    def get_notice_list(self, **_kwargs):
        return {"success": True, "data": {"noticeList": self.notices}}

    def get_roll_call_info(self, roll_call_id, _user_id):
        self.info_calls.append(roll_call_id)
        return {
            "success": True,
            "data": {"rollCallInfo": {"status": -1}, "attendFinish": 0},
        }


class TestAutoAttendanceAutoDisable(unittest.TestCase):
    def test_default_parameters_enable_auto_disable_after_one_success(self):
        api = object.__new__(main_module.Api)

        api._init_state_variables()

        self.assertTrue(api.global_params["auto_attendance_stop_after_success"])
        self.assertEqual(api.global_params["auto_attendance_success_limit"], 1)

    def test_success_count_is_persisted_across_checks_and_disables_at_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            main_module, "AUTO_ATTENDANCE_CONFIG_FILE", f"{temp_dir}/attendance.json"
        ):
            main_module._save_auto_attendance_config(
                {
                    "enabled_accounts": {
                        "school-user": {
                            "session_uuid": "session-1",
                            "successful_count": 0,
                        }
                    }
                }
            )

            params = {
                "auto_attendance_stop_after_success": True,
                "auto_attendance_success_limit": 2,
            }

            socketio = mock.Mock()
            with mock.patch.object(main_module, "socketio", socketio, create=True):
                self.assertFalse(
                    main_module._record_auto_attendance_success("school-user", params)
                )
            with open(f"{temp_dir}/attendance.json", encoding="utf-8") as fp:
                config = json.load(fp)
            self.assertEqual(
                config["enabled_accounts"]["school-user"]["successful_count"], 1
            )

            with mock.patch.object(main_module, "socketio", socketio, create=True):
                self.assertTrue(
                    main_module._record_auto_attendance_success("school-user", params)
                )
            config = main_module._load_auto_attendance_config()
            self.assertNotIn("school-user", config["enabled_accounts"])
            socketio.emit.assert_called_once_with(
                "auto_attendance_updated",
                {
                    "enabled": False,
                    "successful_count": 2,
                    "success_limit": 2,
                },
                room="session-1",
            )

    def test_auto_check_stops_processing_after_threshold_success(self):
        notices = [
            {"id": "roll-1", "image": "attendance", "title": "签到 1", "updateBy": "1,2"},
            {"id": "roll-2", "image": "attendance", "title": "签到 2", "updateBy": "3,4"},
        ]
        client = FakeAttendanceClient(notices)
        api = object.__new__(main_module.Api)
        api.api_client = client
        api.user_data = SimpleNamespace(id="user-1", username="school-user")
        api.params = {
            "auto_attendance_stop_after_success": True,
            "auto_attendance_success_limit": 1,
        }
        api.log = mock.Mock()
        api.trigger_attendance = mock.Mock(return_value={"success": True, "message": "签到成功"})

        with mock.patch.object(main_module, "_is_auto_attendance_enabled", return_value=True), mock.patch.object(
            main_module, "_record_auto_attendance_success", return_value=True
        ) as record_success:
            api._check_and_trigger_auto_attendance(api)

        api.trigger_attendance.assert_called_once()
        record_success.assert_called_once_with("school-user", api.params)
        self.assertEqual(client.info_calls, ["roll-1"])

    def test_disabled_auto_close_does_not_change_persisted_count(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            main_module, "AUTO_ATTENDANCE_CONFIG_FILE", f"{temp_dir}/attendance.json"
        ):
            main_module._save_auto_attendance_config(
                {
                    "enabled_accounts": {
                        "school-user": {
                            "session_uuid": "session-1",
                            "successful_count": 3,
                        }
                    }
                }
            )

            self.assertFalse(
                main_module._record_auto_attendance_success(
                    "school-user",
                    {
                        "auto_attendance_stop_after_success": False,
                        "auto_attendance_success_limit": 1,
                    },
                )
            )
            config = main_module._load_auto_attendance_config()
            self.assertEqual(
                config["enabled_accounts"]["school-user"]["successful_count"], 3
            )

    def test_failed_attendance_is_not_counted(self):
        client = FakeAttendanceClient(
            [{"id": "roll-1", "image": "attendance", "title": "签到 1", "updateBy": "1,2"}]
        )
        api = object.__new__(main_module.Api)
        api.api_client = client
        api.user_data = SimpleNamespace(id="user-1", username="school-user")
        api.params = {
            "auto_attendance_stop_after_success": True,
            "auto_attendance_success_limit": 1,
        }
        api.log = mock.Mock()
        api.trigger_attendance = mock.Mock(
            return_value={"success": False, "message": "签到失败"}
        )

        with mock.patch.object(main_module, "_is_auto_attendance_enabled", return_value=True), mock.patch.object(
            main_module, "_record_auto_attendance_success"
        ) as record_success:
            api._check_and_trigger_auto_attendance(api)

        api.trigger_attendance.assert_called_once()
        record_success.assert_not_called()

    def test_already_signed_attendance_is_not_counted(self):
        client = FakeAttendanceClient(
            [{"id": "roll-1", "image": "attendance", "title": "签到 1", "updateBy": "1,2"}]
        )
        api = object.__new__(main_module.Api)
        api.api_client = client
        api.user_data = SimpleNamespace(id="user-1", username="school-user")
        api.params = {
            "auto_attendance_stop_after_success": True,
            "auto_attendance_success_limit": 1,
        }
        api.log = mock.Mock()
        api.trigger_attendance = mock.Mock(
            return_value={"success": True, "message": "已签到"}
        )

        with mock.patch.object(main_module, "_is_auto_attendance_enabled", return_value=True), mock.patch.object(
            main_module, "_record_auto_attendance_success"
        ) as record_success:
            api._check_and_trigger_auto_attendance(api)

        api.trigger_attendance.assert_called_once()
        record_success.assert_not_called()

    def test_success_limit_update_clamps_to_one(self):
        api = object.__new__(main_module.Api)
        api.global_params = {"auto_attendance_success_limit": 1}
        api.params = api.global_params.copy()
        api.is_multi_account_mode = False
        api.user_data = SimpleNamespace(username=None, id=None)
        api.config_path = "config.ini"

        with mock.patch.object(main_module, "_read_config_ini", return_value=None), mock.patch.object(
            main_module, "_write_config_with_comments"
        ):
            result = api.update_param("auto_attendance_success_limit", 0)

        self.assertTrue(result["success"])
        self.assertEqual(api.params["auto_attendance_success_limit"], 1)

    def test_loaded_global_auto_disable_values_reach_single_account_params(self):
        api = object.__new__(main_module.Api)
        api.config_path = "config.ini"
        api.is_multi_account_mode = False
        api.global_params = {
            "auto_attendance_stop_after_success": True,
            "auto_attendance_success_limit": 1,
            "auto_attendance_refresh_s": 15,
            "attendance_user_radius_m": 40,
        }
        api.params = api.global_params.copy()

        config = main_module._get_default_config()
        config.add_section("Config")
        config.set("Config", "auto_attendance_stop_after_success", "false")
        config.set("Config", "auto_attendance_success_limit", "4")

        with mock.patch.object(main_module.os.path, "exists", return_value=True), mock.patch.object(
            main_module, "_read_config_ini", return_value=config
        ):
            api._load_global_config()

        self.assertFalse(api.params["auto_attendance_stop_after_success"])
        self.assertEqual(api.params["auto_attendance_success_limit"], 4)


if __name__ == "__main__":
    unittest.main()
