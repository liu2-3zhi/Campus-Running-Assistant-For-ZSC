import math

import pytest

from campus_map import coordinates


def test_forward_formula_matches_a_known_campus_pair():
    longitude, latitude = coordinates.wgs84_to_gcj02(113.3865167, 22.5319451)
    assert longitude == pytest.approx(113.391997, abs=1e-7)
    assert latitude == pytest.approx(22.529253, abs=1e-7)


def test_forward_formula_leaves_coordinates_outside_china_unchanged():
    assert coordinates.wgs84_to_gcj02(13.4, 52.5) == (13.4, 52.5)


@pytest.mark.parametrize("point", [(True, 22), (math.inf, 22), (113, math.nan), (181, 22), (113, -91)])
def test_forward_formula_rejects_invalid_coordinates(point):
    with pytest.raises(ValueError):
        coordinates.wgs84_to_gcj02(*point)


def test_bounds_envelope_uses_the_supplied_official_converter():
    calls = []

    def convert(points):
        calls.append(points)
        return [(longitude + .006, latitude - .003) for longitude, latitude in points]

    result = coordinates.transform_bounds((113.38, 22.52, 113.39, 22.54), converter=convert)
    assert result == pytest.approx((113.386, 22.517, 113.396, 22.537))
    assert len(calls) == 1 and len(calls[0]) == 132


def test_bounds_envelope_contains_transformed_campus_edges():
    bounds = (113.3798, 22.5255, 113.3901, 22.5355)
    west, south, east, north = coordinates.transform_bounds(bounds)
    for longitude in (bounds[0], (bounds[0] + bounds[2]) / 2, bounds[2]):
        for latitude in (bounds[1], (bounds[1] + bounds[3]) / 2, bounds[3]):
            converted_longitude, converted_latitude = coordinates.wgs84_to_gcj02(longitude, latitude)
            assert west <= converted_longitude <= east
            assert south <= converted_latitude <= north


def test_source_conversion_uses_the_local_formula_without_network():
    points = [(113.38, 22.53)]
    converted = coordinates.convert_nodes(points)
    assert converted[0] == pytest.approx(list(coordinates.wgs84_to_gcj02(*points[0])))
