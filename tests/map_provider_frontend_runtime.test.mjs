import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function extractFunctionSource(source, functionName) {
  const asyncSignature = `async function ${functionName}`;
  const syncSignature = `function ${functionName}`;
  let start = source.indexOf(asyncSignature);
  if (start === -1) {
    start = source.indexOf(syncSignature);
  }
  assert.notEqual(start, -1, `${functionName} should exist in scripts/main.new.js`);

  const paramsEnd = source.indexOf(')', start);
  assert.notEqual(paramsEnd, -1, `${functionName} should have a parameter list`);
  const bodyStart = source.indexOf('{', paramsEnd);
  assert.notEqual(bodyStart, -1, `${functionName} should have a body`);

  let depth = 0;
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let inTemplate = false;
  let inLineComment = false;
  let inBlockComment = false;

  for (let i = bodyStart; i < source.length; i += 1) {
    const char = source[i];
    const next = source[i + 1];
    const prev = source[i - 1];

    if (inLineComment) {
      if (char === '\n') inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (prev === '*' && char === '/') inBlockComment = false;
      continue;
    }
    if (!inSingleQuote && !inDoubleQuote && !inTemplate) {
      if (char === '/' && next === '/') {
        inLineComment = true;
        continue;
      }
      if (char === '/' && next === '*') {
        inBlockComment = true;
        continue;
      }
    }
    if (!inDoubleQuote && !inTemplate && char === "'" && prev !== '\\') {
      inSingleQuote = !inSingleQuote;
      continue;
    }
    if (!inSingleQuote && !inTemplate && char === '"' && prev !== '\\') {
      inDoubleQuote = !inDoubleQuote;
      continue;
    }
    if (!inSingleQuote && !inDoubleQuote && char === '`' && prev !== '\\') {
      inTemplate = !inTemplate;
      continue;
    }
    if (inSingleQuote || inDoubleQuote || inTemplate) {
      continue;
    }
    if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, i + 1);
      }
    }
  }

  throw new Error(`Failed to extract ${functionName}`);
}

function createDocument() {
  const elements = new Map();
  const appendedScripts = [];
  const createElementObject = (id = '') => ({
    id,
    children: [],
    dataset: {},
    style: {},
    innerHTML: '',
    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
      if (child.tagName === 'script') {
        appendedScripts.push(child);
      }
    },
    removeChild(child) {
      this.children = this.children.filter((item) => item !== child);
      child.parentNode = null;
    },
    classList: {
      add() {},
      remove() {},
    },
  });

  return {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, createElementObject(id));
      }
      return elements.get(id);
    },
    createElement(tagName) {
      return {
        ...createElementObject(''),
        tagName,
        async: false,
        defer: false,
        onload: null,
        onerror: null,
        src: '',
      };
    },
    querySelector() {
      return null;
    },
    head: createElementObject('head'),
    body: createElementObject('body'),
    appendedScripts,
  };
}

function createTencentSdk() {
  class LatLng {
    constructor(lat, lng) {
      this.lat = lat;
      this.lng = lng;
    }
  }
  class LatLngBounds {
    constructor() {
      this.points = [];
    }
    extend(point) {
      this.points.push(point);
    }
  }
  class TencentMap {
    constructor(container, options) {
      this.container = container;
      this.options = options;
      this.fitBoundsCalls = [];
      this.zoomByCalls = [];
      this.events = [];
    }
    setCenter(center) {
      this.center = center;
    }
    setZoom(zoom) {
      this.zoom = zoom;
    }
    on(eventName, handler) {
      this.events.push({ eventName, handler });
    }
    fitBounds(bounds, options) {
      this.fitBoundsCalls.push({ bounds, options });
    }
    zoomBy(delta) {
      this.zoomByCalls.push(delta);
    }
    destroy() {
      this.destroyed = true;
    }
  }
  class MultiMarker {
    constructor(options) {
      this.options = options;
      this.map = options.map;
    }
    setMap(map) {
      this.map = map;
    }
  }
  class MultiPolyline extends MultiMarker {}
  class MarkerStyle {
    constructor(options) {
      this.options = options;
    }
  }
  class PolylineStyle {
    constructor(options) {
      this.options = options;
    }
  }
  return { Map: TencentMap, LatLng, LatLngBounds, MultiMarker, MultiPolyline, MarkerStyle, PolylineStyle };
}

