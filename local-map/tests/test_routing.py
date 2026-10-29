"""Contract and Valhalla boundary tests for the offline routing adapter."""

import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from campus_map.routing import RouteInputError, RouteNotFoundError, RoutingService, RoutingUnavailableError
from campus_map.pipeline import COORDINATE_METADATA


START = [113.383, 22.529]
MID = [113.384, 22.53]
END = [113.385, 22.531]
BOUNDS = [113.3798, 22.5255, 113.3901, 22.5355]


def encode_line(points):
    output = []
    previous = [0, 0]
    for point in points:
        for axis, value in enumerate([point[1], point[0]]):
            scaled = round(value * 1_000_000)
            delta = scaled - previous[axis]
            previous[axis] = scaled
            number = ~(delta << 1) if delta < 0 else delta << 1
            while number >= 32:
                output.append(chr((32 | (number & 31)) + 63))
                number >>= 5
            output.append(chr(number + 63))
    return "".join(output)


class ActorDouble:
    instances = []

    def __init__(self, config):
        self.config = config
        self.calls = []
        self.active = 0
        self.maximum_active = 0
        self.__class__.instances.append(self)

    def route(self, payload):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        time.sleep(0.002)
        self.calls.append(payload)
        locations = payload["locations"]
        legs = []
        for start, end in zip(locations, locations[1:]):
            coordinates = [[start["lon"], start["lat"]], [end["lon"], end["lat"]]]
            legs.append({"shape": encode_line(coordinates), "summary": {"length": 0.15, "time": 107.14}, "maneuvers": []})
        self.active -= 1
        return {"trip": {"locations": locations, "legs": legs, "summary": {"length": len(legs) * 0.15, "time": len(legs) * 107.14}, "units": "kilometers", "status": 0, "status_message": "Found route between points"}}

    def locate(self, payload):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        time.sleep(0.002)
        self.active -= 1
        return [{"edges": [{"correlated_lon": point["lon"], "correlated_lat": point["lat"]}]} for point in payload["locations"]]


@pytest.fixture
def release(tmp_path, monkeypatch):
    (tmp_path / "routing" / "tiles").mkdir(parents=True)
    (tmp_path / "routing" / "tiles" / "sample.gph").write_bytes(b"graph")
    (tmp_path / "manifest.json").write_text(json.dumps({"bounds": BOUNDS, **COORDINATE_METADATA}), encoding="utf-8")
    (tmp_path / "routing" / "valhalla.json").write_text(json.dumps({"mjolnir": {"tile_dir": "C:/removed-stage/tiles", "tile_extract": "", "tile_url": "https://invalid.example/tiles"}}), encoding="utf-8")
    monkeypatch.setattr("campus_map.routing.Actor", ActorDouble)
    ActorDouble.instances.clear()
    return tmp_path


def test_route_has_one_leg_per_interval_and_preserves_waypoint_order(release):
    service = RoutingService(release)
    result = service.route(START, END, [MID])
    assert result["route"]["geometry"] == {"type": "LineString", "coordinates": [START, MID, END]}
    assert len(result["legs"]) == 2
    assert result["distance_m"] == pytest.approx(300)
    assert result["duration_s"] == pytest.approx(214.28)
    assert result["snapped_points"][1]["input"] == MID
    assert result["snapped_points"][1]["offset_m"] == 0
    assert result["coordinate_system"] == "GCJ-02"
    request = ActorDouble.instances[-1].calls[-1]
    assert request["costing"] == "pedestrian"
    assert request["costing_options"] == {"pedestrian": {"shortest": True, "walking_speed": 5.04}}
    assert [(point["lon"], point["lat"]) for point in request["locations"]] == [tuple(START), tuple(MID), tuple(END)]
    assert all(point["type"] == "break" and point["radius"] == point["search_cutoff"] == 50 and point["minimum_reachability"] == 1 for point in request["locations"])


