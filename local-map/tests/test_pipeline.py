import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import httpx

from campus_map import pipeline


@pytest.fixture
def official_conversion(monkeypatch):
    def convert(points):
        return [[longitude + .006, latitude - .003] for longitude, latitude in points]

    monkeypatch.setattr(pipeline, "convert_nodes", convert)
    return convert


def test_overpass_json_retains_nodes_ways_relations(tmp_path):
    raw = {"elements": [{"type": "node", "id": 1, "lat": 22.53, "lon": 113.38},
                        {"type": "way", "id": 2, "nodes": [1], "tags": {"name": "A & B", "highway": "footway"}},
                        {"type": "relation", "id": 3, "members": [{"type": "way", "ref": 2, "role": "outer"}], "tags": {"type": "multipolygon"}}]}
    target = tmp_path / "map.osm"
    pipeline.overpass_to_osm(raw, target)
    text = target.read_text(encoding="utf-8")
    assert 'ref="1"' in text and 'type="way"' in text
    assert "A &amp; B" in text


def test_tile_coverage_includes_all_zoom_levels():
    coverage = pipeline.tile_coverage(14, 20)
    assert set(t.z for t in coverage) == set(range(14, 21))
    assert len(coverage) > 1000
    assert len(set(coverage)) == len(coverage)


def test_failed_build_never_replaces_current(tmp_path, monkeypatch):
    (tmp_path / "current.json").write_text('{"version":"working"}', encoding="utf-8")
    (tmp_path / "staging" / "prepared").mkdir(parents=True)
    (tmp_path / "staging" / "prepared" / "prepared.json").write_text(json.dumps(pipeline.COORDINATE_METADATA), encoding="utf-8")
    monkeypatch.setattr(pipeline, "_build_release", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("broken graph")))
    with pytest.raises(RuntimeError, match="broken graph"):
        pipeline.build(tmp_path)
    assert json.loads((tmp_path / "current.json").read_text()) == {"version": "working"}


def test_validate_rejects_missing_tile_and_corruption(tmp_path):
    release = tmp_path / "test"
    release.mkdir()
    (release / "manifest.json").write_text(json.dumps({"bounds": list(pipeline.BOUNDS), "minzoom": 14, "maxzoom": 14, "checksums": {"features/roads.geojson": "0" * 64}, **pipeline.COORDINATE_METADATA}))
    with pytest.raises(ValueError):
        pipeline.validate_release(release)


def test_imported_source_preserves_original_bytes(tmp_path, monkeypatch, official_conversion):
    from campus_map import render

    original = tmp_path / "input.osm"
    original.write_text('<osm version="0.6"><node id="1" lat="22.53" lon="113.38"/></osm>', encoding="utf-8")
    monkeypatch.setattr(render, "_assets", lambda **_: [])
    result = pipeline.prepare(tmp_path / "data", original, tile_provider="osm")
    assert Path(result["source_file"]).read_bytes() == original.read_bytes()
    assert result["sources"][0]["sha256"] == pipeline.sha256(original)
    assert result["sources"][0]["coordinate_system"] == "WGS84"
    assert result["bounds"] == pytest.approx([113.3858, 22.5225, 113.3961, 22.5325])
    assert all(result[key] == value for key, value in pipeline.COORDINATE_METADATA.items())
    calibration = json.loads((tmp_path / "data/staging/prepared/coordinate-calibration.json").read_text())
    assert calibration["columns"] == calibration["rows"] == 17
    assert len(calibration["points"]) == 289
    assert calibration["points"][0] == pytest.approx([113.3858, 22.5225])
    assert calibration["points"][-1] == pytest.approx([113.3961, 22.5325])


