import copy
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import background_task_manager as runtime
from background_task_manager import BackgroundTaskManager


def make_manager(state=None):
    manager = object.__new__(BackgroundTaskManager)
    manager.lock = threading.Lock()
    manager.tasks = {"session": copy.deepcopy(state)} if state is not None else {}
    manager.execution_tokens = {}
    manager.route_failure_batches = {}
    manager.save_task_state = Mock()
    manager.load_task_state = Mock(return_value=None)
    return manager


def make_run(index=1):
    return SimpleNamespace(run_name="test", run_coords=[[113.39, 22.52, 100], [113.40, 22.53, 100]],
                           current_point_index=index, distance_covered_m=12.5, target_sequence=2,
                           is_in_target_zone=True, suppress_last_target_until_finish=False,
                           target_points=[[113.40, 22.53]], details_fetched=True)


def test_queue_ordinal_projects_real_task_index_without_selecting_or_mutating():
    runs = [make_run(0), make_run(2), make_run(1), make_run(1)]
    state = {"status": "running", "task_indices": [3, 1], "current_task_index": 1,
             "current_position": {"lon": 0, "lat": 0}, "run_coords": [[0, 0]], "nested": {"value": [1]}}
    manager = make_manager(state)
    api = SimpleNamespace(all_run_data=runs, current_run_idx=3, save_state=Mock())
    before_runs = copy.deepcopy([vars(run) for run in runs])
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": api})):
        status = manager.get_task_status("session")
    assert status["current_task_index"] == 1
    assert status["active_task_index"] == 1
    assert status["route_ready"] is True
    assert status["singleProcessedPoints"] == 2
    assert status["singleTotalPoints"] == 2
    assert status["current_position"] == {"lon": 113.40, "lat": 22.53, "point_index": 2, "distance": 12.5, "target_sequence": 2}
    status["nested"]["value"].append(2)
    status["current_position"]["lon"] = 0
    assert manager.tasks["session"] == state
    assert [vars(run) for run in runs] == before_runs
    assert api.current_run_idx == 3
    manager.save_task_state.assert_not_called()
    api.save_state.assert_not_called()


@pytest.mark.parametrize("ordinal", [-1, 99, "bad", None, True, 1.5])
def test_invalid_queue_ordinal_never_selects_another_task(ordinal):
    manager = make_manager({"status": "running", "task_indices": [0, 1], "current_task_index": ordinal,
                            "current_position": {"lon": 0, "lat": 0}, "run_coords": [[0, 0]]})
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[make_run(), make_run()])})):
        status = manager.get_task_status("session")
    assert status["current_task_index"] == ordinal
    assert status.get("active_task_index") is None
    assert status["route_ready"] is False
    assert "current_position" not in status


@pytest.mark.parametrize("point_index,processed", [(0, 0), (-1, 0), (None, 0), (True, 0), ("2", 0), (float("inf"), 0), (99, 2), (2, 2)])
def test_live_point_index_zero_last_and_invalid_cannot_leave_stale_position(point_index, processed):
    run = make_run(point_index)
    state = {"status": "running", "active_task_index": 0, "current_task_index": 0,
             "current_position": {"lon": 0, "lat": 0}, "singleProcessedPoints": 999}
    manager = make_manager(state)
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[run])})):
        status = manager.get_task_status("session")
    assert status["active_task_index"] == 0
    assert status["singleProcessedPoints"] == processed
    if processed:
        assert status["current_position"]["lon"] == run.run_coords[processed - 1][0]
        assert status["current_position"]["point_index"] == processed
    else:
        assert "current_position" not in status
    assert manager.tasks["session"] == state
    assert run.current_point_index == point_index
    manager.save_task_state.assert_not_called()


def test_independent_memory_batch_overrides_saved_queue_and_rejects_old_updates():
    old_state = {"status": "completed", "current_task_index": 9, "run_coords": [[0, 0]]}
    manager = make_manager(old_state)
    old = manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 1})
    current = manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 0})
    assert not manager.update_route_planning_batch_status("session", old, {"active_task_index": 1, "status": "completed"})
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[make_run(0), make_run(2)])})):
        status = manager.get_task_status("session")
    assert status["active_task_index"] == 0
    assert status["status"] == "running"
    assert status["singleProcessedPoints"] == 0
    assert "current_position" not in status
    assert manager.route_failure_batches["session"][0] is current
    batch_status = manager.route_failure_batches["session"][2]
    assert batch_status["status"] == "running"
    assert batch_status["active_task_index"] == 0
    assert batch_status["execution_id"] == status["execution_id"]
    assert manager.tasks["session"] == old_state
    manager.save_task_state.assert_not_called()


@pytest.mark.parametrize("active_index", [None, True, -1, 99, "0"])
def test_invalid_explicit_active_index_does_not_fall_back_to_valid_queue_index(active_index):
    manager = make_manager({"status": "running", "active_task_index": active_index,
                            "task_indices": [0], "current_task_index": 0})
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[make_run(2)])})):
        status = manager.get_task_status("session")
    assert status["active_task_index"] is None
    assert status["route_ready"] is False
    assert "current_position" not in status


