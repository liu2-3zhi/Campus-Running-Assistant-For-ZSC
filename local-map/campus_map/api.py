"""Same-origin HTTP API and static assets for the offline campus map."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import (
    CampusMap,
    DataUnavailableError,
    RouteInputError,
    RouteNotFoundError,
    RoutingUnavailableError,
    SDK_MEDIA_TYPES,
    bounded_path,
)


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


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_name: str = Field(default="", max_length=256)
    target_point_names: str = Field(default="", max_length=8192)
    target_points: Annotated[list[Point], Field(min_length=2, max_length=100)]
    recommended_coords: Annotated[list[Point], Field(max_length=2000)] = Field(default_factory=list)


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


class TaskTarget(BaseModel):
    name: str
    coordinate: Point


class ConnectorProperties(BaseModel):
    target_index: int
    distance_m: float


class ConnectorFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Geometry
    properties: ConnectorProperties


class TaskConnectors(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[ConnectorFeature]


class TaskPaths(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[RouteFeature]


class TaskResult(BaseModel):
    coordinate_system: Literal["GCJ-02"]
    task_name: str
    target_points: list[TaskTarget]
    route: RouteFeature
    distance_m: float
    duration_s: float
    connectors: TaskConnectors
    recommended_paths: TaskPaths


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


ROUTE_ERRORS = {status: {"model": ErrorResponse} for status in (404, 422, 503)}


def create_app(data_root: Path | None = None):
    campus_map = CampusMap(data_root)
    web_root = campus_map.web_root
    app = FastAPI(title="Offline Campus Map API", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.data_root = campus_map.data_root

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
    async def invalid_request(request, _error):
        if request.url.path == "/api/v1/tasks/plan":
            message = "任务需要 2 至 100 个 target_points 和最多 2000 个 recommended_coords，坐标格式为 GCJ-02 [经度, 纬度]。"
        else:
            message = "Provide GCJ-02 [longitude, latitude] route points (at most 20 waypoints), or WGS84 GPS points for /coordinates/gps."
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": message}})

    @app.get("/healthz")
    def health():
        return campus_map.health()

    @app.get("/api/v1/map")
    def map_metadata():
        return campus_map.map_metadata()

    @app.get("/api/v1/sdk/{filename}", include_in_schema=False)
    def embedded_map_sdk(filename: str):
        try:
            path = campus_map.sdk_asset(filename)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path, media_type=SDK_MEDIA_TYPES[filename])

    @app.get("/api/v1/map-style")
    def map_style():
        manifest = campus_map.map_metadata()
        attribution = "(c) OpenStreetMap contributors"
        style = {"version": 8, "name": "Campus GCJ-02", "sources": {"campus": {
            "type": "raster", "tiles": ["/api/v1/tiles/{z}/{x}/{y}.png?v=" + manifest["version"]], "tileSize": 256,
            "bounds": manifest["bounds"], "minzoom": manifest["minzoom"], "maxzoom": manifest["maxzoom"],
            "attribution": attribution}}, "layers": [
                {"id": "background", "type": "background", "paint": {"background-color": "#f5f4ef"}},
                {"id": "campus", "type": "raster", "source": "campus"}]}
        return style

    @app.post("/api/v1/coordinates/gps", summary="将设备 GPS 换算至 GCJ-02（离线）",
              description="仅 GPS 输入采用 WGS84；服务使用准备阶段生成的本地 GCJ-02 转换校准网格。路线接口始终采用 GCJ-02。")
    def gps_coordinates(body: GpsRequest):
        if any(not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90 for point in body.points):
            raise RouteInputError("GPS coordinates must be valid WGS84 longitude and latitude.")
        calibration = campus_map.calibration()
        converted = [calibration.convert(point) for point in body.points]
        methods = [method for _, method in converted]
        return {"coordinate_system": "GCJ-02", "points": [point for point, _ in converted],
                "method": "local-calibration" if all(method == "local-calibration" for method in methods) else "local-approximation"}

    @app.get("/api/v1/features/{layer}")
    def features(layer: str):
        try:
            collection = campus_map.features(layer)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return JSONResponse(content=collection, media_type="application/geo+json")

    @app.get("/api/v1/tiles/{z}/{x}/{y}.png")
    def tiles(z: int, x: int, y: int):
        try:
            path = campus_map.tile(z, x, y)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    @app.post("/api/v1/routes", response_model=RouteResult, responses=ROUTE_ERRORS,
              summary="离线步行最短路线",
              description="GCJ-02（火星坐标）[经度, 纬度]；输入原样进入 GCJ-02 离线路网，不做逆向坐标转换。最多 20 个有序途经点，每个途经点独立分段。道路吸附上限 50 米，无法连接时返回明确错误。吸附点不代表建筑入口。")
    def routes(body: RouteRequest):
        return campus_map.routes(body.start, body.end, body.waypoints)

    @app.post("/api/v1/tasks/plan", response_model=TaskResult, responses=ROUTE_ERRORS,
              summary="离线规划校园任务",
              description="直接接受任务 JSON，按 target_points 顺序经过每个打卡点。recommended_coords 作为可步行小路，[0, 0] 分隔小路。路网未到达打卡点时，从同一可达路网上最近的位置以直线补接。")
    def tasks(body: TaskRequest):
        return campus_map.tasks(body.model_dump())

    @app.get("/valhalla/route", responses=ROUTE_ERRORS,
             description="官方 Web 的原生兼容接口。坐标与 polyline6 均为 GCJ-02；所有请求固定为步行最短路和 50 米吸附，与统一 API 共用引擎。")
    def native_route(json_query: Annotated[str, Query(alias="json", max_length=16_384)]):
        try:
            payload = json.loads(json_query, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except ValueError as error:
            raise RouteInputError("The json query must contain a valid JSON object.") from error
        return campus_map.native_route(payload)

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
            path = bounded_path(web_root, relative)
        except DataUnavailableError:
            raise HTTPException(status_code=404, detail="Unknown static resource") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Local web asset missing; run the web build")
        return FileResponse(path)

    return app
