import re
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = PROJECT_ROOT / "TEST"


def _read_html(name: str) -> str:
    return (TEST_DIR / name).read_text(encoding="utf-8")


def _extract_last_inline_script(html: str) -> str:
    scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
    if not scripts:
        raise AssertionError("未找到内联 script")
    return scripts[-1]


class TestMapDebugPages(unittest.TestCase):
    DEBUG_PAGES = [
        "TEST_TianDiTu_MAP.html",
        "TEST_Tencent_MAP.html",
        "TEST_Baidu_MAP.html",
    ]

    def test_debug_page_inline_scripts_are_valid_javascript(self):
        for page_name in self.DEBUG_PAGES:
            with self.subTest(page=page_name):
                script = _extract_last_inline_script(_read_html(page_name))
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", suffix=".js", delete=False
                ) as tmp:
                    tmp.write(script)
                    tmp_path = Path(tmp.name)
                try:
                    result = subprocess.run(
                        ["node", "--check", str(tmp_path)],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
                if result.returncode != 0:
                    self.fail(
                        f"{page_name} 内联脚本语法检查失败\n"
                        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                    )

    def test_provider_debug_pages_use_real_provider_sdks_and_route_apis(self):
        tianditu = _read_html("TEST_TianDiTu_MAP.html")
        tencent = _read_html("TEST_Tencent_MAP.html")
        baidu = _read_html("TEST_Baidu_MAP.html")

        self.assertIn("https://api.tianditu.gov.cn/api?v=4.0&tk=", tianditu)
        self.assertIn("https://api.tianditu.gov.cn/drive?postStr=", tianditu)
        self.assertIn("routelatlon", tianditu)
        self.assertIn("new T.Polyline(pathPoints", tianditu)
        self.assertIn("AbortController", tianditu)
        self.assertIn("地图路线服务请求超时", tianditu)
        self.assertIn("signal: controller.signal", tianditu)

        self.assertIn("https://map.qq.com/api/gljs?v=1.exp&key=", tencent)
        self.assertIn("https://apis.map.qq.com/ws/direction/v1/", tencent)
        self.assertIn("output=jsonp", tencent)
        self.assertIn("callback=", tencent)
        self.assertIn("new TMap.MultiPolyline", tencent)

        self.assertIn("https://api.map.baidu.com/api?v=3.0&ak=", baidu)
        self.assertIn("callback=__onBaiduMapApiLoaded", baidu)
        self.assertIn("new BMap.WalkingRoute", baidu)
        self.assertIn("new BMap.DrivingRoute", baidu)
        self.assertIn("currentRouteSearch.search(startCoord.point, endCoord.point)", baidu)

    def test_tencent_route_requests_use_lat_lng_order_required_by_direction_api(self):
        tencent = _read_html("TEST_Tencent_MAP.html")

        self.assertIn("${startCoord.lat},${startCoord.lng}", tencent)
        self.assertIn("${endCoord.lat},${endCoord.lng}", tencent)
        self.assertIn("return { lng, lat, latLng: new TMap.LatLng(lat, lng) };", tencent)


if __name__ == "__main__":
    unittest.main()
