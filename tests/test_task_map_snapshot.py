import copy
import collections
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import api_runtime
from api_runtime import Api
from runtime_models import RunData


def test_map_snapshot_is_read_only_and_whitelisted():
    run = SimpleNamespace(run_name="task", run_coords=[[113, 22, 100], [114, 23, 100]],
                          current_point_index=1, target_points=[[113, 22]],
                          api_key="secret", client=Mock(), details_fetched=False)
    api = object.__new__(Api)
    api.all_run_data = [run]
    api.current_run_idx = 7
    api.target_range_m = 30
    api.api_client = Mock()
    api.save_state = Mock()
    before = copy.deepcopy(run.run_coords)
    snapshot = api.get_task_map_snapshot(0)
    assert snapshot["route_ready"] is True
    assert snapshot["details"]["current_position"] == {"lon": 113, "lat": 22}
    assert "api_key" not in snapshot["details"]
    assert "client" not in snapshot["details"]
    snapshot["details"]["run_coords"][0][0] = 0
    assert run.run_coords == before
    assert api.current_run_idx == 7
    assert run.details_fetched is False
    api.api_client.get_run_details.assert_not_called()
    api.save_state.assert_not_called()


def test_invalid_snapshot_index_does_not_select_or_fetch():
    api = object.__new__(Api)
    api.all_run_data = []
    for index in (-1, 0, "0", True, None):
        assert api.get_task_map_snapshot(index) == {"success": False, "message": "无效的任务索引"}


def test_rerun_clears_previous_progress_before_publishing_current_task():
    run = RunData()
    run.run_coords = [[113, 22, 100], [114, 23, 100]]
    run.current_point_index = 2
    run.distance_covered_m = 100
    run.target_sequence = 2
    run.is_in_target_zone = True
    run.status = 1
    execution_id = object()
    manager = SimpleNamespace(lock=threading.Lock(), route_failure_batches={"session": (execution_id, [], {})})
    api = object.__new__(Api)
    api.all_run_data = [run]
    api.stop_run_flag = threading.Event()
    api._web_session_id = "session"
    api.window = None
    api.api_client = Mock()
    api.log_and_notify_frontend = Mock()
    observed = []
    def publish(*_args):
        observed.append(api.get_task_map_snapshot(0)["details"])
        assert run.current_point_index == 0
        assert run.distance_covered_m == 0
        assert run.target_sequence == 0
        assert run.is_in_target_zone is False
        return True
    manager.update_route_planning_batch_status = Mock(side_effect=publish)
    manager.get_route_planning_execution = Mock(return_value=("batch-id", 1.0))
    api._run_submission_thread = Mock(side_effect=lambda *args: args[4].set())
    with patch.object(api_runtime, "_main", return_value=SimpleNamespace(background_task_manager=manager)), patch.object(api_runtime.time, "sleep"):
        assert api._execute_all_task_queue(collections.deque([0]), False, execution_id) == 1
    assert observed[0]["current_point_index"] == 0
    assert "current_position" not in observed[0]
