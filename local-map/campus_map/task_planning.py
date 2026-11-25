"""Plan ordered task checkpoints on the campus roads and imported footpaths."""

from collections import defaultdict
from heapq import heappop, heappush
import math

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .routing import RouteInputError, RouteNotFoundError, _distance_m
from .task_network import build_task_network


CAMPUS_METRES_PER_DEGREE = math.pi * 6_371_008.8 / 180
WALKING_SPEED_M_S = 5.04 / 3.6
CONNECTOR_PRECISION_M = 0.1
NETWORK_PRECISION_M = 0.002


def _recommended_paths(points):
    paths = []
    section = []
    for point in [*points, [0, 0]]:
        if point == [0, 0]:
            if len(section) > 1:
                paths.append(section)
            section = []
        elif not section or point != section[-1]:
            section.append(point)
    return paths


def _edge_components(edges):
    incidences = defaultdict(list)
    for index, (start, end) in enumerate(edges):
        incidences[start].append(index)
        incidences[end].append(index)
    seen = set()
    for initial in range(len(edges)):
        if initial in seen:
            continue
        seen.add(initial)
        stack, component = [initial], []
        while stack:
            index = stack.pop()
            component.append(edges[index])
            for node in edges[index]:
                for neighbor in incidences.pop(node, []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        yield component


def _select_component(edges, targets):
    # All checkpoints need to share a walkable component. Minimize the total
    # distance of their straight connections before routing along those roads.
    best_key, best = (math.inf, 0), None
    for component in _edge_components(edges):
        lines = [LineString(edge) for edge in component]
        tree = STRtree(lines)
        anchors = []
        for target, index in zip(targets, tree.nearest(targets)):
            line = lines[index]
            projected = line.interpolate(line.project(target))
            position = tuple(projected.coords[0])
            anchors.append((int(index), position, projected.distance(target)))
        key = (sum(anchor[2] for anchor in anchors), -len(component))
        if key < best_key:
            best_key, best = key, (component, anchors)
    return best


def _split_at_anchors(component, anchors):
    cuts = defaultdict(list)
    for index, position, _ in anchors:
        cuts[index].append(position)
    neighbors = defaultdict(list)
    for index, (start, end) in enumerate(component):
        points = sorted({start, end, *cuts.get(index, [])}, key=lambda point: math.dist(start, point))
        for first, second in zip(points, points[1:]):
            length = math.dist(first, second)
            neighbors[first].append((second, length))
            neighbors[second].append((first, length))
    return neighbors


def _shortest_path(neighbors, start, end):
    frontier = [(0, start)]
    best = {start: 0}
    predecessor = {}
    while frontier:
        length, node = heappop(frontier)
        if node == end:
            path = [end]
            while path[-1] != start:
                path.append(predecessor[path[-1]])
            return path[::-1]
        if length != best[node]:
            continue
        for neighbor, distance in neighbors[node]:
            candidate = length + distance
            if candidate < best.get(neighbor, math.inf):
                best[neighbor] = candidate
                predecessor[neighbor] = node
                heappush(frontier, (candidate, neighbor))
    raise RouteNotFoundError("No connected pedestrian roads for this task.")


def _line_feature(coordinates, properties):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": properties}


def plan_task(bounds, roads, recommended, targets, task_name, point_names):
    west, south, east, north = bounds
    paths = _recommended_paths(recommended)
    points = [*targets, *(point for point in recommended if point != [0, 0])]
    if any(not (west <= lon <= east and south <= lat <= north) for lon, lat in points):
        raise RouteInputError("Task coordinates must be GCJ-02 points inside the campus bounds.")

    longitude_scale = CAMPUS_METRES_PER_DEGREE * math.cos(math.radians((south + north) / 2))

    def to_xy(point):
        return ((point[0] - west) * longitude_scale, (point[1] - south) * CAMPUS_METRES_PER_DEGREE)

    def to_lon_lat(point):
        return [west + point[0] / longitude_scale, south + point[1] / CAMPUS_METRES_PER_DEGREE]

    edges = build_task_network(roads, paths, to_xy)
    if not edges:
        raise RouteNotFoundError("No pedestrian roads or usable recommended paths for this task.")
    component, anchors = _select_component(edges, [Point(to_xy(point)) for point in targets])
    neighbors = _split_at_anchors(component, anchors)
    positions = [anchor[1] for anchor in anchors]
    snaps = [to_lon_lat(position) for position in positions]
    connectors = []
    for index, (point, snapped) in enumerate(zip(targets, snaps)):
        distance = _distance_m(snapped, point)
        if distance > CONNECTOR_PRECISION_M:
            connectors.append(_line_feature([snapped, point], {"target_index": index, "distance_m": distance}))

    coordinates = [targets[0]]
    for index, (start, end) in enumerate(zip(positions, positions[1:])):
        geometry = [to_lon_lat(point) for point in _shortest_path(neighbors, start, end)]
        if len(geometry) > 1:
            first = int(_distance_m(targets[index], snaps[index]) <= NETWORK_PRECISION_M)
            last = -1 if _distance_m(targets[index + 1], snaps[index + 1]) <= NETWORK_PRECISION_M else None
            geometry = geometry[first:last]
        for point in [*geometry, targets[index + 1]]:
            if point != coordinates[-1]:
                coordinates.append(point)
    if len(coordinates) == 1:
        coordinates.append(coordinates[0])

    distance = sum(_distance_m(first, second) for first, second in zip(coordinates, coordinates[1:]))
    metrics = {"distance_m": distance, "duration_s": distance / WALKING_SPEED_M_S}
    names = point_names.split("|")
    return {
        "coordinate_system": "GCJ-02",
        "task_name": task_name.strip(),
        "target_points": [
            {"name": names[index].strip() if index < len(names) else "", "coordinate": point}
            for index, point in enumerate(targets)
        ],
        "route": _line_feature(coordinates, metrics),
        **metrics,
        "connectors": {"type": "FeatureCollection", "features": connectors},
        "recommended_paths": {
            "type": "FeatureCollection",
            "features": [_line_feature(path, {}) for path in paths],
        },
    }
