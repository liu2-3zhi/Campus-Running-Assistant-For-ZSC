"""Build-time rasterization with the full upstream TileServer GL engine."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import httpx

PROJECT = Path(__file__).resolve().parents[1]
FONT = "Noto Sans CJK SC Regular"
ASSETS = {
    "sdfglyph.cjs": ("https://maplibre.org/font-maker/sdfglyph.js", "2d5cce9e20511e3e1798a696b496cfb4fb9c55cd9cceaa73fd77849e1c3d7a64", "BSD-3-Clause"),
    "sdfglyph.wasm": ("https://maplibre.org/font-maker/sdfglyph.wasm", "de2986e66201499de76f21bb3a649e1f27d7d68af21cb2616dc3a7b25bade691", "BSD-3-Clause / FreeType"),
    "NotoSansCJKsc-Regular.otf": ("https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf", "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b", "SIL Open Font License 1.1"),
    "OFL.txt": ("https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/LICENSE", "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2", "SIL Open Font License 1.1"),
    "FONT-MAKER-LICENSE.txt": ("https://raw.githubusercontent.com/maplibre/font-maker/714ccaea67d384717890a3c2c27143dfdd4189b7/LICENSE.txt", "41528f3766c7a63ac8aa3982063067f6d887244face7ae20f978ea1ae9c4ddb2", "BSD-3-Clause"),
    "FREETYPE-LICENSE.txt": ("https://raw.githubusercontent.com/freetype/freetype/VER-2-13-3/docs/FTL.TXT", "08c135755dd589039470f1fdbb400daaabaaa50d0b366d19cebff4d22986baa1", "FreeType License"),
}


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _assets(allow_download: bool = False) -> list:
    from .pipeline import sha256

    vendor = PROJECT / "tools/vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    result = []
    for name, (url, digest, license_name) in ASSETS.items():
        file = vendor / name
        if not file.exists():
            if not allow_download:
                raise RuntimeError(f"Missing local build asset {name}; run prepare while online")
            response = httpx.get(url, follow_redirects=True, timeout=90)
            response.raise_for_status()
            file.write_bytes(response.content)
        if sha256(file) != digest:
            raise ValueError(f"Pinned upstream build asset checksum mismatch: {name}")
        result.append({"name": name, "url": url, "sha256": digest, "license": license_name})
    return result


def _style(bounds, minzoom, maxzoom):
    sources = {name: {"type": "geojson", "data": f"file://{name}.geojson", "maxzoom": 20}
               for name in ("roads", "buildings", "boundary", "pois", "landuse", "water")}
    label = {"text-field": ["get", "name"], "text-font": [FONT], "text-size": 12,
             "text-max-width": 8, "text-padding": 3}
    paint = {"text-color": "#2d493f", "text-halo-color": "#fffff4", "text-halo-width": 1.5}
    layers = [
        {"id": "background", "type": "background", "paint": {"background-color": "#edf0e4"}},
        {"id": "campus", "type": "fill", "source": "boundary", "paint": {"fill-color": "#f8f6e9"}},
        {"id": "green", "type": "fill", "source": "landuse", "paint": {"fill-color": "#cbdcb4", "fill-opacity": .8}},
        {"id": "water", "type": "fill", "source": "water", "paint": {"fill-color": "#a6cfd3"}},
        {"id": "buildings", "type": "fill", "source": "buildings", "paint": {"fill-color": "#d6c9b0", "fill-outline-color": "#af9f82"}},
        {"id": "road-outline", "type": "line", "source": "roads", "layout": {"line-cap": "round", "line-join": "round"},
         "paint": {"line-color": "#d5c8ae", "line-width": ["interpolate", ["linear"], ["zoom"], 14, 2, 18, 7, 20, 15]}},
        {"id": "roads", "type": "line", "source": "roads", "layout": {"line-cap": "round", "line-join": "round"},
         "paint": {"line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 5, 20, 12]}},
        {"id": "campus-edge", "type": "line", "source": "boundary", "paint": {"line-color": "#6e8665", "line-width": 1.2, "line-dasharray": [3, 2]}},
        {"id": "building-label", "type": "symbol", "source": "buildings", "minzoom": 17, "layout": label, "paint": paint},
        {"id": "poi-label", "type": "symbol", "source": "pois", "minzoom": 16, "layout": label, "paint": paint},
        {"id": "road-label", "type": "symbol", "source": "roads", "minzoom": 16,
         "layout": {**label, "symbol-placement": "line", "text-size": 11}, "paint": paint},
    ]
    return {"version": 8, "name": "Campus OSM", "glyphs": "{fontstack}/{range}.pbf", "sources": sources, "layers": layers,
            "metadata": {"attribution": "(c) OpenStreetMap contributors; ODbL", "bounds": list(bounds), "minzoom": minzoom, "maxzoom": maxzoom}}


def render_tiles(release: Path, tiles: list, bounds, minzoom: int, maxzoom: int) -> dict:
    sources = _assets(allow_download=False)
    node = shutil.which("node")
    entry = PROJECT / "tools/node_modules/tileserver-gl/src/main.js"
    if not node or not entry.exists():
        raise RuntimeError("Install Node 24 and run npm ci --prefix tools before build")
    renderer = release / "renderer"
    renderer.mkdir(exist_ok=True)
    ranges = {0}
    for file in (release / "features").glob("*.geojson"):
        data = json.loads(file.read_text(encoding="utf-8"))
        for feature in data["features"]:
            for char in feature["properties"].get("name", ""):
                ranges.add(ord(char) // 256 * 256)
    _write(renderer / "ranges.json", sorted(ranges))
    font_dir = renderer / "fonts" / FONT
    cache = PROJECT / ".runtime/glyphs" / ASSETS["NotoSansCJKsc-Regular.otf"][1][:16]
    glyphs = subprocess.run([node, str(PROJECT / "tools/glyphs.cjs"), str(PROJECT / "tools/vendor/NotoSansCJKsc-Regular.otf"),
                             str(renderer / "ranges.json"), str(cache)], capture_output=True, text=True, timeout=600)
    (renderer / "glyphs.log").write_text(glyphs.stdout + glyphs.stderr, encoding="utf-8")
    if glyphs.returncode or not list(cache.glob("*.pbf")):
        raise RuntimeError("Official Font Maker glyph generation failed: " + glyphs.stderr[-2000:])
    font_dir.mkdir(parents=True, exist_ok=True)
    for start in ranges:
        name = f"{start}-{start+255}.pbf"
        shutil.copyfile(cache / name, font_dir / name)
    _write(renderer / "styles/campus.json", _style(bounds, minzoom, maxzoom))
    _write(renderer / "tileserver.json", {"options": {"paths": {"root": str(renderer), "styles": "styles", "fonts": "fonts", "files": str(release / "features")},
            "minRendererPoolSizes": [1], "maxRendererPoolSizes": [2], "maxScaleFactor": 1,
            "serveAllFonts": True, "frontPage": False, "allowRemoteMarkerIcons": False, "tileMargin": 8},
            "styles": {"campus": {"style": "campus.json", "tilejson": {"bounds": list(bounds), "minzoom": minzoom, "maxzoom": maxzoom}}}, "data": {}})
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log_path = renderer / "tileserver.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([node, str(entry), "--config", str(renderer / "tileserver.json"), "--bind", "127.0.0.1", "--port", str(port)],
                                   stdout=log, stderr=subprocess.STDOUT, cwd=renderer,
                                   env=dict(os.environ, UV_THREADPOOL_SIZE="4"))
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 60
            with httpx.Client(timeout=60, trust_env=False) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("TileServer GL exited during startup: " + log_path.read_text(encoding="utf-8")[-3000:])
                    try:
                        if client.get(base + "/styles/campus.json").status_code == 200: break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() > deadline: raise RuntimeError("TileServer GL startup timed out")
                    time.sleep(.25)

                def render(tile):
                    url = f"{base}/styles/campus/256/{tile.z}/{tile.x}/{tile.y}.png"
                    for attempt in range(3):
                        try:
                            response = client.get(url)
                            response.raise_for_status()
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError):
                            if attempt == 2 or process.poll() is not None: raise
                    if response.content[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("Renderer returned a non-PNG tile")
                    path = release / f"tiles/{tile.z}/{tile.x}/{tile.y}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(response.content)

                with ThreadPoolExecutor(max_workers=2) as pool:
                    for count, _ in enumerate(pool.map(render, tiles), 1):
                        if count % 100 == 0 or count == len(tiles):
                            print(f"Rendered {count}/{len(tiles)} offline raster tiles", flush=True)
        finally:
            # Only terminate the specific process created above; no process-name or port-wide cleanup.
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    if "Error handling renderer request" in log_path.read_text(encoding="utf-8"):
        raise RuntimeError("TileServer GL reported missing rendering resources; see " + str(log_path))
    shutil.copyfile(PROJECT / "tools/vendor/OFL.txt", renderer / "OFL.txt")
    shutil.copyfile(PROJECT / "tools/vendor/FONT-MAKER-LICENSE.txt", renderer / "FONT-MAKER-LICENSE.txt")
    shutil.copyfile(PROJECT / "tools/vendor/FREETYPE-LICENSE.txt", renderer / "FREETYPE-LICENSE.txt")
    shutil.copyfile(PROJECT / "tools/node_modules/tileserver-gl/LICENSE.md", renderer / "TILESERVER-GL-LICENSE.md")
    sources.append({"name": "TileServer GL", "version": "5.7.0", "license": "BSD-2-Clause", "url": "https://github.com/maptiler/tileserver-gl/tree/v5.7.0"})
    return {"sources": sources}
