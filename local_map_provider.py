"""HTTP client for the configured campus map service."""

import hashlib
import json
import secrets
from threading import Lock
from time import monotonic

import requests
from flask import Response, abort, request


# MapLibre 5.15.0 from local-map/web/package-lock.json. Never relay unchecked
# executable bytes from a configured service onto the application's origin.
SDK_ASSETS = {
    "maplibre-gl-csp.js": ("application/javascript", "7921d93722ed56359a9e838203f09d27843bc665f7d825b9e772e50c2423018f"),
    "maplibre-gl-csp-worker.js": ("application/javascript", "e058a262b0a0475e2c11697b696a356315bc997614b229ccd44c420287b30d29"),
    "maplibre-gl.css": ("text/css", "1dae8925ee5906e442f0fd7028dded2884381b9acd7a780e5270025e09fc7c5e"),
}
JSON_TYPE = "application/json"
RESOURCE_CONTEXT_TTL_S = 6 * 3600
RESOURCE_CONTEXT_LIMIT = 64


def fetch_local_map(origin, path, *, body=None, content_type=JSON_TYPE):
    """Fetch a fixed service path without forwarding browser state or redirects."""
    with requests.Session() as session:
        session.trust_env = False
        with session.request(
            "GET" if body is None else "POST", origin + path,
            json=body, timeout=(3, 10), allow_redirects=False, stream=True,
        ) as response:
            status = response.status_code
            if status != 200 and (content_type != JSON_TYPE or status not in {404, 422, 503}):
                return status, None
            actual_type = response.headers.get("Content-Type", "").partition(";")[0].strip().lower()
            valid_types = {content_type, "text/javascript"} if content_type == "application/javascript" else {content_type}
            if actual_type not in valid_types:
                raise ValueError("Invalid local map content type")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4 * 1024 * 1024:
                    raise ValueError("Local map response is too large")
            return status, json.loads(data) if content_type == JSON_TYPE else bytes(data)


def plan_local_map_route(origin, waypoints, recommended_coords):
    if not isinstance(waypoints, (list, tuple)) or not 2 <= len(waypoints) <= 100:
        return {"error": "校园离线地图需要 2 至 100 个有序坐标。"}
    if recommended_coords is None:
        endpoint = "/api/v1/routes"
        body = {"start": waypoints[0], "end": waypoints[-1], "waypoints": waypoints[1:-1]}
    else:
        endpoint = "/api/v1/tasks/plan"
        body = {"target_points": waypoints, "recommended_coords": recommended_coords}
    try:
        status, data = fetch_local_map(origin, endpoint, body=body)
        if status != 200:
            messages = {404: "校园离线路网无法连接所需打卡点。", 422: "打卡点超出校园地图范围或坐标无效。"}
            return {"error": messages.get(status, "校园离线地图服务暂不可用。"), "http_status": status}
        if data["coordinate_system"] != "GCJ-02":
            raise ValueError("Invalid local map coordinate system")
        if endpoint == "/api/v1/routes":
            path = []
            legs = data["legs"]
            if len(legs) != len(waypoints) - 1:
                raise ValueError("Invalid local map leg count")
            for start, leg, end in zip(waypoints, legs, waypoints[1:]):
                geometry = leg["geometry"]
                if geometry["type"] != "LineString" or not geometry["coordinates"]:
                    raise ValueError("Invalid local map geometry")
                for point in [start, *geometry["coordinates"], end]:
                    if not path or tuple(point) != tuple(path[-1]):
                        path.append(point)
        else:
            geometry = data["route"]["geometry"]
            if geometry["type"] != "LineString":
                raise ValueError("Invalid local map geometry")
            path = geometry["coordinates"]
        if not isinstance(path, list) or len(path) < 2:
            raise ValueError("Invalid local map path")
        return {"path": path}
    except requests.RequestException:
        return {"error": "无法连接校园离线地图服务。"}
    except (KeyError, TypeError, ValueError):
        return {"error": "校园离线地图返回了无效的路线数据。"}


def register_local_map_asset_routes(app, load_selected_origin, load_candidate_origin=None):
    contexts = {}
    context_lock = Lock()

    def issue_resource_context(origin):
        with context_lock:
            now = monotonic()
            token = None
            for existing_token, (existing_origin, expires_at) in list(contexts.items()):
                if expires_at <= now:
                    del contexts[existing_token]
                elif origin == existing_origin:
                    token = existing_token
            if token is None:
                token = secrets.token_urlsafe(18)
                if len(contexts) >= RESOURCE_CONTEXT_LIMIT:
                    del contexts[next(iter(contexts))]
            else:
                del contexts[token]
            contexts[token] = (origin, now + RESOURCE_CONTEXT_TTL_S)
            return token

    def resource_origin(token):
        with context_lock:
            context = contexts.get(token)
            if context is None:
                return None
            origin, expires_at = context
            if expires_at <= monotonic():
                del contexts[token]
                return None
            return origin

    def fetch_asset(origin, path, content_type=JSON_TYPE):
        if not origin:
            abort(404)
        try:
            status, data = fetch_local_map(origin, path, content_type=content_type)
        except (requests.RequestException, ValueError):
            abort(502)
        if status != 200 or data is None:
            abort(404 if status == 404 else 502)
        return data

    def asset_origin():
        config_id = request.args.get("config_id")
        if config_id is None:
            return load_selected_origin()
        return load_candidate_origin(config_id) if load_candidate_origin is not None else None

    @app.get("/api/local-map/map")
    def campus_map_metadata():
        origin = asset_origin()
        data = fetch_asset(origin, "/api/v1/map")
        fields = ("coordinate_system", "bounds", "center", "minzoom", "maxzoom", "version")
        if not isinstance(data, dict) or not all(field in data for field in fields) or data["coordinate_system"] != "GCJ-02":
            abort(502)
        metadata = {field: data[field] for field in fields}
        metadata["resource_context"] = issue_resource_context(origin)
        return metadata, {"Cache-Control": "no-store"}

    @app.get("/api/local-map/tiles/<int:z>/<int:x>/<int:y>.png")
    def campus_map_tile(z, x, y):
        if z > 24 or x >= 2**z or y >= 2**z:
            abort(404)
        origin = resource_origin(request.args.get("context"))
        data = fetch_asset(origin, f"/api/v1/tiles/{z}/{x}/{y}.png", "image/png")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            abort(502)
        return Response(data, mimetype="image/png", headers={"Cache-Control": "private, max-age=300"})

    @app.get("/api/local-map/sdk/<filename>")
    def campus_map_sdk(filename):
        asset = SDK_ASSETS.get(filename)
        if not asset:
            abort(404)
        content_type, digest = asset
        data = fetch_asset(asset_origin(), f"/api/v1/sdk/{filename}", content_type)
        if hashlib.sha256(data).hexdigest() != digest:
            abort(502)
        return Response(data, mimetype=content_type, headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        })