def test_config_is_relocated_and_cannot_fetch_remote_graph_tiles(release):
    RoutingService(release)
    config = ActorDouble.instances[-1].config
    assert config["mjolnir"]["tile_dir"] == str((release / "routing" / "tiles").resolve())
    assert not config["mjolnir"].get("tile_url")
    assert not config["mjolnir"].get("tile_extract")
    assert config["service_limits"]["pedestrian"]["max_locations"] == 22


@pytest.mark.parametrize("start,end,waypoints", [
    ([math.nan, 22.53], END, []),
    ([113.38, math.inf], END, []),
    ([True, 22.53], END, []),
    ([22.53, 113.38], END, []),
    ([113.37, 22.53], END, []),
    ([113.38], END, []),
    (START, END, [MID] * 21),
])
def test_invalid_points_never_reach_actor(release, start, end, waypoints):
    service = RoutingService(release)
    with pytest.raises(RouteInputError):
        service.route(start, end, waypoints)
    assert not ActorDouble.instances[-1].calls


def test_duplicate_waypoints_keep_zero_legs(release):
    result = RoutingService(release).route(START, END, [START, MID, MID])
    assert len(result["legs"]) == 4
    assert [leg["distance_m"] for leg in result["legs"]] == [0, 150, 0, 150]
    assert len(result["snapped_points"]) == 5
    assert result["route"]["geometry"]["coordinates"] == [START, MID, END]


def test_identical_start_and_end_returns_valid_zero_route(release):
    service = RoutingService(release)
    result = service.route(START, START, [START])
    assert result["distance_m"] == result["duration_s"] == 0
    assert len(result["legs"]) == 2
    assert result["route"]["geometry"]["coordinates"] == [START, START]
    assert len(result["snapped_points"]) == 3


def test_native_interface_cannot_override_pedestrian_or_inject_options(release):
    service = RoutingService(release)
    native = service.native_route({"locations": [{"lon": START[0], "lat": START[1]}, {"lon": END[0], "lat": END[1]}], "costing": "auto", "costing_options": {"auto": {"ignore_access": True}}, "format": "osrm", "shape_format": "geojson", "language": "en-US", "alternates": 8})
    assert native["trip"]["legs"][0]["shape"] == encode_line([START, END])
    request = ActorDouble.instances[-1].calls[-1]
    assert request["format"] == "json"
    assert request["shape_format"] == "polyline6"
    assert "alternates" not in request
    assert request["costing"] == "pedestrian"


def test_all_actor_calls_are_serialized(release):
    service = RoutingService(release)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: service.route(START, START if index % 2 else END, []), range(24)))
    assert ActorDouble.instances[-1].maximum_active == 1


def test_missing_configuration_has_clear_unavailable_error(tmp_path):
    with pytest.raises(RoutingUnavailableError):
        RoutingService(tmp_path)


@pytest.fixture(scope="module")
def actual_release(tmp_path_factory):
    """Build an actual Valhalla graph; no network and no production campus data."""
    import osmium
    from valhalla import get_config
    from valhalla._scripts import PYVALHALLA_BIN_DIR

    root = tmp_path_factory.mktemp("valhalla-actual")
    tiles = root / "routing" / "tiles"
    tiles.mkdir(parents=True)
    pbf = root / "fixture.osm.pbf"
    points = {
        1: START,
        2: [113.384, 22.529],
        3: [113.384, 22.53],
        4: [113.383, 22.53],
        5: [113.388, 22.533],
        6: [113.389, 22.533],
    }
    with osmium.SimpleWriter(str(pbf)) as writer:
        for identifier, point in points.items():
            writer.add_node(osmium.osm.mutable.Node(id=identifier, location=point))
        writer.add_way(osmium.osm.mutable.Way(id=101, nodes=[1, 4, 3, 2], tags={"highway": "footway"}))
        # The shortest permitted route uses steps; shortest=True must not
        # prefer the longer footway. A shorter foot=no road must stay excluded.
        writer.add_way(osmium.osm.mutable.Way(id=102, nodes=[1, 3], tags={"highway": "steps"}))
        writer.add_way(osmium.osm.mutable.Way(id=103, nodes=[1, 2], tags={"highway": "residential", "foot": "no"}))
        writer.add_way(osmium.osm.mutable.Way(id=104, nodes=[5, 6], tags={"highway": "footway"}))
    config = get_config(tile_dir=tiles, tile_extract="")
    config["mjolnir"].update({"admin": "", "timezone": "", "hierarchy": False, "shortcuts": False, "concurrency": 1})
    config["service_limits"]["pedestrian"]["max_locations"] = 22
    config_path = root / "routing" / "valhalla.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"bounds": BOUNDS, **COORDINATE_METADATA}), encoding="utf-8")
    environment = dict(os.environ, PATH=str(PYVALHALLA_BIN_DIR) + os.pathsep + os.environ.get("PATH", ""))
    build = subprocess.run([sys.executable, "-m", "valhalla", "valhalla_build_tiles", "-c", str(config_path), str(pbf)], env=environment, capture_output=True, text=True, timeout=90)
    assert build.returncode == 0, build.stdout + build.stderr
    assert any(tiles.rglob("*.gph")), build.stdout + build.stderr
    return root


