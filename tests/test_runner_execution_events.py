import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import api_runtime
import background_task_manager as background_runtime
from api_runtime import Api
from background_task_manager import BackgroundTaskManager
from runtime_models import RunData


def make_manager():
    manager = object.__new__(BackgroundTaskManager)
    manager.lock = threading.Lock()
    manager.tasks = {}
    manager.route_failure_batches = {}
    manager.save_task_state = Mock()
    return manager


def test_public_execution_id_rotates_and_only_projects_in_memory():
    manager = make_manager()
    old = manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 0})
    old_public, _ = manager.get_route_planning_execution("session", old)
    current = manager.begin_route_planning_batch("session", {"status": "running", "active_task_index": 0})
    current_public, started = manager.get_route_planning_execution("session", current)
    with patch.object(background_runtime, "_main", return_value=SimpleNamespace(web_sessions={})):
        status = manager.get_task_status("session")
    assert old_public != current_public
    assert len(current_public) == 32
    assert status["execution_id"] == current_public
    assert status["execution_started_at"] == started
    assert manager.get_route_planning_execution("session", old) == ("", 0.0)
    assert manager.tasks == {}
    manager.save_task_state.assert_not_called()


def test_superseded_worker_cannot_emit_position_or_execution_start():
    manager = make_manager()
    old = manager.begin_route_planning_batch("session")
    old_public, started = manager.get_route_planning_execution("session", old)
    manager.begin_route_planning_batch("session")
    api = object.__new__(Api)
    api._safe_socketio_emit = Mock()
    with patch.object(api_runtime, "_main", return_value=SimpleNamespace(background_task_manager=manager)):
        assert not api._emit_runner_execution_started("session", 0, old_public, started, old)
        assert not api._emit_runner_position_update("session", {"execution_id": old_public, "point_index": 99}, old)
    api._safe_socketio_emit.assert_not_called()


def test_single_account_submission_emits_real_progress_with_one_execution_id():
    api = object.__new__(Api)
    api._web_session_id = "session"
    api._active_execution_id = "public-batch"
    api._active_execution_started_at = 1.0
    api.current_run_idx = 0
    api.stop_run_flag = threading.Event()
    api.user_data = SimpleNamespace(student_id="student")
    api.log_and_notify_frontend = Mock()
    api._calculate_distance_m = Mock(return_value=1.0)
    api.check_target_reached_during_run = Mock()
    api._safe_socketio_emit = Mock(return_value=True)
    api._submit_chunk_with_retries = Mock(side_effect=lambda *args, **kwargs: api.stop_run_flag.set() or True)
    run = RunData()
    run.run_name = "test"
    run.run_coords = [(113.0, 22.0, 0), (113.1, 22.1, 0)]
    client = SimpleNamespace(app=api)
    runtime = SimpleNamespace(socketio=Mock(), PID_KP=0, PID_KI=0, PID_KD=0, PID_DEADZONE=0,
                              PID_DEADZONE_BOOST_MAX=1, PID_DEADZONE_BOOST_STEP=0, PID_INTEGRAL_LIMIT=1)
    finished = threading.Event()
    with patch.object(api_runtime, "_main", return_value=runtime):
        api._run_submission_thread(run, 0, client, True, finished, "public-batch")
    events = api._safe_socketio_emit.call_args_list
    assert events[0].args[0] == "runner_execution_started"
    positions = [call.args[1] for call in events if call.args[0] == "runner_position_update_new"]
    assert [position["point_index"] for position in positions] == [1, 2]
    assert all(position["execution_id"] == "public-batch" for position in positions)
    assert all(position["task_index"] == 0 for position in positions)
    assert positions[-1]["lon"] == 113.1
    assert finished.is_set()
