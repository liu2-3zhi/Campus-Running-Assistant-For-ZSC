import json
import xml.etree.ElementTree as ET

import pytest

from campus_map.network_merge import append_footpaths


def write_osm(path, *, forbidden=False):
    root = ET.Element("osm", version="0.6", coordinate_system="GCJ-02")
    for identifier, longitude, latitude in ((1, 113.38, 22.53), (2, 113.381, 22.53), (3, 113.381, 22.531), (4, 113.382, 22.531)):
        ET.SubElement(root, "node", id=str(identifier), lon=str(longitude), lat=str(latitude))
    way = ET.SubElement(root, "way", id="10")
    for identifier in (1, 2):
        ET.SubElement(way, "nd", ref=str(identifier))
    ET.SubElement(way, "tag", k="highway", v="footway")
    if forbidden:
        restricted = ET.SubElement(root, "way", id="11")
        for identifier in (3, 4):
            ET.SubElement(restricted, "nd", ref=str(identifier))
        ET.SubElement(restricted, "tag", k="highway", v="service")
        ET.SubElement(restricted, "tag", k="access", v="no")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_geojson(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def feature(points, **properties):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": points},
            "properties": {"coordinate_system": "GCJ-02", "osm_tags": {}, **properties}}


def test_appends_real_steps_and_connects_only_same_grade_route_steps(tmp_path):
    osm = tmp_path / "campus.osm"
    write_osm(osm)
    geojson = tmp_path / "footpaths.geojson"
    write_geojson(geojson, [
        feature([[113.381, 22.53], [113.381, 22.531]], route_id="r", path_index=0, step_index=0, osm_tags={"highway": "footway"}),
        feature([[113.381, 22.531], [113.382, 22.531]], route_id="r", path_index=0, step_index=1, osm_tags={"highway": "steps"}),
    ])
    result = append_footpaths(osm, geojson)
    root = ET.parse(osm).getroot()
    ways = root.findall("way")
    assert result["ways"] == 2
    assert result["source_steps"] == 2
    assert len(ways) == 3
    assert all(any(tag.get("k") == "source" and tag.get("v") == "AMap walking API" for tag in way.findall("tag")) for way in ways[1:])
    # The first step meets the existing footway and the next step at real endpoints.
    assert result["intersection_nodes"] == 2


def test_grade_separated_paths_do_not_connect_at_crossing(tmp_path):
    osm = tmp_path / "campus.osm"
    write_osm(osm)
    geojson = tmp_path / "footpaths.geojson"
    write_geojson(geojson, [
        feature([[113.38, 22.53], [113.382, 22.531]], route_id="bridge", path_index=0, step_index=0,
                osm_tags={"highway": "footway", "bridge": "yes", "layer": "1"}),
        feature([[113.38, 22.531], [113.382, 22.53]], route_id="ground", path_index=0, step_index=0,
                osm_tags={"highway": "footway"}),
    ])
    result = append_footpaths(osm, geojson)
    assert result["intersection_nodes"] == 0


def test_rejects_non_gcj_source_and_non_linestring(tmp_path):
    osm = tmp_path / "campus.osm"
    write_osm(osm)
    geojson = tmp_path / "footpaths.geojson"
    write_geojson(geojson, [feature([[113.38, 22.53], [113.381, 22.53]], coordinate_system="WGS84")])
    with pytest.raises(ValueError, match="GCJ-02"):
        append_footpaths(osm, geojson)
    write_geojson(geojson, [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [113.38, 22.53]}, "properties": {}}])
    with pytest.raises(ValueError, match="LineStrings"):
        append_footpaths(osm, geojson)


def test_removes_supplemental_overlap_with_restricted_way(tmp_path):
    osm = tmp_path / "campus.osm"
    write_osm(osm, forbidden=True)
    geojson = tmp_path / "footpaths.geojson"
    write_geojson(geojson, [feature([[113.381, 22.531], [113.382, 22.531]], route_id="restricted", path_index=0, step_index=0)])
    result = append_footpaths(osm, geojson)
    assert result["restricted_overlaps_removed"] == 1
    assert result["ways"] == 0
