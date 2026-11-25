import hashlib
from unittest.mock import Mock, patch

from flask import Flask

import local_map_provider
import main
from local_map_provider import RESOURCE_CONTEXT_TTL_S, register_local_map_asset_routes
from map_runtime_origin import get_map_config_candidates


def test_builtin_map_serves_assets_and_plans_without_http_upstream(monkeypatch, tmp_path):
    config = main._get_default_config()
    profile = get_map_config_candidates(config, "frontend")[0]
    assert profile["provider"] == "local_map"
    assert profile["service_url"] == ""
    app = Flask(__name__)
    register_local_map_asset_routes(app, lambda: profile["service_url"], {profile["id"]: ""}.get)

    sdk = tmp_path / "maplibre-gl-csp.js"
    sdk.write_bytes(b"test sdk")
    tile = tmp_path / "tile.png"
    tile.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setitem(local_map_provider.SDK_ASSETS, sdk.name,
                        ("application/javascript", hashlib.sha256(sdk.read_bytes()).hexdigest()))
    campus = Mock()
    campus.sdk_asset.return_value = sdk
    campus.tile.return_value = tile
    campus.map_metadata.return_value = {
        "coordinate_system": "GCJ-02", "bounds": [113.38, 22.52, 113.39, 22.53],
        "center": [113.385, 22.525], "minzoom": 14, "maxzoom": 20, "version": "test",
    }
    start, end = [113.385, 22.525], [113.386, 22.526]
    campus.tasks.return_value = {
        "coordinate_system": "GCJ-02",
        "route": {"geometry": {"type": "LineString", "coordinates": [start, end]}},
    }
    monkeypatch.setattr(local_map_provider, "_embedded_map", campus)
    monkeypatch.setattr("requests.Session.request", Mock(side_effect=AssertionError("embedded map used HTTP")))

    client = app.test_client()
    config_id = {"config_id": profile["id"]}
    assert client.get(f"/api/local-map/sdk/{sdk.name}", query_string=config_id).data == sdk.read_bytes()
    metadata = client.get("/api/local-map/map", query_string=config_id).get_json()
    assert metadata["version"] == "test"
    response = client.get("/api/local-map/tiles/0/0/0.png", query_string={"context": metadata["resource_context"]})
    assert response.data == tile.read_bytes()
    campus.tile.assert_called_once_with(0, 0, 0)

    result = main._plan_route_path_with_provider_runtime("session", [start, end], runtime_config=config,
                                                        recommended_coords=[])
    assert result["path"] == [{"lng": lng, "lat": lat} for lng, lat in (start, end)]
    campus.tasks.assert_called_once_with({"target_points": [start, end], "recommended_coords": []})


def test_local_task_route_uses_task_footpaths_without_a_browser():
    start, road_start, road_end, end = (
        (113.389, 22.527), (113.38901, 22.527),
        (113.390, 22.527), (113.39003, 22.527),
    )
    recommended = [road_start, road_end]
    provider_plan = {
        "provider": "local_map",
        "actual_mode": "walking",
        "provider_config": {"service_url": "http://127.0.0.1:18765"},
    }
    data = {
        "coordinate_system": "GCJ-02",
        "route": {"geometry": {"type": "LineString", "coordinates": [road_start, road_end]}},
    }
    with patch.object(main, "_plan_route_with_map_provider", return_value=provider_plan), \
         patch.object(main, "chrome_pool", None, create=True), \
         patch("local_map_provider.fetch_local_map", return_value=(200, data)) as fetch:
        result = main._plan_route_path_with_provider_runtime(
            "session", [start, end], provider="local_map", runtime_config=object(), recommended_coords=recommended,
        )
    fetch.assert_called_once_with(
        "http://127.0.0.1:18765", "/api/v1/tasks/plan",
        body={"target_points": [start, end], "recommended_coords": recommended},
    )
    assert result["path"] == [{"lng": lng, "lat": lat} for lng, lat in (start, road_start, road_end, end)]
    assert result["diagnostic"]["api_type"] == "local_map_route"


