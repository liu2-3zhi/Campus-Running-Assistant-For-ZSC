"""Generated GPS routes must end at the final checkpoint."""

from collections import deque
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import api_runtime
from api_runtime import Api


def test_generated_run_route_straight_connects_to_final_waypoint():
    api = Api.__new__(Api)
    start = (113.0, 22.0)
    destination = (113.005, 22.0)
    run = SimpleNamespace(target_points=[start, destination], run_coords=[])
    api.current_run_idx = 0
    api.all_run_data = [run]
    api.params = {"interval_ms": 10000, "location_random_m": 0}
    api.log_and_notify_frontend = lambda *args, **kwargs: None
    api._gps_random_offset = lambda lng, lat, params: (lng, lat)
    api._build_route_path_with_random_detours = lambda *args, **kwargs: [start, destination]

    with patch("api_runtime.random.uniform", side_effect=lambda low, high: low):
        result = api.auto_generate_path_with_api(
            [{"lng": start[0], "lat": start[1]},
             {"lng": destination[0], "lat": destination[1]}],
            1,
            1,
            500,
            apply_result=False,
        )

    assert result["success"]
    assert result["run_coords"][-2][:2] != destination
    assert result["run_coords"][-1][:2] == destination
    assert result["run_coords"][-1][2] > 0
    expected_distance = api._calculate_distance_m(*start, *destination)
    assert result["total_dist"] == pytest.approx(expected_distance, abs=0.1)
    assert result["total_time"] > 60


def test_queued_generation_uses_the_tasks_waypoints_after_selection_changes():
    api = Api.__new__(Api)
    waypoints = [(113.0, 22.0), (113.005, 22.0)]
    run = SimpleNamespace(run_name="queued", target_points=waypoints, run_coords=[], details_fetched=True)
    api.all_run_data = [run]
    api.stop_run_flag = Event()
    api.window = None
    api._web_session_id = "test-session"
    api.params = {"interval_ms": 3000, "location_random_m": 0}
    api.api_client = Mock()
    api.log_and_notify_frontend = Mock()
    api._run_submission_thread = Mock(side_effect=lambda *args: args[4].set())
    api._build_route_path_with_random_detours = Mock(return_value=waypoints)

    def plan(_session_id, targets, **_kwargs):
        api.current_run_idx = -1
        return {"path": [{"lng": lon, "lat": lat} for lon, lat in targets]}

    runtime = SimpleNamespace(_plan_route_path_with_provider_runtime=plan)
    with patch.object(api_runtime, "_main", return_value=runtime), patch.object(api_runtime.time, "sleep"):
        assert api._execute_all_task_queue(deque([0]), True) == 1

    assert api._build_route_path_with_random_detours.call_args.args[1] is waypoints
    assert run.run_coords[-1][:2] == waypoints[-1]
