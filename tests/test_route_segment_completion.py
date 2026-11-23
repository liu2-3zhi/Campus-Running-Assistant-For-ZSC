"""Partial SDK geometry must reach each requested waypoint without losing road points."""

import pytest

from test_route_runtime_timeouts import PROVIDERS, run_scenario


# Vendor-native points and independently checked GCJ-02 projections. China fixtures
# exercise Baidu/Tianditu conversion rather than the identity outside China.
NATIVE_ROADS = [[116.001, 39.001], [116.002, 39.002],
                [116.003, 39.003], [116.004, 39.004]]
PROJECTED_ROADS = {
    "amap": NATIVE_ROADS,
    "tencent": NATIVE_ROADS,
    "tianditu": [[116.0070215402, 39.0018892421], [116.0080250541, 39.0028928941],
                 [116.0090285662, 39.0038965445], [116.0100320755, 39.0049001926]],
    "baidu": [[115.9944200483, 38.9952540677], [115.9954234120, 38.9962408631],
              [115.9964269858, 38.9972269980], [115.9974307599, 38.9982125106]],
}
START = [116.0, 39.0]
MIDDLE = [116.02, 39.02]
END = [116.03, 39.03]


def assert_path(result, expected):
    assert "error" not in result, result
    actual = [[point["lng"], point["lat"]] for point in result["path"]]
    assert len(actual) == len(expected), actual
    for point, target in zip(actual, expected):
        assert point == pytest.approx(target, abs=1e-9, rel=0)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("missing", ("start", "end", "both", "neither"))
def test_partial_single_segment_extends_to_requested_endpoints(provider, missing):
    roads = PROJECTED_ROADS[provider][:2]
    start = START if missing in ("start", "both") else roads[0]
    end = END if missing in ("end", "both") else roads[-1]
    result = run_scenario(provider, "walking", retries=0, waypoints=[start, end],
                          segment_paths=[NATIVE_ROADS[:2]])["result"]
    # Stored projection fixtures can differ by <1e-9 after conversion. Always
    # require exact requested endpoints, then verify the road sequence survives.
    assert result["path"][0] == {"lng": start[0], "lat": start[1]}
    assert result["path"][-1] == {"lng": end[0], "lat": end[1]}
    coordinates = [[point["lng"], point["lat"]] for point in result["path"]]
    road_indexes = [next(index for index, point in enumerate(coordinates)
                         if point == pytest.approx(road, abs=1e-9, rel=0)) for road in roads]
    assert road_indexes == sorted(road_indexes)
    assert len(coordinates) <= 4


@pytest.mark.parametrize("provider", PROVIDERS)
def test_adjacent_snapped_segments_keep_both_road_endpoints_and_middle_waypoint(provider):
    result = run_scenario(provider, "walking", retries=0, waypoints=[START, MIDDLE, END],
                          segment_paths=[NATIVE_ROADS[:2], NATIVE_ROADS[2:]])["result"]
    roads = PROJECTED_ROADS[provider]
    assert_path(result, [START, *roads[:2], MIDDLE, *roads[2:], END])


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("failed_segment", (0, 1))
def test_fallback_and_partial_success_join_at_the_requested_waypoint(provider, failed_segment):
    paths = [NATIVE_ROADS[:2], NATIVE_ROADS[2:]]
    paths[failed_segment] = None
    result = run_scenario(provider, "walking", retries=0, fallback=True,
                          waypoints=[START, MIDDLE, END], segment_paths=paths)["result"]
    roads = PROJECTED_ROADS[provider]
    expected = ([START, MIDDLE, *roads[2:], END] if failed_segment == 0
                else [START, *roads[:2], MIDDLE, END])
    assert_path(result, expected)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("waypoints", ([START, MIDDLE, START], [START, START, END]),
                         ids=("closed-route", "consecutive-repeated-waypoint"))
def test_repeated_waypoints_keep_their_position_in_the_route(provider, waypoints):
    result = run_scenario(provider, "walking", retries=0, waypoints=waypoints,
                          segment_paths=[NATIVE_ROADS[:2], NATIVE_ROADS[2:]])["result"]
    roads = PROJECTED_ROADS[provider]
    assert_path(result, [waypoints[0], *roads[:2], waypoints[1], *roads[2:], waypoints[2]])


@pytest.mark.parametrize("provider", ("amap", "tencent"))
def test_complete_segment_boundaries_are_not_duplicated(provider):
    result = run_scenario(provider, "walking", retries=0, waypoints=[START, MIDDLE, END],
                          segment_paths=[[START, MIDDLE], [MIDDLE, END]])["result"]
    assert_path(result, [START, MIDDLE, END])


def test_amap_single_returned_road_point_is_kept_between_requested_endpoints():
    result = run_scenario("amap", "walking", retries=0, waypoints=[START, END],
                          segment_paths=[[NATIVE_ROADS[0]]])["result"]
    assert_path(result, [START, NATIVE_ROADS[0], END])