function createTianDiTuSdk() {
  class LngLat {
    constructor(lng, lat) {
      this.lng = lng;
      this.lat = lat;
    }
  }
  class TianDiTuMap {
    constructor(containerId) {
      this.containerId = containerId;
      this.overlays = [];
      this.setViewportCalls = [];
      this.zoomInCalls = 0;
      this.zoomOutCalls = 0;
    }
    centerAndZoom(center, zoom) {
      this.center = center;
      this.zoom = zoom;
    }
    addEventListener(eventName, handler) {
      this.eventName = eventName;
      this.handler = handler;
    }
    addOverLay(overlay) {
      this.overlays.push(overlay);
    }
    removeOverLay(overlay) {
      this.overlays = this.overlays.filter((item) => item !== overlay);
    }
    setMapType(mapType) {
      this.mapType = mapType;
    }
    setViewport(points) {
      this.setViewportCalls.push(points);
    }
    zoomIn() {
      this.zoomInCalls += 1;
    }
    zoomOut() {
      this.zoomOutCalls += 1;
    }
    clearOverLays() {
      this.overlays = [];
    }
  }
  class Marker {
    constructor(position, options = {}) {
      this.position = position;
      this.options = options;
    }
  }
  class Polyline extends Marker {}
  class TileLayer {
    constructor(url, options) {
      this.url = url;
      this.options = options;
    }
  }
  class MapType {
    constructor(layers, name) {
      this.layers = layers;
      this.name = name;
    }
  }
  return { Map: TianDiTuMap, LngLat, Marker, Polyline, TileLayer, MapType };
}

function createBaiduSdk() {
  class Point {
    constructor(lng, lat) {
      this.lng = lng;
      this.lat = lat;
    }
  }
  class BaiduMap {
    constructor(containerId) {
      this.containerId = containerId;
      this.overlays = [];
      this.setViewportCalls = [];
      this.zoomInCalls = 0;
      this.zoomOutCalls = 0;
    }
    centerAndZoom(center, zoom) {
      this.center = center;
      this.zoom = zoom;
    }
    enableScrollWheelZoom(enabled) {
      this.scrollWheelEnabled = enabled;
    }
    addEventListener(eventName, handler) {
      this.eventName = eventName;
      this.handler = handler;
    }
    addOverlay(overlay) {
      this.overlays.push(overlay);
    }
    removeOverlay(overlay) {
      this.overlays = this.overlays.filter((item) => item !== overlay);
    }
    setViewport(points) {
      this.setViewportCalls.push(points);
    }
    zoomIn() {
      this.zoomInCalls += 1;
    }
    zoomOut() {
      this.zoomOutCalls += 1;
    }
    clearOverlays() {
      this.overlays = [];
    }
  }
  class Marker {
    constructor(position) {
      this.position = position;
    }
  }
  class Polyline {
    constructor(points, options) {
      this.points = points;
      this.options = options;
    }
  }
  return { Map: BaiduMap, Point, Marker, Polyline };
}

