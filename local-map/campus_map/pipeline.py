"""Reproducible OSM preparation and atomic offline release publication."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

import httpx
import mercantile

from .coordinates import COORDINATE_CONVERSION, COORDINATE_SYSTEM, SOURCE_COORDINATE_SYSTEM, convert_nodes, transform_bounds, wgs84_to_gcj02

SOURCE_BOUNDS = (113.3798, 22.5255, 113.3901, 22.5355)
BOUNDS = transform_bounds(SOURCE_BOUNDS)
CENTER = wgs84_to_gcj02((SOURCE_BOUNDS[0] + SOURCE_BOUNDS[2]) / 2,
                       (SOURCE_BOUNDS[1] + SOURCE_BOUNDS[3]) / 2)
COORDINATE_METADATA = {"coordinate_system": COORDINATE_SYSTEM,
                       "graph_coordinate_system": COORDINATE_SYSTEM,
                       "source_coordinate_system": SOURCE_COORDINATE_SYSTEM,
                       "coordinate_conversion": COORDINATE_CONVERSION}
PROJECT = Path(__file__).resolve().parents[1]
OSM_LICENSE = "Open Database License 1.0 (ODbL)"
OSM_ATTRIBUTION = "(c) OpenStreetMap contributors"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_gcj02(metadata: dict, resource: str) -> None:
    if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in COORDINATE_METADATA.items()):
        raise ValueError(f"{resource} must use the local GCJ-02 coordinate conversion; run prepare and build again")


def _calibration_grid(target: Path) -> None:
    columns = rows = 17
    west, south, east, north = SOURCE_BOUNDS
    points = [(west + (east - west) * column / (columns - 1), south + (north - south) * row / (rows - 1))
              for row in range(rows) for column in range(columns)]
    _json(target, {"source_bounds": list(SOURCE_BOUNDS), "columns": columns, "rows": rows,
                   "points": convert_nodes(points), **COORDINATE_METADATA})


def _validate_calibration(path: Path) -> None:
    grid = json.loads(path.read_text(encoding="utf-8"))
    _require_gcj02(grid, "Coordinate calibration")
    if grid.get("columns") != 17 or grid.get("rows") != 17 or grid.get("source_bounds") != list(SOURCE_BOUNDS):
        raise ValueError("Invalid coordinate calibration extent")
    points = grid.get("points")
    if not isinstance(points, list) or len(points) != 289:
        raise ValueError("Invalid coordinate calibration point count")
    for point in points:
        if (not isinstance(point, list) or len(point) != 2
                or not all(type(value) in (int, float) and math.isfinite(value) for value in point)
                or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
            raise ValueError("Invalid coordinate calibration point")


def overpass_to_osm(data: dict, target: Path) -> None:
    root = ET.Element("osm", version="0.6", generator="campus-offline-map / Overpass import")
    for kind in ("node", "way", "relation"):
        for item in sorted((i for i in data["elements"] if i["type"] == kind), key=lambda i: i["id"]):
            attrs = {"id": str(item["id"]), "version": str(item.get("version", 1))}
            if kind == "node":
                attrs.update(lat=str(item["lat"]), lon=str(item["lon"]))
            element = ET.SubElement(root, kind, attrs)
            for ref in item.get("nodes", []):
                ET.SubElement(element, "nd", ref=str(ref))
            for member in item.get("members", []):
                ET.SubElement(element, "member", type=member["type"], ref=str(member["ref"]), role=member.get("role", ""))
            for key, value in item.get("tags", {}).items():
                ET.SubElement(element, "tag", k=key, v=str(value))
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def _fetch_source(target: Path) -> dict:
    west, south, east, north = SOURCE_BOUNDS
    query = f"[out:xml][timeout:25];(nwr({south},{west},{north},{east});way(620224814);way(1468135556););(._;>;);out meta;"
    attempts = []
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "CampusOfflineMap/1.0 (local educational map builder)"}) as client:
        # A bounded primary request and retry, followed by one official small-map fallback.
        for _ in range(2):
            try:
                response = client.post("https://overpass-api.de/api/interpreter", data={"data": query})
                response.raise_for_status()
                if ET.fromstring(response.content).tag != "osm":
                    raise ValueError("Overpass did not return OSM XML")
                target.write_bytes(response.content)
                return {"url": str(response.url), "query": query, "method": "POST", "fallback": False, "attempts": attempts}
            except (httpx.HTTPError, ET.ParseError, ValueError) as error:
                attempts.append({"provider": "Overpass", "error": type(error).__name__})
        url = f"https://api.openstreetmap.org/api/0.6/map?bbox={west},{south},{east},{north}"
        response = client.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        if root.tag != "osm" or not root.findall("way"):
            raise ValueError("Official OSM map response contains no ways")
        target.write_bytes(response.content)
        return {"url": url, "method": "GET", "fallback": True, "attempts": attempts}


def _write_derived(xml_file: Path, target: Path) -> None:
    import osmium
    import osm2geojson

    tree = ET.parse(xml_file)
    root = tree.getroot()
    if root.tag != "osm" or root.get("coordinate_system") != COORDINATE_SYSTEM:
        raise ValueError("Derived OSM must be marked as GCJ-02")
    pbf = target / "campus.osm.pbf"
    writer = osmium.SimpleWriter(str(pbf), overwrite=True)

    class PbfCopy(osmium.SimpleHandler):
        def node(self, item): writer.add_node(item)
        def way(self, item): writer.add_way(item)
        def relation(self, item): writer.add_relation(item)

    try:
        PbfCopy().apply_file(str(xml_file))
    finally:
        writer.close()
    features = osm2geojson.xml2geojson(xml_file.read_text(encoding="utf-8"), filter_used_refs=True)
    _json(target / "all.geojson", features)


def _convert_source(source: Path, target: Path) -> dict:
    import osmium

    xml_file = target / "campus.osm"
    if source.suffix.lower() == ".json":
        overpass_to_osm(json.loads(source.read_text(encoding="utf-8")), xml_file)
    elif source.suffix.lower() == ".pbf":
        writer = osmium.SimpleWriter(str(xml_file), overwrite=True)

        class XmlCopy(osmium.SimpleHandler):
            def node(self, item): writer.add_node(item)
            def way(self, item): writer.add_way(item)
            def relation(self, item): writer.add_relation(item)

        try:
            XmlCopy().apply_file(str(source))
        finally:
            writer.close()
    else:
        shutil.copyfile(source, xml_file)
    tree = ET.parse(xml_file)
    root = tree.getroot()
    if root.tag != "osm":
        raise ValueError("Source is not an OSM document")
    if root.get("coordinate_system", SOURCE_COORDINATE_SYSTEM) != SOURCE_COORDINATE_SYSTEM:
        raise ValueError("Import the original WGS84 OSM source, not an already converted GCJ-02 file")
    nodes = root.findall("node")
    converted = convert_nodes([(float(node.attrib["lon"]), float(node.attrib["lat"])) for node in nodes])
    for node, (longitude, latitude) in zip(nodes, converted):
        node.set("lon", f"{longitude:.10f}")
        node.set("lat", f"{latitude:.10f}")
    for element in root.findall("bounds"):
        west, south, east, north = transform_bounds([float(element.attrib[key]) for key in ("minlon", "minlat", "maxlon", "maxlat")], converter=convert_nodes)
        for key, value in zip(("minlon", "minlat", "maxlon", "maxlat"), (west, south, east, north)):
            element.set(key, f"{value:.10f}")
    root.set("coordinate_system", COORDINATE_SYSTEM)
    tree.write(xml_file, encoding="utf-8", xml_declaration=True)
    _write_derived(xml_file, target)
    source_center = ((SOURCE_BOUNDS[0] + SOURCE_BOUNDS[2]) / 2, (SOURCE_BOUNDS[1] + SOURCE_BOUNDS[3]) / 2)
    return {"bounds": list(transform_bounds(SOURCE_BOUNDS, converter=convert_nodes)),
            "center": list(convert_nodes([source_center])[0]), **COORDINATE_METADATA}


def prepare(data_root: Path, source: Path | None = None, *, tile_provider: str = "osm", minzoom: int = 14, maxzoom: int = 18) -> dict:
    from .render import _assets

    if tile_provider != "osm":
        raise ValueError("The only supported tile provider is local OSM rendering")
    tile_coverage(minzoom, maxzoom)
    data_root = Path(data_root).resolve()
    stage_root = data_root / "staging"
    stage_root.mkdir(parents=True, exist_ok=True)
    work = stage_root / ("prepare-" + uuid.uuid4().hex)
    work.mkdir()
    try:
        if source is None:
            original = work / "download.osm"
            provenance = _fetch_source(original)
        else:
            original = Path(source).resolve(strict=True)
            if original.suffix.lower() not in (".osm", ".xml", ".pbf", ".json"):
                raise ValueError("Source must be OSM XML, PBF, or Overpass JSON")
            provenance = {"url": original.as_uri(), "method": "local import", "fallback": False}
        digest = sha256(original)
        source_dir = data_root / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        stored = source_dir / (digest[:20] + original.suffix.lower())
        if not stored.exists():
            shutil.copyfile(original, stored)
        previous_provenance = source_dir / (digest[:20] + ".provenance.json")
        if source is not None and previous_provenance.exists():
            recorded = json.loads(previous_provenance.read_text(encoding="utf-8"))
            if recorded.get("sha256") == digest:
                provenance = recorded
        provenance.update({"name": "OpenStreetMap", "license": OSM_LICENSE,
                           "license_url": "https://www.openstreetmap.org/copyright",
                           "attribution": OSM_ATTRIBUTION, "sha256": digest,
                           "retrieved_at": datetime.now(timezone.utc).isoformat(), "bounds": list(SOURCE_BOUNDS),
                           "coordinate_system": SOURCE_COORDINATE_SYSTEM,
                           "file": stored.relative_to(data_root).as_posix()})
        build_assets = _assets(allow_download=True) if tile_provider == "osm" else []
        conversion = _convert_source(stored, work)
        _require_gcj02(conversion, "Converted source")
        _calibration_grid(work / "coordinate-calibration.json")
        _validate_calibration(work / "coordinate-calibration.json")
        result = {"source_file": str(stored), "sources": [provenance], "build_assets": build_assets,
                  "source_bounds": list(SOURCE_BOUNDS), "tile_provider": tile_provider,
                  "tile_minzoom": minzoom, "tile_maxzoom": maxzoom, **conversion}
        _json(source_dir / (digest[:20] + ".provenance.json"), provenance)
        _json(work / "prepared.json", result)
        previous = stage_root / "prepared"
        backup = stage_root / ("previous-" + uuid.uuid4().hex)
        if previous.exists():
            previous.rename(backup)
        try:
            work.rename(previous)
        except BaseException:
            if backup.exists(): backup.rename(previous)
            raise
        if backup.exists(): shutil.rmtree(backup)
        return result
    finally:
        if work.exists(): shutil.rmtree(work)


def tile_coverage(minzoom: int, maxzoom: int, bounds=None):
    if not 0 <= minzoom <= maxzoom <= 22:
        raise ValueError("Require 0 <= minzoom <= maxzoom <= 22")
    return list(mercantile.tiles(*(bounds if bounds is not None else BOUNDS), zooms=range(minzoom, maxzoom + 1)))


def _feature_layers(prepared: Path, release: Path) -> dict:
    all_features = json.loads((prepared / "all.geojson").read_text(encoding="utf-8"))["features"]
    layers = {name: [] for name in ("roads", "buildings", "boundary", "pois", "landuse", "water")}
    for item in all_features:
        props = item.get("properties", {})
        tags = props.get("tags", {})
        geometry = item.get("geometry", {}).get("type", "")
        feature = {**item, "id": f"{props.get('type')}/{props.get('id')}",
                   "properties": {**tags, "osm_id": props.get("id"), "osm_type": props.get("type"),
                                  "name": tags.get("name:zh", tags.get("name", ""))}}
        if tags.get("highway") and "LineString" in geometry:
            layers["roads"].append(feature)
        if tags.get("building") and "Polygon" in geometry:
            layers["buildings"].append(feature)
        if (props.get("id") in (620224814, 1468135556) or tags.get("amenity") in ("university", "college")) and "Polygon" in geometry:
            layers["boundary"].append(feature)
        if "Polygon" in geometry and (tags.get("landuse") or tags.get("leisure") or tags.get("natural") in ("wood", "grassland", "scrub")):
            layers["landuse"].append(feature)
        if "Polygon" in geometry and (tags.get("natural") == "water" or tags.get("water") or tags.get("waterway")):
            layers["water"].append(feature)
        if (tags.get("name") and (tags.get("amenity") or tags.get("shop") or tags.get("tourism"))) or tags.get("entrance") or tags.get("barrier") == "gate":
            layers["pois"].append(feature)
    summary = {}
    for name, features in layers.items():
        path = release / "features" / (name + ".geojson")
        _json(path, {"type": "FeatureCollection", "features": features})
        summary[name] = {"file": path.relative_to(release).as_posix(), "count": len(features)}
    if not layers["roads"] or not layers["buildings"] or not layers["boundary"]:
        raise ValueError("Source must contain actual campus roads, buildings, and boundary polygons")
    return summary


def _build_graph(prepared: Path, release: Path) -> dict:
    import valhalla
    from valhalla._scripts import PYVALHALLA_BIN_DIR

    routing = release / "routing"
    tiles = routing / "tiles"
    tiles.mkdir(parents=True)
    config = valhalla.get_config(tile_dir=tiles, tile_extract="")
    config["mjolnir"].update({"concurrency": 2, "admin": str(routing / "admins.sqlite"),
                              "timezone": str(routing / "timezones.sqlite"), "include_driveways": True})
    config["mjolnir"].pop("tile_url", None)
    config["service_limits"]["pedestrian"]["max_locations"] = 22
    config["mjolnir"]["logging"] = {"type": "std_out", "color": False}
    config_path = routing / "valhalla.json"
    _json(config_path, config)
    env = dict(os.environ, PATH=str(PYVALHALLA_BIN_DIR) + os.pathsep + os.environ.get("PATH", ""))
    command = [sys.executable, "-m", "valhalla", "valhalla_build_tiles", "-c", str(config_path), "-j", "2", str(prepared / "campus.osm.pbf")]
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    (routing / "build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Valhalla graph build failed ({result.returncode}): {result.stderr[-1000:]}; see {routing / 'build.log'}")
    if not list(tiles.rglob("*.gph")):
        raise RuntimeError("Valhalla produced no graph tiles")
    return config


def _route_examples(release: Path, config: dict, bounds=None, center=None) -> list:
    import valhalla
    from .routing import RoutingService
    from shapely.geometry import Point, shape

    bounds = bounds if bounds is not None else BOUNDS
    center = center if center is not None else CENTER
    roads = json.loads((release / "features/roads.geojson").read_text(encoding="utf-8"))["features"]
    boundaries = json.loads((release / "features/boundary.geojson").read_text(encoding="utf-8"))["features"]
    campus = [shape(item["geometry"]) for item in boundaries]
    candidates = []
    for road in roads:
        if road["properties"].get("highway") in ("motorway", "motorway_link", "trunk", "trunk_link"):
            continue
        geometry = road["geometry"]
        lines = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for line in lines:
            for point in line[::max(1, len(line) // 3)]:
                if bounds[0] < point[0] < bounds[2] and bounds[1] < point[1] < bounds[3] and any(polygon.covers(Point(point[:2])) for polygon in campus):
                    candidates.append(point[:2])
    if len(candidates) < 4:
        raise ValueError("Insufficient campus road nodes")
    actor = valhalla.Actor(config)
    # Use real campus road vertices, and verify the same shortest/50-metre snapping contract as runtime.
    extrema = [sorted(candidates, key=lambda p: p[1]), sorted(candidates, key=lambda p: p[0])]
    middle = min(candidates, key=lambda p: (p[0] - center[0])**2 + (p[1] - center[1])**2)
    groups = [("校园南北道路步行", extrema[0], []), ("校园东西道路步行", extrema[1], []),
              ("途经校园中部道路", extrema[0], [middle])]
    result = []
    for name, ordered, via in groups:
        for i in range(min(40, len(candidates)//2)):
            start, end = ordered[i], ordered[-1-i]
            try:
                trip = actor.route(RoutingService._request([start, *via, end]))
                if isinstance(trip, str): trip = json.loads(trip)
                if trip["trip"]["summary"]["length"] < .15: continue
            except Exception:
                continue
            result.append({"id": f"campus-walk-{len(result)+1}", "name": name,
                           "description": "由已收录的真实 OSM 校园道路点生成，不代表建筑入口", "start": start, "end": end, "waypoints": via,
                           "length_km": trip["trip"]["summary"]["length"]})
            break
    if len(result) != 3:
        raise ValueError("Could not validate three pedestrian routes on the built graph")
    return result


def _coverage(prepared: Path, release: Path, minzoom: int, maxzoom: int, bounds=None) -> dict:
    from shapely.geometry import Point, shape

    bounds = bounds if bounds is not None else BOUNDS
    layers = {name: json.loads((release / f"features/{name}.geojson").read_text(encoding="utf-8"))["features"]
              for name in ("boundary", "roads", "buildings")}
    nodes = ET.parse(prepared / "campus.osm").getroot().findall("node")
    entrances = []
    gates = []
    for node in nodes:
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in node.findall("tag")}
        point = Point(float(node.attrib["lon"]), float(node.attrib["lat"]))
        if tags.get("entrance") and tags["entrance"] != "no": entrances.append(point)
        if tags.get("barrier") == "gate": gates.append(point)
    campuses = []
    for boundary in layers["boundary"]:
        polygon = shape(boundary["geometry"])
        roads = [road for road in layers["roads"] if polygon.intersects(shape(road["geometry"]))]
        campus_id = "main" if boundary["properties"]["osm_id"] == 620224814 else "north"
        campuses.append({"id": campus_id, "name": "主校区" if campus_id == "main" else "北校区",
                         "osm_id": boundary["properties"]["osm_id"], "roads": len(roads),
                         "footways": sum(road["properties"].get("highway") in ("footway", "path", "pedestrian") for road in roads),
                         "steps": sum(road["properties"].get("highway") == "steps" for road in roads),
                         "buildings": sum(polygon.intersects(shape(building["geometry"])) for building in layers["buildings"]),
                         "entrances": sum(polygon.buffer(.000001).covers(point) for point in entrances),
                         "gates": sum(polygon.buffer(.000001).covers(point) for point in gates)})
    notes = [f"{campus['name']}：OSM 收录道路 {campus['roads']} 条（步行道路 {campus['footways']}、台阶 {campus['steps']}），建筑 {campus['buildings']} 栋，entrance 标记 {campus['entrances']} 个、gate 标记 {campus['gates']} 个。" for campus in campuses]
    notes.append("OSM 内部步道和建筑入口并未完整收录；道路吸附点不代表真实入口，不保证各楼宇均可达。未补画或推断缺失道路。")
    return {"bounds": list(bounds), "coordinate_system": COORDINATE_SYSTEM, "minzoom": minzoom, "maxzoom": maxzoom,
            "tiles": len(tile_coverage(minzoom, maxzoom, bounds)), "campuses": campuses,
            "notes": notes}


def _build_release(data_root: Path, release: Path, minzoom: int, maxzoom: int) -> dict:
    from .render import render_tiles

    prepared = data_root / "staging" / "prepared"
    source_info = json.loads((prepared / "prepared.json").read_text(encoding="utf-8"))
    _require_gcj02(source_info, "Prepared data")
    bounds, center = source_info["bounds"], source_info["center"]
    tile_provider = source_info.get("tile_provider", "osm")
    _validate_calibration(prepared / "coordinate-calibration.json")
    layers = _feature_layers(prepared, release)
    config = _build_graph(prepared, release)
    examples = _route_examples(release, config, bounds, center)
    coverage = tile_coverage(minzoom, maxzoom, bounds)
    rendering = render_tiles(release, coverage, bounds, minzoom, maxzoom)
    shutil.copyfile(prepared / "coordinate-calibration.json", release / "coordinate-calibration.json")
    manifest = {"version": release.name, "name": "电子科技大学中山学院离线地图", "bounds": list(bounds), "center": list(center),
                **COORDINATE_METADATA, "source_bounds": list(SOURCE_BOUNDS),
                "tile_provider": tile_provider,
                "minzoom": minzoom, "maxzoom": maxzoom, "layers": layers,
                "coverage": _coverage(prepared, release, minzoom, maxzoom, bounds),
                "sources": source_info["sources"] + rendering["sources"], "examples": examples,
                "engines": {"routing": "Valhalla 3.9.1", "rendering": "TileServer GL 5.7.0"},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "checksums": {p.relative_to(release).as_posix(): sha256(p) for p in sorted(release.rglob("*")) if p.is_file() and p.name != "manifest.json"}}
    _json(release / "manifest.json", manifest)
    return manifest


def validate_release(release: Path) -> dict:
    release = release.resolve()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    _require_gcj02(manifest, "Map release")
    checksums = manifest.get("checksums", {})
    if not checksums: raise ValueError("No checksums")
    for name, expected in checksums.items():
        path = (release / name).resolve()
        if not path.is_relative_to(release) or not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Missing or corrupt release file: {name}")
    if not list((release / "routing/tiles").rglob("*.gph")):
        raise ValueError("Missing routing graph")
    if "coordinate-calibration.json" not in checksums:
        raise ValueError("Missing coordinate calibration")
    _validate_calibration(release / "coordinate-calibration.json")
    for tile in tile_coverage(manifest["minzoom"], manifest["maxzoom"], manifest["bounds"]):
        name = f"tiles/{tile.z}/{tile.x}/{tile.y}.png"
        path = release / name
        if name not in checksums or not path.is_file(): raise ValueError(f"Missing raster tile: {name}")
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[16:24] != (256).to_bytes(4, "big") * 2:
            raise ValueError(f"Invalid 256px PNG: {name}")
    return manifest


def build(data_root: Path, minzoom: int = 14, maxzoom: int = 18) -> dict:
    data_root = Path(data_root).resolve()
    tile_coverage(minzoom, maxzoom)
    if not (data_root / "staging/prepared/prepared.json").exists():
        raise ValueError("Run prepare before build")
    _require_gcj02(json.loads((data_root / "staging/prepared/prepared.json").read_text(encoding="utf-8")), "Prepared data")
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    release = data_root / "builds" / version
    release.mkdir(parents=True)
    # Immutable release directories may remain for diagnosis after failure; current never points at them.
    manifest = _build_release(data_root, release, minzoom, maxzoom)
    validate_release(release)
    temporary = data_root / ("current-" + uuid.uuid4().hex + ".tmp")
    _json(temporary, {"version": version})
    os.replace(temporary, data_root / "current.json")
    return manifest
