import json
import struct
from types import SimpleNamespace
import zlib

import httpx
import mercantile
import pytest

from campus_map import amap


BOUNDS = [113.389, 22.528, 113.3891, 22.5281]


def points(count):
    return [[113.38 + index * .00001, 22.53] for index in range(count)]


def png(width=256, height=256):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    rows = b"\x00" + b"\x20\x40\x60" * width
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows * height)) + chunk(b"IEND", b""))


def test_web_key_prefers_environment_and_reads_local_config(tmp_path, monkeypatch):
    configuration = tmp_path / ".local-config.json"
    configuration.write_text(json.dumps({"amap_web_key": "config-key"}), encoding="utf-8")
    monkeypatch.delenv("AMAP_WEB_KEY", raising=False)
    assert amap.load_web_key(configuration) == "config-key"
    monkeypatch.setenv("AMAP_WEB_KEY", " environment-key ")
    assert amap.load_web_key(configuration) == "environment-key"


def test_conversion_batches_forty_points_and_uses_six_decimal_inputs():
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.params["key"] == "private-key"
        assert request.url.params["coordsys"] == "gps"
        assert request.headers["referer"] == "https://zslf.zsc.edu.cn/"
        assert request.headers["origin"] == "https://zslf.zsc.edu.cn"
        pairs = request.url.params["locations"].split("|")
        assert all(len(axis.split(".")[1]) == 6 for pair in pairs for axis in pair.split(","))
        return httpx.Response(200, json={"status": "1", "locations": ";".join("113.39,22.53" for _ in pairs)})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = amap.convert_points([[113.38456789 + index * .00001, 22.53123456] for index in range(81)], key="private-key", client=client)
    assert [len(request.url.params["locations"].split("|")) for request in calls] == [40, 40, 1]
    assert result == [[113.39, 22.53]] * 81


def test_conversion_throttles_only_its_own_client(monkeypatch):
    now, delays = [0.0], []

    def pause(delay):
        delays.append(delay)
        now[0] += delay

    def respond(request):
        count = len(request.url.params["locations"].split("|"))
        return httpx.Response(200, json={"status": "1", "locations": ";".join("113.39,22.53" for _ in range(count))})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(amap.httpx, "Client", lambda **options: client)
    monkeypatch.setattr(amap.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(amap.time, "sleep", pause)
    assert len(amap.convert_points(points(81), key="private-key")) == 81
    assert delays == [.5, .5]


@pytest.mark.parametrize("infocode", ["10019", "10021"])
def test_conversion_retries_only_transient_qps_failures(infocode, monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) < 3:
            return httpx.Response(200, json={"status": "0", "infocode": infocode, "info": "private-key"})
        return httpx.Response(200, json={"status": "1", "locations": "113.39,22.53"})

    monkeypatch.setattr(amap.time, "sleep", lambda _: pytest.fail("Injected clients must not sleep"))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert amap.convert_points([[113.38, 22.53]], key="private-key", client=client) == [[113.39, 22.53]]
    assert len(requests) == 3


@pytest.mark.parametrize("infocode,attempts", [("10019", 3), ("10021", 3), ("10001", 1)])
def test_conversion_stops_after_finite_upstream_retries(infocode, attempts):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"status": "0", "infocode": infocode, "info": "private-key"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(amap.AMapError) as failure:
            amap.convert_points([[113.38, 22.53]], key="private-key", client=client)
    assert len(requests) == attempts
    assert "private-key" not in str(failure.value)


def test_conversion_reports_progress_without_printing_the_key(capsys):
    def respond(request):
        count = len(request.url.params["locations"].split("|"))
        return httpx.Response(200, json={"status": "1", "locations": ";".join("113.39,22.53" for _ in range(count))})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        amap.convert_points(points(401), key="private-key", client=client)
    output = capsys.readouterr().out
    assert "Converted 400/401" in output and "Converted 401/401" in output
    assert "private-key" not in output


@pytest.mark.parametrize("payload", [
    {"status": "0", "info": "private-key"},
    {"status": "1", "locations": "113.39,22.53;113.4,22.54"},
    {"status": "1", "locations": "113.39,22.53", "count": "2"},
    {"status": "1", "locations": "nan,22.53"},
    {"status": "1", "locations": "113.39,inf"},
    {"status": "1", "locations": "private-key"},
    [],
])
def test_conversion_rejects_invalid_upstream_results_without_leaking_keys(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        with pytest.raises(amap.AMapError) as failure:
            amap.convert_points([[113.38, 22.53]], key="private-key", client=client)
    assert "private-key" not in str(failure.value)


def test_http_failure_does_not_include_the_key_or_request_url():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403))) as client:
        with pytest.raises(amap.AMapError) as failure:
            amap.convert_points([[113.38, 22.53]], key="private-key", client=client)
    assert "private-key" not in str(failure.value)
    assert "https://" not in str(failure.value)
    assert failure.value.__cause__ is None


