import pytest

from campus_map.gps import Calibration
from campus_map.pipeline import COORDINATE_METADATA


def grid():
    return {**COORDINATE_METADATA, "source_bounds": [113.38, 22.52, 113.39, 22.53], "columns": 2, "rows": 2,
            "points": [[113.385, 22.517], [113.395, 22.517], [113.385, 22.527], [113.395, 22.527]]}


@pytest.mark.parametrize("point,expected", [
    ([113.38, 22.52], [113.385, 22.517]),
    ([113.39, 22.53], [113.395, 22.527]),
    ([113.385, 22.525], [113.39, 22.522]),
])
def test_calibration_interpolates_corners_edges_and_interior(point, expected):
    converted, method = Calibration(grid()).convert(point)
    assert method == "amap-calibration"
    assert converted == pytest.approx(expected)


def test_gps_outside_calibration_is_explicitly_approximate():
    converted, method = Calibration(grid()).convert([0, 0])
    assert converted == [0, 0]
    assert method == "local-approximation"


def test_corrupt_calibration_is_rejected():
    document = grid()
    document["points"][0][0] = float("nan")
    with pytest.raises(ValueError, match="calibration"):
        Calibration(document)


@pytest.mark.parametrize("document", [None, [], {"coordinate_system": "WGS84"}])
def test_invalid_calibration_datum_is_rejected(document):
    with pytest.raises(ValueError, match="calibration"):
        Calibration(document)
