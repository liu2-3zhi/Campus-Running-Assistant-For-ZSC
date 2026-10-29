"""HTTP contracts, local static resources, and unavailable data behavior."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from campus_map.api import create_app
from campus_map.pipeline import COORDINATE_METADATA


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
    monkeypatch.setattr("campus_map.api.RoutingService", RoutingDouble)
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


def test_routes_and_native_endpoint(client):
    response = client.post("/api/v1/routes", json={"start": [113.383, 22.529], "end": [113.385, 22.531], "waypoints": [[113.384, 22.53]]})
    assert response.status_code == 200
    assert response.json()["snapped_points"][1]["input"] == [113.384, 22.53]
    assert len(response.json()["legs"]) == 2
    native = client.get("/valhalla/route", params={"json": json.dumps({"locations": [{"lon": 113.383, "lat": 22.529}, {"lon": 113.385, "lat": 22.531}]})})
    assert native.status_code == 200
    assert native.json()["trip"]["status"] == 0


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

    monkeypatch.setattr("campus_map.api.hashlib.file_digest", fail_read)
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