@pytest.mark.parametrize("status,attempts", [(403, 1), (429, 3), (503, 3)])
def test_http_failures_have_bounded_retries_and_safe_status_messages(status, attempts, monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status)

    monkeypatch.setattr(amap.time, "sleep", lambda _: pytest.fail("Injected clients must not sleep"))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(amap.AMapError, match=f"HTTP {status}"):
            amap.convert_points(points(1), key="private-key", client=client)
    assert len(requests) == attempts


def test_transport_failures_retry_without_leaking_exception_details():
    requests = []

    def respond(request):
        requests.append(request)
        raise httpx.ConnectTimeout("private-key in the upstream URL", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(amap.AMapError, match="ConnectTimeout") as failure:
            amap.convert_points(points(1), key="private-key", client=client)
    assert len(requests) == 3
    assert "private-key" not in str(failure.value)


def test_http_retries_back_off_and_recover_with_an_owned_client(monkeypatch):
    responses = [503, 429, 200]
    delays = []

    def respond(request):
        return httpx.Response(responses.pop(0), json={"status": "1", "locations": "113.39,22.53"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(amap.httpx, "Client", lambda **options: client)
    monkeypatch.setattr(amap.time, "sleep", delays.append)
    assert amap.convert_points(points(1), key="private-key") == [[113.39, 22.53]]
    assert delays == [1, 2]


def test_coordinate_cache_deduplicates_and_can_be_reused_without_key_or_network(tmp_path, monkeypatch):
    cache = tmp_path / "coordinate-cache.json"
    requests = []

    def respond(request):
        requested = request.url.params["locations"].split("|")
        requests.extend(requested)
        return httpx.Response(200, json={"status": "1", "locations": ";".join(requested)})

    coordinates = [[113.38000001, 22.53], [113.38000002, 22.53], [113.381, 22.53]]
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = amap.convert_points(coordinates, key="private-key", client=client, cache_path=cache)
    assert requests == ["113.380000,22.530000", "113.381000,22.530000"]
    assert first == [[113.38, 22.53], [113.38, 22.53], [113.381, 22.53]]
    payload = json.loads(cache.read_text())
    assert payload["source"] == amap.COORDINATE_SOURCE
    assert "private-key" not in cache.read_text()
    monkeypatch.setattr(amap, "load_web_key", lambda: pytest.fail("Cached results must not load a key"))
    assert amap.convert_points(coordinates, client=object(), cache_path=cache) == first


def test_partial_coordinate_batches_survive_a_failure_and_resume(tmp_path):
    cache = tmp_path / "coordinate-cache.json"
    attempted = []

    def fail_second_batch(request):
        requested = request.url.params["locations"].split("|")
        attempted.append(requested)
        if len(attempted) > 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "1", "locations": ";".join(requested)})

    with httpx.Client(transport=httpx.MockTransport(fail_second_batch)) as client:
        with pytest.raises(amap.AMapError, match="HTTP 503"):
            amap.convert_points(points(81), key="private-key", client=client, cache_path=cache)
    assert len(attempted) == 4
    assert len(json.loads(cache.read_text())["coordinates"]) == 40
    resumed = []

    def finish(request):
        requested = request.url.params["locations"].split("|")
        resumed.extend(requested)
        return httpx.Response(200, json={"status": "1", "locations": ";".join(requested)})

    with httpx.Client(transport=httpx.MockTransport(finish)) as client:
        converted = amap.convert_points(points(81), key="private-key", client=client, cache_path=cache)
    assert len(converted) == 81 and len(resumed) == 41
    assert not set(resumed).intersection(attempted[0])
    assert len(json.loads(cache.read_text())["coordinates"]) == 81
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("damage", ["json", "source", "origin", "coordinate", "key", "schema"])
def test_corrupt_or_mixed_source_coordinate_cache_is_rejected_without_secrets(tmp_path, damage):
    cache = tmp_path / "coordinate-cache.json"
    payload = {"schema_version": 1, "source": dict(amap.COORDINATE_SOURCE),
               "coordinates": {"113.380000,22.530000": [113.39, 22.53]}}
    if damage == "source":
        payload["source"]["url"] = "https://other.invalid/private-key"
    elif damage == "origin":
        payload["source"]["request_origin"] = "https://other.invalid/private-key"
    elif damage == "coordinate":
        payload["coordinates"]["113.380000,22.530000"] = [float("nan"), 22.53]
    elif damage == "key":
        payload["coordinates"] = {"private-key": [113.39, 22.53]}
    elif damage == "schema":
        payload["schema_version"] = True
    cache.write_text("private-key" if damage == "json" else json.dumps(payload))
    original = cache.read_bytes()
    with pytest.raises(amap.AMapError, match="coordinate cache") as failure:
        amap.convert_points(points(1), key="private-key", client=object(), cache_path=cache)
    assert "private-key" not in str(failure.value)
    assert cache.read_bytes() == original


@pytest.mark.parametrize("point", [[True, 22.53], [113.38, float("nan")], [181, 22.53], [113.38], "113,22"])
def test_conversion_rejects_invalid_input_without_network(point):
    with pytest.raises(amap.AMapError):
        amap.convert_points([point], key="private-key", client=object())


def test_empty_conversion_does_not_require_a_key(monkeypatch):
    monkeypatch.setattr(amap, "load_web_key", lambda: pytest.fail("No key is needed"))
    assert amap.convert_points([]) == []


def test_prepare_downloads_once_and_reuses_valid_cached_tiles(tmp_path):
    requests = []
    tile_bytes = png()

    def respond(request):
        requests.append(request)
        assert request.url.host == "webrd01.is.autonavi.com"
        assert request.url.params["style"] == "8"
        assert request.headers["referer"] == "https://zslf.zsc.edu.cn/"
        assert request.headers["origin"] == "https://zslf.zsc.edu.cn"
        return httpx.Response(200, content=tile_bytes)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = amap.prepare_tiles(tmp_path, BOUNDS, 18, 18, client=client)
        second = amap.prepare_tiles(tmp_path, BOUNDS, 18, 18, client=client)
    assert first["downloaded"] == len(requests) == first["tiles"]
    assert second["downloaded"] == 0
    assert second["cached"] == first["tiles"]
    assert second["coordinate_system"] == "GCJ-02"
    assert second["sources"][0]["native_maxzoom"] == 18
    assert second["sources"][0]["request_origin"] == "https://zslf.zsc.edu.cn"
    assert json.loads((tmp_path / "amap-cache.json").read_text())["tiles"] == first["tiles"]


def test_prepare_failure_preserves_valid_cache_and_previous_metadata(tmp_path):
    tiles = list(mercantile.tiles(*BOUNDS, zooms=18))
    first = tiles[0]
    cached = tmp_path / str(first.z) / str(first.x) / f"{first.y}.png"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(png())
    (tmp_path / "amap-cache.json").write_text('{"old":true}')
    wider_bounds = [*BOUNDS[:2], BOUNDS[2] + .003, BOUNDS[3] + .003]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(502))) as client:
        with pytest.raises(amap.AMapError, match="request failed"):
            amap.prepare_tiles(tmp_path, wider_bounds, 18, 18, client=client)
    assert cached.read_bytes() == png()
    assert json.loads((tmp_path / "amap-cache.json").read_text()) == {"old": True}
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("content", [b"<html>error</html>", png(512), png()[:-5]])
def test_invalid_map_images_are_never_cached(tmp_path, content):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))) as client:
        with pytest.raises(amap.AMapError):
            amap.prepare_tiles(tmp_path, BOUNDS, 18, 18, client=client)
    assert not list(tmp_path.rglob("*.png"))
    assert not (tmp_path / "amap-cache.json").exists()