def test_old_normal_worker_cannot_reset_new_batch_progress_or_publish_task_index():
    manager = make_manager({"status": "running", "current_task_index": 9})
    old = manager.begin_route_planning_batch("session")
    current = manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 0})
    manager.execution_tokens["session"] = object()
    run = make_run(2)
    before = copy.deepcopy(vars(run))
    api = SimpleNamespace(all_run_data=[run], _run_submission_thread=Mock())
    with patch.object(runtime, "_main", return_value=SimpleNamespace(_release_school_account_execution=Mock())):
        manager._execute_tasks_background("session", api, [0], False, old)
    assert vars(run) == before
    assert manager.route_failure_batches["session"][0] is current
    assert manager.tasks["session"]["current_task_index"] == 9
    manager.save_task_state.assert_not_called()
    api._run_submission_thread.assert_not_called()


def test_loading_saved_status_is_read_only_and_cannot_replace_new_memory_batch():
    manager = make_manager()
    disk = {"status": "completed", "current_task_index": 0, "task_indices": [1]}
    manager.load_task_state.return_value = disk
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={})):
        assert manager.get_task_status("session")["status"] == "completed"
    assert manager.tasks == {}
    assert disk == {"status": "completed", "current_task_index": 0, "task_indices": [1]}

    def load_while_new_batch_starts(_session):
        manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 0})
        return disk
    manager.load_task_state.side_effect = load_while_new_batch_starts
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[make_run(0)])})):
        status = manager.get_task_status("session")
    assert status["status"] == "running"
    assert status["active_task_index"] == 0
    assert manager.tasks == {}
    manager.save_task_state.assert_not_called()


def test_normal_queue_clears_previous_progress_before_publishing_new_task_index():
    manager = make_manager({"status": "running", "task_indices": [0], "current_task_index": 0,
                            "current_position": {"lon": 113.40, "lat": 22.53}, "singleProcessedPoints": 2,
                            "current_distance_m": 200, "elapsed_time_s": 60})
    batch = manager.begin_route_planning_batch("session")
    manager.execution_tokens["session"] = object()
    run = make_run(2)
    api = SimpleNamespace(all_run_data=[run], stop_run_flag=threading.Event(), api_client=Mock(), log_and_notify_frontend=Mock())
    api._run_submission_thread = Mock(side_effect=lambda *args: args[4].set())
    published = []

    def capture_publication(_session, state):
        published.append((copy.deepcopy(state), copy.deepcopy(vars(run))))
    manager.save_task_state.side_effect = capture_publication
    with patch.object(runtime, "_main", return_value=SimpleNamespace(_release_school_account_execution=Mock())):
        manager._execute_tasks_background("session", api, [0], False, batch)
    first_state, first_run = published[0]
    assert first_state["current_task_index"] == 0
    assert first_run["current_point_index"] == 0
    assert first_run["distance_covered_m"] == 0
    assert first_run["target_sequence"] == 0
    assert first_run["is_in_target_zone"] is False
    assert first_run["suppress_last_target_until_finish"] is True
    assert "current_position" not in first_state
    assert first_state["singleProcessedPoints"] == 0
    assert first_state["current_distance_m"] == 0
    assert first_state["elapsed_time_s"] == 0
    api._run_submission_thread.assert_called_once()


def test_explicit_pending_batch_does_not_project_previous_task_progress():
    manager = make_manager({"status": "running", "task_indices": [0], "current_task_index": 0})
    manager.begin_route_planning_batch("session", {"active_task_index": None})
    run = make_run(2)
    with patch.object(runtime, "_main", return_value=SimpleNamespace(web_sessions={"session": SimpleNamespace(all_run_data=[run])})):
        status = manager.get_task_status("session")
    assert status["active_task_index"] is None
    assert status["route_ready"] is False
    assert status["singleProcessedPoints"] == 0
    assert "current_position" not in status
    assert run.current_point_index == 2


def test_first_status_before_background_worker_cannot_restore_previous_completed_progress():
    manager = make_manager()
    run = make_run(2)
    api = SimpleNamespace(all_run_data=[run], is_offline_mode=True,
                          _resolve_waive_charge=Mock(return_value=False),
                          stop_run_flag=threading.Event(), api_client=Mock(),
                          log_and_notify_frontend=Mock())
    api._run_submission_thread = Mock(side_effect=lambda *args: args[4].set())
    threads = []

    class ControlledThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            threads.append(self)

        def start(self):
            if self is not threads[0]:
                self.target(*self.args)

        def join(self, timeout=None):
            pass

    main = SimpleNamespace(web_sessions={"session": api},
                           _get_active_map_provider=Mock(return_value="amap"),
                           _claim_school_account_execution=Mock(return_value=(True, None)),
                           _release_school_account_execution=Mock())
    with patch.object(runtime, "_main", return_value=main), patch.object(runtime.threading, "Thread", ControlledThread):
        assert manager.start_background_task("session", api, [0])["success"] is True
        assert len(threads) == 1
        api._run_submission_thread.assert_not_called()
        assert run.current_point_index == 2
        pending = manager.get_task_status("session")
        assert pending["active_task_index"] is None
        assert pending["route_ready"] is False
        assert pending["singleProcessedPoints"] == 0
        assert "current_position" not in pending

        threads[0].target(*threads[0].args)
        active = manager.get_task_status("session")

    api._run_submission_thread.assert_called_once()
    assert active["execution_id"] == pending["execution_id"]
    assert active["active_task_index"] == 0
    assert active["route_ready"] is True
    assert active["singleProcessedPoints"] == 0
    assert "current_position" not in active
    assert run.current_point_index == 0
    assert run.distance_covered_m == 0
    assert "active_task_index" not in manager.save_task_state.call_args_list[0].args[1]
