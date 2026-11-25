"""Topology of the combined pedestrian roads and imported task paths."""

from campus_map.task_network import build_task_network


def road(*coordinates, **tags):
    return {
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {"highway": "residential", **tags},
    }


def network(roads, paths):
    return set(build_task_network(roads, paths, tuple))


def test_task_and_osm_crossing_split_both_edges_at_the_same_node():
    edges = network([road((0, 0), (10, 0))], [[(5, -5), (5, 5)]])

    assert edges == {
        ((0, 0), (5, 0)),
        ((5, -5), (5, 0)),
        ((5, 0), (5, 5)),
        ((5, 0), (10, 0)),
    }


def test_only_infer_crossings_when_a_task_path_participates_and_layers_permit():
    roads = [
        road((0, 0), (10, 0)),
        road((5, -5), (5, 5)),
        road((0, 5), (10, 5), bridge="yes"),
    ]
    edges = network(roads, [[(9, 3.5), (9, 7)]])

    assert edges == {
        ((0, 0), (10, 0)),
        ((5, -5), (5, 5)),
        ((0, 5), (10, 5)),
        ((9, 3.5), (9, 7)),
    }


def test_collinear_osm_and_task_edges_are_split_and_deduplicated():
    edges = network([road((0, 0), (10, 0))], [[(15, 0), (5, 0)]])

    assert edges == {((0, 0), (5, 0)), ((5, 0), (10, 0)), ((10, 0), (15, 0))}


def test_task_endpoint_repairs_a_small_gap_to_the_nearest_segment():
    edges = network(
        [road((0, 0), (20, 0)), road((0, -0.1), (20, -0.1))],
        [[(5, 2.5), (5, 5)], [(16, 3.1), (16, 8)]],
    )

    assert edges == {
        ((0, 0), (5, 0)),
        ((5, 0), (5, 2.5)),
        ((5, 0), (20, 0)),
        ((5, 2.5), (5, 5)),
        ((0, -0.1), (20, -0.1)),
        ((16, 3.1), (16, 8)),
    }


def test_excludes_walk_prohibitions_and_allows_explicit_pedestrian_access():
    roads = [
        road((0, 0), (10, 0), highway="busway"),
        road((0, 1), (10, 1), foot="no"),
        road((0, 2), (10, 2), access="private"),
        road((0, 3), (10, 3), access="private", foot="yes"),
        road((0, 4), (10, 4), highway="steps"),
    ]

    assert network(roads, []) == {((0, 3), (10, 3)), ((0, 4), (10, 4))}