def test_source_network_failure_keeps_prepared_source(tmp_path, monkeypatch):
    prepared = tmp_path / "staging" / "prepared"
    prepared.mkdir(parents=True)
    (prepared / "prepared.json").write_text('{"valid":true}')
    monkeypatch.setattr(pipeline, "_fetch_source", lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        pipeline.prepare(tmp_path)
    assert json.loads((prepared / "prepared.json").read_text()) == {"valid": True}


def test_fetch_has_two_overpass_attempts_and_one_official_fallback(tmp_path, monkeypatch):
    calls = []

    def respond(request):
        calls.append((request.method, request.url.host))
        if request.url.host == "overpass-api.de":
            return httpx.Response(502, request=request)
        return httpx.Response(200, content=b'<osm version="0.6"><way id="1"/></osm>', request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(pipeline.httpx, "Client", lambda **_: client)
    target = tmp_path / "source.osm"
    result = pipeline._fetch_source(target)
    assert calls == [("POST", "overpass-api.de"), ("POST", "overpass-api.de"), ("GET", "api.openstreetmap.org")]
    assert result["fallback"] is True
    assert len(result["attempts"]) == 2
    assert target.read_bytes().startswith(b"<osm")


def test_build_assets_never_download_when_offline(tmp_path, monkeypatch):
    from campus_map import render

    monkeypatch.setattr(render, "PROJECT", tmp_path)
    monkeypatch.setattr(render.httpx, "get", lambda *a, **k: pytest.fail("Offline build attempted HTTP"))
    with pytest.raises(RuntimeError, match="run prepare while online"):
        render._assets(allow_download=False)


def test_reimport_retains_archived_upstream_provenance(tmp_path, monkeypatch, official_conversion):
    from campus_map import render

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    original = source_dir / "campus.osm"
    original.write_bytes(b'<osm version="0.6"/>')
    digest = pipeline.sha256(original)
    (source_dir / (digest[:20] + ".provenance.json")).write_text(json.dumps({"sha256": digest, "url": "https://api.openstreetmap.org/original", "query": "original bounded query"}))
    monkeypatch.setattr(render, "_assets", lambda **_: [])
    result = pipeline.prepare(tmp_path, original, tile_provider="osm")
    assert result["sources"][0]["url"] == "https://api.openstreetmap.org/original"
    assert result["sources"][0]["query"] == "original bounded query"


def test_convert_source_moves_xml_pbf_and_geojson_once(tmp_path, official_conversion):
    import osmium

    original = tmp_path / "original.osm"
    original.write_text('<osm version="0.6"><bounds minlon="113.38" minlat="22.52" maxlon="113.39" maxlat="22.54"/>'
                        '<node id="1" lat="22.53" lon="113.38"/><node id="2" lat="22.531" lon="113.381"/>'
                        '<way id="3"><nd ref="1"/><nd ref="2"/><tag k="highway" v="footway"/></way></osm>', encoding="utf-8")
    target = tmp_path / "converted"
    target.mkdir()
    pipeline._convert_source(original, target)
    root = ET.parse(target / "campus.osm").getroot()
    assert root.get("coordinate_system") == "GCJ-02"
    assert float(root.find("node").get("lon")) == pytest.approx(113.386)
    assert float(root.find("node").get("lat")) == pytest.approx(22.527)
    assert float(root.find("bounds").get("minlon")) == pytest.approx(113.386)
    nodes = []

    class NodeReader(osmium.SimpleHandler):
        def node(self, item):
            nodes.append([item.location.lon, item.location.lat])

    NodeReader().apply_file(str(target / "campus.osm.pbf"))
    assert nodes[0] == pytest.approx([113.386, 22.527])
    features = json.loads((target / "all.geojson").read_text())
    assert features["features"][0]["geometry"]["coordinates"][0] == pytest.approx(nodes[0])
    second = tmp_path / "second"
    second.mkdir()
    with pytest.raises(ValueError, match="original WGS84"):
        pipeline._convert_source(target / "campus.osm", second)


def test_build_rejects_legacy_prepared_data_before_creating_a_release(tmp_path):
    prepared = tmp_path / "staging/prepared"
    prepared.mkdir(parents=True)
    (prepared / "prepared.json").write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="GCJ-02"):
        pipeline.build(tmp_path)
    assert not (tmp_path / "builds").exists()


def test_validate_rejects_legacy_coordinate_system(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"coordinate_system": "WGS84"}), encoding="utf-8")
    with pytest.raises(ValueError, match="GCJ-02"):
        pipeline.validate_release(tmp_path)


