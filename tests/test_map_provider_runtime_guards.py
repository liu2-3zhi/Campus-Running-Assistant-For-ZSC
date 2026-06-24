import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"
LOAD_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "load_amap_watermark.js"
MAIN_PATH = PROJECT_ROOT / "main.py"
INDEX_PATH = PROJECT_ROOT / "index.html"


class TestMapProviderRuntimeGuards(unittest.TestCase):
    def test_frontend_has_provider_adapter_contract(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('function getActiveMapProvider(', source)
        self.assertIn('function getMapProviderDisplayName(', source)
        self.assertIn('function getMapProviderConfig(', source)
        self.assertIn('function getMapProviderKeyRequirement(', source)
        self.assertIn('function getActiveMapProviderApiKey(', source)
        self.assertIn('function convertMapCoordinatesToGcj02(', source)
        self.assertIn('function convertGcj02ToProviderCoordinates(', source)

    def test_missing_key_modal_is_provider_agnostic(self):
        html = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="map-provider-key-modal-title"', html)
        self.assertIn('id="map-provider-key-modal-description"', html)
        self.assertIn('id="map-provider-key-modal-link"', html)
        self.assertIn('id="map-provider-key-input-label"', html)
        self.assertNotIn("程序需要一个有效的高德地图JS API Key才能使用地图功能", html)

    def test_frontend_missing_key_prompt_uses_active_provider_contract(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('function showMissingMapProviderKeyModal(', source)
        self.assertIn('function ensureActiveMapProviderRuntimeIfNeeded(', source)
        self.assertIn('fieldKey: "js_key"', source)
        self.assertIn('fieldKey: "map_key"', source)
        self.assertIn('fieldKey: "token"', source)
        self.assertIn('fieldKey: "ak"', source)
        self.assertIn('callPythonAPI("save_map_provider_key"', source)
        self.assertIn('if (provider !== "amap")', source)

    def test_frontend_map_initializers_gate_amap_runtime_by_active_provider(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        init_app_block = source[
            source.index("async function initializeApp("):
            source.index("function getActiveMapProvider(")
        ]
        init_map_block = source[
            source.index("function initMap("):
            source.index("function showMainApp(", source.index("function initMap("))
        ]
        mobile_map_block = source[
            source.index("async function initMobileMap("):
            source.index("async function loadMobileTaskHistoryPanel", source.index("async function initMobileMap("))
        ]

        self.assertIn('function renderMapProviderFrontendPlaceholder(', source)
        self.assertIn('if (!multiAccountMap && getActiveMapProvider() === "amap" && AMapInstance)', init_app_block)
        self.assertIn('if (getActiveMapProvider() !== "amap")', init_map_block)
        self.assertIn('initProviderMap("map-container", false)', init_map_block)
        self.assertIn('if (getActiveMapProvider() !== "amap")', mobile_map_block)
        self.assertIn('initProviderMap(containerId, isMultiAccount)', mobile_map_block)

    def test_non_amap_desktop_map_views_initialize_provider_map(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        show_main_block = source[
            source.index("function showMainApp("):
            source.index("function resetUI(", source.index("function showMainApp("))
        ]
        switch_multi_block = source[
            source.index("async function switchToMultiMode("):
            source.index("async function exitMultiMode(", source.index("async function switchToMultiMode("))
        ]
        init_app_block = source[
            source.index("async function initializeApp("):
            source.index("function getActiveMapProvider(")
        ]

        self.assertIn('initProviderMap("map-container", false)', show_main_block)
        self.assertIn('initProviderMap("multi-map-container", true)', switch_multi_block)
        self.assertIn('initProviderMap("multi-map-container", true)', init_app_block)

    def test_non_amap_frontend_maps_load_real_provider_sdks(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        runtime_source = source[
            source.index("async function ensureActiveMapProviderRuntimeIfNeeded("):
            source.index("function convertMapCoordinatesToGcj02(", source.index("async function ensureActiveMapProviderRuntimeIfNeeded("))
        ]
        init_map_block = source[
            source.index("function initMap("):
            source.index("function showMainApp(", source.index("function initMap("))
        ]
        mobile_map_block = source[
            source.index("async function initMobileMap("):
            source.index("async function loadMobileTaskHistoryPanel", source.index("async function initMobileMap("))
        ]

        self.assertIn("function loadTencentMapOnce(", source)
        self.assertIn("function loadTianDiTuMapOnce(", source)
        self.assertIn("function loadBaiduMapOnce(", source)
        self.assertIn("async function loadActiveMapProviderRuntime(", source)
        self.assertIn("function initProviderMap(", source)
        self.assertIn('case "tencent":', runtime_source)
        self.assertIn('case "tianditu":', runtime_source)
        self.assertIn('case "baidu":', runtime_source)
        self.assertIn('initProviderMap("map-container", false)', init_map_block)
        self.assertIn("initProviderMap(containerId, isMultiAccount)", mobile_map_block)

    def test_provider_map_reinit_does_not_clear_existing_sdk_dom(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        provider_map_source = source[
            source.index("function initProviderMap("):
            source.index("function renderMapProviderFrontendPlaceholder(", source.index("function initProviderMap("))
        ]

        self.assertIn("if (!instance) {", provider_map_source)
        self.assertIn('container.innerHTML = "";', provider_map_source)
        self.assertLess(
            provider_map_source.index("if (!instance) {"),
            provider_map_source.index('container.innerHTML = "";'),
        )

    def test_provider_map_instances_are_recreated_when_provider_changes(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        provider_map_source = source[
            source.index("function initProviderMap("):
            source.index("const MAP_COORD_PI", source.index("function initProviderMap("))
        ]
        destroy_source = source[
            source.index("function destroyProviderMapInstance("):
            source.index("function getProviderOverlayBucket(", source.index("function destroyProviderMapInstance("))
        ]
        clear_source = source[
            source.index("function clearProviderMapOverlays("):
            source.index("function getProviderMapDefaultZoom(", source.index("function clearProviderMapOverlays("))
        ]

        self.assertIn("let providerMapInstanceProviders = {};", source)
        self.assertIn("providerMapInstanceProviders[containerId]", provider_map_source)
        self.assertIn("destroyProviderMapInstance(containerId);", provider_map_source)
        self.assertIn("providerMapInstanceProviders[containerId] = provider;", provider_map_source)
        self.assertIn("delete providerMapInstanceProviders[containerId];", destroy_source)
        self.assertIn("providerMapInstanceProviders[containerId] || getActiveMapProvider()", clear_source)

    def test_manual_auto_generation_uses_backend_provider_dispatch(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        auto_generate_source = source[
            source.index("async function onConfirmAutoGenerate("):
            source.index("async function loadHistory(", source.index("async function onConfirmAutoGenerate("))
        ]

        self.assertIn('callPythonAPI("auto_generate_path_with_provider"', auto_generate_source)
        self.assertNotIn("getWalkingPath(", auto_generate_source)
        self.assertNotIn("new AMapInstance.LngLat", auto_generate_source)
        self.assertNotIn("正在调用高德地图API进行路径规划", auto_generate_source)

    def test_legacy_js_path_queue_is_amap_only(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        queue_source = source[
            source.index("async function process_path_queue("):
            source.index("function triggerPathGenerationForPy(", source.index("async function process_path_queue("))
        ]

        self.assertIn('if (getActiveMapProvider() !== "amap")', queue_source)
        self.assertIn("旧版前端路径规划队列仅支持高德地图", queue_source)
        self.assertIn("getWalkingPath(waypoints)", queue_source)

    def test_legacy_get_walking_path_guarded_as_amap_only(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        walking_source = source[
            source.index("async function getWalkingPath("):
            source.index("async function onConfirmAutoGenerate(", source.index("async function getWalkingPath("))
        ]

        self.assertIn('if (getActiveMapProvider() !== "amap")', walking_source)
        self.assertIn("getWalkingPath 仅支持高德地图", walking_source)
        self.assertIn("new AMap.Walking", walking_source)

    def test_mobile_auxiliary_maps_use_provider_map_or_guard_amap_only_pick(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        track_source = source[
            source.index("async function initMobileTrackMap("):
            source.index("function clearMobileTrackMap(", source.index("async function initMobileTrackMap("))
        ]
        attendance_source = source[
            source.index("async function initMobileMapAttendance("):
            source.index("function confirmMobileMapAttendance(", source.index("async function initMobileMapAttendance("))
        ]

        self.assertIn('if (getActiveMapProvider() !== "amap")', track_source)
        self.assertIn('initProviderMap("mobile-track-map-container", false)', track_source)
        self.assertIn('if (getActiveMapProvider() !== "amap")', attendance_source)
        self.assertIn('renderMapProviderFrontendPlaceholder("mobile-map-attendance-container", false)', attendance_source)

    def test_frontend_draws_routes_on_active_map_provider(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        draw_source = source[
            source.index("function drawOnMap_signature("):
            source.index("function drawOnMap(", source.index("function drawOnMap_signature("))
        ]
        history_source = source[
            source.index("async function showHistoricalTrack("):
            source.index("function updateSingleProgress(", source.index("async function showHistoricalTrack("))
        ]
        mobile_track_source = source[
            source.index("async function openMobileTrackModal("):
            source.index("async function initMobileTrackMap(", source.index("async function openMobileTrackModal("))
        ]

        self.assertIn("function drawProviderRouteOnMap(", source)
        self.assertIn("function clearProviderMapOverlays(", source)
        self.assertIn("function convertGcj02ToProviderCoordinates(", source)
        self.assertIn('drawProviderRouteOnMap("map-container"', draw_source)
        self.assertNotIn('renderMapProviderFrontendPlaceholder("map-container", false)', draw_source)
        self.assertIn('drawProviderRouteOnMap("map-container"', history_source)
        self.assertNotIn("前端历史轨迹绘制暂仅支持高德地图", history_source)
        self.assertIn('drawProviderRouteOnMap("mobile-track-map-container"', mobile_track_source)
        self.assertNotIn('if (getActiveMapProvider() !== "amap" || !AMapInstance)', mobile_track_source)

    def test_amap_only_frontend_pick_actions_are_guarded(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        manual_attendance_source = source[
            source.index("async function handleManualAttendance("):
            source.index("async function handleMakeupAttendance(", source.index("async function handleManualAttendance("))
        ]
        manual_makeup_source = source[
            source.index("async function handleManualMakeupAttendance("):
            source.index("async function markAsRead(", source.index("async function handleManualMakeupAttendance("))
        ]
        runner_source = source[
            source.index("function updateRunnerPosition("):
            source.index("async function loadHistory(", source.index("function updateRunnerPosition("))
        ]

        self.assertIn('if (getActiveMapProvider() !== "amap" || !map || !AMapInstance)', manual_attendance_source)
        self.assertIn('if (getActiveMapProvider() !== "amap" || !map || !AMapInstance)', manual_makeup_source)
        self.assertIn('if (getActiveMapProvider() !== "amap" || !map || !AMapInstance)', runner_source)

    def test_frontend_keeps_amap_specific_logic_separate_from_generic_runtime_guards(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_source = LOAD_SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('function installGenericMapRuntimeGuards(', source)
        self.assertIn('function installAmapRuntimeGuards(', source)
        self.assertIn('if (provider === "amap")', source)
        self.assertIn('if (normalizedProvider === "baidu")', source)
        self.assertIn('installAmapNativeDialogGuard();', load_source)

    def test_backend_distinguishes_generic_vs_amap_specific_runtime_protection(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def _install_map_runtime_guard(', source)
        self.assertIn('def _install_amap_dialog_guard(', source)
        self.assertIn('if provider == "amap":', source)

    def test_frontend_default_config_distinguishes_provider_and_business_coordinates(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        default_config_source = source[
            source.index("var DEFAULT_CONFIG = {"):
            source.index("};", source.index("var DEFAULT_CONFIG = {"))
        ]

        self.assertIn('amap: { provider: "amap", display_name: "高德地图", js_key: "", coordinate_system: "gcj02", business_coordinate_system: "gcj02" }', default_config_source)
        self.assertIn('tencent: { provider: "tencent", display_name: "腾讯地图", map_key: "", coordinate_system: "gcj02", business_coordinate_system: "gcj02" }', default_config_source)
        self.assertIn('tianditu: { provider: "tianditu", display_name: "天地图", token: "", coordinate_system: "wgs84", business_coordinate_system: "gcj02" }', default_config_source)
        self.assertIn('baidu: { provider: "baidu", display_name: "百度地图", ak: "", coordinate_system: "bd09", business_coordinate_system: "gcj02" }', default_config_source)

    def test_provider_route_drawing_splits_separator_points_before_rendering(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        draw_source = source[
            source.index("function drawProviderRouteOnMap("):
            source.index("function installGenericMapRuntimeGuards(", source.index("function drawProviderRouteOnMap("))
        ]

        self.assertIn("function isRouteSegmentSeparator(", source)
        self.assertIn("function splitRouteCoordsIntoDrawableSegments(", source)
        self.assertIn("const gcjSegments = splitRouteCoordsIntoDrawableSegments(coords);", draw_source)
        self.assertNotIn("const gcjCoords = normalizeRouteCoords(coords);", draw_source)
        self.assertIn("gcjSegments.map((segment)", draw_source)

    def test_non_amap_historical_track_uses_mobile_track_map_in_mobile_mode(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        history_source = source[
            source.index("async function showHistoricalTrack("):
            source.index("function updateSingleProgress(", source.index("async function showHistoricalTrack("))
        ]

        self.assertLess(
            history_source.index("if (isMobileMode)"),
            history_source.index('if (getActiveMapProvider() !== "amap")'),
        )
        self.assertIn('drawProviderRouteOnMap("mobile-track-map-container"', history_source)
        self.assertIn('await ensureActiveMapProviderRuntimeIfNeeded("历史轨迹地图")', history_source)

    def test_mobile_track_map_initialization_loads_active_provider_runtime(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        track_source = source[
            source.index("async function initMobileTrackMap("):
            source.index("function clearMobileTrackMap(", source.index("async function initMobileTrackMap("))
        ]

        self.assertIn('await ensureActiveMapProviderRuntimeIfNeeded("移动历史轨迹地图")', track_source)
        self.assertIn('initProviderMap("mobile-track-map-container", false)', track_source)
        self.assertLess(
            track_source.index('if (getActiveMapProvider() !== "amap")'),
            track_source.index("if (mobileTrackMapInstance) return;"),
        )

    def test_saving_provider_key_refreshes_non_amap_map_instances(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        key_source = source[
            source.index("async function onConfirmAmapKey("):
            source.index("function bindImmediateRefreshForUserSelects(", source.index("async function onConfirmAmapKey("))
        ]

        self.assertIn('await ensureActiveMapProviderRuntimeIfNeeded("保存 Key 后刷新")', key_source)
        self.assertIn("ensureSingleMap();", key_source)
        self.assertNotIn('if (getActiveMapProvider() === "amap") {\n          ensureSingleMap();\n        }', key_source)

    def test_tianditu_frontend_map_uses_tokenized_tile_layers(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        init_provider_source = source[
            source.index("function initProviderMap("):
            source.index("const MAP_COORD_PI", source.index("function initProviderMap("))
        ]

        self.assertIn("function createTianDiTuTileLayer(", source)
        self.assertIn("function applyTianDiTuDefaultMapType(", source)
        self.assertIn("applyTianDiTuDefaultMapType(instance);", init_provider_source)
        self.assertIn("tk=${token}", source)


if __name__ == "__main__":
    unittest.main()
