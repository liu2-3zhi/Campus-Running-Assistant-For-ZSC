"""HTTP contracts, local static resources, and unavailable data behavior."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from campus_map.api import create_app
from campus_map.pipeline import COORDINATE_METADATA
from campus_map.service import CampusMap, RouteInputError


BOUNDS = [113.3798, 22.5255, 113.3901, 22.5355]


@pytest.fixture
def data_root(tmp_path):
    release = tmp_path / "builds" / "test-v1"
    (release / "features").mkdir(parents=True)
    (release / "tiles" / "14" / "13352").mkdir(parents=True)
    (release / "routing" / "tiles").mkdir(parents=True)
    (release / "features" / "roads.geojson").write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    (release / "tiles" / "14" / "13352" / "7139.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    (release / "routing" / "valhalla.json").write_text('{"mjolnir":{"tile_dir":"tiles"}}', encoding="utf-8")
    (release / "routing" / "tiles" / "test.gph").write_bytes(b"graph")
    (release / "coordinate-calibration.json").write_text(json.dumps({**COORDINATE_METADATA, "source_bounds": [113.38, 22.52, 113.39, 22.53],
        "columns": 2, "rows": 2, "points": [[113.385, 22.517], [113.395, 22.517], [113.385, 22.527], [113.395, 22.527]]}), encoding="utf-8")
    files = [path for path in release.rglob("*") if path.is_file()]
    manifest = {"version": "test-v1", "name": "Campus", "bounds": BOUNDS, "center": [113.385, 22.53], "minzoom": 14, "maxzoom": 20, "layers": {"roads": {"file": "features/roads.geojson", "count": 0}}, "coverage": {}, "sources": [], "examples": [], "checksums": {path.relative_to(release).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    manifest.update(**COORDINATE_METADATA, tile_provider="osm")
    (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "current.json").write_text('{"version":"test-v1"}', encoding="utf-8")
    return tmp_path


class RoutingDouble:
    def __init__(self, release):
        self.release = release

    def route(self, start, end, waypoints):
        points = [start, *waypoints, end]
        geometry = {"type": "LineString", "coordinates": points}
        return {"route": {"type": "Feature", "geometry": geometry, "properties": {"distance_m": 150, "duration_s": 100}},
                "legs": [{"index": index, "start_index": index, "end_index": index + 1,
                          "distance_m": 75, "duration_s": 50,
                          "geometry": {"type": "LineString", "coordinates": [first, second]}}
                         for index, (first, second) in enumerate(zip(points, points[1:]))],
                "distance_m": 150, "duration_s": 100,
                "snapped_points": [{"input": point, "snapped": point, "offset_m": 0} for point in points]}

    def native_route(self, payload):
        return {"trip": {"status": 0, "legs": []}}


@pytest.fixture
def client(data_root, monkeypatch):
    monkeypatch.setattr("campus_map.service.RoutingService", RoutingDouble)
    return TestClient(create_app(data_root))


def test_manifest_features_and_tiles_are_local(client):
    manifest = client.get("/api/v1/map")
    assert manifest.status_code == 200
    assert manifest.json()["version"] == "test-v1"
    assert manifest.json()["coordinate_system"] == "GCJ-02"
    assert client.get("/api/v1/features/roads").json()["type"] == "FeatureCollection"
    tile = client.get("/api/v1/tiles/14/13352/7139.png")
    assert tile.status_code == 200
    assert tile.headers["content-type"] == "image/png"
    assert client.get("/healthz").status_code == 200


def test_embedded_map_sdk_serves_only_allowlisted_assets(data_root, monkeypatch, tmp_path):
    monkeypatch.setattr("campus_map.service.PROJECT_ROOT", tmp_path)
    sdk_root = tmp_path / "web" / "dist" / "static" / "vendor" / "maplibre"
    sdk_root.mkdir(parents=True)
    (sdk_root / "maplibre-gl-csp.js").write_bytes(b"window.maplibregl = {};")
    (sdk_root / "other.js").write_bytes(b"")
    with TestClient(create_app(data_root)) as client:
        response = client.get("/api/v1/sdk/maplibre-gl-csp.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/javascript")
        assert response.content == b"window.maplibregl = {};"
        assert client.get("/api/v1/sdk/other.js").status_code == 404


def test_routes_and_native_endpoint(client):
    response = client.post("/api/v1/routes", json={"start": [113.383, 22.529], "end": [113.385, 22.531], "waypoints": [[113.384, 22.53]]})
    assert response.status_code == 200
    assert response.json()["snapped_points"][1]["input"] == [113.384, 22.53]
    assert len(response.json()["legs"]) == 2
    native = client.get("/valhalla/route", params={"json": json.dumps({"locations": [{"lon": 113.383, "lat": 22.529}, {"lon": 113.385, "lat": 22.531}]})})
    assert native.status_code == 200
    assert native.json()["trip"]["status"] == 0


def test_task_route_visits_targets_in_order_and_projects_onto_the_path(client):
    start = [113.383, 22.529]
    end = [113.385, 22.529]
    off_path = [113.384, 22.5292]
    body = {
        "task_name": "校园任务",
        "recommended_coords": [start, end],
        "target_points": [start, off_path, end, off_path],
        "target_point_names": "起点|打卡点|折返点|打卡点",
        "run_coords (gps)": [[1, 2]],
        "draft_coords (gps)": [],
    }

    response = client.post("/api/v1/tasks/plan", json=body)

    assert response.status_code == 200
    result = response.json()
    assert result["coordinate_system"] == "GCJ-02"
    assert result["task_name"] == body["task_name"]
    assert result["target_points"] == [
        {"name": name, "coordinate": point}
        for name, point in zip(body["target_point_names"].split("|"), body["target_points"])
    ]
    projection = [113.384, 22.529]
    coordinates = result["route"]["geometry"]["coordinates"]
    assert len(coordinates) == 7
    for point, expected in zip(coordinates, [start, projection, off_path, projection, end, projection, off_path]):
        assert point == pytest.approx(expected, abs=1e-8)
    connectors = result["connectors"]["features"]
    assert [feature["properties"]["target_index"] for feature in connectors] == [1, 3]
    assert connectors[0]["geometry"]["coordinates"][0] == pytest.approx(projection, abs=1e-8)
    assert connectors[0]["properties"]["distance_m"] == pytest.approx(22.24, abs=0.01)
    assert result["distance_m"] > 350


def test_task_gaps_are_preserved_and_target_uses_the_nearest_reachable_segment(client):
    start = [113.381, 22.529]
    middle = [113.382, 22.529]
    end = [113.383, 22.529]
    isolated = [[113.382, 22.5295], [113.384, 22.5295]]
    target = [113.3825, 22.5295]
    response = client.post("/api/v1/tasks/plan", json={
        "recommended_coords": [start, end, [0, 0], [0, 0], *isolated],
        "target_points": [start, middle, end, target],
    })
    assert response.status_code == 200
    result = response.json()
    assert [feature["geometry"]["coordinates"] for feature in result["recommended_paths"]["features"]] == [[start, end], isolated]
    assert result["route"]["geometry"]["coordinates"][-1] == target
    connector, = result["connectors"]["features"]
    assert connector["properties"]["target_index"] == 3
    assert connector["geometry"]["coordinates"][0] == pytest.approx([113.3825, 22.529], abs=1e-8)


def test_task_input_checks_coordinates_and_requires_two_targets(client):
    valid_path = [[113.383, 22.529], [113.385, 22.529]]
    path = "/api/v1/tasks/plan"
    for recommended, targets in [
        (valid_path, valid_path[:1]),
        ([[True, 22.529], valid_path[1]], valid_path),
        (valid_path, [valid_path[0], [113.38, 23]]),
    ]:
        response = client.post(path, json={"recommended_coords": recommended, "target_points": targets})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_shared_service_accepts_application_coordinates_and_validates_direct_calls(data_root):
    campus_map = CampusMap(data_root)
    start, end = (113.383, 22.529), (113.385, 22.529)
    result = campus_map.tasks({"target_points": [start, end], "recommended_coords": [start, end]})
    assert result["route"]["geometry"]["coordinates"] == [list(start), list(end)]
    with pytest.raises(RouteInputError):
        campus_map.tasks({"target_points": [start, [True, end[1]]]})


@pytest.mark.parametrize("body", [
    {"start": [True, 22.529], "end": [113.385, 22.531]},
    {"start": [113.383, 22.529], "end": [113.385, 22.531], "waypoints": [[113.384, 22.53]] * 21},
    {"start": [113.383], "end": [113.385, 22.531]},
    {"start": [113.383, 22.529], "end": [113.385, 22.531], "costing": "auto"},
])
def test_request_validation_returns_422(client, body):
    assert client.post("/api/v1/routes", json=body).status_code == 422


def test_native_invalid_json_returns_422(client):
    assert client.get("/valhalla/route", params={"json": "{invalid"}).status_code == 422


def test_unknown_and_out_of_bounds_assets_return_404(client):
    assert client.get("/api/v1/features/private").status_code == 404
    assert client.get("/api/v1/tiles/99/0/0.png").status_code == 404
    assert client.get("/api/v1/tiles/14/-1/7139.png").status_code == 404
    assert client.get("/api/v1/tiles/14/0/0.png").status_code == 404


def test_missing_data_keeps_app_alive_and_returns_clear_503(tmp_path):
    client = TestClient(create_app(tmp_path))
    for path in ["/api/v1/map", "/healthz", "/api/v1/features/roads", "/api/v1/tiles/14/1/1.png"]:
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATA_UNAVAILABLE"
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("version", ["../outside", "/outside", "..", "C:/outside", "safe/child"])
def test_release_pointer_cannot_escape_builds(data_root, version):
    (data_root / "current.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    assert TestClient(create_app(data_root)).get("/api/v1/map").status_code == 503


def test_corrupt_asset_is_not_served(client, data_root):
    (data_root / "builds" / "test-v1" / "features" / "roads.geojson").write_text("damaged", encoding="utf-8")
    response = client.get("/api/v1/features/roads")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATA_UNAVAILABLE"


def test_malformed_manifest_does_not_crash(data_root):
    (data_root / "builds" / "test-v1" / "manifest.json").write_text("null", encoding="utf-8")
    assert TestClient(create_app(data_root)).get("/api/v1/map").status_code == 503


def test_docs_have_no_runtime_cdn(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "cdn.jsdelivr.net" not in response.text
    assert "unpkg.com" not in response.text
    assert "/openapi.json" in response.text
    if "swagger-ui-bundle.js" in response.text:
        assert client.get("/static/vendor/swagger/swagger-ui-bundle.js").status_code == 200
        assert client.get("/static/vendor/swagger/swagger-ui.css").status_code == 200


def test_static_resource_traversal_is_blocked(client):
    assert client.get("/%2e%2e%2frequirements.txt").status_code == 404


def test_file_read_error_is_reported_as_unavailable(client, monkeypatch):
    def fail_read(*_args):
        raise PermissionError("fixture unreadable")

    monkeypatch.setattr("campus_map.service.hashlib.file_digest", fail_read)
    assert client.get("/api/v1/features/roads").status_code == 503


def test_dynamic_map_style_matches_active_release(client):
    style = client.get("/api/v1/map-style").json()
    assert style["sources"]["campus"]["bounds"] == BOUNDS
    assert style["sources"]["campus"]["tiles"] == ["/api/v1/tiles/{z}/{x}/{y}.png?v=test-v1"]
    assert style["sources"]["campus"]["attribution"] == "(c) OpenStreetMap contributors"


def test_gps_uses_local_calibration_without_network(client):
    response = client.post("/api/v1/coordinates/gps", json={"points": [[113.385, 22.525]]})
    assert response.status_code == 200
    assert response.json()["coordinate_system"] == "GCJ-02"
    assert response.json()["method"] == "local-calibration"
    assert response.json()["points"][0] == pytest.approx([113.39, 22.522])


def test_old_coordinate_release_is_not_served(data_root):
    path = data_root / "builds/test-v1/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["coordinate_system"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    response = TestClient(create_app(data_root)).get("/api/v1/map")
    assert response.status_code == 503
    assert "GCJ-02" in response.json()["error"]["message"]
