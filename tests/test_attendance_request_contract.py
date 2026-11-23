"""Attendance payloads follow the App's record identity and coordinate order."""

from types import SimpleNamespace

import pytest

from api_runtime import Api


class AttendanceService:
    def __init__(self, record_id):
        self.record_id = record_id
        self.submissions = []

    def get_roll_call_info(self, roll_call_id, user_id):
        assert (roll_call_id, user_id) == ("roll-call-1", "user-1")
        info = {"status": -1}
        if self.record_id is not None:
            info["id"] = self.record_id
        return {
            "code": 200,
            "success": True,
            "data": {"rollCallInfo": info, "attendFinish": 0},
        }

    def submit_attendance(self, payload):
        self.submissions.append(payload)
        return {"code": 200, "success": True, "data": {}}


def attendance_api(service):
    api = object.__new__(Api)
    api.api_client = service
    api.user_data = SimpleNamespace(id="user-1", username="student-1", name="测试学生")
    api.params = {}
    api.is_multi_account_mode = False
    api.log_and_notify_frontend = lambda message: None
    api._fetch_server_attendance_radius_if_needed = lambda client, acc: 0
    api._get_device_sign_code = lambda username: "device-1"
    return api


@pytest.mark.parametrize("is_makeup, status", [(False, 1), (True, 2)])
def test_attendance_uses_server_record_identity_and_latitude_first(is_makeup, status):
    service = AttendanceService(record_id="attendance-record-2")
    api = attendance_api(service)

    result = api.trigger_attendance(
        "roll-call-1", (113.25, 22.5), is_makeup=is_makeup
    )

    assert result["success"] is True
    assert len(service.submissions) == 1
    payload = service.submissions[0]
    assert payload["id"] == "attendance-record-2"
    assert payload["rollCallId"] == "roll-call-1"
    assert payload["name"] == "测试学生"
    assert payload["coordinate"] == "22.5,113.25"
    assert payload["status"] == status


def test_missing_server_record_identity_is_not_replaced_with_roll_call_id():
    service = AttendanceService(record_id=None)
    api = attendance_api(service)

    result = api.trigger_attendance("roll-call-1", (113.25, 22.5))

    assert result["success"] is True
    assert "id" not in service.submissions[0]