function createRuntime(provider, options = {}) {
  const source = readFileSync(resolve('scripts/main.new.js'), 'utf8');
  const functionNames = [
    'getActiveMapProvider',
    'getMapProviderDisplayName',
    'getMapProviderConfig',
    'getMapProviderKeyRequirement',
    'showMissingMapProviderKeyModal',
    'ensureActiveMapProviderRuntimeIfNeeded',
    'loadScriptOnce',
    'loadTencentMapOnce',
    'loadTianDiTuMapOnce',
    'loadBaiduMapOnce',
    'loadActiveMapProviderRuntime',
    'getTianDiTuToken',
    'createTianDiTuTileLayer',
    'applyTianDiTuDefaultMapType',
    'destroyProviderMapInstance',
    'getProviderOverlayBucket',
    'clearProviderRunnerMarkers',
    'clearProviderMapOverlays',
    'getProviderMapDefaultZoom',
    'initProviderMap',
    'isCoordinateOutOfChina',
    'transformMapCoordLat',
    'transformMapCoordLng',
    'wgs84ToGcj02',
    'gcj02ToWgs84',
    'gcj02ToBd09',
    'bd09ToGcj02',
    'convertGcj02ToProviderCoordinates',
    'normalizeRouteCoord',
    'isRouteSegmentSeparator',
    'normalizeRouteCoords',
    'splitRouteCoordsIntoDrawableSegments',
    'getProviderMapInstance',
    'fitProviderMapToCoordinates',
    'zoomProviderMap',
    'fitProviderMapToLastRoute',
    'removeProviderOverlayFromMap',
    'escapeProviderSvgText',
    'normalizeProviderMarkerLabel',
    'resolveProviderMarkerColor',
    'createTencentMarkerStyleOptions',
    'updateProviderRunnerMarker',
    'resolveRunnerTargetSequence',
    'addProviderMarker',
    'drawProviderRouteOnMap',
    'getSingleProviderMapContainerIds',
    'estimateProviderCoordDistanceMeters',
    'getProviderMarkerDisplayCoord',
    'findNearestProviderRouteIndex',
    'getProviderRouteProgressStatus',
    'appendProviderRouteProgressSegment',
    'buildProviderRouteProgressSegments',
    'drawProviderTaskOnMap',
    'drawOnMap_signature',
    'updateRunnerPosition',
    'installGenericMapRuntimeGuards',
  ];
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  const document = createDocument();
  const window = {
    APP_CONFIG: {
      map_provider: provider,
      map_providers: {
        amap: { provider: 'amap', display_name: '高德地图', js_key: 'amap-key' },
        tencent: { provider: 'tencent', display_name: '腾讯地图', map_key: 'tencent-key' },
        tianditu: { provider: 'tianditu', display_name: '天地图', token: 'tianditu-token' },
        baidu: { provider: 'baidu', display_name: '百度地图', ak: 'baidu-ak' },
      },
    },
  };
  if (options.preloadSdks !== false) {
    window.TMap = createTencentSdk();
    window.T = createTianDiTuSdk();
    window.BMap = createBaiduSdk();
  }

  const factory = Function('window', 'document', `
    const TMap = window.TMap;
    const T = window.T;
    const BMap = window.BMap;
    let AMAP_API_KEY = 'amap-key';
    let AMapInstance = null;
    let map = null;
    let multiAccountMap = null;
    let mobileTrackMapInstance = null;
    let tencentMapLoadingPromise = null;
    let tiandituMapLoadingPromise = null;
    let baiduMapLoadingPromise = null;
    let providerMapInstances = {};
    let providerMapInstanceProviders = {};
    let providerMapEventsBound = {};
    let providerMapOverlays = {};
    let providerMapLastFitCoords = {};
    let providerRunnerMarkers = {};
    let currentRunData = null;
    let runAccumulatedMs = 0;
    const $ = (id) => document.getElementById(id);
    const MAP_COORD_PI = Math.PI;
    const MAP_COORD_X_PI = Math.PI * 3000.0 / 180.0;
    const MAP_COORD_A = 6378245.0;
    const MAP_COORD_EE = 0.00669342162296594323;
    function logMessage_Info() {}
    function logMessage_Warning() {}
    function logMessage_Error() {}
    function updateDashboard() {}
    ${functionSources.join('\n\n')}
    return {
      initProviderMap,
      addProviderMarker,
      drawProviderRouteOnMap,
      ensureActiveMapProviderRuntimeIfNeeded,
      loadActiveMapProviderRuntime,
      zoomProviderMap,
      fitProviderMapToLastRoute,
      updateProviderRunnerMarker,
      drawOnMap_signature,
      updateRunnerPosition,
      getProviderMapInstance,
      setCurrentRunData: (data) => {
        currentRunData = data;
      },
      getCurrentRunData: () => currentRunData,
      getState: () => ({
        providerMapInstances,
        providerMapOverlays,
        providerMapLastFitCoords,
        providerRunnerMarkers,
      }),
      getDocument: () => document,
      getWindow: () => window,
    };
  `);

  return factory(window, document);
}

