"""Bounded AMap data preparation; daily serving uses only the local cache."""

from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time
import uuid
import zlib

import httpx
import mercantile


PROJECT = Path(__file__).resolve().parents[1]
CONVERT_URL = "https://restapi.amap.com/v3/assistant/coordinate/convert"
TILE_URL = "https://webrd01.is.autonavi.com/appmaptile"
REQUEST_ORIGIN = "https://zslf.zsc.edu.cn"
REQUEST_HEADERS = {"Referer": REQUEST_ORIGIN + "/", "Origin": REQUEST_ORIGIN}
MAX_ZOOM = 18
MAX_TILES = 4096
MAX_BOUNDS_SPAN = 0.05
EMPTY_TILE_SHA256 = "b6a1668e09b04b052bbba659ec12aa45932d8db9685872139bb6b737eb6de0b4"
SOURCE = {
    "name": "AMap raster tiles",
    "url": TILE_URL,
    "request_origin": REQUEST_ORIGIN,
    "coordinate_system": "GCJ-02",
    "native_maxzoom": MAX_ZOOM,
    "attribution": "(c) AMap",
    "license": "AMap Open Platform service terms",
    "terms_url": "https://lbs.amap.com/pages/terms",
    "style": 8,
    "notes": "Undocumented raster endpoint; availability and compatibility are not guaranteed. Native maximum zoom is 18; higher web zooms overzoom the cached image.",
}
COORDINATE_SOURCE = {
    "name": "AMap official coordinate conversion",
    "url": CONVERT_URL,
    "request_origin": REQUEST_ORIGIN,
    "input_coordinate_system": "WGS84",
    "coordinate_system": "GCJ-02",
    "input_precision_decimals": 6,
}


class AMapError(RuntimeError):
    """An upstream preparation failure whose message contains no API key."""


def load_web_key(config_path: Path | None = None) -> str | None:
    configured = os.environ.get("AMAP_WEB_KEY")
    if configured:
        return configured.strip() or None
    path = Path(config_path) if config_path is not None else PROJECT / ".local-config.json"
    if not path.exists():
        return None
    try:
        configuration = json.loads(path.read_text(encoding="utf-8"))
        configured = configuration.get("amap_web_key")
    except (OSError, ValueError, AttributeError):
        raise AMapError("Cannot read the local AMap configuration.") from None
    if configured is None:
        return None
    if not isinstance(configured, str):
        raise AMapError("The local AMap web key must be a string.")
    return configured.strip() or None


