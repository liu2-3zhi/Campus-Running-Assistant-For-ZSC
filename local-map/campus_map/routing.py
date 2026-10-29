"""A bounded, thread-safe adapter around the official Valhalla Python Actor."""

from __future__ import annotations

import json
import math
from pathlib import Path
from threading import Lock

try:
    from valhalla import Actor
except ImportError:
    Actor = None


class RouteInputError(ValueError):
    """The caller supplied coordinates outside the public route contract."""


class RoutingUnavailableError(RuntimeError):
    """The local routing release cannot be loaded or read."""


class RouteNotFoundError(RuntimeError):
    """Valhalla could not connect the requested pedestrian locations."""


def _distance_m(first, second):
    lat1, lat2 = math.radians(first[1]), math.radians(second[1])
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second[0] - first[0])
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6_371_008.8 * 2 * math.asin(min(1.0, math.sqrt(value)))


def _decode_polyline(value):
    coordinates, cursor, previous = [], 0, [0, 0]
    while cursor < len(value):
        for axis in range(2):
            number, shift = 0, 0
            while True:
                if cursor >= len(value) or shift > 35:
                    raise ValueError("Invalid route geometry")
                byte = ord(value[cursor]) - 63
                cursor += 1
                if byte < 0 or byte > 63:
                    raise ValueError("Invalid route geometry")
                number |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            previous[axis] += ~(number >> 1) if number & 1 else number >> 1
        coordinates.append([previous[1] / 1_000_000, previous[0] / 1_000_000])
    return coordinates


def _encode_polyline(coordinates):
    result, previous = [], [0, 0]
    for longitude, latitude in coordinates:
        for axis, value in enumerate((latitude, longitude)):
            scaled = round(value * 1_000_000)
            delta = scaled - previous[axis]
            previous[axis] = scaled
            number = ~(delta << 1) if delta < 0 else delta << 1
            while number >= 32:
                result.append(chr((32 | (number & 31)) + 63))
                number >>= 5
            result.append(chr(number + 63))
    return "".join(result)