function decodeTencentMarkerStyleSvg(marker) {
  const style = marker?.options?.styles?.marker;
  assert.ok(style, 'Tencent markers should include a MarkerStyle named marker');
  assert.match(style.options.src, /^data:image\/svg\+xml;charset=UTF-8,/);
  return decodeURIComponent(style.options.src.split(',')[1] || '');
}

function collectTencentMarkerSvgs(runtime, containerId) {
  return (runtime.getState().providerMapOverlays[containerId] || [])
    .filter((overlay) => overlay?.options?.geometries?.[0]?.styleId === 'marker')
    .map((marker) => decodeTencentMarkerStyleSvg(marker));
}

function findTencentMarkerByTitle(runtime, containerId, title) {
  return (runtime.getState().providerMapOverlays[containerId] || [])
    .find((overlay) => overlay?.options?.geometries?.[0]?.properties?.title === title);
}

test('provider maps initialize and expose marker-only viewport controls without network SDKs', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider);
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    const marker = runtime.addProviderMarker('map-container', { lng: 113.39, lat: 22.52 });
    assert.ok(marker, `${provider} marker should be created`);

    assert.equal(runtime.zoomProviderMap('map-container', 1), true, provider);
    assert.equal(runtime.zoomProviderMap('map-container', -1), true, provider);
    assert.equal(runtime.fitProviderMapToLastRoute('map-container'), true, provider);

    const instance = runtime.getProviderMapInstance('map-container');
    if (provider === 'tencent') {
      assert.deepEqual(instance.zoomByCalls, [1, -1]);
      assert.equal(instance.fitBoundsCalls.length, 1);
      assert.equal(instance.fitBoundsCalls[0].bounds.points.length, 1);
    } else if (provider === 'tianditu') {
      assert.equal(instance.zoomInCalls, 1);
      assert.equal(instance.zoomOutCalls, 1);
      assert.equal(instance.setViewportCalls.length, 1);
      assert.equal(instance.setViewportCalls[0].length, 1);
    } else if (provider === 'baidu') {
      assert.equal(instance.zoomInCalls, 1);
      assert.equal(instance.zoomOutCalls, 1);
      assert.equal(instance.setViewportCalls.length, 1);
      assert.equal(instance.setViewportCalls[0].length, 1);
    }
  }
});

test('provider runner marker updates current position on non-amap maps', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider);
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    const firstMarker = runtime.updateProviderRunnerMarker('map-container', { lng: 113.39, lat: 22.52 });
    const secondMarker = runtime.updateProviderRunnerMarker('map-container', { lng: 113.40, lat: 22.53 });

    assert.ok(firstMarker, `${provider} first runner marker should be created`);
    assert.ok(secondMarker, `${provider} second runner marker should be created`);
    assert.notEqual(firstMarker, secondMarker, `${provider} runner marker should be replaced when position changes`);
    assert.equal(Object.keys(runtime.getState().providerRunnerMarkers).length, 1, provider);
  }
});

