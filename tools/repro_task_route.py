"""临时复现脚本：用真实任务文件复现腾讯地图路径规划缺陷。

用法: python tools/repro_task_route.py [任务json路径]
仅用于本地诊断，不属于运行时依赖。
"""

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAP_KEY = "XQBBZ-WMQEL-VYQPF-E3SA2-XDD52-4CBS7"
DEFAULT_TASK = ROOT / "tests" / "fixtures" / "map_route_task_9points.json"


def load_waypoints(task_path):
    payload = json.loads(Path(task_path).read_text(encoding="utf-8"))
    return [tuple(point) for point in payload["target_points"]], payload


def request_route(start, end, mode="walking", timeout=30):
    url = (
        f"https://apis.map.qq.com/ws/direction/v1/{mode}/"
        f"?from={urllib.parse.quote(f'{start[1]},{start[0]}')}"
        f"&to={urllib.parse.quote(f'{end[1]},{end[0]}')}"
        f"&output=json&key={MAP_KEY}"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"status": -1, "message": f"请求异常: {exc}"}


def decode_polyline(polyline):
    """与 main.py 内腾讯运行时 JS 完全一致的解码实现。"""
    if not isinstance(polyline, list) or len(polyline) < 2:
        return []
    coors = list(polyline)
    for i in range(2, len(coors)):
        coors[i] = float(coors[i - 2]) + float(coors[i]) / 1000000.0
    points = []
    for i in range(0, len(coors) - 1, 2):
        lat, lng = float(coors[i]), float(coors[i + 1])
        points.append({"lng": lng, "lat": lat})
    return points


def search_segment(start, end, retries=3):
    """复刻 JS 中 searchSegment 的行为（含 result.routes[0] 的空数组缺陷）。

    额外带限流退避：腾讯 Key 有每秒请求上限，命中时会返回缺少 result 的响应。
    """
    data = request_route(start, end)
    if isinstance(data, dict) and data.get("status") == 120 and retries > 0:
        time.sleep(1.5)
        return search_segment(start, end, retries=retries - 1)
    if not isinstance(data, dict):
        return {"error": "路线服务未返回有效数据。"}
    if data.get("status") != 0:
        return {"error": data.get("message") or f"路线服务返回状态异常：{data.get('status')}"}
    routes = (data.get("result") or {}).get("routes") or []
    first = routes[0] if routes else None
    if first is None:
        # 真实 JS 在此处抛出 TypeError("Cannot read properties of undefined"),
        # execute_js 捕获后整段规划返回 None。
        return {"error": "TypeError: Cannot read properties of undefined (reading 'polyline')"}
    points = decode_polyline(first.get("polyline"))
    if len(points) < 2:
        return {"error": "路线服务未返回可绘制的有效路径点。"}
    return {"path": points, "distance": first.get("distance")}


def distance_m(a, b):
    avg_lat = math.radians((a["lat"] + b["lat"]) / 2.0)
    dx = (a["lng"] - b["lng"]) * math.cos(avg_lat) * 111320.0
    dy = (a["lat"] - b["lat"]) * 110540.0
    return math.hypot(dx, dy)


def simulate_planning(waypoints, queue_interval_s=0.35):
    segment_count = len(waypoints) - 1
    paths = [None] * segment_count
    errors = [None] * segment_count
    details = []
    for i in range(segment_count):
        start, end = waypoints[i], waypoints[i + 1]
        info = request_route(start, end)
        routes = (info.get("result") or {}).get("routes") or []
        first = routes[0] if routes else None
        api_distance = first.get("distance") if first else None
        result = search_segment(start, end)
        if result.get("path"):
            paths[i] = result["path"]
        else:
            errors[i] = result.get("error")
        details.append(
            {
                "index": i,
                "status": info.get("status"),
                "message": info.get("message"),
                "api_distance": api_distance,
                "decoded_points": len(result.get("path") or []),
                "error": errors[i],
                "straight_line_m": distance_m(
                    {"lng": start[0], "lat": start[1]},
                    {"lng": end[0], "lat": end[1]},
                ),
            }
        )
        time.sleep(max(0.0, queue_interval_s))

    all_path = []
    for i in range(segment_count):
        path = paths[i]
        if not path:
            continue
        all_path.extend(path if i == 0 else path[1:])
    return all_path, paths, errors, details


