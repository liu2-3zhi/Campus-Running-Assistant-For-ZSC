import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestMapProviderBusinessExecutionContract(unittest.TestCase):
    def test_run_all_auto_generation_uses_backend_provider_dispatch_instead_of_frontend_amap_callback(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        run_all_block = source.split("def _run_all_tasks_manager(", 1)[1].split(
            "def get_task_history(", 1
        )[0]

        self.assertIn("_plan_route_path_with_provider_runtime(", run_all_block)
        self.assertNotIn('triggerPathGenerationForPy("', run_all_block)
        self.assertNotIn("调用高德API进行路径规划", run_all_block)

    def test_multi_account_business_execution_uses_provider_runtime_helper(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        worker_block = source.split("def _multi_account_worker(", 1)[1].split(
            "def _run_all_multi_accounts_thread(", 1
        )[0]

        self.assertIn("_plan_route_path_with_provider_runtime(", worker_block)
        self.assertNotIn("AMapLoader", worker_block)
        self.assertNotIn("AMap.Walking", worker_block)
        self.assertNotIn("https://webapi.amap.com/loader.js", worker_block)
        self.assertNotIn("正在调用高德地图API进行路径规划", worker_block)

    def test_background_auto_generation_uses_provider_runtime_helper(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        background_block = source.split("def _execute_tasks_background(", 1)[1].split(
            "def stop_task(", 1
        )[0]

        self.assertIn("_plan_route_path_with_provider_runtime(", background_block)
        self.assertIn('guard_label="BackgroundTaskPathPlanning"', background_block)
        self.assertNotIn('"Map", "amap_js_key"', background_block)
        self.assertNotIn("AMapLoader", background_block)
        self.assertNotIn("AMap.Walking", background_block)
        self.assertNotIn("https://webapi.amap.com/loader.js", background_block)
        self.assertNotIn("正在向Chrome页面加载高德地图SDK", background_block)

    def test_single_account_manual_auto_generation_uses_provider_runtime_helper(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("def auto_generate_path_with_provider(", source)
        manual_block = source.split("def auto_generate_path_with_provider(", 1)[1].split(
            "def start_all_runs(", 1
        )[0]

        self.assertIn("_plan_route_path_with_provider_runtime(", manual_block)
        self.assertIn('guard_label="SingleManualPathPlanning"', manual_block)
        self.assertIn("self.auto_generate_path_with_api(", manual_block)
        self.assertNotIn("_plan_route_path_with_amap_runtime(", manual_block)
        self.assertNotIn("AMapLoader", manual_block)
        self.assertNotIn("AMap.Walking", manual_block)

    def test_multi_account_thread_launcher_helper_remains_defined(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn("def _start_multi_account_threads(", source)
        self.assertIn("def _run_all_multi_accounts_thread(self, *args, **kwargs):", source)
        self.assertIn("return self._start_multi_account_threads(*args, **kwargs)", source)

    def test_backend_exposes_provider_specific_business_runtime_helpers(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn("def _plan_route_path_with_provider_runtime(", source)
        self.assertIn("def _plan_route_path_with_amap_runtime(", source)
        self.assertIn('if provider == "amap":', source)
        self.assertIn('if provider == "tencent":', source)
        self.assertIn('if provider == "tianditu":', source)
        self.assertIn('if provider == "baidu":', source)

    def test_provider_specific_route_helpers_are_only_called_from_dispatcher(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        for helper in [
            "_plan_route_path_with_amap_runtime(",
            "_plan_route_path_with_tencent_runtime(",
            "_plan_route_path_with_tianditu_runtime(",
            "_plan_route_path_with_baidu_runtime(",
        ]:
            self.assertEqual(
                source.count(helper),
                2,
                f"{helper} should only appear in its definition and provider dispatcher",
            )

    def test_provider_route_helpers_return_gcj02_business_coordinates(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        tianditu_block = source.split("def _plan_route_path_with_tianditu_runtime(", 1)[1].split(
            "def _plan_route_path_with_baidu_runtime(", 1
        )[0]
        baidu_block = source.split("def _plan_route_path_with_baidu_runtime(", 1)[1].split(
            "def _plan_route_path_with_provider_runtime(", 1
        )[0]
        tencent_block = source.split("def _plan_route_path_with_tencent_runtime(", 1)[1].split(
            "def _plan_route_path_with_tianditu_runtime(", 1
        )[0]

        self.assertIn("function gcj02ToTdtCoordinate(", tianditu_block)
        self.assertIn("function tdtCoordinateToGcj02(", tianditu_block)
        self.assertIn("return tdtCoordinateToGcj02({ lng, lat });", tianditu_block)
        self.assertIn("function gcj02ToBd09(", baidu_block)
        self.assertIn("function bd09ToGcj02(", baidu_block)
        self.assertIn("const converted = bd09ToGcj02(Number(point.lng), Number(point.lat));", baidu_block)
        self.assertIn("points.push({ lng, lat });", tencent_block)


if __name__ == "__main__":
    unittest.main()
