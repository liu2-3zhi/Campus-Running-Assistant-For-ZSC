from types import SimpleNamespace
from unittest.mock import Mock

import main
from config_adapter import JsonConfigAdapter


WAYPOINTS = [[113.389, 22.527], [113.390, 22.528]]


def make_config(selected):
    config = JsonConfigAdapter.__new__(JsonConfigAdapter)
    config._data = {"Map": {
        "backend_config_id": selected,
        "frontend_config_id": "first-amap",
        "configs": [
            {"id": "campus", "name": "Campus", "provider": "local_map",
             "service_url": "http://127.0.0.1:8765"},
            {"id": "first-amap", "name": "First Amap", "provider": "amap",
             "js_key": "first-test-key", "backend_page_origin": "https://first.test"},
            {"id": "missing-key", "name": "Empty Baidu", "provider": "baidu"},
            {"id": "second-amap", "name": "Second Amap", "provider": "amap",
             "js_key": "second-test-key", "backend_page_origin": "https://second.test"},
            {"id": "tencent", "name": "Tencent", "provider": "tencent",
             "map_key": "tencent-test-key", "backend_page_origin": "https://tencent.test"},
        ],
    }}
    return config


def test_routes_try_actual_profiles_in_order_and_then_use_campus(monkeypatch):
    attempts = []

    def online_failure(_session, _page, _waypoints, plan, _params):
        profile = plan["provider_config"]
        attempts.append((profile["config_id"], profile.get("js_key") or profile.get("map_key"),
                         plan["_runtime_page_origin"]))
        return {"error": "invalid map credentials"}

    def local_success(service_url, waypoints, recommended):
        attempts.append(("campus", service_url, recommended))
        return {"path": waypoints}

    monkeypatch.setattr(main, "chrome_pool", SimpleNamespace(), raising=False)
    monkeypatch.setattr(main, "_plan_route_path_with_tencent_runtime", online_failure)
    monkeypatch.setattr(main, "_plan_route_path_with_amap_runtime", online_failure)
    monkeypatch.setattr(main, "_plan_route_path_with_baidu_runtime", Mock(side_effect=AssertionError))
    monkeypatch.setattr(main, "plan_local_map_route", local_success)

    result = main._plan_route_path_with_provider_runtime(
        "test-session", WAYPOINTS, runtime_config=make_config("tencent"), recommended_coords=[],
    )

    assert attempts == [
        ("tencent", "tencent-test-key", "https://tencent.test"),
        ("first-amap", "first-test-key", "https://first.test"),
        ("second-amap", "second-test-key", "https://second.test"),
        ("campus", "http://127.0.0.1:8765", []),
    ]
    assert result["provider"] == "local_map"
    assert result["fallback_used"] is True
    assert result["notices"] == []
    assert result["path"][-1] == {"lng": 113.390, "lat": 22.528}


def test_selected_campus_success_does_not_attempt_online_maps(monkeypatch):
    monkeypatch.setattr(main, "chrome_pool", None, raising=False)
    local = Mock(return_value={"path": WAYPOINTS})
    monkeypatch.setattr(main, "plan_local_map_route", local)

    result = main._plan_route_path_with_provider_runtime(
        "test-session", WAYPOINTS, runtime_config=make_config("campus"),
    )

    local.assert_called_once_with("http://127.0.0.1:8765", WAYPOINTS, None)
    assert result["provider"] == "local_map"
    assert result["fallback_used"] is False


def test_campus_is_available_when_browser_pool_is_down(monkeypatch):
    monkeypatch.setattr(main, "chrome_pool", None, raising=False)
    local = Mock(return_value={"path": WAYPOINTS})
    monkeypatch.setattr(main, "plan_local_map_route", local)

    result = main._plan_route_path_with_provider_runtime(
        "test-session", WAYPOINTS, runtime_config=make_config("tencent"),
    )

    assert result["provider"] == "local_map"
    assert result["fallback_used"] is True
    local.assert_called_once()