test('provider runner marker does not overwrite route fit coordinates', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.drawProviderRouteOnMap('map-container', [
    { lng: 113.39, lat: 22.52 },
    { lng: 113.40, lat: 22.53 },
  ]);
  const before = runtime.getState().providerMapLastFitCoords['map-container'].map((coord) => ({ ...coord }));
  const overlayCountBefore = runtime.getState().providerMapOverlays['map-container'].length;

  runtime.updateProviderRunnerMarker('map-container', { lng: 113.41, lat: 22.54 });
  runtime.updateProviderRunnerMarker('map-container', { lng: 113.42, lat: 22.55 });

  assert.deepEqual(runtime.getState().providerMapLastFitCoords['map-container'], before);
  assert.equal(runtime.getState().providerMapOverlays['map-container'].length, overlayCountBefore);
});

test('tencent provider markers use styled marker geometry for custom labels', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);

  const marker = runtime.addProviderMarker(
    'map-container',
    { lng: 113.39, lat: 22.52 },
    {
      title: '教学楼',
      content: '<div>教学楼</div>',
      anchor: 'bottom-center',
      zIndex: 110,
    },
  );

  assert.ok(marker);
  assert.equal(marker.options.zIndex, 110);
  assert.equal(marker.options.geometries[0].styleId, 'marker');
  assert.equal(marker.options.geometries[0].content, undefined);
  assert.ok(marker.options.styles.marker instanceof runtime.getWindow().TMap.MarkerStyle);
  assert.match(decodeTencentMarkerStyleSvg(marker), /教学楼/);
});

test('tencent single map redraws checkpoint status while preserving current position marker', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 1,
    target_point_names: '教学楼|操场',
    target_points: [
      [113.39, 22.52],
      [113.40, 22.53],
    ],
    run_coords: [
      [113.38, 22.51],
      [113.39, 22.52],
      [113.395, 22.525],
      [113.40, 22.53],
      [113.41, 22.54],
    ],
  });

  const runnerMarker = runtime.updateProviderRunnerMarker('map-container', { lng: 113.385, lat: 22.515 });
  runtime.drawOnMap_signature();

  assert.equal(runtime.getState().providerRunnerMarkers['map-container'], runnerMarker);
  let markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.equal(markerSvgs.some((svg) => svg.includes('起点') || svg.includes('终点')), false);
  assert.ok(markerSvgs.some((svg) => svg.includes('教学楼') && svg.includes('#0284c7')));
  assert.ok(markerSvgs.some((svg) => svg.includes('操场') && svg.includes('#059669')));

  runtime.updateRunnerPosition(113.392, 22.522, 100, 1, 1000);

  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  assert.ok(runtime.getState().providerRunnerMarkers['map-container']);
  markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.some((svg) => svg.includes('教学楼') && svg.includes('#94a3b8')));
  assert.ok(markerSvgs.some((svg) => svg.includes('操场') && svg.includes('#0284c7')));
  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'completed'));
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'active'));
});

test('tencent task route colors completed segments from checkpoint sequence', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    target_point_names: '教学楼|操场',
    target_points: [
      [113.39, 22.52],
      [113.40, 22.53],
    ],
    run_coords: [
      [113.38, 22.51],
      [113.39, 22.52],
      [113.395, 22.525],
      [113.40, 22.53],
    ],
  });

  runtime.drawOnMap_signature();

  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.ok(routeLayer);
  assert.equal(routeLayer.options.styles.completed.options.color, '#94a3b8');
  assert.equal(routeLayer.options.styles.active.options.color, '#ef4444');
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'completed'));
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'active'));
});

test('tencent completed checkpoint marker does not regress on stale position sequence', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    target_point_names: '求知路3|操场',
    target_points: [
      [113.39, 22.52],
      [113.40, 22.53],
    ],
    run_coords: [
      [113.38, 22.51],
      [113.39, 22.52],
      [113.395, 22.525],
      [113.40, 22.53],
    ],
  });
  runtime.drawOnMap_signature();

  runtime.updateRunnerPosition(113.391, 22.521, 100, 0, 1000);

  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  const markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.some((svg) => svg.includes('求知路3') && svg.includes('#94a3b8')));
  assert.equal(markerSvgs.some((svg) => svg.includes('求知路3') && svg.includes('#0284c7')), false);
});

