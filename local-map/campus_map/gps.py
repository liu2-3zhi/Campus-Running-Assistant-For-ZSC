"""Offline forward GPS conversion using a grid sampled from AMap at prepare time."""

import math

from .coordinates import wgs84_to_gcj02


class Calibration:
    def __init__(self, document):
        if (not isinstance(document, dict) or document.get("coordinate_system") != "GCJ-02" or
                document.get("source_coordinate_system") != "WGS84" or
                document.get("coordinate_conversion") != "AMap Web Service gps -> GCJ-02"):
            raise ValueError("Invalid AMap GPS calibration coordinate system")
        self.bounds = document["source_bounds"]
        self.columns, self.rows = document["columns"], document["rows"]
        self.points = document["points"]
        if (len(self.bounds) != 4 or
                not all(type(value) in (int, float) and math.isfinite(value) for value in self.bounds) or
                not self.bounds[0] < self.bounds[2] or not self.bounds[1] < self.bounds[3] or
                type(self.columns) is not int or type(self.rows) is not int or
                not 2 <= self.columns <= 256 or not 2 <= self.rows <= 256 or
                not isinstance(self.points, list) or len(self.points) != self.columns * self.rows or
                any(not isinstance(point, list) or len(point) != 2 or
                    not all(type(value) in (int, float) and math.isfinite(value) for value in point)
                    for point in self.points)):
            raise ValueError("Invalid AMap GPS calibration grid")

    def convert(self, point):
        longitude, latitude = point
        west, south, east, north = self.bounds
        if not (west <= longitude <= east and south <= latitude <= north):
            return list(wgs84_to_gcj02(longitude, latitude)), "local-approximation"
        x = (longitude - west) / (east - west) * (self.columns - 1)
        y = (latitude - south) / (north - south) * (self.rows - 1)
        column, row = min(int(x), self.columns - 2), min(int(y), self.rows - 2)
        dx, dy = x - column, y - row
        corners = [self.points[row * self.columns + column],
                   self.points[row * self.columns + column + 1],
                   self.points[(row + 1) * self.columns + column],
                   self.points[(row + 1) * self.columns + column + 1]]
        weights = [(1 - dx) * (1 - dy), dx * (1 - dy), (1 - dx) * dy, dx * dy]
        converted = [sum(corner[axis] * weight for corner, weight in zip(corners, weights))
                     for axis in range(2)]
        return converted, "amap-calibration"
