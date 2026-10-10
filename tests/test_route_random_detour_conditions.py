"""折返补距行为测试：距终点 50 m 起折返、条件随机选点、精确收尾、回退策略。

覆盖 ``Api._build_route_path_with_random_detours`` 的约束：
1. 折返起点沿用既有语义（total_len - 50，路线 < 100 m 时取 2/3）。
2. 条件随机：候选必须同时满足最小距离与不越过目标距离，且不连续重复。
3. 输出累计长度恰好等于目标距离（保证不超时）。
4. 所有打卡点都不符合条件时，回退到道路网络上距折返点 > 100 m 的点。
"""

import math
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import api_runtime  # noqa: E402
from api_runtime import Api  # noqa: E402


def _make_runtime():
    runtime = Api.__new__(Api)
    runtime.params = {}
    runtime.log = lambda *args, **kwargs: None
    return runtime


def _straight_geometry(start, end, steps=12):
    """用直线几何模拟地图服务返回的道路路径（测试中不需要真实路网）。"""
    return [
        (
            start[0] + (end[0] - start[0]) * i / steps,
            start[1] + (end[1] - start[1]) * i / steps,
        )
        for i in range(steps + 1)
    ]


def _path_length(runtime, path):
    total = 0.0
    for i in range(len(path) - 1):
        total += runtime._calculate_distance_m(
            path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]
        )
    return total


class _RoutePlannerStub:
    """替身：按直线几何返回路线，并记录每次规划请求。"""

    def __init__(self, fail_pairs=()):
        self.calls = []
        self.fail_pairs = {tuple(pair) for pair in fail_pairs}

    def __call__(self, session_id, waypoints, **kwargs):
        waypoints = list(waypoints)
        key = (tuple(waypoints[0]), tuple(waypoints[-1]))
        self.calls.append({"waypoints": waypoints, "guard_label": kwargs.get("guard_label")})
        if key in self.fail_pairs:
            return {"error": "路线服务未返回可绘制的有效路径点。"}
        geometry = _straight_geometry(key[0], key[1])
        return {"path": [{"lng": p[0], "lat": p[1]} for p in geometry], "provider": "stub"}


