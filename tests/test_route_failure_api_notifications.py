from types import SimpleNamespace
from unittest.mock import Mock, patch
import collections
import threading

import api_runtime
from background_task_manager import BackgroundTaskManager
from route_diagnostics import build_route_failure_summary


def make_api(group="user"):
    api = object.__new__(api_runtime.Api)
    api.auth_username = "owner"
    api._web_session_id = "target"
    api.log_and_notify_frontend = Mock()
    runtime = SimpleNamespace(auth_system=SimpleNamespace(get_user_group=Mock(return_value=group)))
    return api, runtime


def test_single_shared_notification_never_contains_the_reason():
    api, runtime = make_api("admin")
    with patch.object(api_runtime, "_main", return_value=runtime):
        summary = api._notify_route_planning_failure({"error": "INVALID_USER_KEY", "diagnostic_id": "d1", "provider": "amap"})
    assert summary["message"] == "INVALID_USER_KEY"
    call = api.log_and_notify_frontend.call_args
    assert "INVALID_USER_KEY" in call.args[0]
    assert "INVALID_USER_KEY" not in call.kwargs["frontend_message"]


def test_multi_uses_session_owner_group_and_fails_closed():
    api, runtime = make_api("user")
    account = SimpleNamespace(log_and_notify_frontend=Mock())
    failure = {"error": "INVALID_USER_KEY", "diagnostic_id": "d2", "provider": "amap"}
    with patch.object(api_runtime, "_main", return_value=runtime):
        api._notify_route_planning_failure(failure, account=account)
        assert "INVALID_USER_KEY" not in account.log_and_notify_frontend.call_args.kwargs["frontend_message"]
        runtime.auth_system.get_user_group.return_value = "admin"
        api._notify_route_planning_failure(failure, account=account)
        assert "INVALID_USER_KEY" in account.log_and_notify_frontend.call_args.kwargs["frontend_message"]
        runtime.auth_system.get_user_group.side_effect = RuntimeError("unavailable")
        api._notify_route_planning_failure(failure, account=account)
        assert "INVALID_USER_KEY" not in account.log_and_notify_frontend.call_args.kwargs["frontend_message"]


def test_manual_exception_is_a_safe_http_failure_not_a_raw_exception():
    api, runtime = make_api("admin")
    api.current_run_idx = 0
    api.all_run_data = [SimpleNamespace(target_points=[(1, 2), (3, 4)])]
    api.params = {}
    runtime._plan_route_path_with_provider_runtime = Mock(side_effect=RuntimeError("provider failure"))
    with patch.object(api_runtime, "_main", return_value=runtime):
        result = api.auto_generate_path_with_provider(20, 30, 2000)
    assert result["success"] is False
    assert result["diagnostic_id"]
    assert "provider failure" not in result["message"]
    assert result["_route_failure"]["message"] == "provider failure"


def test_exception_summary_uses_the_same_id_in_memory_and_notifications():
    api, runtime = make_api()
    recorded = []
    def record(_session, result, _batch):
        summary = build_route_failure_summary(result)
        recorded.append(summary)
        return summary
    runtime.background_task_manager = SimpleNamespace(record_route_planning_failure=record)
    with patch.object(api_runtime, "_main", return_value=runtime):
        summary = api._notify_route_planning_failure({"error": "exception"}, execution_id=object())
    assert recorded[0]["diagnostic_id"] == summary["diagnostic_id"]


def test_background_geometry_can_be_calculated_before_committing_to_run():
    api, _runtime = make_api()
    run = SimpleNamespace(target_points=[(1, 2), (1.001, 2)], run_coords=[], total_run_time_s=0, total_run_distance_m=0)
    api.current_run_idx = 0
    api.all_run_data = [run]
    api.params = {"interval_ms": 1000}
    api._build_route_path_with_random_detours = Mock(return_value=run.target_points)
    api._calculate_distance_m = Mock(return_value=10)
    api._gps_random_offset = lambda lon, lat, _params: (lon, lat)
    result = api.auto_generate_path_with_api([{"lng": 1, "lat": 2}, {"lng": 1.001, "lat": 2}], 0.01, 0.02, 10, apply_result=False)
    assert result["success"]
    assert result["run_coords"]
    assert run.run_coords == []


def test_manual_simulation_failure_retains_the_route_diagnostic_id():
    for raises in (False, True):
        api, runtime = make_api()
        api.current_run_idx = 0
        api.all_run_data = [SimpleNamespace(target_points=[(1, 2), (3, 4)])]
        api.params = {}
        runtime._plan_route_path_with_provider_runtime = Mock(return_value={"path": [{"lng": 1, "lat": 2}], "provider": "amap", "diagnostic_id": "route1"})
        api.auto_generate_path_with_api = Mock(side_effect=RuntimeError("simulation failure")) if raises else Mock(return_value={"success": False, "message": "simulation failure"})
        with patch.object(api_runtime, "_main", return_value=runtime):
            result = api.auto_generate_path_with_provider(20, 30, 2000)
        assert result["diagnostic_id"] == "route1"
        assert "simulation failure" not in result["message"]
        assert result["_route_failure"]["message"] == "simulation failure"


def test_direct_run_all_exposes_its_final_failure_to_status_polling():
    api, runtime = make_api()
    api.stop_run_flag = threading.Event()
    manager = object.__new__(BackgroundTaskManager)
    manager.lock = threading.Lock()
    manager.route_failure_batches = {}
    manager.tasks = {}
    runtime.background_task_manager = manager
    def run_queue(_queue, _auto_generate, execution_id):
        api._notify_route_planning_failure({"error": "INVALID_USER_KEY", "diagnostic_id": "direct"}, execution_id=execution_id)
        return 0
    api._execute_all_task_queue = run_queue
    with patch.object(api_runtime, "_main", return_value=runtime):
        api._run_all_tasks_manager(collections.deque([0]), True)
    status = manager.get_task_status("target", include_route_failures=True)
    assert status["status"] == "error"
    assert status["route_planning_failures"][0]["message"] == "INVALID_USER_KEY"


def test_direct_run_all_exception_and_superseded_completion_are_isolated():
    for superseded in (False, True):
        api, runtime = make_api()
        api.stop_run_flag = threading.Event()
        manager = object.__new__(BackgroundTaskManager)
        manager.lock = threading.Lock()
        manager.route_failure_batches = {}
        manager.tasks = {}
        runtime.background_task_manager = manager
        def run_queue(_queue, _auto_generate, _execution_id):
            if superseded:
                manager.begin_route_planning_batch("target", task_status={"status": "running"})
            raise RuntimeError("late provider failure")
        api._execute_all_task_queue = run_queue
        with patch.object(api_runtime, "_main", return_value=runtime):
            api._run_all_tasks_manager(collections.deque([0]), True)
        status = manager.get_task_status("target", include_route_failures=True)
        assert status["status"] == ("running" if superseded else "error")
        assert api.stop_run_flag.is_set() is not superseded
        if superseded:
            assert not status.get("route_planning_failures")
            api.log_and_notify_frontend.assert_not_called()
        else:
            assert status["route_planning_failures"][0]["message"] == "late provider failure"