def test_local_map_relay_does_not_serve_unchecked_executable_assets():
    app = Flask(__name__)
    register_local_map_asset_routes(app, lambda: "http://127.0.0.1:18765")
    client = app.test_client()
    with patch("local_map_provider.fetch_local_map", return_value=(200, b"unexpected script")) as fetch:
        assert client.get("/api/local-map/sdk/unknown.js").status_code == 404
        fetch.assert_not_called()
        response = client.get("/api/local-map/sdk/maplibre-gl-csp.js")
    assert response.status_code == 502
    assert b"unexpected script" not in response.data


def test_named_campus_fallback_can_load_while_online_map_is_preferred():
    app = Flask(__name__)
    origin = "http://127.0.0.1:18766"
    register_local_map_asset_routes(app, lambda: None, {"campus-fallback": origin}.get)
    client = app.test_client()
    metadata = {
        "coordinate_system": "GCJ-02", "bounds": [113.38, 22.52, 113.39, 22.53],
        "center": [113.385, 22.525], "minzoom": 14, "maxzoom": 20, "version": "test",
    }
    with patch("local_map_provider.fetch_local_map", return_value=(200, metadata)) as fetch:
        assert client.get("/api/local-map/map").status_code == 404
        assert client.get("/api/local-map/map?config_id=back-only").status_code == 404
        fetch.assert_not_called()
        response = client.get("/api/local-map/map?config_id=campus-fallback")
    assert response.status_code == 200
    assert response.json["resource_context"]
    assert origin not in response.text
    fetch.assert_called_once_with(origin, "/api/v1/map", content_type="application/json")


def test_local_tiles_stay_bound_to_the_map_opened_before_profile_switch():
    app = Flask(__name__)
    old_origin = "http://127.0.0.1:18765"
    new_origin = "http://127.0.0.1:18766"
    selected_origin = old_origin
    register_local_map_asset_routes(app, lambda: selected_origin)
    client = app.test_client()
    metadata = {
        "coordinate_system": "GCJ-02", "bounds": [113.38, 22.52, 113.39, 22.53],
        "center": [113.385, 22.525], "minzoom": 14, "maxzoom": 20, "version": "shared-version",
    }
    png = b"\x89PNG\r\n\x1a\n"
    tile_path = "/api/local-map/tiles/0/0/0.png"

    def fetch(origin, path, content_type):
        return 200, metadata if path == "/api/v1/map" else png + origin.encode("ascii")

    with patch("local_map_provider.fetch_local_map", side_effect=fetch) as fetch_mock, \
         patch("local_map_provider.monotonic", return_value=0) as clock:
        old_map = client.get("/api/local-map/map").get_json()
        assert old_origin not in str(old_map)
        old_context = old_map["resource_context"]
        assert client.get("/api/local-map/map").get_json()["resource_context"] == old_context
        selected_origin = new_origin
        new_context = client.get("/api/local-map/map").get_json()["resource_context"]
        assert old_context != new_context
        assert client.get(tile_path, query_string={"context": old_context}).data == png + old_origin.encode()
        assert client.get(tile_path, query_string={"context": new_context}).data == png + new_origin.encode()
        selected_origin = None
        assert client.get("/api/local-map/map").status_code == 404
        assert client.get(tile_path, query_string={"context": old_context}).status_code == 200
        request_count = fetch_mock.call_count
        assert client.get(tile_path).status_code == 404
        assert client.get(tile_path, query_string={"context": "unknown"}).status_code == 404
        assert fetch_mock.call_count == request_count
        clock.return_value = RESOURCE_CONTEXT_TTL_S
        assert client.get(tile_path, query_string={"context": old_context}).status_code == 404
        assert fetch_mock.call_count == request_count