def _point(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise AMapError("Coordinates must be [longitude, latitude] pairs.")
    if any(type(number) not in (int, float) or not math.isfinite(number) for number in value):
        raise AMapError("Coordinates must contain finite numbers.")
    longitude, latitude = value
    if not -180 <= longitude <= 180 or not -85.05112878 <= latitude <= 85.05112878:
        raise AMapError("Coordinates are outside the supported longitude/latitude range.")
    return [float(longitude), float(latitude)]


def _get(client, url, parameters, resource, *, sleep_retries=False):
    for attempt in range(3):
        try:
            response = client.get(url, params=parameters, headers=REQUEST_HEADERS)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            transient = status == 429 or 500 <= status < 600
            reason = f"HTTP {status}"
        except httpx.TransportError as error:
            transient = True
            reason = type(error).__name__
        except httpx.HTTPError as error:
            transient = False
            reason = type(error).__name__
        if not transient or attempt == 2:
            raise AMapError(f"AMap {resource} request failed ({reason}); retry preparation while online.") from None
        if sleep_retries:
            time.sleep(attempt + 1)


def _coordinate_key(point) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"


def _load_coordinate_cache(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
                or payload["schema_version"] != 1 or payload.get("source") != COORDINATE_SOURCE
                or not isinstance(payload.get("coordinates"), dict)):
            raise ValueError
        coordinates = payload["coordinates"]
        for key, point in coordinates.items():
            if not isinstance(key, str) or not re.fullmatch(r"-?\d+\.\d{6},-?\d+\.\d{6}", key):
                raise ValueError
            original = _point([float(number) for number in key.split(",")])
            if _coordinate_key(original) != key:
                raise ValueError
            _point(point)
        return coordinates
    except (OSError, ValueError, TypeError, KeyError, AMapError):
        raise AMapError("The local AMap coordinate cache is invalid or has a different source.") from None


def _save_coordinate_cache(path: Path | None, coordinates: dict) -> None:
    if path is None:
        return
    payload = {"schema_version": 1, "source": dict(COORDINATE_SOURCE), "coordinates": coordinates}
    try:
        _atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    except OSError:
        raise AMapError("Cannot write the local AMap coordinate cache.") from None


def convert_points(points, *, key: str | None = None, client: httpx.Client | None = None,
                   cache_path: Path | None = None) -> list[list[float]]:
    """Convert unique six-decimal GPS points, optionally saving each completed batch."""
    coordinates = [_point(point) for point in points]
    if not coordinates:
        return []
    cache = Path(cache_path) if cache_path is not None else None
    converted = _load_coordinate_cache(cache)
    coordinate_keys = [_coordinate_key(point) for point in coordinates]
    missing = list(dict.fromkeys(point_key for point_key in coordinate_keys if point_key not in converted))
    completed = len(coordinates) - sum(point_key not in converted for point_key in coordinate_keys)
    if completed:
        print(f"Reused {completed}/{len(coordinates)} cached official AMap coordinates", flush=True)
    if not missing:
        return [list(converted[point_key]) for point_key in coordinate_keys]
    api_key = key if key is not None else load_web_key()
    if not isinstance(api_key, str) or not api_key.strip():
        raise AMapError("Set AMAP_WEB_KEY or amap_web_key in .local-config.json before prepare.")
    rate_limit = client is None
    next_request_at = 0.0
    next_progress = (completed // 400 + 1) * 400
    connection = nullcontext(client) if client is not None else httpx.Client(timeout=30, trust_env=False)
    with connection as upstream:
        for start in range(0, len(missing), 40):
            batch = missing[start:start + 40]
            for attempt in range(3):
                if rate_limit:
                    delay = next_request_at - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    next_request_at = time.monotonic() + 0.5
                response = _get(upstream, CONVERT_URL, {
                    "key": api_key.strip(), "coordsys": "gps", "output": "JSON",
                    "locations": "|".join(batch),
                }, "coordinate conversion", sleep_retries=rate_limit)
                try:
                    payload = response.json()
                except ValueError:
                    raise AMapError("AMap returned invalid coordinate conversion results.") from None
                if (isinstance(payload, dict) and payload.get("status") == "0"
                        and str(payload.get("infocode")) in ("10019", "10021") and attempt < 2):
                    continue
                break
            try:
                if not isinstance(payload, dict) or payload.get("status") != "1":
                    raise ValueError
                locations = payload["locations"]
                if not isinstance(locations, str):
                    raise ValueError
                batch_result = [_point([float(number) for number in pair.split(",")]) for pair in locations.split(";")]
                if len(batch_result) != len(batch) or ("count" in payload and int(payload["count"]) != len(batch)):
                    raise ValueError
            except (ValueError, TypeError, KeyError, OverflowError, AMapError):
                raise AMapError("AMap returned invalid coordinate conversion results.") from None
            converted.update(zip(batch, batch_result))
            _save_coordinate_cache(cache, converted)
            completed = sum(point_key in converted for point_key in coordinate_keys)
            if completed >= next_progress or completed == len(coordinates):
                print(f"Converted {completed}/{len(coordinates)} coordinates with the official AMap API", flush=True)
                next_progress = (completed // 400 + 1) * 400
    return [list(converted[point_key]) for point_key in coordinate_keys]


def _validate_png(content: bytes) -> None:
    if content[:8] != b"\x89PNG\r\n\x1a\n":
        raise AMapError("AMap returned a non-PNG map tile.")
    if hashlib.sha256(content).hexdigest() == EMPTY_TILE_SHA256:
        raise AMapError("AMap returned an empty map tile; the requested zoom is unavailable.")
    offset, first, has_data = 8, True, False
    while offset + 12 <= len(content):
        size = struct.unpack_from(">I", content, offset)[0]
        chunk_end = offset + size + 12
        if chunk_end > len(content):
            break
        chunk = content[offset + 4:offset + 8]
        body = content[offset + 8:offset + 8 + size]
        checksum = struct.unpack_from(">I", content, offset + 8 + size)[0]
        if zlib.crc32(chunk + body) & 0xFFFFFFFF != checksum:
            break
        if first:
            if chunk != b"IHDR" or size != 13 or struct.unpack_from(">II", body) != (256, 256):
                raise AMapError("AMap map tiles must be 256 by 256 PNG images.")
            first = False
        elif chunk == b"IHDR":
            break
        if chunk == b"IDAT" and size:
            has_data = True
        if chunk == b"IEND":
            if size == 0 and has_data and chunk_end == len(content):
                return
            break
        offset = chunk_end
    raise AMapError("AMap returned an incomplete or damaged PNG map tile.")


def _read_tile(path: Path) -> bytes:
    try:
        content = path.read_bytes()
    except OSError:
        raise AMapError("A required cached AMap tile is missing or unreadable; run prepare.") from None
    _validate_png(content)
    return content


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _coverage(bounds, minzoom, maxzoom):
    if type(minzoom) is not int or type(maxzoom) is not int or not 0 <= minzoom <= maxzoom <= MAX_ZOOM:
        raise AMapError(f"AMap tiles require 0 <= minzoom <= maxzoom <= {MAX_ZOOM}; higher display zooms use overzoom.")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise AMapError("AMap tile bounds must be [west, south, east, north].")
    west, south = _point(bounds[:2])
    east, north = _point(bounds[2:])
    if not west < east or not south < north:
        raise AMapError("AMap tile bounds must have increasing longitude and latitude.")
    if east - west > MAX_BOUNDS_SPAN or north - south > MAX_BOUNDS_SPAN:
        raise AMapError("AMap tile preparation is limited to a local campus area.")
    tiles = list(mercantile.tiles(west, south, east, north, zooms=range(minzoom, maxzoom + 1)))
    if len(tiles) > MAX_TILES:
        raise AMapError(f"AMap tile preparation is limited to {MAX_TILES} tiles.")
    return tiles


def _tile_path(root: Path, tile) -> Path:
    try:
        x, y, z = tile.x, tile.y, tile.z
        if any(type(number) is not int for number in (x, y, z)) or not 0 <= z <= MAX_ZOOM or not 0 <= x < 2**z or not 0 <= y < 2**z:
            raise ValueError
    except (AttributeError, ValueError):
        raise AMapError("Invalid AMap XYZ tile address.") from None
    return root / str(z) / str(x) / f"{y}.png"


def prepare_tiles(cache_dir: Path, bounds, minzoom: int, maxzoom: int, *, client: httpx.Client | None = None) -> dict:
    """Download only the requested campus coverage, retaining valid cached files."""
    coverage = _coverage(bounds, minzoom, maxzoom)
    cache = Path(cache_dir)
    downloaded = cached = 0
    connection = nullcontext(client) if client is not None else httpx.Client(timeout=30, trust_env=False)
    with connection as upstream:
        for count, tile in enumerate(coverage, 1):
            path = _tile_path(cache, tile)
            reusable = False
            if path.is_file():
                try:
                    _read_tile(path)
                    cached += 1
                    reusable = True
                except AMapError:
                    pass
            if not reusable:
                response = _get(upstream, TILE_URL, {
                    "style": 8, "x": tile.x, "y": tile.y, "z": tile.z,
                    "lang": "zh_cn", "size": 1, "scale": 1,
                }, "map tile", sleep_retries=client is None)
                _validate_png(response.content)
                _atomic_write(path, response.content)
                downloaded += 1
            if count % 25 == 0 or count == len(coverage):
                print(f"Loaded {count}/{len(coverage)} offline AMap tiles", flush=True)
    metadata = {"bounds": list(bounds), "minzoom": minzoom, "maxzoom": maxzoom, "tiles": len(coverage),
                "downloaded": downloaded, "cached": cached, "coordinate_system": "GCJ-02", "sources": [dict(SOURCE)]}
    _atomic_write(cache / "amap-cache.json", (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return metadata


def copy_tiles(cache_dir: Path, release: Path, tiles) -> dict:
    """Publish an already prepared tile set without contacting upstream servers."""
    cache, destination = Path(cache_dir), Path(release) / "tiles"
    coverage = list(tiles)
    # Validate the entire coverage before writing anything into the staging release.
    for tile in coverage:
        _read_tile(_tile_path(cache, tile))
    for tile in coverage:
        _atomic_write(_tile_path(destination, tile), _read_tile(_tile_path(cache, tile)))
    return {"sources": [dict(SOURCE)]}
