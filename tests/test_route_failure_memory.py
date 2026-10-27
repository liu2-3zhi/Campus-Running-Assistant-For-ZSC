import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

import background_task_manager as background_runtime
from background_task_manager import BackgroundTaskManager


def manager():
    instance = object.__new__(BackgroundTaskManager)
    instance.lock = threading.Lock()
    instance.tasks = {"session": {"status": "error", "error": "sensitive provider reason"}}
    instance.route_failure_batches = {}
    instance.save_task_state = Mock()
    return instance


def test_failure_summaries_are_bounded_and_never_persisted():
    instance = manager()
    batch = instance.begin_route_planning_batch("session")
    for i in range(25):
        instance.record_route_planning_failure("session", {
            "diagnostic_id": str(i), "provider": "amap", "error": "失败" * 3000,
        }, execution_id=batch)
    summaries = instance.get_route_planning_failures("session")
    assert len(summaries) == 20
    assert summaries[0]["diagnostic_id"] == "5"
    assert all(len(json.dumps(row, ensure_ascii=False).encode("utf-8")) <= 2048 for row in summaries)
    assert "route_planning_failures" not in instance.tasks["session"]
    instance.save_task_state.assert_not_called()


def test_late_old_batch_cannot_replace_new_batch_details():
    instance = manager()
    old = instance.begin_route_planning_batch("session")
    current = instance.begin_route_planning_batch("session")
    instance.record_route_planning_failure("session", {"error": "old"}, execution_id=old)
    assert instance.get_route_planning_failures("session") == []
    instance.record_route_planning_failure("session", {"error": "current"}, execution_id=current)
    assert instance.get_route_planning_failures("session")[0]["message"] == "current"
    instance.clear_route_planning_failures("session")
    instance.record_route_planning_failure("session", {"error": "late"}, execution_id=current)
    assert instance.get_route_planning_failures("session") == []


def test_status_is_an_independent_permission_filtered_snapshot():
    instance = manager()
    batch = instance.begin_route_planning_batch("session")
    instance.record_route_planning_failure("session", {"error": "INVALID_USER_KEY", "diagnostic_id": "d1"}, execution_id=batch)
    public = instance.get_task_status("session")
    assert "sensitive provider reason" not in json.dumps(public)
    assert "route_planning_failures" not in public
    private = instance.get_task_status("session", include_route_failures=True)
    assert private["route_planning_failures"][0]["message"] == "INVALID_USER_KEY"
    private["route_planning_failures"][0]["message"] = "changed"
    private["status"] = "changed"
    assert instance.get_route_planning_failures("session")[0]["message"] == "INVALID_USER_KEY"
    assert instance.tasks["session"]["status"] == "error"


def test_superseded_generation_cannot_mutate_run_or_submit_old_task():
    instance = manager()
    instance.tasks["session"] = {"status": "running"}
    instance.execution_tokens = {"session": object()}
    batch = instance.begin_route_planning_batch("session")
    run = SimpleNamespace(run_name="task", details_fetched=True, run_coords=[], target_points=[(1, 2), (3, 4)])
    api = SimpleNamespace(all_run_data=[run], params={}, stop_run_flag=threading.Event(), api_client=Mock(), log_and_notify_frontend=Mock())
    api._run_submission_thread = Mock(side_effect=lambda *args: args[-1].set())
    def generate(*_args, **_kwargs):
        instance.begin_route_planning_batch("session")
        instance.tasks["session"] = {"status": "running", "marker": "new"}
        return {"success": True, "run_coords": [(1, 2, 10), (3, 4, 10)], "total_dist": 1, "total_time": 1}
    api.auto_generate_path_with_api = generate
    runtime = SimpleNamespace(
        _plan_route_path_with_provider_runtime=Mock(return_value={"path": [(1, 2), (3, 4)], "diagnostic_id": "d1"}),
        _release_school_account_execution=Mock(),
    )
    with patch.object(background_runtime, "_main", return_value=runtime):
        instance._execute_tasks_background("session", api, [0], True, batch)
    assert run.run_coords == []
    api._run_submission_thread.assert_not_called()
    assert instance.tasks["session"] == {"status": "running", "marker": "new"}


def test_late_worker_cannot_release_the_new_batch_account_claim():
    instance = manager()
    old = instance.begin_route_planning_batch("session")
    instance.begin_route_planning_batch("session")
    new_claim = object()
    instance.execution_tokens = {"session": new_claim}
    runtime = SimpleNamespace(_release_school_account_execution=Mock())
    with patch.object(background_runtime, "_main", return_value=runtime):
        instance._execute_tasks_background("session", SimpleNamespace(), [0], True, old)
    assert instance.execution_tokens["session"] is new_claim
    runtime._release_school_account_execution.assert_not_called()


def test_direct_run_all_has_pollable_memory_status_without_task_files():
    instance = manager()
    instance.tasks.clear()
    batch = instance.begin_route_planning_batch("session", task_status={"status": "running", "total_tasks": 1})
    assert instance.get_task_status("session")["status"] == "running"
    instance.record_route_planning_failure("session", {"diagnostic_id": "direct", "error": "INVALID_USER_KEY"}, batch)
    instance.update_route_planning_batch_status("session", batch, {"status": "error"})
    private = instance.get_task_status("session", include_route_failures=True)
    assert private["status"] == "error"
    assert private["route_planning_failures"][0]["diagnostic_id"] == "direct"
    public = instance.get_task_status("session")
    assert "INVALID_USER_KEY" not in str(public)
    assert "direct" in public["error"]
    instance.save_task_state.assert_not_called()


def test_memory_queue_overrides_old_saved_status_and_stops_without_saving():
    instance = manager()
    old = instance.begin_route_planning_batch("session", task_status={"status": "running"})
    current = instance.begin_route_planning_batch("session", task_status={"status": "running"})
    assert not instance.update_route_planning_batch_status("session", old, {"status": "error"})
    assert instance.get_task_status("session")["status"] == "running"
    assert instance.stop_task("session")["success"]
    assert instance.get_task_status("session")["status"] == "stopped"
    assert instance.route_failure_batches["session"][0] is current
    assert instance.tasks["session"]["status"] == "error"
    instance.save_task_state.assert_not_called()
