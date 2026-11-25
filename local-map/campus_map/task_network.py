"""Connect imported footpaths to the pedestrian features of the local map."""

from dataclasses import dataclass
from itertools import pairwise

from shapely import LineString, Point, STRtree, get_coordinates


_JOIN_DISTANCE_M = 3
_WALKABLE = {
    "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link",
    "unclassified", "residential", "living_street", "service", "pedestrian", "track",
    "path", "footway", "steps", "bridleway", "road",
}
_PUBLIC = {"yes", "permissive", "designated", "official"}
_FOOT_OPTIONAL = {"trunk", "trunk_link", "cycleway"}

Coordinate = tuple[float, float]
Edge = tuple[Coordinate, Coordinate]


@dataclass(frozen=True, slots=True)
class _Segment:
    endpoints: Edge
    section: int | None
    at_grade: bool


def _walkable(tags):
    highway = tags.get("highway")
    foot = tags.get("foot")
    if foot is not None and foot not in _PUBLIC:
        return False
    if tags.get("oneway:foot") not in (None, "no", "0", "false"):
        return False
    if any(tags.get(key) not in _PUBLIC and key in tags for key in ("foot:forward", "foot:backward")):
        return False
    if foot is None and tags.get("access") not in (_PUBLIC | {None}):
        return False
    return highway in _WALKABLE or (highway in _FOOT_OPTIONAL and foot in _PUBLIC)


def _node(coordinate):
    # Millimetre keys keep independently calculated intersections identical.
    return round(float(coordinate[0]), 3), round(float(coordinate[1]), 3)


def _add_line(segments, points, section=None, at_grade=True):
    segments.extend(_Segment((first, second), section, at_grade) for first, second in pairwise(points) if first != second)


def build_task_network(roads, recommended_paths, to_xy) -> list[Edge]:
    """Return atomic metric edges, inferring crossings only for imported paths."""
    segments = []
    for feature in roads:
        tags = feature["properties"]
        if not _walkable(tags):
            continue
        geometry = feature["geometry"]
        if geometry["type"] == "LineString":
            lines = [geometry["coordinates"]]
        elif geometry["type"] == "MultiLineString":
            lines = geometry["coordinates"]
        else:
            continue
        at_grade = tags.get("layer") in (None, "0") and all(tags.get(key) in (None, "no") for key in ("bridge", "tunnel"))
        for line in lines:
            _add_line(segments, (_node(to_xy(point)) for point in line), at_grade=at_grade)

    first_task_segment = len(segments)
    open_ends = []
    for section, path in enumerate(recommended_paths):
        points = [_node(to_xy(point)) for point in path]
        first = len(segments)
        _add_line(segments, points, section)
        if len(segments) > first and points[0] != points[-1]:
            open_ends.extend(((section, points[0]), (section, points[-1])))

    if first_task_segment == len(segments):
        return list(dict.fromkeys(tuple(sorted(segment.endpoints)) for segment in segments))

    lines = [LineString(segment.endpoints) for segment in segments]
    tree = STRtree(lines)
    cuts = [set(segment.endpoints) for segment in segments]
    for index in range(first_task_segment, len(segments)):
        line = lines[index]
        for other in tree.query(line, predicate="intersects"):
            # A road crossing at a bridge/tunnel is not a junction. Shared
            # source vertices already remain joined via their node keys.
            if other >= index or not segments[other].at_grade:
                continue
            intersection = {_node(position) for position in get_coordinates(line.intersection(lines[other]))}
            cuts[index].update(intersection)
            cuts[other].update(intersection)

    joins = []
    for section, endpoint in open_ends:
        point = Point(endpoint)
        candidates = [index for index in tree.query(point, predicate="dwithin", distance=_JOIN_DISTANCE_M)
                      if segments[index].section != section and segments[index].at_grade]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda index: (lines[index].distance(point), index))
        line = lines[nearest]
        projection = _node(line.interpolate(line.project(point)).coords[0])
        cuts[nearest].add(projection)
        if endpoint != projection:
            joins.append((endpoint, projection))

    edges = dict.fromkeys(tuple(sorted(join)) for join in joins)
    for segment, points in zip(segments, cuts):
        (x, y), (end_x, end_y) = segment.endpoints
        dx, dy = end_x - x, end_y - y
        ordered = sorted(points, key=lambda point: ((point[0] - x) * dx + (point[1] - y) * dy, point))
        edges.update((tuple(sorted(edge)), None) for edge in pairwise(ordered))
    return list(edges)