def main():
    task_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TASK
    waypoints, payload = load_waypoints(task_path)
    from main import _complete_route_path_with_waypoint_endpoints

    print(f"任务: {payload.get('task_name')}")
    print(f"打卡点: {payload.get('target_point_names')}")
    print(f"路点数量: {len(waypoints)}")
    for index, point in enumerate(waypoints):
        print(f"  路点 {index}: {point}")

    all_path, paths, errors, details = simulate_planning(waypoints)

    print("\n分段规划结果:")
    for d in details:
        print(
            f"  段 {d['index']}: status={d['status']} api={d['api_distance']} "
            f"解码点数={d['decoded_points']} 直线距离={d['straight_line_m']:.1f}m "
            f"错误={d['error']}"
        )

    failed = [i for i, p in enumerate(paths) if not p]
    print(f"\n失败段: {failed}")

    print(f"合并后路径点数: {len(all_path)}")
    completed = _complete_route_path_with_waypoint_endpoints(list(all_path), waypoints)
    print(f"后端补点后路径点数: {len(completed)}")

    if len(completed) >= 2:
        # 判定基准：补点不得让相邻间距比原始路线最密/最疏处更差
        raw_coords = [{"lng": p["lng"], "lat": p["lat"]} for p in all_path]
        raw_max = max(
            distance_m(raw_coords[i], raw_coords[i + 1])
            for i in range(len(raw_coords) - 1)
        )
        print(f"\n原始路线最大相邻间距: {raw_max:.1f}m")

        top = sorted(
            ((distance_m(completed[i], completed[i + 1]), i) for i in range(len(completed) - 1)),
            reverse=True,
        )[:8]
        print("补点后相邻点最大间距 Top8（超过原始最大值即判定为新增直线段）:")
        new_jumps = 0
        waypoint_set = {(round(wp[0], 6), round(wp[1], 6)) for wp in waypoints}
        for dist, i in top:
            left = (round(completed[i]["lng"], 6), round(completed[i]["lat"], 6))
            right = (round(completed[i + 1]["lng"], 6), round(completed[i + 1]["lat"], 6))
            is_waypoint_pair = left in waypoint_set and right in waypoint_set
            flag = ""
            if dist > raw_max + 1.0:
                flag = "  <== 新增直线段"
                new_jumps += 1
            elif is_waypoint_pair:
                flag = "  (原路线固有长直路段)"
            print(
                f"  idx={i:4d} {dist:8.1f}m  "
                f"{completed[i]['lng']:.6f},{completed[i]['lat']:.6f} -> "
                f"{completed[i + 1]['lng']:.6f},{completed[i + 1]['lat']:.6f}{flag}"
            )
        print(
            "\n结论: "
            + ("未发现补点引入的直线段 ✔" if new_jumps == 0 else f"发现 {new_jumps} 处新增直线段 ✘")
        )

    print("\n路点是否落在补点后的路径上:")
    for index, wp in enumerate(waypoints):
        found = any(
            abs(p["lng"] - wp[0]) <= 1e-6 and abs(p["lat"] - wp[1]) <= 1e-6 for p in completed
        )
        if found:
            print(f"  路点 {index}: 已补进路径")
            continue
        nearest = min(distance_m({"lng": wp[0], "lat": wp[1]}, p) for p in completed)
        print(f"  路点 {index}: 未补进路径，但距最近路径点 {nearest:.1f}m（在吸附容差内）")


if __name__ == "__main__":
    main()