def test_amap_prepare_and_build_use_official_extent_without_build_network(tmp_path, monkeypatch, official_conversion):
    from campus_map import amap, render

    original = tmp_path / "input.osm"
    original.write_text('<osm version="0.6"><node id="1" lat="22.53" lon="113.38"/></osm>', encoding="utf-8")
    calls = []
    monkeypatch.setattr(render, "_assets", lambda **_: pytest.fail("AMap preparation does not need rasterizer assets"))

    def prepare_tiles(cache, bounds, minzoom, maxzoom):
        calls.append((cache, bounds, minzoom, maxzoom))
        return {"sources": [amap.SOURCE]}

    monkeypatch.setattr(amap, "prepare_tiles", prepare_tiles)
    data_root = tmp_path / "data"
    prepared = pipeline.prepare(data_root, original, minzoom=14, maxzoom=14)
    assert prepared["tile_provider"] == "amap"
    assert calls == [(data_root / "amap-cache", prepared["bounds"], 14, 14)]
    monkeypatch.setattr(pipeline, "convert_nodes", lambda *_: pytest.fail("Offline build tried coordinate conversion"))
    monkeypatch.setattr(render, "render_tiles", lambda *_: pytest.fail("AMap build started the OSM rasterizer"))
    monkeypatch.setattr(pipeline, "_feature_layers", lambda *_: {"roads": {"file": "features/roads.geojson", "count": 0}})

    def build_graph(_prepared, release):
        tiles = release / "routing/tiles"
        tiles.mkdir(parents=True)
        (tiles / "test.gph").write_bytes(b"graph")
        return {}

    monkeypatch.setattr(pipeline, "_build_graph", build_graph)

    def examples(_release, _config, bounds, center):
        assert bounds == prepared["bounds"] and center == prepared["center"]
        return []

    monkeypatch.setattr(pipeline, "_route_examples", examples)
    monkeypatch.setattr(pipeline, "_coverage", lambda _prepared, _release, _minimum, _maximum, bounds: {"bounds": bounds})

    def copy_tiles(cache, release, coverage):
        assert cache == data_root / "amap-cache"
        assert set(coverage) == set(pipeline.tile_coverage(14, 14, prepared["bounds"]))
        for tile in coverage:
            target = release / f"tiles/{tile.z}/{tile.x}/{tile.y}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (256).to_bytes(4, "big") * 2)
        return {"sources": [amap.SOURCE]}

    monkeypatch.setattr(amap, "copy_tiles", copy_tiles)
    manifest = pipeline.build(data_root, minzoom=14, maxzoom=14)
    assert manifest["bounds"] == prepared["bounds"]
    assert manifest["center"] == prepared["center"]
    assert manifest["tile_provider"] == "amap"
    assert manifest["coordinate_system"] == manifest["graph_coordinate_system"] == "GCJ-02"
    assert manifest["source_coordinate_system"] == "WGS84"
    release = data_root / "builds" / manifest["version"]
    assert "coordinate-calibration.json" in manifest["checksums"]
    assert pipeline.validate_release(release) == manifest
    assert json.loads((data_root / "current.json").read_text())["version"] == manifest["version"]


def test_build_rejects_a_damaged_official_calibration_grid(tmp_path, monkeypatch, official_conversion):
    from campus_map import render

    original = tmp_path / "input.osm"
    original.write_text('<osm version="0.6"/>', encoding="utf-8")
    monkeypatch.setattr(render, "_assets", lambda **_: [])
    pipeline.prepare(tmp_path / "data", original, tile_provider="osm")
    calibration = tmp_path / "data/staging/prepared/coordinate-calibration.json"
    grid = json.loads(calibration.read_text())
    grid["points"][0] = [True, 22.5]
    calibration.write_text(json.dumps(grid), encoding="utf-8")
    monkeypatch.setattr(pipeline, "_build_graph", lambda *_: pytest.fail("Invalid coordinate grid reached graph build"))
    with pytest.raises(ValueError, match="calibration point"):
        pipeline.build(tmp_path / "data")
