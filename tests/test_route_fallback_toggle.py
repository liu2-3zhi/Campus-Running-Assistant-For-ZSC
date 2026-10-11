"""路径规划重试策略的行为测试（真实执行 provider JS）。

验证「规划失败时使用直线连接」(api_fallback_line) 是否真的生效：
    - 开启时：失败的段用起终点直线补齐，整体仍返回 path；
    - 关闭时：返回 error，不偷偷兜底；
    - 开关必须来自 pythonParams，不能写死。

做法：从 main.py 抽出 execute_js 的 JS 字符串，交给 tests/frontend 下的
Node 装置，在伪造的 AMap / 天地图 / 百度 / JSONP 桩上真实执行。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_provider_js import extract_js  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HARNESS = PROJECT_ROOT / "tests" / "frontend" / "route_fallback_harness.mjs"

# (provider, main.py 中函数起点, 函数终点)
PROVIDER_BOUNDS = {
    "amap": (
        "def _plan_route_path_with_amap_runtime",
        "def _plan_route_path_with_tencent_runtime",
    ),
    "tianditu": (
        "def _plan_route_path_with_tianditu_runtime",
        "def _plan_route_path_with_baidu_runtime",
    ),
}

WAYPOINTS = [
    [113.10, 22.10],
    [113.20, 22.20],
    [113.30, 22.30],
]
SINGLE_SEGMENT = [
    [113.10, 22.10],
    [113.20, 22.20],
]


def _node_available() -> bool:
    return shutil.which("node") is not None


class TestRouteFallbackToggle(unittest.TestCase):
    """amap / 天地图：直线兜底开关必须真实可控。"""

    @classmethod
    def setUpClass(cls):
        if not _node_available():
            raise unittest.SkipTest("未找到 node")
        cls.source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        cls.tmp = tempfile.mkdtemp(prefix="route_fallback_")
        cls.js_paths = {}
        for provider, (start, end) in PROVIDER_BOUNDS.items():
            body = cls.source[
                cls.source.index(start) : cls.source.index(end)
            ]
            js = extract_js(body)
            path = os.path.join(cls.tmp, f"{provider}.js")
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(js)
            cls.js_paths[provider] = path

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _run(self, provider, mode, fallback, fail_segments, rate_limited=None, waypoints=None):
        params = {
            "api_fallback_line": fallback,
            "api_retries": 1,
            "api_retry_delay_s": 0,
            "api_queue_interval_s": 0,
            "api_qps_limit": 100,
        }
        scenario = {
            "arg": [waypoints or WAYPOINTS, "fake-key", params, mode],
            "failSegments": fail_segments,
            "rateLimitedSegments": rate_limited or [],
            "rateLimitUntilAttempt": 3,
        }
        scenario_path = os.path.join(self.tmp, "scenario.json")
        with open(scenario_path, "w", encoding="utf-8") as fp:
            json.dump(scenario, fp)

        proc = subprocess.run(
            [
                "node",
                str(HARNESS),
                self.js_paths[provider],
                provider,
                scenario_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        self.assertTrue(
            proc.stdout and proc.stdout.strip(),
            f"node 无输出: rc={proc.returncode} stderr={(proc.stderr or '')[:400]}",
        )
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(payload.get("ok"), payload)
        return payload

    # ── 开启兜底 ──────────────────────────────────────────
    def test_amap_fallback_on_returns_straight_line(self):
        """单段失败时，该段应被起终点直线替代。"""
        payload = self._run(
            "amap", "walking", True, [0], waypoints=SINGLE_SEGMENT
        )

        # 单段路线（2 个航点）：失败段走直线，结果就是起终点两点
        path = payload["result"].get("path")
        self.assertIsNotNone(path, f"开启兜底后应返回 path: {payload['result']}")
        self.assertEqual(
            [(round(p["lng"], 4), round(p["lat"], 4)) for p in path],
            [(113.1, 22.1), (113.2, 22.2)],
            "单段失败且开启兜底时，应退化为起终点两点直线",
        )

    def test_amap_fallback_replaces_only_the_failed_segment(self):
        """失败段走直线，成功段仍保留真实路线。"""
        payload = self._run("amap", "walking", True, [0])
        path = payload["result"]["path"]

        # waypoints[0] -> waypoints[1] 失败走直线：中间不应有真实路线的中间点
        between = [
            (round(p["lng"], 4), round(p["lat"], 4))
            for p in path
            if 113.1 < p["lng"] < 113.2
        ]
        self.assertEqual(
            between, [], "失败段必须是直线，不应包含路线中间点"
        )
        # waypoints[1] -> waypoints[2] 成功：应保留桩生成的中间点（共 4 段细分）
        after = [p for p in path if p["lng"] > 113.2]
        self.assertGreater(
            len(after), 1, "成功段必须保留真实路线的中间点"
        )
        self.assertEqual(
            (round(path[-1]["lng"], 4), round(path[-1]["lat"], 4)),
            (113.3, 22.3),
            "整条路线必须终止于最后一个航点",
        )

    def test_amap_all_segments_failed_returns_full_straight_line(self):
        """全部段都失败时，整条路线应等于航点直连。"""
        payload = self._run("amap", "walking", True, [0, 1])
        path = payload["result"]["path"]

        self.assertEqual(
            [(round(p["lng"], 4), round(p["lat"], 4)) for p in path],
            [(113.1, 22.1), (113.2, 22.2), (113.3, 22.3)],
            "全部失败时应退化为航点直连折线",
        )

    # ── 关闭兜底 ──────────────────────────────────────────
    def test_amap_fallback_off_reports_error(self):
        payload = self._run("amap", "walking", False, [0])

        self.assertIn(
            "error",
            payload["result"],
            "关闭兜底时不得偷偷用直线补齐",
        )
        self.assertNotIn("path", payload["result"])

    def test_toggle_actually_changes_behaviour(self):
        """同一个失败场景，开关两个取值必须产生不同结果。"""
        on = self._run("amap", "walking", True, [0])["result"]
        off = self._run("amap", "walking", False, [0])["result"]

        self.assertIn("path", on)
        self.assertIn("error", off)
        self.assertNotEqual(on, off)

    def test_fallback_defaults_to_false_when_param_absent(self):
        """参数缺失时应视为关闭（JS 里是 ?? false）。"""
        scenario = {
            "arg": [WAYPOINTS, "fake-key", {"api_retries": 1, "api_retry_delay_s": 0, "api_queue_interval_s": 0, "api_qps_limit": 100}, "walking"],
            "failSegments": [0],
        }
        scenario_path = os.path.join(self.tmp, "scenario_missing.json")
        with open(scenario_path, "w", encoding="utf-8") as fp:
            json.dump(scenario, fp)

        proc = subprocess.run(
            ["node", str(HARNESS), self.js_paths["amap"], "amap", scenario_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        payload = json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertIn("error", payload["result"])

    def test_retry_budget_is_respected(self):
        """每一段最多请求 maxRetries+1 次（maxRetries=1 -> 2 次）。

        注意必须按段统计：并发波次会把"成功段"的调用也算进总数，
        直接看 searchCallCount 会得到 3（第 1 段 2 次 + 第 2 段 1 次）。
        """
        payload = self._run("amap", "walking", True, [0])

        per_segment = {}
        for call in payload["searchLog"]:
            per_segment.setdefault(call["segmentIndex"], []).append(call)

        self.assertEqual(
            len(per_segment[0]),
            2,
            "失败段应请求 2 次（初始 + 1 次重试）后放弃并兜底",
        )
        self.assertEqual(
            len(per_segment[1]),
            1,
            "成功段不得被重复请求",
        )

    def test_rate_limited_segment_does_not_consume_retry_budget(self):
        """被限流时不应消耗重试预算（限流 != 该段无路线）。

        桩在若干次限流后转为成功；若限流消耗了重试预算，JS 早就放弃了。
        """
        payload = self._run("amap", "walking", True, [], rate_limited=[0])

        per_segment = {}
        for call in payload["searchLog"]:
            per_segment.setdefault(call["segmentIndex"], []).append(call)

        attempts = len(per_segment[0])
        self.assertGreater(
            attempts,
            2,
            f"限流不应消耗重试预算，该段请求次数应超过 maxRetries+1；实际 {attempts}",
        )
        self.assertIn(
            "path", payload["result"], "限流恢复后应拿到真实路线"
        )

    def test_tianditu_fallback_on_returns_straight_line(self):
        payload = self._run("tianditu", "driving", True, [0])
        path = payload["result"].get("path")

        self.assertIsNotNone(path, f"天地图开启兜底后应返回 path: {payload['result']}")
        self.assertGreaterEqual(len(path), 2)

    def test_tianditu_fallback_off_reports_error(self):
        payload = self._run("tianditu", "driving", False, [0])

        self.assertIn("error", payload["result"])


class TestFallbackWiring(unittest.TestCase):
    """四个 provider 都必须读取同一个开关。"""

    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

    def test_all_providers_read_the_toggle(self):
        self.assertEqual(
            self.source.count("const useFallback = pythonParams.api_fallback_line ?? false;"),
            4,
            "四个 provider 都必须从 pythonParams 读取 api_fallback_line",
        )

    def test_every_provider_has_a_fallback_branch(self):
        self.assertEqual(
            self.source.count("if (useFallback) {"),
            4,
            "四个 provider 都必须有直线兜底分支",
        )


if __name__ == "__main__":
    unittest.main()
