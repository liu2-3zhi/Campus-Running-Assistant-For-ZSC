"""Node real GCJ-02 walking geometries without inventing connector segments."""

from collections import defaultdict
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


SOURCE = "AMap walking API"
FIRST_LOCAL_ID = 9_000_000_000_000


def _tags(element):
    return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}


def _grade(tags):
    bridge = tags.get("bridge") not in (None, "no", "false", "0")
    tunnel = tags.get("tunnel") not in (None, "no", "false", "0")
    return str(tags.get("layer", "1" if bridge else "-1" if tunnel else "0")), bridge, tunnel


def _walkable(tags):
    return bool(tags.get("highway")) and tags.get("foot") not in ("no", "private") and not (
        tags.get("access") in ("no", "private") and tags.get("foot") not in ("yes", "designated", "permissive"))


def _point_key(point):
    return round(point[0], 10), round(point[1], 10)


def _intersection_points(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [tuple(geometry.coords[0])]
    if geometry.geom_type == "LineString":
        return [tuple(geometry.coords[0]), tuple(geometry.coords[-1])]
    return [point for part in geometry.geoms for point in _intersection_points(part)]


def _lines(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [list(geometry.coords)]
    if geometry.geom_type in ("MultiLineString", "GeometryCollection"):
        return [line for part in geometry.geoms for line in _lines(part)]
    return []


def append_footpaths(osm_path: Path, geojson_path: Path) -> dict:
    tree = ET.parse(osm_path)
    root = tree.getroot()
    if root.get("coordinate_system") != "GCJ-02":
        raise ValueError("Supplementary walking paths require the GCJ-02 prepared OSM file")
    document = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        raise ValueError("Supplementary walking paths must be a GeoJSON FeatureCollection")
    nodes = {int(node.get("id")): node for node in root.findall("node")}
    coordinates = {identifier: (float(node.get("lon")), float(node.get("lat"))) for identifier, node in nodes.items()}
    latitude = sum(point[1] for point in coordinates.values()) / max(1, len(coordinates))
    scale_x, scale_y = 111_195 * math.cos(math.radians(latitude)), 111_195
    existing, forbidden = [], defaultdict(list)
    existing_keys = {}
    buckets = defaultdict(list)

    def metres(first, second):
        return math.hypot((first[0] - second[0]) * scale_x, (first[1] - second[1]) * scale_y)

    def bucket(point):
        return math.floor(point[0] * scale_x), math.floor(point[1] * scale_y)

    def remember(grade, point):
        cell = bucket(point)
        if point not in buckets[(grade, *cell)]:
            buckets[(grade, *cell)].append(point)

    for element in root.findall("way"):
        tags = _tags(element)
        if not tags.get("highway"):
            continue
        references = [int(node.get("ref")) for node in element.findall("nd")]
        if len(references) < 2 or any(reference not in coordinates for reference in references):
            continue
        points, grade = [coordinates[reference] for reference in references], _grade(tags)
        if not _walkable(tags):
            forbidden[grade].append(LineString(points))
            continue
        existing.append({"element": element, "points": points, "grade": grade})
        for reference, point in zip(references, points):
            existing_keys.setdefault((grade, _point_key(point)), reference)
            remember(grade, point)

    supplemental = []
    for feature in document["features"]:
        geometry, properties = feature.get("geometry", {}), feature.get("properties", {})
        if geometry.get("type") != "LineString":
            raise ValueError("Supplementary walking steps must be LineStrings")
        if properties.get("coordinate_system", "GCJ-02") != "GCJ-02":
            raise ValueError("Supplementary walking coordinates must be GCJ-02")
        points = geometry.get("coordinates")
        if not isinstance(points, list) or len(points) < 2 or any(
                not isinstance(point, (list, tuple)) or len(point) < 2 or
                not all(type(value) in (int, float) and math.isfinite(value) for value in point[:2])
                for point in points):
            raise ValueError("Invalid supplementary walking geometry")
        points = [tuple(point[:2]) for point in points]
        tags = {str(key): str(value) for key, value in properties.get("osm_tags", {}).items()}
        tags.update(source=SOURCE, foot="yes", access="yes", supplement="amap_walking")
        tags.setdefault("highway", "footway")
        if properties.get("road_name") or properties.get("name"):
            tags["name"] = str(properties.get("road_name") or properties["name"])
        grade = _grade(tags)
        # Only endpoints are rounded onto a real coincident vertex, never onto an arbitrary nearby edge.
        for index in (0, len(points) - 1):
            x, y = bucket(points[index])
            candidates = [candidate for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                          for candidate in buckets[(grade, x + dx, y + dy)]
                          if metres(points[index], candidate) <= 1]
            if candidates:
                points[index] = min(candidates, key=lambda candidate: metres(points[index], candidate))
            remember(grade, points[index])
        supplemental.append({"points": points, "grade": grade, "tags": tags, "properties": properties})

    aliases = {}

    def canonical(key):
        while key in aliases:
            key = aliases[key]
        return key

    routes = defaultdict(list)
    for record in supplemental:
        properties = record["properties"]
        if properties.get("route_id") is not None and type(properties.get("step_index")) is int:
            routes[(properties["route_id"], properties.get("path_index", 0))].append(record)
    for records in routes.values():
        records.sort(key=lambda record: record["properties"]["step_index"])
        for first, second in zip(records, records[1:]):
            if second["properties"]["step_index"] != first["properties"]["step_index"] + 1 or metres(first["points"][-1], second["points"][0]) > 1:
                continue
            point = first["points"][-1]
            first_key, second_key = (first["grade"], _point_key(point)), (second["grade"], _point_key(second["points"][0]))
            if first_key in existing_keys and second_key in existing_keys and existing_keys[first_key] != existing_keys[second_key]:
                continue
            second["points"][0] = point
            second_key = (second["grade"], _point_key(point))
            if canonical(first_key) != canonical(second_key):
                aliases[canonical(second_key)] = canonical(first_key)

    filtered, duplicates, clipped = [], 0, 0
    seen = set()
    for record in supplemental:
        line = LineString(record["points"])
        for restricted in forbidden[record["grade"]]:
            overlap = line.intersection(restricted)
            if overlap.length > 1e-8:
                line = line.difference(restricted)
                clipped += 1
        for points in _lines(line):
            if len(points) < 2 or len(set(points)) < 2:
                continue
            key_points = tuple(_point_key(point) for point in points)
            identity = (record["grade"], min(key_points, tuple(reversed(key_points))))
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            filtered.append({**record, "points": points})
    records = existing + filtered
    segments, segment_records, split_points = [], [], []
    for record_index, record in enumerate(records):
        for segment_index, (first, second) in enumerate(zip(record["points"], record["points"][1:])):
            if first == second:
                continue
            segments.append(LineString((first, second)))
            segment_records.append((record_index, segment_index))
            split_points.append({_point_key(first), _point_key(second)})
    index = STRtree(segments)
    intersections = set()
    for first_index, first in enumerate(segments):
        first_record = segment_records[first_index][0]
        if first_record < len(existing):
            continue
        for match in index.query(first, predicate="intersects"):
            second_index = int(match)
            second_record = segment_records[second_index][0]
            if first_index == second_index or (second_record >= len(existing) and second_index < first_index):
                continue
            if records[first_record]["grade"] != records[second_record]["grade"]:
                continue
            for point in _intersection_points(first.intersection(segments[second_index])):
                key = _point_key(point)
                split_points[first_index].add(key)
                split_points[second_index].add(key)
                intersections.add((records[first_record]["grade"], key))
    next_node = max(FIRST_LOCAL_ID, max(nodes, default=0) + 1)
    next_way = max(FIRST_LOCAL_ID, max((int(way.get("id")) for way in root.findall("way")), default=0) + 1)
    registry = {canonical(key): identifier for key, identifier in existing_keys.items()}
    added_nodes = []

    def node_id(grade, point):
        nonlocal next_node
        key = canonical((grade, _point_key(point)))
        if key not in registry:
            identifier = next_node
            next_node += 1
            registry[key] = identifier
            added_nodes.append(ET.Element("node", id=str(identifier), version="1", lon=f"{point[0]:.10f}", lat=f"{point[1]:.10f}"))
        return registry[key]

    ordered_segments = defaultdict(list)
    for segment_index, geometry in enumerate(segments):
        record_index, position = segment_records[segment_index]
        points = sorted(split_points[segment_index], key=lambda point: geometry.project(Point(point)))
        ordered_segments[record_index].append((position, points))
    added_ways = []
    for record_index, record in enumerate(records):
        references = []
        for _, points in sorted(ordered_segments[record_index]):
            for point in points:
                reference = node_id(record["grade"], point)
                if not references or reference != references[-1]:
                    references.append(reference)
        if len(references) < 2:
            continue
        if record_index < len(existing):
            element = record["element"]
            for child in list(element):
                if child.tag == "nd":
                    element.remove(child)
            for position, reference in enumerate(references):
                element.insert(position, ET.Element("nd", ref=str(reference)))
        else:
            element = ET.Element("way", id=str(next_way), version="1")
            next_way += 1
            for reference in references:
                ET.SubElement(element, "nd", ref=str(reference))
            for key, value in record["tags"].items():
                ET.SubElement(element, "tag", k=key, v=value)
            added_ways.append(element)
    for node in added_nodes:
        root.append(node)
    for way in added_ways:
        root.append(way)
    # libosmium requires nodes before ways, even when supplemented nodes were appended later.
    children = list(root)
    root[:] = sorted(children, key=lambda element: ({"bounds": 0, "node": 1, "way": 2, "relation": 3}.get(element.tag, 4), int(element.get("id", "0"))))
    tree.write(osm_path, encoding="utf-8", xml_declaration=True)
    return {"ways": len(added_ways), "nodes": len(added_nodes), "source_steps": len(supplemental),
            "deduplicated_steps": duplicates, "restricted_overlaps_removed": clipped,
            "intersection_nodes": len(intersections), "source": SOURCE, "coordinate_system": "GCJ-02"}
