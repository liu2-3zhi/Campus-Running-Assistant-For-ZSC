"""路线补点回归测试：确保不会把打卡点搬到路径末尾形成直线段。

历史缺陷：``_complete_route_path_with_waypoint_endpoints`` 每轮都从路径末尾做
全局最近邻匹配，导致后面的打卡点被依次追加到尾部。实测 115 点主路线被补成
124 点，并出现 285.4m / 277.1m / 214.6m / 149.0m 的直线段（正好是两个打卡点
直接相连）。本测试用同一批真实打卡点与吸附路径锁死该行为。
"""

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as main_module  # noqa: E402


def _metric(a, b):
    avg_lat = math.radians((a[1] + b[1]) / 2.0)
    dx = (a[0] - b[0]) * math.cos(avg_lat) * 111320.0
    dy = (a[1] - b[1]) * 110540.0
    return math.hypot(dx, dy)


# 复现场景使用的 9 个打卡点（含首尾同坐标的重复点，用于覆盖去重逻辑）
WAYPOINTS = [
    (113.391301, 22.529941),
    (113.391996, 22.528900),
    (113.393432, 22.529986),
    (113.392730, 22.529626),
    (113.393842, 22.529502),
    (113.391335, 22.530610),
    (113.392747, 22.530308),
    (113.394130, 22.528156),
    (113.393432, 22.529986),
]

# 腾讯地图逐段规划的吸附结果（简化采样，保留真实走向与稀疏度）
ROUTE = [
    (113.391279, 22.529939),
    (113.391964, 22.530548),
    (113.391931, 22.529884),
    (113.391964, 22.529254),
    (113.392025, 22.529865),
    (113.392281, 22.530453),
    (113.392801, 22.530252),
    (113.393307, 22.529980),
    (113.393432, 22.529986),
    (113.393577, 22.529930),
    (113.393639, 22.529986),
    (113.393850, 22.529514),
    (113.393842, 22.529502),
    (113.393410, 22.529901),
    (113.392756, 22.530308),
    (113.392747, 22.530308),
    (113.393000, 22.530150),
    (113.394128, 22.528155),
    (113.394130, 22.528156),
    (113.393433, 22.529983),
]


class TestRouteWaypointEndpointMonotonic(unittest.TestCase):
    def _complete(self, route, waypoints):
        path = [{"lng": lng, "lat": lat} for lng, lat in route]
        return main_module._complete_route_path_with_waypoint_endpoints(path, waypoints)

    def test_no_straight_jump_between_raw_waypoints(self):
        """补点后不得出现「两个原始打卡点直接相连」的长直线段。"""
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        waypoint_set = set(WAYPOINTS)
        for i in range(len(coords) - 1):
            if coords[i] in waypoint_set and coords[i + 1] in waypoint_set:
                gap = _metric(coords[i], coords[i + 1])
                self.assertLessEqual(
                    gap,
                    150.0,
                    f"打卡点之间出现 {gap:.1f}m 的直线段: {coords[i]} -> {coords[i + 1]}",
                )

    def test_completed_path_keeps_all_route_points(self):
        """补点只能新增，不得删除既有路线点。"""
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        route_set = set(ROUTE)
        missing = [point for point in ROUTE if point not in coords]
        self.assertEqual(missing, [], f"以下路线点被删除: {missing}")
        self.assertGreaterEqual(len(coords), len(route_set))

    def test_completed_path_has_no_long_jumps(self):
        """补点后相邻点间距不得超过原路径的最大间距太多。"""
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        route_max = max(
            _metric(ROUTE[i], ROUTE[i + 1]) for i in range(len(ROUTE) - 1)
        )
        completed_max = max(
            _metric(coords[i], coords[i + 1]) for i in range(len(coords) - 1)
        )
        self.assertLessEqual(
            completed_max,
            route_max + 35.0,
            f"补点引入了新的长直线段: 原最大 {route_max:.1f}m -> 补点后 {completed_max:.1f}m",
        )

    def test_waypoints_are_either_present_or_already_snapped(self):
        """每个打卡点要么被补进路径，要么已有一个路线点在其吸附容差内。"""
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        for waypoint in WAYPOINTS:
            if waypoint in coords:
                continue
            nearest = min(_metric(waypoint, point) for point in coords)
            self.assertLessEqual(
                nearest,
                30.0,
                f"打卡点 {waypoint} 既未补进路径，也不在吸附容差内（最近 {nearest:.1f}m）",
            )

    def test_endpoints_are_preserved(self):
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        self.assertEqual(coords[0], WAYPOINTS[0])
        self.assertEqual(coords[-1], WAYPOINTS[-1])

    def test_duplicate_waypoints_do_not_break_alignment(self):
        """重复打卡点（首尾同坐标）不应破坏顺序对齐。"""
        completed = self._complete(ROUTE, WAYPOINTS)
        coords = [(point["lng"], point["lat"]) for point in completed]
        self.assertEqual(coords[0], WAYPOINTS[0])
        self.assertEqual(coords[-1], WAYPOINTS[-1])
        self.assertGreaterEqual(len(coords), len(ROUTE))

    def test_alignment_is_monotonic(self):
        """DP 对齐结果必须单调不减。"""
        route_points = [
            main_module._normalize_provider_route_point({"lng": lng, "lat": lat})
            for lng, lat in ROUTE
        ]
        waypoints = [
            main_module._normalize_provider_route_point(point) for point in WAYPOINTS
        ]
        aligned = main_module._align_waypoints_to_route(route_points, waypoints)
        self.assertIsNotNone(aligned)
        self.assertEqual(len(aligned), len(waypoints))
        for i in range(1, len(aligned)):
            self.assertLessEqual(aligned[i - 1], aligned[i])


if __name__ == "__main__":
    unittest.main()