class RoutingService:
    """Load one immutable release and serialize every call to its Actor."""

    def __init__(self, release_dir: Path):
        self.release_dir = Path(release_dir).resolve()
        self._lock = Lock()
        try:
            manifest = json.loads((self.release_dir / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("coordinate_system") != "GCJ-02" or manifest.get("graph_coordinate_system") != "GCJ-02":
                raise ValueError("The routing graph must be rebuilt in GCJ-02")
            if manifest.get("source_coordinate_system") != "WGS84" or manifest.get("coordinate_conversion") != "Local WGS84 -> GCJ-02 formula":
                raise ValueError("The routing graph has no verified local coordinate conversion")
            self.bounds = tuple(manifest["bounds"])
            if len(self.bounds) != 4 or not all(type(value) in (float, int) and math.isfinite(value) for value in self.bounds):
                raise ValueError("Invalid bounds")
            config = json.loads((self.release_dir / "routing" / "valhalla.json").read_text(encoding="utf-8"))
            tiles = self.release_dir / "routing" / "tiles"
            extract = self.release_dir / "routing" / "tiles.tar"
            if not (tiles.is_dir() and any(tiles.rglob("*.gph"))) and not extract.is_file():
                raise ValueError("No routing graph tiles")
            for path in (tiles, extract):
                if not path.resolve().is_relative_to(self.release_dir):
                    raise ValueError("Routing graph leaves release")
            mjolnir = config.setdefault("mjolnir", {})
            mjolnir["tile_dir"] = str(tiles)
            mjolnir["tile_extract"] = str(extract) if extract.is_file() else ""
            mjolnir["tile_url"] = ""
            mjolnir["traffic_extract"] = ""
            mjolnir["incident_dir"] = ""
            mjolnir["incident_log"] = ""
            # These databases are optional for a self-contained pedestrian graph.
            for key in ("admin", "timezone"):
                local = self.release_dir / "routing" / f"{key}.sqlite"
                mjolnir[key] = str(local) if local.is_file() else ""
            for component in ("loki", "thor", "odin", "mjolnir"):
                config.setdefault(component, {}).setdefault("logging", {})["type"] = ""
            config.setdefault("logging", {})["type"] = ""
            config.setdefault("service_limits", {}).setdefault("pedestrian", {})["max_locations"] = 22
            if Actor is None:
                raise RuntimeError("pyvalhalla is not installed")
            with self._lock:
                self._actor = Actor(config)
        except Exception as error:
            raise RoutingUnavailableError("Local routing data is unavailable; run prepare and build.") from error

    def _point(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise RouteInputError("Each coordinate must contain longitude and latitude.")
        if not all(type(number) in (int, float) and math.isfinite(number) for number in value):
            raise RouteInputError("Coordinates must be finite numbers.")
        longitude, latitude = value
        west, south, east, north = self.bounds
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90 and west <= longitude <= east and south <= latitude <= north):
            raise RouteInputError("Coordinates must be GCJ-02 points inside the campus bounds.")
        return [float(longitude), float(latitude)]

    def _points(self, start, end, waypoints):
        if waypoints is None:
            waypoints = []
        if not isinstance(waypoints, (list, tuple)) or len(waypoints) > 20:
            raise RouteInputError("At most 20 waypoints are allowed.")
        return [self._point(point) for point in [start, *waypoints, end]]

    @staticmethod
    def _request(points):
        return {
            "locations": [{"lon": point[0], "lat": point[1], "type": "break", "radius": 50, "search_cutoff": 50, "minimum_reachability": 1} for point in points],
            "costing": "pedestrian",
            "costing_options": {"pedestrian": {"shortest": True, "walking_speed": 5.04}},
            "units": "kilometers",
            "format": "json",
            "shape_format": "polyline6",
            "directions_options": {"units": "kilometers", "language": "en-US"},
        }

    def _call(self, action, payload):
        try:
            with self._lock:
                response = getattr(self._actor, action)(payload)
            return json.loads(response) if isinstance(response, str) else response
        except Exception as error:
            code = getattr(error, "code", None)
            # Routing failures are normal user results; missing/broken graph files
            # must instead signal that the local service needs rebuilding.
            if isinstance(error, OSError) or code in (110, 111, 112, 113, 114):
                raise RoutingUnavailableError("Local routing data could not be read.") from error
            raise RouteNotFoundError("No walkable route within 50 metres of the requested points.") from error

    def _native(self, points):
        unique = [points[0]]
        for point in points[1:]:
            if point != unique[-1]:
                unique.append(point)
        if len(unique) == 1:
            located = self._call("locate", self._request(unique))
            try:
                edge = located[0]["edges"][0]
                snapped = [edge["correlated_lon"], edge["correlated_lat"]]
                if _distance_m(points[0], snapped) > 50.1:
                    raise RouteNotFoundError("No pedestrian path within 50 metres of this point.")
            except (KeyError, IndexError, TypeError) as error:
                raise RouteNotFoundError("No pedestrian path within 50 metres of this point.") from error
            native = {"trip": {"locations": [], "legs": [], "summary": {"length": 0, "time": 0, "min_lon": snapped[0], "max_lon": snapped[0], "min_lat": snapped[1], "max_lat": snapped[1]}, "units": "kilometers", "language": "en-US", "status": 0, "status_message": "Found route between points"}}
            snapped_unique = [snapped]
        else:
            native = self._call("route", self._request(unique))
            try:
                legs = native["trip"]["legs"]
                if len(legs) != len(unique) - 1:
                    raise ValueError("Unexpected number of Valhalla legs")
                lines = [_decode_polyline(leg["shape"]) for leg in legs]
                if any(len(line) < 2 for line in lines):
                    raise ValueError("Empty Valhalla geometry")
                snapped_unique = [line[0] for line in lines] + [lines[-1][-1]]
            except (KeyError, TypeError, ValueError, IndexError) as error:
                raise RoutingUnavailableError("Local routing engine returned invalid geometry.") from error
        trip = native["trip"]
        original_legs = trip["legs"]
        expanded, snapped_points, unique_index = [], [snapped_unique[0]], 0
        for first, second in zip(points, points[1:]):
            if first == second:
                snapped = snapped_unique[unique_index]
                expanded.append({"shape": _encode_polyline([snapped, snapped]), "summary": {"length": 0, "time": 0, "min_lon": snapped[0], "max_lon": snapped[0], "min_lat": snapped[1], "max_lat": snapped[1]}, "maneuvers": []})
            else:
                expanded.append(original_legs[unique_index])
                unique_index += 1
            snapped_points.append(snapped_unique[unique_index])
        for original, snapped in zip(points, snapped_points):
            if _distance_m(original, snapped) > 50.1:
                raise RouteNotFoundError("No pedestrian path within 50 metres of a requested point.")
        trip["legs"] = expanded
        trip["locations"] = [{"lon": original[0], "lat": original[1], "type": "break", "original_index": index} for index, original in enumerate(points)]
        return native, snapped_points

    def route(self, start, end, waypoints=None):
        points = self._points(start, end, waypoints)
        native, snapped = self._native(points)
        coordinates, legs = [], []
        for index, leg in enumerate(native["trip"]["legs"]):
            line = _decode_polyline(leg["shape"])
            for point in line:
                if not coordinates or point != coordinates[-1]:
                    coordinates.append(point)
            legs.append({"index": index, "start_index": index, "end_index": index + 1, "distance_m": float(leg["summary"]["length"]) * 1000, "duration_s": float(leg["summary"]["time"]), "geometry": {"type": "LineString", "coordinates": line}})
        if len(coordinates) == 1:
            coordinates.append(coordinates[0][:])
        distance = sum(leg["distance_m"] for leg in legs)
        duration = sum(leg["duration_s"] for leg in legs)
        return {
            "coordinate_system": "GCJ-02",
            "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates}, "properties": {"distance_m": distance, "duration_s": duration}},
            "legs": legs, "distance_m": distance, "duration_s": duration,
            "snapped_points": [{"input": original, "snapped": point, "offset_m": _distance_m(original, point)} for original, point in zip(points, snapped)],
        }

    def native_route(self, payload):
        if not isinstance(payload, dict):
            raise RouteInputError("Valhalla request must be an object.")
        locations = payload.get("locations")
        if not isinstance(locations, list) or not 2 <= len(locations) <= 22:
            raise RouteInputError("Provide between 2 and 22 locations.")
        try:
            points = [self._point([location["lon"], location["lat"]]) for location in locations]
        except (KeyError, TypeError) as error:
            raise RouteInputError("Each location must contain lon and lat.") from error
        # Only coordinates enter the engine: browser profiles, costing overrides,
        # alternates and remote options cannot weaken this service's contract.
        native, _ = self._native(points)
        native["coordinate_system"] = "GCJ-02"
        return native