test('tencent mobile single map receives route checkpoints and current position updates', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  assert.equal(runtime.initProviderMap('mobile-map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 1,
    target_point_names: '图书馆|操场',
    target_points: [
      [113.39, 22.52],
      [113.40, 22.53],
    ],
    run_coords: [
      [113.38, 22.51],
      [113.41, 22.54],
    ],
  });

  runtime.drawOnMap_signature();

  let mobileMarkerSvgs = collectTencentMarkerSvgs(runtime, 'mobile-map-container');
  assert.equal(mobileMarkerSvgs.some((svg) => svg.includes('起点') || svg.includes('终点')), false);
  assert.ok(mobileMarkerSvgs.some((svg) => svg.includes('图书馆') && svg.includes('#0284c7')));
  assert.ok(mobileMarkerSvgs.some((svg) => svg.includes('操场') && svg.includes('#059669')));

  runtime.updateRunnerPosition(113.392, 22.522, 100, 1, 1000, true);

  assert.ok(runtime.getState().providerRunnerMarkers['mobile-map-container']);
  mobileMarkerSvgs = collectTencentMarkerSvgs(runtime, 'mobile-map-container');
  assert.ok(mobileMarkerSvgs.some((svg) => svg.includes('图书馆') && svg.includes('#94a3b8')));
  assert.ok(mobileMarkerSvgs.some((svg) => svg.includes('操场') && svg.includes('#0284c7')));
  assert.ok(runtime.getProviderMapInstance('mobile-map-container').fitBoundsCalls.length >= 2);
});

test('tencent task marker display snaps to nearby route without mutating task coordinates', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  const taskData = {
    status: 0,
    target_sequence: 1,
    target_point_names: '求知路3|终点楼',
    target_points: [
      [113.390000, 22.520000],
      [113.400000, 22.530000],
    ],
    run_coords: [
      [113.390000, 22.520000],
      [113.390180, 22.520160],
      [113.399820, 22.529840],
      [113.400000, 22.530000],
    ],
  };
  runtime.setCurrentRunData(taskData);

  runtime.drawOnMap_signature();

  const startMarker = findTencentMarkerByTitle(runtime, 'map-container', '求知路3');
  const endMarker = findTencentMarkerByTitle(runtime, 'map-container', '终点楼');
  assert.ok(startMarker);
  assert.ok(endMarker);
  assert.equal(startMarker.options.geometries[0].position.lng, 113.390180);
  assert.equal(startMarker.options.geometries[0].position.lat, 22.520160);
  assert.equal(endMarker.options.geometries[0].position.lng, 113.399820);
  assert.equal(endMarker.options.geometries[0].position.lat, 22.529840);
  assert.deepEqual(taskData.target_points[0], [113.390000, 22.520000]);
  assert.deepEqual(taskData.target_points[1], [113.400000, 22.530000]);
});

test('initProviderMap renders real map not placeholder for non-amap providers', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];
  for (const provider of providers) {
    const runtime = createRuntime(provider);
    const doc = runtime.getDocument();
    const mapContainer = doc.getElementById('map-container');
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    const containerInner = mapContainer.innerHTML.toLowerCase();
    assert.doesNotMatch(containerInner, /已启用/, provider + ' should not show placeholder');
    assert.doesNotMatch(containerInner, /后端/, provider + ' should not show placeholder');
    assert.ok(runtime.getProviderMapInstance('map-container'), provider + ' map instance should exist');
  }
});


