"""地图「不要每次 GPS 更新都重绘并复位视野」回归测试。

历史缺陷：
1. ``drawOnMap_signature`` 末尾无条件调用 ``resetMapView()``，而
   ``updateRunnerPosition`` 每次 GPS 更新都会调用它，导致地图被反复复位；
2. 进度推进被当作「整图重绘」条件，每次前进一个点都会清空并重建全部覆盖物。

修复后：
- ``drawOnMap_signature`` 支持 ``options.resetView === false``；
- 进度推进走 ``updateTaskProgressSegmentsInPlace`` 就地着色（不清覆盖物、不 fitView）；
- 只有「打卡点推进 / 首次进入运行态」才重建标记并允许重新适配视野。
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = PROJECT_ROOT / "scripts" / "main.js"
RENDER_JS = PROJECT_ROOT / "scripts" / "legacy-map-render.js"
RUNTIME_JS = PROJECT_ROOT / "scripts" / "legacy-map-runtime.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_function(source: str, signature: str) -> str:
    """提取函数体：先跳过参数列表，再对函数体的花括号配对。"""
    start = source.index(signature)
    # 找到参数列表结束的右括号（跳过默认值里的 {} 与 () ）
    paren = source.index("(", start)
    depth = 0
    params_end = -1
    for index in range(paren, len(source)):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                params_end = index
                break
    if params_end < 0:
        raise AssertionError(f"无法定位函数参数列表 {signature}")
    brace = source.index("{", params_end)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"无法提取函数 {signature}")


class TestMapProgressRedrawDoesNotResetView(unittest.TestCase):
    def test_draw_on_map_signature_accepts_reset_view_option(self):
        source = _read(MAIN_JS)
        function_source = _extract_function(source, "function drawOnMap_signature(")
        self.assertIn("options = {}", function_source)
        self.assertIn("options.resetView !== false", function_source)
        # 不得再无条件复位视野
        self.assertNotIn("\n  resetMapView();\n}", function_source)

    def test_in_place_update_short_circuits_full_redraw(self):
        source = _read(MAIN_JS)
        function_source = _extract_function(source, "function drawOnMap_signature(")
        guard_index = function_source.index("updateTaskProgressSegmentsInPlace")
        clear_index = function_source.index("clearMapOverlays()")
        self.assertLess(
            guard_index,
            clear_index,
            "就地更新必须在清空覆盖物之前短路返回",
        )

    def test_runner_position_splits_structural_change_from_progress(self):
        source = _read(MAIN_JS)
        function_source = _extract_function(source, "function updateRunnerPosition(")
        # 结构变化（打卡点推进/首次运行）才整图重绘
        self.assertIn("const structuralChange =", function_source)
        self.assertIn("drawOnMap_signature();", function_source)
        # 进度推进只就地着色
        self.assertIn("const progressAdvanced =", function_source)
        self.assertIn("drawOnMap_signature({ resetView: false });", function_source)
        # 旧的「进度变化即整图重绘」条件必须消失
        self.assertNotIn("previousProgressIndex !== nextProgressIndex);", function_source)

    def test_provider_route_draw_supports_preserve_view(self):
        source = _read(RENDER_JS)
        function_source = _extract_function(source, "function drawProviderRouteOnMap(")
        self.assertIn("options.preserveView !== true", function_source)
        self.assertIn("rememberProviderRouteSegmentOverlays", function_source)

    def test_progress_task_draw_preserves_view_while_running(self):
        source = _read(RENDER_JS)
        function_source = _extract_function(source, "function drawProviderTaskOnMap(")
        self.assertIn("preserveView: activeProgress", function_source)

    def test_in_place_update_function_has_no_fit_or_clear(self):
        source = _read(RENDER_JS)
        function_source = _extract_function(
            source, "function updateProviderRouteProgressSegmentsInPlace("
        )
        # 就地更新不得清空覆盖物或重新适配视野
        self.assertNotIn("clearProviderMapOverlays", function_source)
        self.assertNotIn("fitProviderMapToCoordinates", function_source)

    def test_segment_cache_is_invalidated_when_overlays_cleared(self):
        source = _read(RUNTIME_JS)
        function_source = _extract_function(source, "function clearProviderMapOverlays(")
        self.assertIn("forgetProviderRouteSegmentOverlays", function_source)

    def test_amap_cache_is_invalidated_with_overlays(self):
        source = _read(MAIN_JS)
        function_source = _extract_function(source, "function clearMapOverlays(")
        self.assertIn("amapRouteProgressSegments = null", function_source)


if __name__ == "__main__":
    unittest.main()