class TestRouteRandomDetourConditions(unittest.TestCase):
    def setUp(self):
        api_runtime._DETOUR_LEG_CACHE.clear()
        self.runtime = _make_runtime()

    def _build(self, waypoints, base_path, target_dist_m, planner):
        with mock.patch.object(
            api_runtime._main(), "_plan_route_path_with_provider_runtime", planner, create=True
        ), mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            return self.runtime._build_route_path_with_random_detours(
                base_path,
                waypoints,
                target_dist_m,
                session_id="session-test",
                python_params={},
                guard_label="TestDetour",
            )

    def test_returns_base_path_when_distance_already_sufficient(self):
        base = [(113.39 + i * 0.0001, 22.53) for i in range(40)]
        waypoints = [(113.39, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        result = self._build(waypoints, base, 10.0, planner)
        self.assertEqual(result, base)
        self.assertEqual(planner.calls, [])

    def test_detour_starts_fifty_meters_before_route_end(self):
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        self.assertGreater(total, 100.0)
        waypoints = [(113.39, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        logs = []
        with mock.patch.object(
            api_runtime._main(), "_plan_route_path_with_provider_runtime", planner, create=True
        ), mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            result = self.runtime._build_route_path_with_random_detours(
                base,
                waypoints,
                total + 120.0,
                session_id="session-test",
                python_params={},
                guard_label="TestDetour",
                log_func=logs.append,
            )

        # 折返点应为 base 上累计里程最接近 total-50 的点
        cumulative = 0.0
        best_gap = float("inf")
        expected_idx = 0
        for i in range(len(base)):
            if i > 0:
                cumulative += self.runtime._calculate_distance_m(
                    base[i - 1][0], base[i - 1][1], base[i][0], base[i][1]
                )
            gap = abs(cumulative - (total - 50.0))
            if gap < best_gap:
                best_gap = gap
                expected_idx = i
        self.assertEqual(result[: expected_idx + 1], base[: expected_idx + 1])
        # 折返点应落在「距终点 50 m」附近（受路网点距限制，允许一个点距的误差）
        self.assertLessEqual(best_gap, 12.0)
        # 日志必须明确折返起点在距终点 50 m 处
        self.assertTrue(any("从距终点" in entry for entry in logs))

    def test_detour_turn_point_is_before_route_end(self):
        """折返不得发生在路线终点之后（即不在末端原地横跳）。"""
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [(113.39, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        result = self._build(waypoints, base, total + 120.0, planner)
        turn_prefix = 0
        for i, point in enumerate(result):
            if i < len(base) and point == base[i]:
                turn_prefix = i
            else:
                break
        self.assertLess(turn_prefix, len(base) - 1)

    def test_output_length_never_exceeds_target_distance(self):
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [(113.39, 22.53), (113.3915, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        target = total + 150.0
        result = self._build(waypoints, base, target, planner)
        length = _path_length(self.runtime, result)
        # 不能超时：长度绝不超过目标距离
        self.assertLessEqual(length, target + 0.5)
        # 满足最小距离：应显著长于主路线
        self.assertGreater(length, total)

    def test_output_length_tracks_target_within_tolerance(self):
        """额度充裕时（往返能整圈放进预算），长度应贴合目标距离。"""
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [(113.39, 22.53), (113.3915, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        target = total + 400.0
        result = self._build(waypoints, base, target, planner)
        length = _path_length(self.runtime, result)
        self.assertLessEqual(length, target + 0.5)
        self.assertGreater(length, target * 0.95)

    def test_output_ends_at_last_waypoint_when_detour_round_completes(self):
        """折返整圈完成后末点必须落在最后一个打卡点附近。"""
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        dest = (113.393, 22.53)
        waypoints = [(113.39, 22.53), (113.3915, 22.53), dest]
        planner = _RoutePlannerStub()
        result = self._build(waypoints, base, total + 400.0, planner)
        gap = self.runtime._calculate_distance_m(
            result[-1][0], result[-1][1], dest[0], dest[1]
        )
        # 主路线的最后一个打卡点已包含在路径中
        self.assertTrue(
            any(
                abs(p[0] - dest[0]) < 1e-9 and abs(p[1] - dest[1]) < 1e-9
                for p in result
            ),
            "最后一个打卡点必须出现在路径中",
        )
        self.assertLessEqual(gap, 150.0)
        self.assertLessEqual(_path_length(self.runtime, result), total + 400.0 + 0.5)
        self.assertGreater(_path_length(self.runtime, result), total)

    def test_detour_legs_are_planned_on_road_network(self):
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [(113.39, 22.53), (113.3915, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub()
        self._build(waypoints, base, total + 200.0, planner)
        self.assertTrue(planner.calls, "折返必须通过道路规划获取几何")
        for call in planner.calls:
            self.assertEqual(len(call["waypoints"]), 2)
            self.assertIn("Detour", call["guard_label"])

    def test_candidate_distance_below_minimum_falls_back(self):
        # 只有一个打卡点且紧贴折返点 -> 不满足最小距离 -> 回退到道路网络上前方点
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        turn_point = base[0]
        waypoints = [turn_point, (turn_point[0] + 1e-6, turn_point[1])]
        planner = _RoutePlannerStub()
        result = self._build(waypoints, base, total + 40.0, planner)
        self.assertGreater(_path_length(self.runtime, result), total)
        self.assertAlmostEqual(_path_length(self.runtime, result), total + 40.0, delta=0.5)

    def test_empty_candidate_pool_uses_loop_fallback(self):
        # 打卡点无法规划（模拟服务不可达）-> 走整圈循环兜底
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [(113.39, 22.53), (113.393, 22.53)]
        planner = _RoutePlannerStub(
            fail_pairs=[((113.39, 22.53), (113.393, 22.53))]
        )
        result = self._build(waypoints, base, total + 120.0, planner)
        self.assertAlmostEqual(_path_length(self.runtime, result), total + 120.0, delta=1.0)

    def test_detour_does_not_repeat_same_waypoint_consecutively(self):
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        waypoints = [
            (113.39, 22.53),
            (113.3910, 22.53),
            (113.3915, 22.53),
            (113.3920, 22.53),
            (113.393, 22.53),
        ]
        picks = []

        real_choice = api_runtime.random.choice

        def _recording_choice(seq):
            chosen = real_choice(seq)
            if isinstance(chosen, dict) and "waypoint" in chosen:
                picks.append(chosen["waypoint"])
            return chosen

        planner = _RoutePlannerStub()
        with mock.patch.object(api_runtime.random, "choice", _recording_choice):
            self._build(waypoints, base, total + 600.0, planner)
        for i in range(1, len(picks)):
            self.assertNotEqual(picks[i], picks[i - 1], "不得连续选中同一打卡点")

    def test_over_budget_candidates_are_excluded_or_truncated(self):
        """去程超出本轮额度的打卡点必须被排除，额度内可达的才能被随机选中。"""
        base = [(113.34 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        near = (113.3450, 22.53)   # 距折返点约 41 m，去程在额度内
        far = (113.42, 22.53)      # 距折返点约 7.6 km，远超额度
        waypoints = [(113.34, 22.53), near, far, (113.3457, 22.53)]
        planner = _RoutePlannerStub()
        target = total + 1200.0

        # 直接检查候选筛选结果，避免随机过程带来的不确定性
        with mock.patch.object(
            api_runtime._main(), "_plan_route_path_with_provider_runtime", planner, create=True
        ), mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            turn_point = (113.3454, 22.53)
            viable, stats = self.runtime._select_detour_candidates(
                turn_point,
                waypoints,
                (113.3457, 22.53),
                target - total,
                session_id="session-test",
                python_params={},
                guard_label="TestDetourProbe",
            )

        picked_waypoints = {item["waypoint"] for item in viable}
        self.assertIn(near, picked_waypoints, "额度内可达的候选应通过筛选")
        self.assertNotIn(far, picked_waypoints, "去程超出额度的候选必须被排除")
        self.assertGreaterEqual(stats["over_budget"], 1)

        # 端到端：结果长度不得超过目标距离，且必须长于主路线
        result = self._build(waypoints, base, target, planner)
        length = _path_length(self.runtime, result)
        self.assertLessEqual(length, target + 0.5)
        self.assertGreater(length, total)

    def test_partial_round_is_truncated_within_return_leg(self):
        # 往返里程大于剩余额度时，应走完去程并在返程段内截断
        base = [(113.39 + i * 0.0001, 22.53) for i in range(60)]
        total = _path_length(self.runtime, base)
        dest = (113.3915, 22.53)
        waypoints = [(113.39, 22.53), (113.3902, 22.53), dest]
        planner = _RoutePlannerStub()
        target = total + 25.0
        result = self._build(waypoints, base, target, planner)
        self.assertAlmostEqual(_path_length(self.runtime, result), target, delta=1.0)
        # 折返点 -> 打卡点 的去程必须被真实规划过
        self.assertTrue(planner.calls)

    def test_short_route_uses_two_thirds_turn_point(self):
        base = [(113.39 + i * 0.00005, 22.53) for i in range(20)]
        total = _path_length(self.runtime, base)
        self.assertLess(total, 100.0)
        waypoints = [(113.39, 22.53), (113.391, 22.53)]
        planner = _RoutePlannerStub()
        logs = []
        with mock.patch.object(
            api_runtime._main(), "_plan_route_path_with_provider_runtime", planner, create=True
        ), mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            self.runtime._build_route_path_with_random_detours(
                base,
                waypoints,
                total + 30.0,
                session_id="session-test",
                python_params={},
                guard_label="TestDetour",
                log_func=logs.append,
            )
        joined = "\n".join(logs)
        self.assertIn("从距终点", joined)
        self.assertIn("随机折返", joined)


class TestDetourLegCache(unittest.TestCase):
    def setUp(self):
        api_runtime._DETOUR_LEG_CACHE.clear()

    def test_cache_reuses_planned_leg(self):
        runtime = _make_runtime()
        planner = _RoutePlannerStub()
        start = (113.39, 22.53)
        end = (113.393, 22.53)
        with mock.patch.object(
            api_runtime._main(), "_plan_route_path_with_provider_runtime", planner, create=True
        ), mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            first = runtime._plan_detour_leg(
                start, end, session_id="s", python_params={}, guard_label="G"
            )
            second = runtime._plan_detour_leg(
                start, end, session_id="s", python_params={}, guard_label="G"
            )
        self.assertIsNotNone(first)
        self.assertTrue(second["cached"])
        self.assertEqual(len(planner.calls), 1)

    def test_cache_is_bounded(self):
        runtime = _make_runtime()
        with mock.patch.object(
            api_runtime._main(), "_get_active_map_provider", lambda *a, **k: "stub", create=True
        ):
            for i in range(api_runtime.DETOUR_LEG_CACHE_LIMIT + 20):
                api_runtime._detour_leg_cache_put(
                    "stub",
                    (113.39, 22.53),
                    (113.39 + i * 1e-5, 22.53),
                    [(113.39, 22.53), (113.39 + i * 1e-5, 22.53)],
                )
        self.assertLessEqual(
            len(api_runtime._DETOUR_LEG_CACHE), api_runtime.DETOUR_LEG_CACHE_LIMIT
        )


if __name__ == "__main__":
    unittest.main()
