"""Same-origin HTTP API and static assets for the offline campus map."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from campus_map.routing import RouteInputError, RouteNotFoundError, RoutingService, RoutingUnavailableError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
NUMBER = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Point = Annotated[list[NUMBER], Field(min_length=2, max_length=2)]


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: Point
    end: Point
    waypoints: Annotated[list[Point], Field(max_length=20)] = Field(default_factory=list)


class GpsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: Annotated[list[Point], Field(min_length=1, max_length=40)]


class Geometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[Point]


class RouteFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Geometry
    properties: dict[str, float]


class RouteLeg(BaseModel):
    index: int
    start_index: int
    end_index: int
    distance_m: float
    duration_s: float
    geometry: Geometry


class SnappedPoint(BaseModel):
    input: Point
    snapped: Point
    offset_m: float


class RouteResult(BaseModel):
    coordinate_system: Literal["GCJ-02"] = "GCJ-02"
    route: RouteFeature
    legs: list[RouteLeg]
    distance_m: float
    duration_s: float
    snapped_points: list[SnappedPoint]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


ROUTE_ERRORS = {status: {"model": ErrorResponse} for status in (404, 422, 503)}


class DataUnavailableError(RuntimeError):
    pass


def _bounded(root, relative):
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise DataUnavailableError("Invalid data resource path.")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(part in (".", "..") for part in parts.parts):
        raise DataUnavailableError("Invalid data resource path.")
    target = (root / Path(*parts.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise DataUnavailableError("Data resource leaves the active release.")
    return target


class _Release:
    def __init__(self, root, version):
        self.root = root
        manifest_path = _bounded(root, "manifest.json")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = self.manifest
        required = {"version", "name", "bounds", "center", "minzoom", "maxzoom", "layers", "coverage", "sources", "examples", "checksums"}
        if not isinstance(manifest, dict) or not required.issubset(manifest) or manifest["version"] != version:
            raise DataUnavailableError("The active map manifest is invalid.")
        if manifest.get("coordinate_system") != "GCJ-02" or manifest.get("graph_coordinate_system") != "GCJ-02":
            raise DataUnavailableError("The active map uses an old coordinate system; run prepare and build for GCJ-02.")
        if manifest.get("source_coordinate_system") != "WGS84" or manifest.get("coordinate_conversion") != "AMap Web Service gps -> GCJ-02":
            raise DataUnavailableError("The active map has no verified AMap coordinate conversion; run prepare and build.")
        bounds = manifest["bounds"]
        if not isinstance(bounds, list) or len(bounds) != 4 or not all(type(number) in (int, float) and math.isfinite(number) for number in bounds):
            raise DataUnavailableError("The active map bounds are invalid.")
        west, south, east, north = bounds
        if not (-180 <= west < east <= 180 and -85.05112878 <= south < north <= 85.05112878):
            raise DataUnavailableError("The active map bounds are invalid.")
        minimum, maximum = manifest["minzoom"], manifest["maxzoom"]
        if type(minimum) is not int or type(maximum) is not int or not 0 <= minimum <= maximum <= 24:
            raise DataUnavailableError("The active map zoom range is invalid.")
        if not isinstance(manifest["layers"], dict) or not manifest["layers"]:
            raise DataUnavailableError("The active map layers are invalid.")
        for layer, metadata in manifest["layers"].items():
            if not isinstance(layer, str) or not IDENTIFIER.fullmatch(layer) or not isinstance(metadata, dict) or metadata.get("file") != f"features/{layer}.geojson":
                raise DataUnavailableError("The active map layer path is invalid.")
        checksums = manifest["checksums"]
        if not isinstance(checksums, dict) or not checksums:
            raise DataUnavailableError("The active map checksums are missing.")
        for relative, checksum in checksums.items():
            _bounded(root, relative)
            if not isinstance(checksum, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
                raise DataUnavailableError("The active map checksum is invalid.")
        self._routing = None
        self._routing_lock = Lock()
        self._calibration = None

    def calibration(self):
        from .gps import Calibration

        if self._calibration is None:
            try:
                document = json.loads(self.asset("coordinate-calibration.json").read_text(encoding="utf-8"))
                self._calibration = Calibration(document)
            except (ValueError, KeyError, TypeError, OSError) as error:
                raise DataUnavailableError("Local GPS calibration is unavailable; run prepare and build.") from error
        return self._calibration

    def asset(self, relative):
        path = _bounded(self.root, relative)
        checksum = self.manifest["checksums"].get(relative)
        if not checksum or not path.is_file():
            raise DataUnavailableError("A required local data file is missing; run prepare and build.")
        try:
            with path.open("rb") as handle:
                actual_checksum = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError as error:
            raise DataUnavailableError("A local data file could not be read.") from error
        if actual_checksum.lower() != checksum.lower():
            raise DataUnavailableError("A local data file is damaged; rebuild the map release.")
        return path

    def routing(self):
        with self._routing_lock:
            if self._routing is None:
                self.asset("routing/valhalla.json")
                graph_files = [relative for relative in self.manifest["checksums"] if relative.startswith("routing/tiles/") or relative == "routing/tiles.tar"]
                if not graph_files:
                    raise DataUnavailableError("The local routing graph is missing.")
                for relative in graph_files:
                    self.asset(relative)
                self._routing = RoutingService(self.root)
            return self._routing

    def contains_tile(self, z, x, y):
        if not self.manifest["minzoom"] <= z <= self.manifest["maxzoom"] or not 0 <= x < 2**z or not 0 <= y < 2**z:
            return False
        west, south, east, north = self.manifest["bounds"]
        scale = 2**z
        tile_x = lambda longitude: math.floor((longitude + 180) / 360 * scale)
        tile_y = lambda latitude: math.floor((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * scale)
        return tile_x(west) <= x <= tile_x(east) and tile_y(north) <= y <= tile_y(south)


def create_app(data_root: Path | None = None):
    root = Path(data_root if data_root is not None else PROJECT_ROOT / "data").resolve()
    web_root = PROJECT_ROOT / "web" / "dist"
    app = FastAPI(title="Offline Campus Map API", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.data_root = root
    cache, cache_lock = {}, Lock()

    def release():
        try:
            pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
            version = pointer.get("version") if isinstance(pointer, dict) else None
            if not isinstance(version, str) or not IDENTIFIER.fullmatch(version) or version in (".", ".."):
                raise DataUnavailableError("The active release pointer is invalid.")
            directory = _bounded(root, f"builds/{version}")
            manifest_stat = (directory / "manifest.json").stat()
            identity = (version, manifest_stat.st_mtime_ns, manifest_stat.st_size)
            with cache_lock:
                if cache.get("identity") != identity:
                    cache["release"] = _Release(directory, version)
                    cache["identity"] = identity
                return cache["release"]
        except (OSError, ValueError, TypeError, KeyError, DataUnavailableError) as error:
            if isinstance(error, DataUnavailableError):
                raise
            raise DataUnavailableError("Local map data is unavailable; run prepare and build.") from error

    @app.exception_handler(DataUnavailableError)
    async def data_error(_request, error):
        return JSONResponse(status_code=503, content={"error": {"code": "DATA_UNAVAILABLE", "message": str(error)}})

    @app.exception_handler(RoutingUnavailableError)
    async def routing_error(_request, error):
        return JSONResponse(status_code=503, content={"error": {"code": "ROUTING_UNAVAILABLE", "message": str(error)}})

    @app.exception_handler(RouteNotFoundError)
    async def route_not_found(_request, error):
        return JSONResponse(status_code=404, content={"error": {"code": "ROUTE_NOT_FOUND", "message": str(error)}})

    @app.exception_handler(RouteInputError)
    async def route_input(_request, error):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": str(error)}})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": "Provide GCJ-02 [longitude, latitude] route points (at most 20 waypoints), or WGS84 GPS points for /coordinates/gps."}})

    @app.get("/healthz")
    def health():
        active = release()
        active.routing()
        return {"status": "ok", "version": active.manifest["version"], "offline": True, "coordinate_system": "GCJ-02"}

    @app.get("/api/v1/map")
    def map_metadata():
        return release().manifest


    @app.get("/api/v1/map-style")
    def map_style():
        manifest = release().manifest
        attribution = "高德地图" if manifest.get("tile_provider") == "amap" else "(c) OpenStreetMap contributors"
        style = {"version": 8, "name": "Campus GCJ-02", "sources": {"campus": {
            "type": "raster", "tiles": ["/api/v1/tiles/{z}/{x}/{y}.png?v=" + manifest["version"]], "tileSize": 256,
            "bounds": manifest["bounds"], "minzoom": manifest["minzoom"], "maxzoom": manifest["maxzoom"],
            "attribution": attribution}}, "layers": [
                {"id": "background", "type": "background", "paint": {"background-color": "#f5f4ef"}},
                {"id": "campus", "type": "raster", "source": "campus"}]}
        if "footpaths" in manifest["layers"]:
            style["sources"]["footpaths"] = {"type": "geojson", "data": "/api/v1/features/footpaths?v=" + manifest["version"]}
            style["layers"].extend([
                {"id": "footpaths-outline", "type": "line", "source": "footpaths", "minzoom": 14,
                 "layout": {"line-cap": "round", "line-join": "round"}, "paint": {"line-color": "#fffaf0", "line-width": 5}},
                {"id": "footpaths", "type": "line", "source": "footpaths", "minzoom": 14,
                 "layout": {"line-cap": "round", "line-join": "round"}, "paint": {"line-color": "#cf7c13", "line-width": 2}},
            ])
        return style

    @app.post("/api/v1/coordinates/gps", summary="将设备 GPS 换算至 GCJ-02（离线）",
              description="仅 GPS 输入采用 WGS84；校园内使用准备阶段保存的高德官方转换校准网格，外部使用本地近似算法。路线接口始终采用 GCJ-02。")
    def gps_coordinates(body: GpsRequest):
        if any(not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90 for point in body.points):
            raise RouteInputError("GPS coordinates must be valid WGS84 longitude and latitude.")
        calibration = release().calibration()
        converted = [calibration.convert(point) for point in body.points]
        methods = [method for _, method in converted]
        return {"coordinate_system": "GCJ-02", "points": [point for point, _ in converted],
                "method": "amap-calibration" if all(method == "amap-calibration" for method in methods) else "local-approximation"}

    @app.get("/api/v1/features/{layer}")
    def features(layer: str):
        active = release()
        if layer not in active.manifest["layers"]:
            raise HTTPException(status_code=404, detail="Unknown map layer")
        path = active.asset(active.manifest["layers"][layer]["file"])
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
                raise ValueError("Invalid FeatureCollection")
        except (OSError, ValueError) as error:
            raise DataUnavailableError("A local feature layer is damaged.") from error
        return JSONResponse(content=document, media_type="application/geo+json")

    @app.get("/api/v1/tiles/{z}/{x}/{y}.png")
    def tiles(z: int, x: int, y: int):
        active = release()
        relative = f"tiles/{z}/{x}/{y}.png"
        if not active.contains_tile(z, x, y):
            raise HTTPException(status_code=404, detail="Tile outside map coverage")
        path = active.asset(relative)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    @app.post("/api/v1/routes", response_model=RouteResult, responses=ROUTE_ERRORS,
              summary="离线步行最短路线",
              description="GCJ-02（火星坐标）[经度, 纬度]；输入原样进入 GCJ-02 离线路网，不做逆向坐标转换。最多 20 个有序途经点，每个途经点独立分段。道路吸附上限 50 米，无法连接时返回明确错误。吸附点不代表建筑入口。")
    def routes(body: RouteRequest):
        return release().routing().route(body.start, body.end, body.waypoints)

    @app.get("/valhalla/route", responses=ROUTE_ERRORS,
             description="官方 Web 的原生兼容接口。坐标与 polyline6 均为 GCJ-02；所有请求固定为步行最短路和 50 米吸附，与统一 API 共用引擎。")
    def native_route(json_query: Annotated[str, Query(alias="json", max_length=16_384)]):
        try:
            payload = json.loads(json_query, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except ValueError as error:
            raise RouteInputError("The json query must contain a valid JSON object.") from error
        return release().routing().native_route(payload)

    @app.get("/docs", include_in_schema=False)
    def docs():
        vendor = web_root / "static" / "vendor" / "swagger"
        if (vendor / "swagger-ui-bundle.js").is_file() and (vendor / "swagger-ui.css").is_file():
            return get_swagger_ui_html(openapi_url="/openapi.json", title="Local Campus Map API", swagger_js_url="/static/vendor/swagger/swagger-ui-bundle.js", swagger_css_url="/static/vendor/swagger/swagger-ui.css", swagger_favicon_url="/favicon.ico")
        return HTMLResponse("""<!doctype html><html lang="en"><meta charset="utf-8"><title>Local Campus Map API</title>