def test_real_valhalla_chooses_shortest_steps_and_respects_foot_no(actual_release):
    service = RoutingService(actual_release)
    diagonal = service.route(START, [113.384, 22.53], [])
    assert 140 <= diagonal["distance_m"] <= 160
    assert len(diagonal["route"]["geometry"]["coordinates"]) >= 2
    prohibited = service.route(START, [113.384, 22.529], [])
    assert prohibited["distance_m"] > 200
    assert all(point["offset_m"] < 1 for point in prohibited["snapped_points"])


def test_real_valhalla_zero_route_and_duplicate_breaks(actual_release):
    service = RoutingService(actual_release)
    zero = service.route(START, START, [START])
    assert zero["distance_m"] == 0
    assert len(zero["legs"]) == 2
    duplicate = service.route(START, [113.384, 22.53], [START])
    assert [leg["distance_m"] for leg in duplicate["legs"]][0] == 0
    assert len(duplicate["legs"]) == 2


def test_real_valhalla_disconnected_and_far_away_points_fail(actual_release):
    service = RoutingService(actual_release)
    with pytest.raises(RouteNotFoundError):
        service.route(START, [113.388, 22.533], [])
    with pytest.raises(RouteNotFoundError):
        service.route([113.380, 22.526], START, [])


def test_real_valhalla_accepts_20_waypoints_and_native_polyline6(actual_release):
    service = RoutingService(actual_release)
    result = service.route(START, [113.384, 22.53], [START if index % 2 else [113.384, 22.53] for index in range(20)])
    assert len(result["legs"]) == 21
    native = service.native_route({"locations": [{"lon": START[0], "lat": START[1]}, {"lon": 113.384, "lat": 22.53}]})
    assert isinstance(native["trip"]["legs"][0]["shape"], str)


def test_native_identical_points_include_summary_bounds_for_upstream_web(release):
    native = RoutingService(release).native_route({"locations": [{"lon": START[0], "lat": START[1]}] * 2})
    summary = native["trip"]["summary"]
    assert summary["min_lon"] == summary["max_lon"] == START[0]
    assert summary["min_lat"] == summary["max_lat"] == START[1]


def test_real_valhalla_loads_a_relocated_immutable_release(actual_release, tmp_path):
    published = tmp_path / "builds" / "published-version"
    shutil.copytree(actual_release, published)
    result = RoutingService(published).route(START, [113.384, 22.53], [])
    assert 140 <= result["distance_m"] <= 160


def test_old_wgs84_graph_is_rejected_before_actor_creation(release):
    (release / "manifest.json").write_text(json.dumps({"bounds": BOUNDS}), encoding="utf-8")
    with pytest.raises(RoutingUnavailableError):
        RoutingService(release)
    assert not ActorDouble.instances
