import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestMapProviderBackendContract(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