<style>body{max-width:900px;margin:3rem auto;padding:1rem;font:17px sans-serif}textarea{width:100%;height:8rem}pre{white-space:pre-wrap}button{padding:.7rem}</style>
<h1>Local Campus Map API</h1><p>Interactive local API documentation. <a href="/openapi.json">OpenAPI schema</a></p>
<p>GET /api/v1/map, /api/v1/features/{layer}, /api/v1/tiles/{z}/{x}/{y}.png and /healthz.</p>
<h2>POST /api/v1/routes</h2><p>GCJ-02 [longitude, latitude], up to 20 waypoints. Use /api/v1/map examples.</p>
<textarea id="body">{"start":[113.389,22.527],"end":[113.390,22.528],"waypoints":[]}</textarea><button id="run">Try route</button><pre id="result"></pre>
<script>document.getElementById('run').onclick=async()=>{let output=document.getElementById('result');try{let response=await fetch('/api/v1/routes',{method:'POST',headers:{'Content-Type':'application/json'},body:document.getElementById('body').value});output.textContent=response.status+' '+JSON.stringify(await response.json(),null,2)}catch(error){output.textContent=String(error)}};</script></html>""")

    @app.get("/{resource_path:path}", include_in_schema=False)
    def static(resource_path: str):
        if resource_path.startswith(("api/", "valhalla/")):
            raise HTTPException(status_code=404, detail="Unknown API endpoint")
        relative = resource_path or "index.html"
        try:
            path = _bounded(web_root, relative)
        except DataUnavailableError:
            raise HTTPException(status_code=404, detail="Unknown static resource") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Local web asset missing; run the web build")
        return FileResponse(path)

    return app
