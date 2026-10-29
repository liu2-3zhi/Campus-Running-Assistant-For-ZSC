"""Archive official walking polylines during prepare for later offline graph builds."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import time

import httpx

from . import amap


WALKING_URL = "https://restapi.amap.com/v5/direction/walking"
DEFAULT_BOUNDS = (113.38527452257, 22.522802191841, 113.395582411025, 22.532810058594)
MAX_ROUTE_DISTANCE_M = 3000
MAX_STEP_GAP_M = 5
SOURCE = {
    "name": "AMap walking API",
    "url": WALKING_URL,
    "request_origin": amap.REQUEST_ORIGIN,
    "coordinate_system": "GCJ-02",
    "license": "AMap Open Platform service terms",
    "terms_url": "https://lbs.amap.com/pages/terms",
    "documentation": "https://lbs.amap.com/api/webservice/guide/api/newroute",
}


class FootpathError(amap.AMapError):
    """The requested walking geometry could not be verified or prepared."""


def _distance(first, second):
    first_latitude, second_latitude = math.radians(first[1]), math.radians(second[1])
    latitude_delta = second_latitude - first_latitude
    longitude_delta = math.radians(second[0] - first[0])
    term = math.sin(latitude_delta / 2) ** 2 + math.cos(first_latitude) * math.cos(second_latitude) * math.sin(longitude_delta / 2) ** 2
    return 6_371_008.8 * 2 * math.asin(min(1, math.sqrt(term)))


def _bounds(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise FootpathError("Walking preparation bounds must be [west, south, east, north].")
    west, south = amap._point(value[:2])
    east, north = amap._point(value[2:])
    if not west < east or not south < north or east - west > .05 or north - south > .05:
        raise FootpathError("Walking preparation is limited to a local campus area.")
    return west, south, east, north


def _inside(point, bounds):
    west, south, east, north = bounds
    return west <= point[0] <= east and south <= point[1] <= north


def _coordinate_string(point):
    return f"{point[0]:.6f},{point[1]:.6f}"


def _request(origin, destination):
    return {"endpoint": WALKING_URL, "request_origin": amap.REQUEST_ORIGIN,
            "origin": _coordinate_string(origin), "destination": _coordinate_string(destination),
            "alternative_route": 3, "show_fields": "polyline,navi,cost", "output": "JSON"}


def _digest(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]


def _number(value):
    if isinstance(value, bool):
        raise FootpathError("AMap walking distance must be a finite nonnegative number.")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise FootpathError("AMap walking distance must be a finite nonnegative number.") from None
    if not math.isfinite(number) or number < 0:
        raise FootpathError("AMap walking distance must be a finite nonnegative number.")
    return number


def _polyline(value, bounds):
    if not isinstance(value, str) or not value or len(value) > 500_000:
        raise FootpathError("AMap walking steps must contain an explicit polyline.")
    coordinates = []
    try:
        for pair in value.split(";"):
            point = amap._point([float(number) for number in pair.split(",")])
            if not _inside(point, bounds):
                raise FootpathError("AMap walking geometry leaves the prepared campus bounds.")
            if not coordinates or coordinates[-1] != point:
                coordinates.append(point)
    except (ValueError, TypeError, amap.AMapError):
        raise FootpathError("AMap returned invalid or out-of-bounds walking geometry.") from None
    if len(coordinates) < 2:
        raise FootpathError("AMap walking steps need at least two distinct polyline points.")
    return coordinates


def _tags(step):
    navi = step.get("navi", {})
    if not isinstance(navi, dict):
        raise FootpathError("AMap walking navigation details are invalid.")
    walk_type = str(navi.get("walk_type", step.get("walk_type", "0")))
    if walk_type in ("10", "14", "15", "16", "30"):
        raise FootpathError("A non-footpath transport segment cannot be added as a walking road.")
    road_name = step.get("road_name", step.get("road", ""))
    if not isinstance(road_name, str):
        raise FootpathError("AMap walking road names are invalid.")
    tags = {"highway": "steps" if walk_type in ("8", "20") else "footway", "foot": "yes", "source": SOURCE["name"]}
    if road_name:
        tags["name"] = road_name
    if walk_type in ("4", "11", "22"):
        tags.update(bridge="yes", layer="1")
    if walk_type in ("3", "5", "23"):
        tags.update(tunnel="yes", layer="-1")
    if walk_type == "8":
        tags["conveying"] = "yes"
    if walk_type == "9":
        tags["highway"] = "elevator"
    return road_name, walk_type, tags


def _parse_response(content, request, route_id, pair_index, bounds):
    if not isinstance(content, bytes) or len(content) > 5_000_000:
        raise FootpathError("The AMap walking response is too large or invalid.")
    try:
        payload = json.loads(content)
        if not isinstance(payload, dict) or payload.get("status") != "1":
            raise ValueError
        route = payload["route"]
        if not isinstance(route, dict) or route.get("origin") != request["origin"] or route.get("destination") != request["destination"]:
            raise ValueError
        paths = route["paths"]
        if not isinstance(paths, list) or not 1 <= len(paths) <= 3 or int(payload["count"]) != len(paths):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise FootpathError("AMap returned invalid walking route results.") from None
    features, path_summaries, rejected = [], [], []
    for path_index, path in enumerate(paths):
        try:
            if not isinstance(path, dict):
                raise FootpathError("AMap walking path details are invalid.")
            path_distance = _number(path.get("distance"))
            if path_distance > MAX_ROUTE_DISTANCE_M:
                raise FootpathError("AMap walking paths must remain within 3000 metres.")
            steps = path.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 500:
                raise FootpathError("AMap walking paths must contain explicit steps.")
            previous_end, path_features, geometry_length = None, [], 0.0
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    raise FootpathError("AMap walking step details are invalid.")
                coordinates = _polyline(step.get("polyline"), bounds)
                if previous_end is not None and _distance(previous_end, coordinates[0]) > MAX_STEP_GAP_M:
                    raise FootpathError("AMap walking steps have a gap greater than five metres.")
                previous_end = coordinates[-1]
                road_name, walk_type, tags = _tags(step)
                length = sum(_distance(first, second) for first, second in zip(coordinates, coordinates[1:]))
                geometry_length += length
                path_features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {"source": SOURCE["name"], "coordinate_system": "GCJ-02", "route_id": route_id,
                        "pair_index": pair_index, "path_index": path_index, "step_index": step_index,
                        "road_name": road_name, "name": road_name, "walk_type": walk_type,
                        "instruction": step.get("instruction", ""), "distance_m": _number(step.get("step_distance", length)),
                        "geometry_length_m": length, "osm_tags": tags}})
            if geometry_length > MAX_ROUTE_DISTANCE_M:
                raise FootpathError("AMap walking geometry exceeds the local route length limit.")
            features.extend(path_features)
            path_summaries.append({"path_index": path_index, "distance_m": path_distance,
                                   "geometry_length_m": geometry_length, "steps": len(path_features)})
        except FootpathError as error:
            rejected.append({"path_index": path_index, "reason": str(error)})
    if not path_summaries:
        raise FootpathError("AMap returned no verified continuous walking polylines within the campus bounds.")
    return features, path_summaries, rejected


def _cached(raw_path, metadata_path, request, route_id, pair_index, bounds):
    if not raw_path.exists() and not metadata_path.exists():
        return None
    try:
        content = raw_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (not isinstance(metadata, dict) or metadata.get("source") != SOURCE or metadata.get("request") != request
                or not isinstance(metadata.get("retrieved_at"), str)
                or metadata.get("sha256") != hashlib.sha256(content).hexdigest()):
            raise ValueError
        parsed = _parse_response(content, request, route_id, pair_index, bounds)
        return content, metadata, parsed
    except (OSError, ValueError, TypeError, FootpathError):
        raise FootpathError("The cached AMap walking response is damaged or has a different source.") from None


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def prepare_footpaths(points, target_dir: Path, *, bounds=None, client: httpx.Client | None = None) -> dict:
    """Fetch all unordered reference-point pairs once; never call this while serving."""
    area = _bounds(DEFAULT_BOUNDS if bounds is None else bounds)
    coordinates = [amap._point(point) for point in points]
    if not 2 <= len(coordinates) <= 22:
        raise FootpathError("Walking preparation requires between 2 and 22 reference points.")
    coordinates = [list(point) for point in dict.fromkeys(tuple(float(axis) for axis in _coordinate_string(point).split(",")) for point in coordinates)]
    if len(coordinates) < 2 or not all(_inside(point, area) for point in coordinates):
        raise FootpathError("Walking reference points must be distinct GCJ-02 positions within the campus bounds.")
    pairs = list(combinations(coordinates, 2))
    if any(_distance(first, second) > MAX_ROUTE_DISTANCE_M for first, second in pairs):
        raise FootpathError("Walking reference points must be within 3000 metres of one another.")
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    features, routes, files, skipped_pairs = [], [], {}, []
    key, next_request_at, downloaded = None, 0.0, 0
    connection = nullcontext(client) if client is not None else httpx.Client(timeout=30, trust_env=False)
    with connection as upstream:
        for pair_index, (origin, destination) in enumerate(pairs):
            request = _request(origin, destination)
            digest = _digest(request)
            route_id = "amap-walking-" + digest
            raw_relative, metadata_relative = f"source/route-{digest}.json", f"source/route-{digest}.meta.json"
            raw_path, metadata_path = target / raw_relative, target / metadata_relative
            cached = _cached(raw_path, metadata_path, request, route_id, pair_index, area)
            if cached is not None:
                content, metadata, parsed = cached
            else:
                if key is None:
                    key = amap.load_web_key()
                    if not key:
                        raise FootpathError("Set AMAP_WEB_KEY or amap_web_key in .local-config.json before preparing walking paths.")
                for attempt in range(3):
                    if client is None:
                        delay = next_request_at - time.monotonic()
                        if delay > 0:
                            time.sleep(delay)
                        next_request_at = time.monotonic() + .5
                    parameters = {name: value for name, value in request.items() if name not in ("endpoint", "request_origin")}
                    parameters["key"] = key
                    response = amap._get(upstream, WALKING_URL, parameters, "walking route", sleep_retries=client is None)
                    try:
                        status = response.json()
                    except ValueError:
                        raise FootpathError("AMap returned invalid walking route results.") from None
                    if (isinstance(status, dict) and status.get("status") == "0"
                            and str(status.get("infocode")) in ("10019", "10021") and attempt < 2):
                        continue
                    break
                content = response.content
                if key.encode("utf-8") in content:
                    raise FootpathError("AMap returned unexpected credential content instead of walking geometry.")
                try:
                    parsed = _parse_response(content, request, route_id, pair_index, area)
                except FootpathError as error:
                    if str(error) == "AMap returned no verified continuous walking polylines within the campus bounds.":
                        skipped_pairs.append({"pair_index": pair_index, "origin": origin,
                                               "destination": destination, "reason": str(error)})
                        print(f"Skipped {pair_index + 1}/{len(pairs)} AMap pairs without a walkable path", flush=True)
                        continue
                    raise
                metadata = {"source": dict(SOURCE), "request": request,
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": hashlib.sha256(content).hexdigest()}
                amap._atomic_write(raw_path, content)
                amap._atomic_write(metadata_path, _json_bytes(metadata))
                downloaded += 1
            route_features, path_summaries, rejected = parsed
            features.extend(route_features)
            routes.append({"route_id": route_id, "origin": origin, "destination": destination,
                           "retrieved_at": metadata["retrieved_at"], "raw_file": raw_relative,
                           "metadata_file": metadata_relative, "paths": path_summaries, "rejected_paths": rejected})
            files[raw_relative] = metadata["sha256"]
            files[metadata_relative] = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
            print(f"Prepared {pair_index + 1}/{len(pairs)} official AMap walking pairs", flush=True)
    geojson = {"type": "FeatureCollection", "coordinate_system": "GCJ-02", "features": features}
    geojson_content = _json_bytes(geojson)
    files["footpaths.geojson"] = hashlib.sha256(geojson_content).hexdigest()
    provenance = {**SOURCE, "retrieved_at": datetime.now(timezone.utc).isoformat(), "requested_points": coordinates,
                  "pair_count": len(pairs), "path_count": sum(len(route["paths"]) for route in routes),
                  "skipped_pairs": skipped_pairs,
                  "notes": "Only archived official walking polylines between these references; campus coverage remains incomplete."}
    manifest = {"coordinate_system": "GCJ-02", "bounds": list(area), "points": coordinates,
                "pair_count": len(pairs), "feature_count": len(features), "downloaded_pairs": downloaded,
                "cached_pairs": len(pairs) - downloaded, "skipped_pairs": skipped_pairs,
                "sources": [provenance], "routes": routes, "files": files}
    amap._atomic_write(target / "footpaths.geojson", geojson_content)
    amap._atomic_write(target / "manifest.json", _json_bytes(manifest))
    return {**manifest, "geojson": str((target / "footpaths.geojson").resolve()), "manifest": str((target / "manifest.json").resolve())}
