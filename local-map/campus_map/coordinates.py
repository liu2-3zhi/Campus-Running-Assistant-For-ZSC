"""Convert archived WGS84 OSM nodes once into the application's GCJ-02 datum."""

from __future__ import annotations

import math
from pathlib import Path


COORDINATE_SYSTEM = "GCJ-02"
SOURCE_COORDINATE_SYSTEM = "WGS84"
_A = 6_378_245.0
_EE = 0.00669342162296594323


def outside_china(longitude: float, latitude: float) -> bool:
    return longitude < 72.004 or longitude > 137.8347 or latitude < 0.8293 or latitude > 55.8271


def _latitude_delta(x: float, y: float) -> float:
    value = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    value += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    value += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    value += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    return value


def _longitude_delta(x: float, y: float) -> float:
    value = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    value += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    value += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    value += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    return value


def wgs84_to_gcj02(longitude: float, latitude: float) -> tuple[float, float]:
    if not all(type(value) in (int, float) and math.isfinite(value) for value in (longitude, latitude)):
        raise ValueError("Coordinates must be finite numbers")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("Coordinates are outside the longitude/latitude range")
    if outside_china(longitude, latitude):
        return float(longitude), float(latitude)
    delta_latitude = _latitude_delta(longitude - 105, latitude - 35)
    delta_longitude = _longitude_delta(longitude - 105, latitude - 35)
    radians = math.radians(latitude)
    magic = 1 - _EE * math.sin(radians) ** 2
    root = math.sqrt(magic)
    delta_latitude *= 180 / ((_A * (1 - _EE) / (magic * root)) * math.pi)
    delta_longitude *= 180 / ((_A / root) * math.cos(radians) * math.pi)
    return longitude + delta_longitude, latitude + delta_latitude


def convert_nodes(points) -> list[list[float]]:
    """Convert source data through the official service; never approximate silently."""
    from .amap import convert_points

    return convert_points(points, cache_path=Path(__file__).resolve().parents[1] / "data/amap-cache/coordinate-cache.json")


def transform_bounds(bounds, converter=None) -> tuple[float, float, float, float]:
    """Return a GCJ-02 envelope, sampling the edges of the small source extent."""
    if not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
        raise ValueError("Bounds must contain west, south, east and north")
    west, south, east, north = bounds
    if not all(type(value) in (int, float) and math.isfinite(value) for value in bounds):
        raise ValueError("Bounds must be finite numbers")
    if not -180 <= west < east <= 180 or not -90 <= south < north <= 90:
        raise ValueError("Bounds are outside the longitude/latitude range")
    edge_points = []
    for index in range(33):
        fraction = index / 32
        longitude, latitude = west + (east - west) * fraction, south + (north - south) * fraction
        edge_points.extend(((longitude, south), (longitude, north), (west, latitude), (east, latitude)))
    converted = (converter(edge_points) if converter is not None
                 else [wgs84_to_gcj02(*point) for point in edge_points])
    return (min(point[0] for point in converted), min(point[1] for point in converted),
            max(point[0] for point in converted), max(point[1] for point in converted))
