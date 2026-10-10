"""前端分段着色的 pytest 入口（调用 Node 断言脚本）。

对应 ``tests/frontend/test_map_route_progress_segments.mjs``：验证
「当前位置之前为灰、当前位置到下一打卡点为蓝、其余为红」。
"""

import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "tests" / "frontend" / "test_map_route_progress_segments.mjs"


class TestFrontendRouteProgressSegments(unittest.TestCase):
    def test_node_segment_script_passes(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 不可用")
        result = subprocess.run(
            [node, str(SCRIPT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "前端分段着色断言失败\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    def test_progress_builder_is_used_by_both_draw_paths(self):
        """高德与其它供应商都必须走「按当前位置切开」的分段函数。"""
        render_source = (PROJECT_ROOT / "scripts" / "legacy-map-render.js").read_text(
            encoding="utf-8"
        )
        main_source = (PROJECT_ROOT / "scripts" / "main.js").read_text(encoding="utf-8")

        self.assertIn(
            "buildProviderRouteProgressSegmentsByProgress", render_source
        )
        self.assertIn(
            "buildProviderRouteProgressSegmentsByProgress(routeCoords, data)",
            render_source,
        )

        walk_source = main_source[
            main_source.index("function drawAmapRunRoute(") : main_source.index(
                "function drawOnMap_signature("
            )
        ]
        # 高德必须使用分段结果（历史实现直接忽略 routeSegments）
        self.assertIn("buildProviderRouteProgressSegmentsByProgress", walk_source)
        self.assertIn("polylines.run = lines", walk_source)


if __name__ == "__main__":
    unittest.main()