test('provider route drawing stores fit coordinates for subsequent viewport controls', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  const route = runtime.drawProviderRouteOnMap('map-container', [
    { lng: 113.39, lat: 22.52 },
    { lng: 113.40, lat: 22.53 },
  ]);

  assert.ok(route);
  assert.equal(runtime.fitProviderMapToLastRoute('map-container'), true);
  const instance = runtime.getProviderMapInstance('map-container');
  assert.equal(instance.fitBoundsCalls.length, 2);
  assert.equal(instance.fitBoundsCalls[1].bounds.points.length >= 2, true);
});

test('provider runtime loaders inject the active provider sdk script and resolve from callbacks', async () => {
  const cases = [
    {
      provider: 'tencent',
      expectedSrc: 'https://map.qq.com/api/gljs?v=1.exp&key=tencent-key',
      datasetKey: 'qqMapApi',
      installSdk(window) {
        window.TMap = createTencentSdk();
      },
      finish(window, script) {
        script.onload();
        return window.TMap;
      },
    },
    {
      provider: 'tianditu',
      expectedSrc: 'https://api.tianditu.gov.cn/api?v=4.0&tk=tianditu-token',
      datasetKey: 'tiandituApi',
      installSdk(window) {
        window.T = createTianDiTuSdk();
      },
      finish(window, script) {
        script.onload();
        return window.T;
      },
    },
    {
      provider: 'baidu',
      expectedSrc: 'https://api.map.baidu.com/api?v=3.0&ak=baidu-ak&callback=__onBaiduMapApiLoaded',
      datasetKey: 'baiduMapApi',
      installSdk(window) {
        window.BMap = createBaiduSdk();
      },
      finish(window) {
        window.__onBaiduMapApiLoaded();
        return window.BMap;
      },
    },
  ];

  for (const item of cases) {
    const runtime = createRuntime(item.provider, { preloadSdks: false });
    const window = runtime.getWindow();
    const document = runtime.getDocument();

    const runtimePromise = runtime.ensureActiveMapProviderRuntimeIfNeeded('loader-test');
    assert.equal(document.appendedScripts.length, 1, item.provider);
    const script = document.appendedScripts[0];
    assert.equal(script.src, item.expectedSrc, item.provider);
    assert.equal(script.dataset[item.datasetKey], 'true', item.provider);
    assert.equal(window.__genericMapRuntimeGuardsInstalled, true, item.provider);

    item.installSdk(window);
    const expectedRuntime = item.finish(window, script);
    assert.equal(await runtimePromise, true, item.provider);
    assert.equal(await runtime.loadActiveMapProviderRuntime(item.provider), expectedRuntime, item.provider);
  }
});

test('provider runtime loaders reject when sdk globals are missing after script callback', async () => {
  const cases = [
    {
      provider: 'tencent',
      errorPattern: /腾讯地图脚本加载完成但运行时不可用/,
      finish(window, script) {
        script.onload();
      },
    },
    {
      provider: 'tianditu',
      errorPattern: /天地图脚本加载完成但运行时不可用/,
      finish(window, script) {
        script.onload();
      },
    },
    {
      provider: 'baidu',
      errorPattern: /百度地图脚本加载完成但运行时不可用/,
      finish(window) {
        window.__onBaiduMapApiLoaded();
      },
    },
  ];

  for (const item of cases) {
    const runtime = createRuntime(item.provider, { preloadSdks: false });
    const document = runtime.getDocument();
    const window = runtime.getWindow();

    const runtimePromise = runtime.ensureActiveMapProviderRuntimeIfNeeded('loader-missing-sdk-test');
    assert.equal(document.appendedScripts.length, 1, item.provider);
    item.finish(window, document.appendedScripts[0]);

    await assert.rejects(runtimePromise, item.errorPattern, item.provider);

    const retryPromise = runtime.loadActiveMapProviderRuntime(item.provider);
    assert.equal(document.appendedScripts.length, 2, item.provider);
    item.finish(window, document.appendedScripts[1]);
    await assert.rejects(retryPromise, item.errorPattern, item.provider);
  }
});
