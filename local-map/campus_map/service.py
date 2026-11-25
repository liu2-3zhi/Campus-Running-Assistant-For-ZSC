"""Shared offline campus map operations for the main app and standalone API."""

from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from threading import Lock

from .routing import RouteInputError, RouteNotFoundError, RoutingService, RoutingUnavailableError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SDK_MEDIA_TYPES = {
    "maplibre-gl-csp.js": "text/javascript",
    "maplibre-gl-csp-worker.js": "text/javascript",
    "maplibre-gl.css": "text/css",
    "LICENSE.txt": "text/plain",
}


class DataUnavailableError(RuntimeError):
    pass


def bounded_path(root, relative):
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise DataUnavailableError("Invalid data resource path.")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(part in (".", "..") for part in parts.parts):
        raise DataUnavailableError("Invalid data resource path.")
    target = (root / Path(*parts.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise DataUnavailableError("Data resource leaves the active release.")
    return target


class _Release:
    def __init__(self, root, version):
        self.root = root
        manifest_path = bounded_path(root, "manifest.json")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = self.manifest
        required = {"version", "name", "bounds", "center", "minzoom", "maxzoom", "layers", "coverage", "sources", "examples", "checksums"}
        if not isinstance(manifest, dict) or not required.issubset(manifest) or manifest["version"] != version:
            raise DataUnavailableError("The active map manifest is invalid.")
        if manifest.get("coordinate_system") != "GCJ-02" or manifest.get("graph_coordinate_system") != "GCJ-02":
            raise DataUnavailableError("The active map uses an old coordinate system; run prepare and build for GCJ-02.")
        if manifest.get("source_coordinate_system") != "WGS84" or manifest.get("coordinate_conversion") != "Local WGS84 -> GCJ-02 formula":
            raise DataUnavailableError("The active map has no verified local coordinate conversion; run prepare and build.")
        bounds = manifest["bounds"]
        if not isinstance(bounds, list) or len(bounds) != 4 or not all(type(number) in (int, float) and math.isfinite(number) for number in bounds):
            raise DataUnavailableError("The active map bounds are invalid.")
        west, south, east, north = bounds
        if not (-180 <= west < east <= 180 and -85.05112878 <= south < north <= 85.05112878):
            raise DataUnavailableError("The active map bounds are invalid.")
        minimum, maximum = manifest["minzoom"], manifest["maxzoom"]
        if type(minimum) is not int or type(maximum) is not int or not 0 <= minimum <= maximum <= 24:
            raise DataUnavailableError("The active map zoom range is invalid.")
        if not isinstance(manifest["layers"], dict) or not manifest["layers"]:
            raise DataUnavailableError("The active map layers are invalid.")
        for layer, metadata in manifest["layers"].items():
            if not isinstance(layer, str) or not IDENTIFIER.fullmatch(layer) or not isinstance(metadata, dict) or metadata.get("file") != f"features/{layer}.geojson":
                raise DataUnavailableError("The active map layer path is invalid.")
        checksums = manifest["checksums"]
        if not isinstance(checksums, dict) or not checksums:
            raise DataUnavailableError("The active map checksums are missing.")
        for relative, checksum in checksums.items():
            bounded_path(root, relative)
            if not isinstance(checksum, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
                raise DataUnavailableError("The active map checksum is invalid.")
        self._routing = None
        self._routing_lock = Lock()
        self._calibration = None

    def calibration(self):
        from .gps import Calibration

        if self._calibration is None:
            try:
                document = json.loads(self.asset("coordinate-calibration.json").read_text(encoding="utf-8"))
                self._calibration = Calibration(document)
            except (ValueError, KeyError, TypeError, OSError) as error:
                raise DataUnavailableError("Local GPS calibration is unavailable; run prepare and build.") from error
        return self._calibration

    def asset(self, relative):
        path = bounded_path(self.root, relative)
        checksum = self.manifest["checksums"].get(relative)
        if not checksum or not path.is_file():
            raise DataUnavailableError("A required local data file is missing; run prepare and build.")
        try:
            with path.open("rb") as handle:
                actual_checksum = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError as error:
            raise DataUnavailableError("A local data file could not be read.") from error
        if actual_checksum.lower() != checksum.lower():
            raise DataUnavailableError("A local data file is damaged; rebuild the map release.")
        return path

    def feature_collection(self, layer):
        path = self.asset(self.manifest["layers"][layer]["file"])
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
                raise ValueError("Invalid FeatureCollection")
        except (OSError, ValueError) as error:
            raise DataUnavailableError("A local feature layer is damaged.") from error
        return document

    def routing(self):
        with self._routing_lock:
            if self._routing is None:
                self.asset("routing/valhalla.json")
                graph_files = [relative for relative in self.manifest["checksums"] if relative.startswith("routing/tiles/") or relative == "routing/tiles.tar"]
                if not graph_files:
                    raise DataUnavailableError("The local routing graph is missing.")
                for relative in graph_files:
                    self.asset(relative)
                self._routing = RoutingService(self.root)
            return self._routing

    def contains_tile(self, z, x, y):
        if not self.manifest["minzoom"] <= z <= self.manifest["maxzoom"] or not 0 <= x < 2**z or not 0 <= y < 2**z:
            return False
        west, south, east, north = self.manifest["bounds"]
        scale = 2**z
        tile_x = lambda longitude: math.floor((longitude + 180) / 360 * scale)
        tile_y = lambda latitude: math.floor((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * scale)
        return tile_x(west) <= x <= tile_x(east) and tile_y(north) <= y <= tile_y(south)


class CampusMap:
    """Read the active map release and reuse its routing engine in this process."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = Path(data_root if data_root is not None else PROJECT_ROOT / "data").resolve()
        self.web_root = PROJECT_ROOT / "web" / "dist"
        self._cache_lock = Lock()
        self._release_identity = None
        self._active_release = None

    def _release(self):
        root = self.data_root
        try:
            pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
            version = pointer.get("version") if isinstance(pointer, dict) else None
            if not isinstance(version, str) or not IDENTIFIER.fullmatch(version) or version in (".", ".."):
                raise DataUnavailableError("The active release pointer is invalid.")
            directory = bounded_path(root, f"builds/{version}")
            manifest_stat = (directory / "manifest.json").stat()
            identity = (version, manifest_stat.st_mtime_ns, manifest_stat.st_size)
            with self._cache_lock:
                if self._release_identity != identity:
                    self._active_release = _Release(directory, version)
                    self._release_identity = identity
                return self._active_release
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise DataUnavailableError("Local map data is unavailable; run prepare and build.") from error

    def health(self):
        active = self._release()
        active.routing()
        return {"status": "ok", "version": active.manifest["version"], "offline": True,
                "coordinate_system": "GCJ-02"}

    def map_metadata(self):
        return self._release().manifest

    def sdk_asset(self, filename):
        if filename not in SDK_MEDIA_TYPES:
            raise FileNotFoundError("Unknown map SDK asset")
        path = self.web_root / "static" / "vendor" / "maplibre" / filename
        if not path.is_file():
            path = self.web_root.parent / "node_modules" / "maplibre-gl" / "dist" / filename
        if not path.is_file():
            raise DataUnavailableError("MapLibre SDK assets are missing; build the local-map web app.")
        return path

    def calibration(self):
        return self._release().calibration()

    def features(self, layer):
        active = self._release()
        if layer not in active.manifest["layers"]:
            raise FileNotFoundError("Unknown map layer")
        return active.feature_collection(layer)

    def tile(self, z, x, y):
        active = self._release()
        if not active.contains_tile(z, x, y):
            raise FileNotFoundError("Tile outside map coverage")
        return active.asset(f"tiles/{z}/{x}/{y}.png")

    def routes(self, start, end, waypoints=None):
        return self._release().routing().route(start, end, waypoints)

    def tasks(self, payload: Mapping):
        if not isinstance(payload, Mapping):
            raise RouteInputError("Task input must be an object.")

        points = _task_points(payload.get("target_points"), minimum=2, maximum=100)
        recommended = _task_points(payload.get("recommended_coords", []), minimum=0, maximum=2000)
        name = payload.get("task_name", "")
        point_names = payload.get("target_point_names", "")
        if not isinstance(name, str) or len(name) > 256 or not isinstance(point_names, str) or len(point_names) > 8192:
            raise RouteInputError("Task name or checkpoint names are invalid.")
        active = self._release()
        if "roads" not in active.manifest["layers"]:
            raise DataUnavailableError("The active map is missing its roads layer.")
        roads = active.feature_collection("roads")["features"]
        try:
            from .task_planning import plan_task
        except ImportError as error:
            raise RoutingUnavailableError("Local task routing requires Shapely.") from error
        return plan_task(active.manifest["bounds"], roads, recommended, points, name, point_names)

    def native_route(self, payload):
        return self._release().routing().native_route(payload)


def _task_points(points, *, minimum, maximum):
    if not isinstance(points, (list, tuple)) or not minimum <= len(points) <= maximum:
        raise RouteInputError("Invalid task coordinate count.")
    validated = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(type(value) not in (int, float) for value in point)
                or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
            raise RouteInputError("Task coordinates must be finite GCJ-02 longitude and latitude.")
        validated.append(list(point))
    return validated