def test_known_upstream_blank_tile_is_rejected(monkeypatch):
    monkeypatch.setattr(amap, "EMPTY_TILE_SHA256", __import__("hashlib").sha256(png()).hexdigest())
    with pytest.raises(amap.AMapError, match="empty map tile"):
        amap._validate_png(png())


@pytest.mark.parametrize("bounds,minzoom,maxzoom", [
    (BOUNDS, 18, 19), (BOUNDS, 19, 18), (BOUNDS, -1, 18),
    ([113, 22, 114, 23], 18, 18), ([114, 22, 113, 23], 18, 18),
])
def test_preparation_refuses_unbounded_or_unsupported_downloads(tmp_path, bounds, minzoom, maxzoom):
    with pytest.raises(amap.AMapError):
        amap.prepare_tiles(tmp_path, bounds, minzoom, maxzoom, client=object())
    assert not list(tmp_path.iterdir())


def test_copy_tiles_is_offline_and_validates_the_entire_coverage_first(tmp_path, monkeypatch):
    cache, release = tmp_path / "cache", tmp_path / "release"
    first, missing = mercantile.Tile(1, 1, 2), mercantile.Tile(2, 1, 2)
    path = cache / "2" / "1" / "1.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(png())
    monkeypatch.setattr(amap.httpx, "Client", lambda **_: pytest.fail("Offline copy attempted HTTP"))
    with pytest.raises(amap.AMapError, match="missing"):
        amap.copy_tiles(cache, release, [first, missing])
    assert not release.exists()
    metadata = amap.copy_tiles(cache, release, [first])
    assert (release / "tiles" / "2" / "1" / "1.png").read_bytes() == png()
    assert metadata["sources"][0]["coordinate_system"] == "GCJ-02"


@pytest.mark.parametrize("tile", [SimpleNamespace(x=-1, y=0, z=18), mercantile.Tile(0, 0, 19), object()])
def test_copy_rejects_invalid_xyz_addresses(tmp_path, tile):
    with pytest.raises(amap.AMapError, match="Invalid AMap XYZ"):
        amap.copy_tiles(tmp_path, tmp_path / "release", [tile])
