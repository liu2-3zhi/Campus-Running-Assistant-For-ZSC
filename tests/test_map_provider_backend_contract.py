import unittest
from pathlib import Path
import ast
import subprocess
import tempfile
from unittest import mock

import main as main_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestMapProviderBackendContract(unittest.TestCase):
    def _runtime_config_with_map(self, provider, providers):
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        self.addCleanup(lambda path=temp.name: Path(path).unlink(missing_ok=True))
        temp.write("{}")
        temp.close()
        runtime_config = main_module.JsonConfigAdapter(temp.name)
        runtime_config.add_section("Map")
        runtime_config.set("Map", "provider", provider)
        runtime_config.set("Map", "providers", providers)
        return runtime_config

    def _route_helper_execute_js_source(self, helper_name):
        source = MAIN_PATH.read_text(encoding="utf-8")
        module = ast.parse(source)
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == helper_name:
                for sub_node in ast.walk(node):
                    if (
                        isinstance(sub_node, ast.Call)
                        and isinstance(sub_node.func, ast.Attribute)
                        and sub_node.func.attr == "execute_js"
                    ):
                        js_arg = sub_node.args[1]
                        self.assertIsInstance(js_arg, ast.Constant)
                        self.assertIsInstance(js_arg.value, str)
                        return js_arg.value
        self.fail(f"{helper_name} execute_js source not found")

    def test_frontend_config_includes_map_provider_contract(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('"map_provider"', source)
        self.assertIn('"map_providers"', source)
        self.assertIn('"amap"', source)
        self.assertIn('"tencent"', source)
        self.assertIn('"tianditu"', source)
        self.assertIn('"baidu"', source)

    def test_admin_config_save_accepts_global_provider_and_multi_provider_keys(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('if "Map" in data and "provider" in data["Map"]:', source)
        self.assertIn('config.set("Map", "provider",', source)
        self.assertIn('providers = data["Map"].get("providers") or {}', source)
        self.assertIn('amap_provider = providers.get("amap") or {}', source)
        self.assertIn('tencent_provider = providers.get("tencent") or {}', source)
        self.assertIn('tianditu_provider = providers.get("tianditu") or {}', source)
        self.assertIn('baidu_provider = providers.get("baidu") or {}', source)
        self.assertIn('config.set(\n                    "Map",\n                    "providers",', source)
        self.assertIn('for legacy_key in [', source)
        self.assertIn('config.remove_option("Map", legacy_key)', source)

    def test_backend_exposes_map_provider_resolution_helpers(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('MAP_PROVIDER_KEY_FIELDS = {', source)
        self.assertIn('def _get_active_map_provider(', source)
        self.assertIn('def _get_map_provider_runtime_config(', source)
        self.assertIn('def _get_map_provider_frontend_config(', source)
        self.assertIn('def _normalize_map_provider(', source)
        self.assertIn('def _resolve_amap_js_key(', source)

    def test_backend_runtime_config_exposes_provider_display_and_business_coordinates(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        runtime_source = source[
            source.index("def _get_map_provider_runtime_config("):
            source.index("def _get_map_provider_frontend_config(", source.index("def _get_map_provider_runtime_config("))
        ]

        self.assertIn('"coordinate_system": "gcj02"', runtime_source)
        self.assertIn('"business_coordinate_system": "gcj02"', runtime_source)
        self.assertIn('"coordinate_system": "wgs84"', runtime_source)
        self.assertIn('"coordinate_system": "bd09"', runtime_source)

    def test_backend_exposes_generic_map_provider_key_save_method(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def save_map_provider_key(self, provider, api_key):', source)
        self.assertIn('key_field = MAP_PROVIDER_KEY_FIELDS[provider]', source)
        self.assertIn('"save_map_provider_key": "modify_params"', source)

    def test_tianditu_walking_falls_back_to_driving_with_explicit_notice(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('provider == "tianditu" and route_mode == "walking"', source)
        self.assertIn('actual_mode = "driving"', source)
        self.assertIn('当前地图供应商不支持步行规划，已自动使用驾车规划代替', source)

    def test_route_planning_no_longer_hardcodes_amap_walking_only(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def _plan_route_with_map_provider(', source)
        self.assertIn('provider_config = _get_map_provider_runtime_config(', source)
        self.assertIn('provider = _get_active_map_provider(', source)
        self.assertIn('plugins = _get_map_provider_plugins(', source)

    def test_initial_data_uses_resolved_amap_key(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('"amap_key": _resolve_amap_js_key(self.config_path),', source)

    def test_initial_data_and_login_return_map_provider_contract(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        get_initial_data_source = source[
            source.index("    def get_initial_data("):
            source.index("    def save_amap_key(", source.index("    def get_initial_data("))
        ]
        login_source = source[
            source.rindex("    def login(", 0, source.index("    def logout(")):
            source.index("    def logout(")
        ]

        self.assertIn('map_config = _get_map_provider_frontend_config(cfg)', get_initial_data_source)
        self.assertIn('"map_provider": map_config["map_provider"]', get_initial_data_source)
        self.assertIn('"map_providers": map_config["map_providers"]', get_initial_data_source)
        self.assertIn('login_map_config = _get_map_provider_frontend_config(', login_source)
        self.assertIn('"map_provider": login_map_config["map_provider"]', login_source)
        self.assertIn('"map_providers": login_map_config["map_providers"]', login_source)

    def test_provider_runtime_dispatches_each_configured_provider(self):
        runtime_config = self._runtime_config_with_map("amap", {
            "amap": {"js_key": "amap-key"},
            "tencent": {"map_key": "tencent-key"},
            "tianditu": {"token": "tianditu-token"},
            "baidu": {"ak": "baidu-ak"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        helper_results = {
            "amap": {"path": [{"lng": 1, "lat": 1}]},
            "tencent": {"path": [{"lng": 2, "lat": 2}]},
            "tianditu": {"path": [{"lng": 3, "lat": 3}]},
            "baidu": {"path": [{"lng": 4, "lat": 4}]},
        }
        called = []

        def make_helper(provider):
            def _helper(session_id, page, waypoints, provider_plan, python_params):
                called.append((provider, provider_plan["actual_mode"], provider_plan["provider_config"]))
                return helper_results[provider].copy()
            return _helper

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_amap_runtime", side_effect=make_helper("amap")), \
             mock.patch.object(main_module, "_plan_route_path_with_tencent_runtime", side_effect=make_helper("tencent")), \
             mock.patch.object(main_module, "_plan_route_path_with_tianditu_runtime", side_effect=make_helper("tianditu")), \
             mock.patch.object(main_module, "_plan_route_path_with_baidu_runtime", side_effect=make_helper("baidu")):
            results = {
                provider: main_module._plan_route_path_with_provider_runtime(
                    "session-1",
                    [[113.39, 22.52], [113.40, 22.53]],
                    python_params={"api_retries": 0},
                    provider=provider,
                    runtime_config=runtime_config,
                )
                for provider in ["amap", "tencent", "tianditu", "baidu"]
            }

        self.assertEqual([item[0] for item in called], ["amap", "tencent", "tianditu", "baidu"])
        self.assertEqual(called[0][2]["js_key"], "amap-key")
        self.assertEqual(called[1][2]["map_key"], "tencent-key")
        self.assertEqual(called[2][2]["token"], "tianditu-token")
        self.assertEqual(called[3][2]["ak"], "baidu-ak")
        self.assertEqual(results["amap"]["provider"], "amap")
        self.assertEqual(results["tencent"]["provider"], "tencent")
        self.assertEqual(results["tianditu"]["provider"], "tianditu")
        self.assertEqual(results["baidu"]["provider"], "baidu")

    def test_provider_runtime_navigates_to_session_page_before_backend_js_execution(self):
        runtime_config = self._runtime_config_with_map("amap", {
            "amap": {"js_key": "amap-key"},
        })
        page = mock.Mock(on=mock.Mock(), goto=mock.Mock())

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": page}

        def amap_helper(session_id, helper_page, waypoints, provider_plan, python_params):
            page.goto.assert_called_once_with(
                "http://127.0.0.1:5000/uuid=session-1",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            self.assertIs(helper_page, page)
            return {"path": [{"lng": 1, "lat": 1}]}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_amap_runtime", side_effect=amap_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                provider="amap",
                runtime_config=runtime_config,
                app_base_url="http://127.0.0.1:5000/",
            )

        self.assertEqual(result["provider"], "amap")
        self.assertIn("path", result)

    def test_provider_runtime_reports_unavailable_chrome_pool_with_provider_context(self):
        runtime_config = self._runtime_config_with_map("tencent", {
            "tencent": {"map_key": "tencent-key"},
        })

        with mock.patch.object(main_module, "chrome_pool", None, create=True):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                runtime_config=runtime_config,
            )

        self.assertEqual(result["provider"], "tencent")
        self.assertIn("Chrome浏览器池不可用", result["error"])

    def test_tianditu_provider_runtime_returns_driving_notice_for_walking_contract(self):
        runtime_config = self._runtime_config_with_map("tianditu", {
            "tianditu": {"token": "tianditu-token"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        def tianditu_helper(session_id, page, waypoints, provider_plan, python_params):
            self.assertEqual(provider_plan["actual_mode"], "driving")
            return {"path": [{"lng": 113.39, "lat": 22.52}, {"lng": 113.40, "lat": 22.53}]}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_tianditu_runtime", side_effect=tianditu_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                runtime_config=runtime_config,
            )

        self.assertEqual(result["provider"], "tianditu")
        self.assertIn("当前地图供应商不支持步行规划，已自动使用驾车规划代替", result["notices"])

    def test_provider_route_helpers_report_missing_keys_before_external_js_calls(self):
        page = mock.Mock(goto=mock.Mock())
        waypoints = [[113.39, 22.52], [113.40, 22.53]]

        helpers = [
            (
                main_module._plan_route_path_with_amap_runtime,
                {"provider_config": {"js_key": ""}, "actual_mode": "walking", "plugins": ["AMap.Walking"]},
                "未配置高德地图 JS Key",
            ),
            (
                main_module._plan_route_path_with_tencent_runtime,
                {"provider_config": {"map_key": ""}, "actual_mode": "walking"},
                "未配置腾讯地图 Key",
            ),
            (
                main_module._plan_route_path_with_tianditu_runtime,
                {"provider_config": {"token": ""}, "actual_mode": "driving"},
                "未配置天地图 Token",
            ),
            (
                main_module._plan_route_path_with_baidu_runtime,
                {"provider_config": {"ak": ""}, "actual_mode": "walking"},
                "未配置百度地图 AK",
            ),
        ]

        chrome_pool_mock = mock.Mock(execute_js=mock.Mock())
        with mock.patch.object(main_module, "chrome_pool", chrome_pool_mock, create=True):
            for helper, provider_plan, error_text in helpers:
                with self.subTest(helper=helper.__name__):
                    result = helper("session-1", page, waypoints, provider_plan, python_params={})
                    self.assertIn(error_text, result["error"])

        chrome_pool_mock.execute_js.assert_not_called()
        page.goto.assert_not_called()

    def test_provider_route_helpers_call_chrome_executor_with_provider_credentials(self):
        waypoints = [[113.39, 22.52], [113.40, 22.53]]
        expected_calls = [
            (
                main_module._plan_route_path_with_amap_runtime,
                {"provider_config": {"js_key": "amap-key"}, "actual_mode": "walking", "plugins": ["AMap.Walking"]},
                ["amap-key", {"api_retries": 0}, ["AMap.Walking"], "walking"],
            ),
            (
                main_module._plan_route_path_with_tencent_runtime,
                {"provider_config": {"map_key": "tencent-key"}, "actual_mode": "walking"},
                ["tencent-key", {"api_retries": 0}, "walking"],
            ),
            (
                main_module._plan_route_path_with_tianditu_runtime,
                {"provider_config": {"token": "tianditu-token"}, "actual_mode": "driving"},
                ["tianditu-token", {"api_retries": 0}, "driving"],
            ),
            (
                main_module._plan_route_path_with_baidu_runtime,
                {"provider_config": {"ak": "baidu-ak"}, "actual_mode": "walking"},
                ["baidu-ak", {"api_retries": 0}, "walking"],
            ),
        ]

        for helper, provider_plan, expected_tail in expected_calls:
            with self.subTest(helper=helper.__name__):
                page = mock.Mock(goto=mock.Mock())
                chrome_pool_mock = mock.Mock(
                    execute_js=mock.Mock(return_value={"path": [{"lng": 113.39, "lat": 22.52}]})
                )
                with mock.patch.object(main_module, "chrome_pool", chrome_pool_mock, create=True):
                    result = helper(
                        "session-1",
                        page,
                        waypoints,
                        provider_plan,
                        python_params={"api_retries": 0},
                    )

                page.goto.assert_not_called()
                chrome_pool_mock.execute_js.assert_called_once()
                args = chrome_pool_mock.execute_js.call_args.args
                self.assertEqual(args[0], "session-1")
                self.assertEqual(args[2], waypoints)
                self.assertEqual(list(args[3:]), expected_tail)
                self.assertEqual(result["path"], [{"lng": 113.39, "lat": 22.52}])

    def test_provider_route_helper_js_payloads_are_syntax_valid(self):
        expected_snippets = {
            "_plan_route_path_with_amap_runtime": [
                "https://webapi.amap.com/loader.js",
                "AMapLoader.load",
                "AMap.Walking",
            ],
            "_plan_route_path_with_tencent_runtime": [
                "https://apis.map.qq.com/ws/direction/v1/",
                "output=jsonp",
                "${startCoord.lat},${startCoord.lng}",
            ],
            "_plan_route_path_with_tianditu_runtime": [
                "https://api.tianditu.gov.cn/drive?postStr=",
                "function gcj02ToTdtCoordinate(",
                "function tdtCoordinateToGcj02(",
            ],
            "_plan_route_path_with_baidu_runtime": [
                "https://api.map.baidu.com/api?v=3.0&ak=",
                "function gcj02ToBd09(",
                "function bd09ToGcj02(",
                "百度地图脚本加载完成但运行时不可用",
            ],
        }

        for helper_name, snippets in expected_snippets.items():
            with self.subTest(helper=helper_name):
                js_source = self._route_helper_execute_js_source(helper_name).strip()
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", suffix=".js", delete=False
                ) as tmp:
                    tmp.write(f"const routeHelper = {js_source};\n")
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
                        f"{helper_name} execute_js payload syntax check failed\n"
                        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                    )
                for snippet in snippets:
                    self.assertIn(snippet, js_source)


if __name__ == "__main__":
    unittest.main()
