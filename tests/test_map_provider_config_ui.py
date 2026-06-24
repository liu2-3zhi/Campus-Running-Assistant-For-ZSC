import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"
MAIN_PATH = PROJECT_ROOT / "main.py"
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.json"


def _extract_js_section(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestMapProviderConfigUi(unittest.TestCase):
    def test_config_json_defines_global_provider_and_provider_sections(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        map_config = config.get("Map", {})

        self.assertIn("provider", map_config)
        self.assertIn(map_config.get("provider"), {"amap", "tencent", "tianditu", "baidu"})
        self.assertIn("providers", map_config)
        self.assertIn("amap", map_config["providers"])
        self.assertIn("tencent", map_config["providers"])
        self.assertIn("tianditu", map_config["providers"])
        self.assertIn("baidu", map_config["providers"])
        self.assertIn("js_key", map_config["providers"]["amap"])
        self.assertIn("map_key", map_config["providers"]["tencent"])
        self.assertIn("token", map_config["providers"]["tianditu"])
        self.assertIn("ak", map_config["providers"]["baidu"])
        self.assertNotIn("amap_js_key", map_config)
        self.assertNotIn("tencent_map_key", map_config)
        self.assertNotIn("tianditu_token", map_config)

    def test_load_system_config_renders_map_provider_controls(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_system_config_source = _extract_js_section(
            source,
            "async function loadSystemConfig() {",
            "\nasync function saveSystemConfig() {",
        )

        self.assertIn("地图提供方", load_system_config_source)
        self.assertIn('"select",', load_system_config_source)
        self.assertIn('selectOptions: [', load_system_config_source)
        self.assertIn('{ value: "amap", label: "高德地图" }', load_system_config_source)
        self.assertIn('{ value: "tencent", label: "腾讯地图" }', load_system_config_source)
        self.assertIn('{ value: "tianditu", label: "天地图" }', load_system_config_source)
        self.assertIn('{ value: "baidu", label: "百度地图" }', load_system_config_source)
        self.assertIn('createInput(\n      "Map.providers.amap",\n      "js_key",', load_system_config_source)
        self.assertIn('createInput(\n      "Map.providers.tencent",\n      "map_key",', load_system_config_source)
        self.assertIn('createInput(\n      "Map.providers.tianditu",\n      "token",', load_system_config_source)
        self.assertIn('createInput(\n      "Map.providers.baidu",\n      "ak",', load_system_config_source)

    def test_save_system_config_submits_global_provider_payload(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        save_system_config_source = _extract_js_section(
            source,
            "async function saveSystemConfig() {",
            "\nfunction showTempMessage",
        )

        self.assertIn('provider: $("config-Map-provider").value', save_system_config_source)
        self.assertIn('providers: {', save_system_config_source)
        self.assertIn('amap: { js_key: $("config-Map.providers.amap-js_key").value }', save_system_config_source)
        self.assertIn('tencent: { map_key: $("config-Map.providers.tencent-map_key").value }', save_system_config_source)
        self.assertIn('tianditu: { token: $("config-Map.providers.tianditu-token").value }', save_system_config_source)
        self.assertIn('baidu: { ak: $("config-Map.providers.baidu-ak").value }', save_system_config_source)

    def test_backend_config_load_returns_nested_map_provider_values(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        config_load_source = _extract_js_section(
            source,
            '@app.route("/api/admin/config/load", methods=["GET"])',
            '@app.route("/api/admin/config/save", methods=["POST"])',
        )

        self.assertIn('"provider": _get_active_map_provider(config)', config_load_source)
        self.assertIn('"amap": _get_map_provider_runtime_config(config, provider="amap")', config_load_source)
        self.assertIn('"tencent": _get_map_provider_runtime_config(config, provider="tencent")', config_load_source)
        self.assertIn('"tianditu": _get_map_provider_runtime_config(config, provider="tianditu")', config_load_source)
        self.assertIn('"baidu": _get_map_provider_runtime_config(config, provider="baidu")', config_load_source)

    def test_pc_and_mobile_config_panels_both_expose_provider_controls(self):
        html = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="admin-config-panel_modal"', html)
        self.assertIn('id="mobile-multi-admin-config-panel"', html)
        self.assertIn('id="mobile-multi-admin-config-content"', html)
        self.assertRegex(html, re.compile(r"地图提供方|provider", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
