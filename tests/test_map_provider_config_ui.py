import json
import re
import unittest
from pathlib import Path
from tests.backend_source_utils import read_backend_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.js"
ADMIN_CONFIG_PATH = PROJECT_ROOT / "scripts" / "legacy-admin-config.js"
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
        source = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + ADMIN_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        load_system_config_source = _extract_js_section(
            source,
            "async function loadSystemConfig() {",
            "\nasync function saveSystemConfig() {",
        )

        self.assertIn('renderMapConfigCards(config.Map || {})', load_system_config_source)
        self.assertIn('initMapConfigCardsSort(formContainer)', load_system_config_source)
        for marker in ('data-map-config-select="frontend"', 'data-map-config-select="backend"',
                       'data-map-drag-handle', 'data-map-config-field="name"'):
            self.assertIn(marker, source)
        for field in ('js_key', 'map_key', 'token', 'ak', 'security_js_code'):
            self.assertIn(field, source)

    def test_load_system_config_does_not_duplicate_html_accumulator(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + ADMIN_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        load_system_config_source = _extract_js_section(
            source,
            "async function loadSystemConfig() {",
            "\nasync function saveSystemConfig() {",
        )

        self.assertNotIn("html +=\n    html +=", load_system_config_source)

    def test_save_system_config_submits_global_provider_payload(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + ADMIN_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        save_system_config_source = _extract_js_section(
            source,
            "async function saveSystemConfig() {",
            "\nfunction showTempMessage",
        )

        self.assertIn('...readMapConfigCards(panel)', save_system_config_source)
        self.assertIn('configData.Map.frontend_config_id', save_system_config_source)
        self.assertIn('map_provider: newProvider', save_system_config_source)
        self.assertNotIn('config-Map-provider', save_system_config_source)
        self.assertIn('normalizeBackendPageOrigin($("config-Map-backend_page_origin").value)', save_system_config_source)

    def test_save_system_config_defers_map_provider_runtime_switch(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + ADMIN_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
        save_system_config_source = _extract_js_section(
            source,
            "async function saveSystemConfig() {",
            "\nfunction showTempMessage",
        )
        provider_changed_start = save_system_config_source.index("const providerChanged")
        provider_changed_end = save_system_config_source.index("showModalAlert(", provider_changed_start)
        provider_changed_block = save_system_config_source[
            provider_changed_start:provider_changed_end
        ]

        self.assertIn("queuePendingMapProviderConfig(", save_system_config_source)
        self.assertIn("下次加载地图时", save_system_config_source)
        self.assertNotIn("destroySingleMap();", provider_changed_block)
        self.assertNotIn('ensureActiveMapProviderRuntimeIfNeeded("切换地图提供方")', provider_changed_block)
        self.assertNotIn('initProviderMap("map-container", false)', provider_changed_block)
        self.assertNotIn("initMap(AMapInstance)", provider_changed_block)

    def test_backend_config_load_returns_nested_map_provider_values(self):
        source = read_backend_source()
        config_load_source = _extract_js_section(
            source,
            '@app.route("/api/admin/config/load", methods=["GET"])',
            '@app.route("/api/admin/config/save", methods=["POST"])',
        )

        self.assertIn('"provider": _get_active_map_provider(config, scope="frontend")', config_load_source)
        for provider in ("amap", "tencent", "tianditu", "baidu"):
            self.assertIn(f'"{provider}": _get_map_provider_admin_config(config, provider="{provider}")', config_load_source)
        self.assertIn('"backend_page_origin": config.get("Map", "backend_page_origin", fallback="")', config_load_source)

    def test_pc_and_mobile_config_panels_both_expose_provider_controls(self):
        html = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="admin-config-panel_modal"', html)
        self.assertIn('id="mobile-multi-admin-config-panel"', html)
        self.assertIn('id="mobile-multi-admin-config-content"', html)
        self.assertRegex(html, re.compile(r"地图提供方|provider", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
