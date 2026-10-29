import json
import math

import httpx
import pytest

from campus_map import footpaths


POINTS = [[113.392747, 22.530308], [113.393379, 22.529166], [113.39385, 22.52951]]
BOUNDS = [113.390, 22.528, 113.395, 22.532]


@pytest.fixture(autouse=True)
def fake_amap_key(monkeypatch):
    monkeypatch.setattr(footpaths.amap, "load_web_key", lambda: "private-key")


def route_response(request, *, polyline=None, paths=None):
    origin = request.url.params["origin"]
    destination = request.url.params["destination"]
    steps = [{"road_name": "校园步道", "step_distance": "20", "instruction": "直行",
              "navi": {"walk_type": "13"},
              "polyline": polyline or f"{origin};{destination}"}]
    path = {"distance": "20", "steps": steps}
    payload_paths = paths or [path]
    return httpx.Response(200, json={"status": "1", "info": "ok", "infocode": "10000",
                                     "count": str(len(payload_paths)),
                                     "route": {"origin": origin, "destination": destination, "paths": payload_paths}})


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_prepare_writes_raw_routes_and_step_features_atomically(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "restapi.amap.com"
        assert request.url.path == "/v5/direction/walking"
        assert request.url.params["alternative_route"] == "3"
        assert request.url.params["show_fields"] == "polyline,navi,cost"
        assert request.headers["referer"] == "https://zslf.zsc.edu.cn/"
        assert request.headers["origin"] == "https://zslf.zsc.edu.cn"
        assert request.url.params["key"] == "private-key"
        return route_response(request)

    with client_for(respond) as client:
        result = footpaths.prepare_footpaths(POINTS, tmp_path, bounds=BOUNDS, client=client)
    assert len(calls) == 3
    assert result["pair_count"] == 3
    assert result["feature_count"] == 3
    assert result["coordinate_system"] == "GCJ-02"
    document = json.loads((tmp_path / "footpaths.geojson").read_text(encoding="utf-8"))
    feature = document["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["properties"]["walk_type"] == "13"
    assert feature["properties"]["osm_tags"]["highway"] == "footway"
    assert feature["properties"]["route_id"].startswith("amap-walking-")
    assert len([path for path in (tmp_path / "source").glob("route-*.json") if not path.name.endswith(".meta.json")]) == 3
    assert all(b"private-key" not in path.read_bytes() for path in (tmp_path / "source").glob("*"))


def test_prepare_reuses_raw_pairs_without_key_or_network(tmp_path, monkeypatch):
    responses = []

    def respond(request):
        responses.append(request)
        return route_response(request)

    with client_for(respond) as client:
        first = footpaths.prepare_footpaths(POINTS, tmp_path, bounds=BOUNDS, client=client)
    monkeypatch.setattr(footpaths.amap, "load_web_key", lambda: pytest.fail("cache should avoid key"))
    monkeypatch.setattr(footpaths.amap, "_get", lambda *args, **kwargs: pytest.fail("cache should avoid network"))
    second = footpaths.prepare_footpaths(POINTS, tmp_path, bounds=BOUNDS, client=object())
    assert first["feature_count"] == second["feature_count"] == 3
    assert len(responses) == 3
    assert second["cached_pairs"] == 3


def test_prepare_rejects_missing_polyline_without_synthetic_line(tmp_path):
    def respond(request):
        bad = {"distance": "20", "steps": [{"step_distance": "20", "navi": {"walk_type": "0"}}]}
        return route_response(request, paths=[bad])

    with client_for(respond) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    assert result["feature_count"] == 0
    assert len(result["skipped_pairs"]) == 1
    assert "no verified" in result["skipped_pairs"][0]["reason"]
    assert json.loads((tmp_path / "footpaths.geojson").read_text(encoding="utf-8"))["features"] == []


def test_prepare_rejects_step_gap_and_out_of_bounds_geometry(tmp_path):
    def gap(request):
        origin, destination = request.url.params["origin"], request.url.params["destination"]
        path = {"distance": "20", "steps": [
            {"step_distance": "10", "navi": {"walk_type": "0"}, "polyline": f"{origin};113.3949,22.5319"},
            {"step_distance": "10", "navi": {"walk_type": "0"}, "polyline": f"113.394,22.531;{destination}"},
        ]}
        return route_response(request, paths=[path])

    with client_for(gap) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    assert result["feature_count"] == 0
    assert len(result["skipped_pairs"]) == 1
    assert "no verified" in result["skipped_pairs"][0]["reason"]


@pytest.mark.parametrize("walk_type,expected", [("20", "steps"), ("4", "yes"), ("23", "-1"), ("9", "elevator")])
def test_step_types_map_to_explicit_osm_tags(tmp_path, walk_type, expected):
    def respond(request):
        origin, destination = request.url.params["origin"], request.url.params["destination"]
        path = {"distance": "20", "steps": [{"road_name": "A", "step_distance": "20",
                "navi": {"walk_type": walk_type}, "polyline": f"{origin};{destination}"}]}
        return route_response(request, paths=[path])

    with client_for(respond) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    tags = json.loads((tmp_path / "footpaths.geojson").read_text())["features"][0]["properties"]["osm_tags"]
    if walk_type == "20":
        assert tags["highway"] == expected
    elif walk_type == "4":
        assert tags["bridge"] == expected
    elif walk_type == "23":
        assert tags["layer"] == expected
    else:
        assert tags["highway"] == expected


def test_prepare_rejects_nonwalking_transport_and_long_route(tmp_path):
    def transport(request):
        return route_response(request, paths=[{"distance": "20", "steps": [{"step_distance": "20",
            "navi": {"walk_type": "30"}, "polyline": f"{request.url.params['origin']};{request.url.params['destination']}"}]}])

    with client_for(transport) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    assert result["feature_count"] == 0
    assert len(result["skipped_pairs"]) == 1

    def long(request):
        return route_response(request, paths=[{"distance": "3001", "steps": [{"step_distance": "3001",
            "navi": {"walk_type": "0"}, "polyline": f"{request.url.params['origin']};{request.url.params['destination']}"}]}])

    with client_for(long) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    assert result["feature_count"] == 0
    assert len(result["skipped_pairs"]) == 1


@pytest.mark.parametrize("points,bounds", [([], BOUNDS), (POINTS[:1], BOUNDS), (POINTS, [113, 22, 114, 23]),
                                             ([[113.2, 22.5], POINTS[1]], BOUNDS),
                                             ([POINTS[0], POINTS[0]], BOUNDS)])
def test_prepare_validates_reference_points(points, bounds, tmp_path):
    with pytest.raises(footpaths.FootpathError):
        footpaths.prepare_footpaths(points, tmp_path, bounds=bounds, client=object())
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_corrupt_cached_response_is_rejected_without_network_or_replacement(tmp_path):
    with client_for(lambda request: route_response(request)) as client:
        footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    raw = next((tmp_path / "source").glob("route-*.json"))
    original = raw.read_bytes()
    raw.write_text("{}", encoding="utf-8")
    with pytest.raises(footpaths.FootpathError, match="cached"):
        footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=object())
    assert raw.read_bytes() == b"{}"
    assert original != raw.read_bytes()


def test_rejected_alternate_path_is_reported_but_good_path_retained(tmp_path):
    def respond(request):
        origin, destination = request.url.params["origin"], request.url.params["destination"]
        good = {"distance": "20", "steps": [{"step_distance": "20", "navi": {"walk_type": "0"},
            "polyline": f"{origin};{destination}"}]}
        bad = {"distance": "4000", "steps": []}
        return route_response(request, paths=[good, bad])

    with client_for(respond) as client:
        result = footpaths.prepare_footpaths(POINTS[:2], tmp_path, bounds=BOUNDS, client=client)
    assert result["feature_count"] == 1
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["routes"][0]["rejected_paths"]

