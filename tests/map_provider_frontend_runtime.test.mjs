import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function extractFunctionSource(source, functionName) {
  const asyncSignature = `async function ${functionName}(`;
  const syncSignature = `function ${functionName}(`;
  let start = source.indexOf(asyncSignature);
  if (start === -1) {
    start = source.indexOf(syncSignature);
  }
  assert.notEqual(start, -1, `${functionName} should exist in scripts/main.js`);

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

function createDocument(options = {}) {
  const elements = new Map();
  const appendedScripts = [];
  const strictIds = options.strictIds === true;
  const createElementObject = (id = '') => {
    const element = {
      id,
      children: [],
      dataset: {},
      style: {},
      events: [],
      _innerHTML: '',
      appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        if (child.id) {
          elements.set(child.id, child);
        }
        if (child.tagName === 'script') {
          appendedScripts.push(child);
        }
      },
      removeChild(child) {
        this.children = this.children.filter((item) => item !== child);
        child.parentNode = null;
      },
      remove() {
        if (this.parentNode && typeof this.parentNode.removeChild === 'function') {
          this.parentNode.removeChild(this);
        }
      },
      addEventListener(eventName, handler) {
        this.events.push({ eventName, handler });
      },
      removeEventListener(eventName, handler) {
        this.events = this.events.filter((event) => event.eventName !== eventName || event.handler !== handler);
      },
      contains(child) {
        let node = child;
        while (node) {
          if (node === this) return true;
          node = node.parentNode;
        }
        return false;
      },
      classList: {
        add() {},
        remove() {},
      },
    };
    Object.defineProperty(element, 'innerHTML', {
      get() {
        return this._innerHTML;
      },
      set(value) {
        this._innerHTML = String(value || '');
        const idPattern = /id="([^"]+)"/g;
        let match = idPattern.exec(this._innerHTML);
        while (match) {
          const child = createElementObject(match[1]);
          child.parentNode = this;
          elements.set(match[1], child);
          match = idPattern.exec(this._innerHTML);
        }
      },
    });
    return element;
  };
  [
    'map-container',
    'mobile-map-container',
    'multi-map-container',
    'mobile-track-map-container',
  ].forEach((id) => elements.set(id, createElementObject(id)));

  return {
    getElementById(id) {
      if (!elements.has(id)) {
        if (strictIds) {
          return null;
        }
        elements.set(id, createElementObject(id));
      }
      return elements.get(id);
    },
    createElement(tagName) {
      const element = createElementObject('');
      element.tagName = tagName;
      element.async = false;
      element.defer = false;
      element.onload = null;
      element.onerror = null;
      element.src = '';
      return element;
    },
    querySelector() {
      return null;
    },
    events: [],
    addEventListener(eventName, handler) {
      this.events.push({ eventName, handler });
    },
    removeEventListener(eventName, handler) {
      this.events = this.events.filter((event) => event.eventName !== eventName || event.handler !== handler);
    },
    head: createElementObject('head'),
    body: createElementObject('body'),
    appendedScripts,
  };
}

function createTencentSdk(sdkOptions = {}) {
  const DEFAULT_CONTROL_ID = {
    SCALE: 'scale',
    ZOOM: 'zoom',
    ROTATION: 'rotation',
  };
  const CONTROL_POSITION = {
    TOP_LEFT: 'top-left',
    TOP_RIGHT: 'top-right',
    BOTTOM_RIGHT: 'bottom-right',
  };
  const createNativeControlElement = (id) => ({
    id: `tencent-native-${id}`,
    dataset: { tencentNativeControl: id },
    className: `tmap-control tmap-control-${id}`,
    children: [],
    remove() {
      if (this.parentNode && typeof this.parentNode.removeChild === 'function') {
        this.parentNode.removeChild(this);
      }
    },
  });
  const createNativeControl = (id) => ({
    id,
    element: createNativeControlElement(id),
    position: null,
    className: '',
    setPosition(position) {
      this.position = position;
      return this;
    },
    setClassName(className) {
      this.className = className;
      return this;
    },
  });
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
      this.zoom = options.zoom;
      this.fitBoundsCalls = [];
      this.zoomByCalls = [];
      this.events = [];
      this.controls = [];
      this.controlMap = new Map();
      this.removedControlIds = [];
      if (sdkOptions.injectDefaultControls) {
        Object.values(DEFAULT_CONTROL_ID).forEach((id) => {
          const control = createNativeControl(id);
          this.controls.push(control);
          this.controlMap.set(id, control);
          if (container && typeof container.appendChild === 'function') {
            container.appendChild(control.element);
          }
        });
      }
    }
    setCenter(center) {
      this.center = center;
    }
    setZoom(zoom) {
      this.zoom = zoom;
    }
    getZoom() {
      return this.zoom;
    }
    setPitch(pitch) {
      this.pitch = pitch;
    }
    getPitch() {
      return this.pitch;
    }
    setRotation(rotation) {
      this.rotation = rotation;
    }
    getRotation() {
      return this.rotation;
    }
    setViewMode(viewMode) {
      this.viewMode = viewMode;
    }
    setDraggable(draggable) {
      this.draggable = draggable;
    }
    setScrollable(scrollable) {
      this.scrollable = scrollable;
    }
    setPitchable(pitchable) {
      this.pitchable = pitchable;
    }
    setRotatable(rotatable) {
      this.rotatable = rotatable;
    }
    on(eventName, handler) {
      this.events.push({ eventName, handler });
    }
    off(eventName, handler) {
      this.events = this.events.filter((event) => event.eventName !== eventName || event.handler !== handler);
    }
    emit(eventName, payload) {
      this.events.filter((event) => event.eventName === eventName).slice().forEach((event) => event.handler(payload));
    }
    getControl(id) {
      return this.controlMap.get(id) || null;
    }
    removeControl(id) {
      this.removedControlIds.push(id);
      const control = this.controlMap.get(id);
      if (control && control.element && typeof control.element.remove === 'function') {
        control.element.remove();
      }
      this.controls = this.controls.filter((item) => item.id !== id);
      this.controlMap.delete(id);
      return this;
    }
    fitBounds(bounds, options) {
      this.fitBoundsCalls.push({ bounds, options });
    }
    zoomBy(delta) {
      this.zoomByCalls.push(delta);
    }
    destroy() {
      if (sdkOptions.beforeDestroy) sdkOptions.beforeDestroy(this);
      this.destroyed = true;
      if (!sdkOptions.deferDestroyed) this.emit('destroyed');
    }
  }
  class MultiMarker {
    constructor(options) {
      this.options = options;
      this.map = options.map;
      this.geometryUpdateCount = 0;
    }
    setMap(map) {
      this.map = map;
    }
    stopMove() {
      this.moveStopped = true;
    }
    setGeometries(geometries) {
      this.options.geometries = geometries;
      this.geometryUpdateCount += 1;
    }
    updateGeometries(geometries) {
      this.options.geometries = geometries;
      this.geometryUpdateCount += 1;
    }
    setStyles(styles) {
      this.options.styles = styles;
    }
  }
  class MultiPolyline extends MultiMarker {
    destroy() { this.destroyed = true; this.map = null; }
  }
  class MultiLabel extends MultiMarker {
    destroy() { this.destroyed = true; this.map = null; }
  }
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
  return {
    Map: TencentMap,
    LatLng,
    LatLngBounds,
    MultiMarker,
    MultiPolyline,
    MultiLabel,
    MarkerStyle,
    PolylineStyle,
    constants: { DEFAULT_CONTROL_ID, CONTROL_POSITION },
  };
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
      this.events = [];
      this.setViewportCalls = [];
      this.centerAndZoomCalls = [];
      this.zoomInCalls = 0;
      this.zoomOutCalls = 0;
      this.panByCalls = [];
    }
    centerAndZoom(center, zoom) {
      this.center = center;
      this.zoom = zoom;
      this.centerAndZoomCalls.push({ center, zoom });
    }
    addEventListener(eventName, handler) {
      this.eventName = eventName;
      this.handler = handler;
      this.events.push({ eventName, handler });
    }
    on(eventName, handler) {
      this.addEventListener(eventName, handler);
    }
    getZoom() {
      return this.zoom;
    }
    setZoom(zoom) {
      this.zoom = zoom;
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
    setViewport(points, options) {
      this.setViewportCalls.push(points);
      this.setViewportOptions = options;
    }
    zoomIn() {
      this.zoomInCalls += 1;
      this.zoom = Number(this.zoom || 0) + 1;
    }
    zoomOut() {
      this.zoomOutCalls += 1;
      this.zoom = Number(this.zoom || 0) - 1;
    }
    panBy(x, y) {
      this.panByCalls.push({ x, y });
    }
    clearOverLays() {
      this.overlays = [];
    }
  }
  class Marker {
    constructor(position, options = {}) {
      this.position = position;
      this.options = options;
      this.positionUpdateCount = 0;
    }
    setLngLat(position) {
      this.position = position;
      this.positionUpdateCount += 1;
    }
    setIcon(icon) { this.options.icon = icon; }
  }
  class Icon {
    constructor(options = {}) {
      this.options = options;
    }
  }
  class Polyline {
    constructor(points, options = {}) {
      this.position = points;
      this.options = options;
    }
    setLngLats(points) { this.position = points; }
    setColor(color) { this.options.color = color; }
  }
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
  return { Map: TianDiTuMap, LngLat, Marker, Icon, Polyline, TileLayer, MapType };
}

function createBaiduSdk() {
  class Point {
    constructor(lng, lat) {
      this.lng = lng;
      this.lat = lat;
    }
  }
  class BaiduMap {
    constructor(containerId, options = {}) {
      this.containerId = containerId;
      this.options = options;
      this.overlays = [];
      this.controls = [];
      this.events = [];
      this.setViewportCalls = [];
      this.centerAndZoomCalls = [];
      this.zoomInCalls = 0;
      this.zoomOutCalls = 0;
    }
    centerAndZoom(center, zoom) {
      this.center = center;
      this.zoom = zoom;
      this.centerAndZoomCalls.push({ center, zoom });
    }
    enableScrollWheelZoom(enabled) {
      this.scrollWheelEnabled = enabled;
    }
    enableRotateGestures() {
      this.rotateGesturesEnabled = true;
    }
    enableTiltGestures() {
      this.tiltGesturesEnabled = true;
    }
    enableTilt() {
      this.tiltEnabled = true;
    }
    enableRotate() {
      this.rotateEnabled = true;
    }
    addControl(control) {
      this.controls.push(control);
    }
    setTilt(tilt) {
      this.tilt = tilt;
    }
    getTilt() {
      return this.tilt;
    }
    setHeading(heading) {
      this.heading = heading;
    }
    getHeading() {
      return this.heading;
    }
    addEventListener(eventName, handler) {
      this.eventName = eventName;
      this.handler = handler;
      this.events.push({ eventName, handler });
    }
    on(eventName, handler) {
      this.addEventListener(eventName, handler);
    }
    off(eventName, handler) {
      this.events = this.events.filter((event) => event.eventName !== eventName || event.handler !== handler);
    }
    getZoom() {
      return this.zoom;
    }
    setZoom(zoom) {
      this.zoom = zoom;
    }
    addOverlay(overlay) {
      this.overlays.push(overlay);
    }
    removeOverlay(overlay) {
      this.overlays = this.overlays.filter((item) => item !== overlay);
    }
    setViewport(points, options) {
      this.setViewportCalls.push(points);
      this.setViewportOptions = options;
    }
    zoomIn() {
      this.zoomInCalls += 1;
      this.zoom = Number(this.zoom || 0) + 1;
    }
    zoomOut() {
      this.zoomOutCalls += 1;
      this.zoom = Number(this.zoom || 0) - 1;
    }
    clearOverlays() {
      this.overlays = [];
    }
    destroy() { this.destroyed = true; }
  }
  class Marker {
    constructor(position, options = {}) {
      this.position = position;
      this.options = options;
      this.label = null;
      this.positionUpdateCount = 0;
    }
    setPosition(position) {
      this.position = position;
      this.positionUpdateCount += 1;
    }
    setLabel(label) {
      this.label = label;
    }
    setAnimation(animation) { this.animation = animation; }
  }
  class Label {
    constructor(content, options = {}) {
      this.content = content;
      this.options = options;
    }
    setStyle(style) { this.style = style; }
  }
  class Size {
    constructor(width, height) {
      this.width = width;
      this.height = height;
    }
  }
  class Polyline {
    constructor(points, options) {
      this.points = points;
      this.options = options;
    }
    setPath(points) { this.points = points; }
    setStrokeColor(color) { this.options.strokeColor = color; }
  }
  class NavigationControl3D {
    constructor(options = {}) {
      this.options = options;
    }
  }
  return { Map: BaiduMap, Point, Marker, Label, Size, Polyline, NavigationControl3D };
}

function createAmapSdk() {
  class LngLat {
    constructor(lng, lat) {
      this.lng = lng;
      this.lat = lat;
    }
  }
  class AmapMap {
    constructor(container, options) {
      this.container = container;
      this.options = options;
      this.overlays = [];
      this.removedOverlays = [];
      this.fitViewCalls = [];
      this.center = new LngLat(113.390342, 22.527403);
    }
    add(overlayOrOverlays) {
      const overlays = Array.isArray(overlayOrOverlays) ? overlayOrOverlays : [overlayOrOverlays];
      this.overlays.push(...overlays.filter(Boolean));
    }
    remove(overlayOrOverlays) {
      const overlays = Array.isArray(overlayOrOverlays) ? overlayOrOverlays : [overlayOrOverlays];
      this.removedOverlays.push(...overlays.filter(Boolean));
      this.overlays = this.overlays.filter((item) => !overlays.includes(item));
    }
    setFitView(overlays, immediate, padding) {
      this.fitViewCalls.push({ overlays, immediate, padding });
    }
    setZoomAndCenter(zoom, center) {
      this.zoom = zoom;
      this.center = center;
    }
    getCenter() {
      return this.center;
    }
    setCenter(center) {
      this.center = center;
    }
    setStatus(status) {
      this.status = status;
    }
    resize() {
      this.resized = true;
    }
  }
  class Polyline {
    constructor(options) {
      this.options = options;
    }
  }
  class Marker {
    constructor(options) {
      this.options = options;
      this.position = options.position;
      this.hidden = false;
    }
    setPosition(position) {
      this.position = position;
    }
    hide() {
      this.hidden = true;
    }
  }
  return { Map: AmapMap, LngLat, Polyline, Marker, ControlBar: class {} };
}

function createRuntime(provider, options = {}) {
  const source = [
    readFileSync(resolve('scripts/legacy-app-runtime.js'), 'utf8'),
    readFileSync(resolve('scripts/legacy-map-runtime.js'), 'utf8'),
    readFileSync(resolve('scripts/legacy-map-render.js'), 'utf8'),
    readFileSync(resolve('scripts/legacy-multi-accounts.js'), 'utf8'),
    readFileSync(resolve('scripts/main.js'), 'utf8'),
  ].join('\n\n');
  const functionNames = [
    'normalizeSupportedMapProvider',
    'getActiveMapProvider',
    'getMapProviderDisplayName',
    'getMapProviderConfig',
    'getMapProviderKeyRequirement',
    'showMissingMapProviderKeyModal',
    'createMapProviderRuntimeConfigSnapshot',
    'queuePendingMapProviderConfig',
    'getRunningTaskMapProvider',
    'isCurrentPageMapTaskActive',
    'isMapProviderRuntimeSwitchLocked',
    'applyPendingMapProviderConfigIfAny',
    'syncMapProviderConfigFromInitialData',
    'isTaskMapAutoResetExecutionActive',
    'resetTaskMapView',
    'clearTaskMapAutoResetTimer',
    'scheduleTaskMapAutoResetAfterUserInteraction',
    'bindTaskMapSdkInteractionTracking',
    'bindTaskMapUserInteractionTracking',
    'ensureActiveMapProviderRuntimeIfNeeded',
    'loadScriptOnce',
    'loadTencentMapOnce',
    'loadTianDiTuMapOnce',
    'loadBaiduMapOnce',
    'loadActiveMapProviderRuntime',
    'getProviderMapSurfaceId',
    'getProviderMapSurface',
    'clearProviderMapContainerChildren',
    'ensureProviderMapSurface',
    'isElementInsideContainer',
    'findProviderControlOverlayElement',
    'removeElementOrParentOverlay',
    'getTianDiTuToken',
    'createTianDiTuTileLayer',
    'applyTianDiTuDefaultMapType',
    'destroyProviderMapInstance',
    'isCurrentProviderMapInstance',
    'waitForProviderMapDestruction',
    'showProviderMapLifecycleError',
    'rememberProviderMapRedraw',
    'deferProviderMapInitialization',
    'registerProviderMapInstance',
    'getProviderOverlayBucket',
    'clearProviderRunnerMarkers',
    'clearProviderMapOverlays',
    'getProviderMapDefaultZoom',
    'getProviderMapDefaultCenter',
    'applyProviderMapDefaultOrientation',
    'applyProviderMapDefaultView',
    'addBaiduProvider3DControl',
    'getProvider3DViewControlButtonId',
    'getProvider3DViewButtonId',
    'removeProvider3DViewControl',
    'getProvider3DViewNumber',
    'normalizeProvider3DViewRotation',
    'clampProvider3DViewPitch',
    'adjustProvider3DViewOrientation',
    'attachProvider3DViewControlHandler',
    'getProvider3DViewControlMarkup',
    'renderProvider3DViewControlOverlay',
    'ensureProvider3DViewControl',
    'getProviderMapZoomLevelElementId',
    'formatProviderMapZoomLevel',
    'updateProviderMapZoomLabel',
    'bindProviderMapZoomEvent',
    'bindProviderMapZoomSync',
    'enableTianDiTuRightDragPan',
    'configureTencentNativeViewControls',
    'enableProviderMapInteractions',
    'ensureProviderMapContextMenuGuard',
    'initProviderMap',
    'renderMapProviderFrontendPlaceholder',
    'ensureSingleControls',
    'attachSingleControlHandlers',
    'ensureMultiControls',
    'attachMultiControlHandlers',
    'isCoordinateOutOfChina',
    'transformMapCoordLat',
    'transformMapCoordLng',
    'wgs84ToGcj02',
    'gcj02ToWgs84',
    'gcj02ToBd09',
    'bd09ToGcj02',
    'cloneMapCoordinate',
    'convertMapCoordinatesToGcj02',
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
    'createProviderLabelMarkerSvgOptions',
    'updateProviderRunnerMarker',
    'resolveMultiAccountRunnerColor',
    'multi_updateRunnerPosition',
    'multi_removeRunnerMarker',
    'resolveRunnerTargetSequence',
    'addProviderMarker',
    'rememberProviderRouteSegmentOverlays',
    'forgetProviderRouteSegmentOverlays',
    'updateProviderRouteProgressSegmentsInPlace',
    'createProviderProgressPolyline',
    'drawProviderRouteOnMap',
    'getSingleProviderMapContainerIds',
    'appendSingleMapOverlay',
    'collectSingleMapFitOverlays',
    'removeSingleMapOverlay',
    'estimateProviderCoordDistanceMeters',
    'getProviderMarkerDisplayCoord',
    'findNearestProviderRouteIndex',
    'resolveRouteProgressIndex',
    'resolveTaskProgressSequence',
    'resolveVisualTaskProgressSequence',
    'getProviderRouteProgressStatus',
    'resolveProviderRouteSegmentColor',
    'appendProviderRouteProgressSegment',
    'hasActiveRouteProgress',
    'buildProviderRouteProgressSegments',
    'buildProviderRouteProgressSegmentsByProgress',
    'drawProviderTaskOnMap',
    'syncProviderTaskCheckpointMarkers',
    'updateProviderCheckpointMarkerStyle',
    'clearMapOverlays',
    'resetMapView',
    'drawAmapRunRoute',
    'updateTaskProgressSegmentsInPlace',
    'drawMarkers',
    'drawOnMap_signature',
    'ensureRunnerMarker',
    'updateRunnerPosition',
    'clearSingleExecutionVisuals',
    'onRunStopped',
    'installGenericMapRuntimeGuards',
  ];
  const functionSources = functionNames.map((name) => extractFunctionSource(source, name));
  const document = createDocument({ strictIds: options.strictDocumentIds });
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
    BMAP_ANCHOR_TOP_LEFT: 'top-left',
  };
  window.__scheduledTimeouts = [];
  window.setTimeout = (handler, delay) => {
    const id = window.__scheduledTimeouts.length + 1;
    window.__scheduledTimeouts.push({ id, handler, delay, cleared: false });
    return id;
  };
  window.clearTimeout = (id) => {
    const timer = window.__scheduledTimeouts.find((item) => item.id === id);
    if (timer) timer.cleared = true;
  };
  if (options.preloadSdks !== false) {
    window.TMap = createTencentSdk(options.tencentSdkOptions || {});
    window.T = createTianDiTuSdk();
    window.BMap = createBaiduSdk();
    window.BMapGL = createBaiduSdk();
    window.AMap = createAmapSdk();
  }

  const factory = Function('window', 'document', `
    const TMap = window.TMap;
    const T = window.T;
    const BMap = window.BMap;
    const BMapGL = window.BMapGL;
    const BMAP_ANCHOR_TOP_LEFT = window.BMAP_ANCHOR_TOP_LEFT;
    const AMap = window.AMap;
    let AMAP_API_KEY = 'amap-key';
    let AMapInstance = window.APP_CONFIG.map_provider === 'amap' ? window.AMap : null;
    let AMapReady = !!AMapInstance;
    let map = AMapReady ? new AMapInstance.Map(document.getElementById('map-container'), {}) : null;
    let multiAccountMap = null;
    let multiAccountMarkers = {};
    let multiAccountMarkerColors = {};
    const userColors = [
      '#F44336', '#E91E63', '#9C27B0', '#673AB7',
      '#3F51B5', '#2196F3', '#03A9F4', '#00BCD4',
      '#009688', '#4CAF50', '#8BC34A', '#CDDC39',
      '#FFEB3B', '#FFC107', '#FF9800', '#FF5722',
    ];
    let colorIndex = 0;
    let mobileTrackMapInstance = null;
    let tencentMapLoadingPromise = null;
    let tiandituMapLoadingPromise = null;
    let baiduMapLoadingPromise = null;
    let amapLoadingPromise = null;
    let providerMapInstances = {};
    let sessionUUID = 'session-a';
    const providerMapDestructions = {};
    const providerMapPendingInitializations = {};
    let providerMapSurfaceSequence = 0;
    let providerMapInstanceProviders = {};
    let providerMapEventsBound = {};
    let providerMapOverlays = {};
    const providerRouteSegmentOverlays = {};
    let providerMapLastFitCoords = {};
    let providerRunnerMarkers = {};
    let pendingMapProviderRuntimeConfig = null;
    let activeTaskMapProviderLock = null;
    const TASK_MAP_AUTO_RESET_IDLE_MS = 120000;
    let taskMapAutoResetTimer = null;
    let taskMapAutoResetContainerId = "";
    let currentRunData = null;
    let runAccumulatedMs = 0;
    let singleProcessedPoints = 0;
    let singleTotalPoints = 0;
    let backgroundTaskPollInterval = null;
    let backgroundTaskStartTime = 0;
    let singleRunProgressVisualActive = false;
    let polylines = { recommended: [], draft: null, run: null, history: null };
    let amapRouteProgressSegments = null;
    let markers = [];
    let runnerMarker = null;
    let drawingInfoMarker = null;
    const $ = (id) => document.getElementById(id);
    const MAP_COORD_PI = Math.PI;
    const MAP_COORD_X_PI = Math.PI * 3000.0 / 180.0;
    const MAP_COORD_A = 6378245.0;
    const MAP_COORD_EE = 0.00669342162296594323;
    function logMessage_Info() {}
    function logMessage_Warning() {}
    function logMessage_Error() {}
    function updateDashboard() {}
    function updateSingleProgress() {}
    function stopBackgroundTaskPolling() {
      backgroundTaskPollInterval = null;
      backgroundTaskStartTime = 0;
    }
    ${functionSources.join('\n\n')}
    return {
      initProviderMap,
      destroyProviderMapInstance,
      waitForProviderMapDestruction: typeof waitForProviderMapDestruction === 'function' ? waitForProviderMapDestruction : undefined,
      getProviderMapSurface,
      addProviderMarker,
      drawProviderRouteOnMap,
      ensureActiveMapProviderRuntimeIfNeeded,
      loadActiveMapProviderRuntime,
      zoomProviderMap,
      fitProviderMapToLastRoute,
      fitProviderMapToCoordinates,
      updateProviderRouteProgressSegmentsInPlace,
      updateProviderRunnerMarker,
      resolveMultiAccountRunnerColor,
      multi_updateRunnerPosition,
      multi_removeRunnerMarker,
      drawOnMap_signature,
      updateRunnerPosition,
      clearSingleExecutionVisuals,
      onRunStopped,
      syncMapProviderConfigFromInitialData,
      queuePendingMapProviderConfig,
      applyPendingMapProviderConfigIfAny,
      getProviderMapInstance,
      wgs84ToGcj02,
      gcj02ToWgs84,
      convertMapCoordinatesToGcj02,
      convertGcj02ToProviderCoordinates,
      setCurrentRunData: (data) => {
        currentRunData = data;
      },
      setSession: (session) => { sessionUUID = session; },
      setSingleRunProgressVisualActive: (active) => { singleRunProgressVisualActive = active; },
      getCurrentRunData: () => currentRunData,
      getPendingMapProviderRuntimeConfig: () => pendingMapProviderRuntimeConfig,
      getScheduledTimeouts: () => window.__scheduledTimeouts,
      runLastScheduledTimeout: () => {
        const timer = window.__scheduledTimeouts[window.__scheduledTimeouts.length - 1];
        if (timer && !timer.cleared) timer.handler();
      },
      getState: () => ({
        providerMapInstances,
        providerMapOverlays,
        providerMapLastFitCoords,
        providerRunnerMarkers,
        multiAccountMarkers,
        multiAccountMarkerColors,
        map,
        polylines,
        markers,
        runnerMarker,
        singleRunProgressVisualActive,
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

test('legacy destruction invalidates callbacks and detaches events before releasing Tencent resources', async () => {
  let destroyObserved;
  const runtime = createRuntime('tencent', {
    tencentSdkOptions: {
      beforeDestroy(instance) {
        destroyObserved = {
          disposed: instance.__providerDisposed,
          businessEvents: instance.events.filter((event) => event.eventName !== 'destroyed'),
          domEvents: runtime.getDocument().getElementById('map-container').events,
        };
      },
    },
  });
  assert.equal(runtime.initProviderMap('map-container'), true);
  const instance = runtime.getProviderMapInstance('map-container');
  const staleDrag = instance.events.find((event) => event.eventName === 'dragend').handler;
  const staleDom = runtime.getDocument().getElementById('map-container').events.find((event) => event.eventName === 'mousedown').handler;
  runtime.setCurrentRunData({ status: 'running' });
  const TMap = runtime.getWindow().TMap;
  const line = new TMap.MultiPolyline({ map: instance });
  const label = new TMap.MultiLabel({ map: instance });
  const marker = new TMap.MultiMarker({ map: instance });
  runtime.getState().providerMapOverlays['map-container'] = [line, label, marker];
  runtime.destroyProviderMapInstance('map-container');
  assert.equal(destroyObserved.disposed, true);
  assert.equal(destroyObserved.businessEvents.length, 0);
  assert.equal(destroyObserved.domEvents.length, 0);
  assert.equal(line.destroyed, true);
  assert.equal(label.destroyed, true);
  assert.equal(marker.moveStopped, true);
  assert.equal(marker.map, null);
  staleDrag();
  staleDom();
  assert.equal(runtime.getScheduledTimeouts().filter((timer) => !timer.cleared && timer.delay === 120000).length, 0);
  assert.equal(await runtime.waitForProviderMapDestruction('map-container'), true);
});

test('legacy Tencent rebuild waits for destroyed and gives every map a distinct native host', async () => {
  const runtime = createRuntime('tencent', { strictDocumentIds: true, tencentSdkOptions: { deferDestroyed: true } });
  assert.equal(runtime.initProviderMap('map-container'), true);
  const old = runtime.getProviderMapInstance('map-container');
  const oldSurface = runtime.getProviderMapSurface('map-container');
  runtime.destroyProviderMapInstance('map-container');
  assert.equal(runtime.initProviderMap('map-container'), false);
  assert.equal(runtime.getProviderMapInstance('map-container'), undefined);
  assert.equal(oldSurface.parentNode, runtime.getDocument().getElementById('map-container'));
  old.emit('destroyed');
  assert.equal(await runtime.waitForProviderMapDestruction('map-container'), true);
  await Promise.resolve();
  const replacement = runtime.getProviderMapInstance('map-container');
  assert.ok(replacement);
  assert.notEqual(replacement, old);
  assert.notEqual(runtime.getProviderMapSurface('map-container').id, oldSurface.id);
  assert.equal(oldSurface.parentNode, null);
});

test('legacy Tencent destruction timeout keeps old host isolated and reports a retryable failure', async () => {
  const runtime = createRuntime('tencent', { tencentSdkOptions: { deferDestroyed: true } });
  runtime.initProviderMap('map-container');
  const oldSurface = runtime.getProviderMapSurface('map-container');
  runtime.destroyProviderMapInstance('map-container');
  assert.equal(runtime.initProviderMap('map-container'), false);
  const deadline = runtime.getScheduledTimeouts().find((timer) => timer.delay === 5000 && !timer.cleared);
  assert.ok(deadline);
  deadline.handler();
  assert.equal(await runtime.waitForProviderMapDestruction('map-container'), false);
  assert.equal(runtime.initProviderMap('map-container'), false);
  assert.equal(runtime.getProviderMapSurface('map-container'), oldSurface);
  assert.equal(oldSurface.parentNode, runtime.getDocument().getElementById('map-container'));
  assert.match(runtime.getDocument().getElementById('map-container').__providerLifecycleError.textContent, /超时.*重试/);
});

test('legacy pending Tencent rebuild ignores a changed outer container or provider', async () => {
  const runtime = createRuntime('tencent', { tencentSdkOptions: { deferDestroyed: true } });
  runtime.initProviderMap('map-container');
  const old = runtime.getProviderMapInstance('map-container');
  runtime.destroyProviderMapInstance('map-container');
  assert.equal(runtime.initProviderMap('map-container'), false);
  runtime.getWindow().APP_CONFIG.map_provider = 'baidu';
  old.emit('destroyed');
  await runtime.waitForProviderMapDestruction('map-container');
  await Promise.resolve();
  assert.equal(runtime.getProviderMapInstance('map-container'), undefined);
  assert.equal(runtime.initProviderMap('map-container'), true);
  assert.ok(runtime.getProviderMapInstance('map-container') instanceof runtime.getWindow().BMap.Map);
});

test('legacy pending Tencent rebuild ignores a changed session or replaced outer DOM', async () => {
  for (const mutation of ['session', 'container']) {
    const runtime = createRuntime('tencent', { tencentSdkOptions: { deferDestroyed: true } });
    runtime.initProviderMap('map-container');
    const old = runtime.getProviderMapInstance('map-container');
    runtime.destroyProviderMapInstance('map-container');
    assert.equal(runtime.initProviderMap('map-container'), false);
    if (mutation === 'session') runtime.setSession('session-c');
    else {
      const document = runtime.getDocument();
      const original = document.getElementById.bind(document);
      const replacement = document.createElement('div');
      replacement.id = 'map-container';
      document.getElementById = (id) => id === 'map-container' ? replacement : original(id);
    }
    old.emit('destroyed');
    await runtime.waitForProviderMapDestruction('map-container');
    await Promise.resolve();
    assert.equal(runtime.getProviderMapInstance('map-container'), undefined, mutation);
  }
});

test('legacy repeated teardown cancels an already scheduled rebuild', async () => {
  const runtime = createRuntime('tencent', { tencentSdkOptions: { deferDestroyed: true } });
  runtime.initProviderMap('map-container');
  const old = runtime.getProviderMapInstance('map-container');
  runtime.destroyProviderMapInstance('map-container');
  runtime.initProviderMap('map-container');
  runtime.destroyProviderMapInstance('map-container');
  old.emit('destroyed');
  await runtime.waitForProviderMapDestruction('map-container');
  await Promise.resolve();
  assert.equal(runtime.getProviderMapInstance('map-container'), undefined);
});

test('legacy Tencent deferred rebuild restores the most recent route and ignores captured old callbacks', async () => {
  const runtime = createRuntime('tencent', { tencentSdkOptions: { deferDestroyed: true } });
  runtime.initProviderMap('map-container');
  const old = runtime.getProviderMapInstance('map-container');
  const oldZoom = old.events.find((event) => event.eventName === 'zoomend').handler;
  runtime.drawProviderRouteOnMap('map-container', [[113.4, 22.5], [113.41, 22.51]]);
  runtime.destroyProviderMapInstance('map-container');
  runtime.initProviderMap('map-container');
  runtime.drawProviderRouteOnMap('map-container', [[113.5, 22.6], [113.51, 22.61]]);
  old.emit('destroyed');
  await runtime.waitForProviderMapDestruction('map-container');
  await Promise.resolve();
  const replacement = runtime.getProviderMapInstance('map-container');
  assert.notEqual(replacement, old);
  const line = runtime.getState().providerMapOverlays['map-container'].find((overlay) => overlay instanceof runtime.getWindow().TMap.MultiPolyline);
  assert.equal(line.options.geometries[0].paths[0].lng, 113.5);
  const label = runtime.getDocument().getElementById('provider-map-zoom-level-map-container');
  const previous = label.textContent;
  replacement.zoom = 9;
  oldZoom();
  assert.equal(label.textContent, previous);
});

test('legacy automatic Tencent and Baidu route fits disable SDK animation', () => {
  for (const provider of ['tencent', 'baidu']) {
    const runtime = createRuntime(provider);
    runtime.initProviderMap('map-container');
    const instance = runtime.getProviderMapInstance('map-container');
    runtime.fitProviderMapToCoordinates('map-container', [{ lng: 113.4, lat: 22.5 }, { lng: 113.41, lat: 22.51 }]);
    if (provider === 'tencent') assert.equal(instance.fitBoundsCalls.at(-1).options.ease.duration, 0);
    else assert.equal(instance.setViewportOptions.enableAnimation, false);
  }
});

test('legacy map teardown and rebuild keeps route and runner updates isolated across desktop and mobile hosts', async () => {
  const coordinates = Array.from({ length: 20 }, (_, index) => [113.4 + index * 0.0001, 22.5 + index * 0.0001]);
  for (const provider of ['tencent', 'baidu']) {
    for (const containerId of ['map-container', 'mobile-map-container', 'multi-map-container', 'mobile-track-map-container']) {
      const runtime = createRuntime(provider, { strictDocumentIds: true });
      const hostIds = new Set();
      for (let round = 0; round < 3; round += 1) {
        assert.equal(runtime.initProviderMap(containerId, containerId === 'multi-map-container'), true);
        const instance = runtime.getProviderMapInstance(containerId);
        const surface = runtime.getProviderMapSurface(containerId);
        assert.equal(hostIds.has(surface.id), false);
        hostIds.add(surface.id);
        runtime.drawProviderRouteOnMap(containerId, coordinates);
        const route = runtime.getState().providerMapOverlays[containerId][0];
        for (let index = 0; index < 10; index += 1) {
          const marker = runtime.updateProviderRunnerMarker(containerId, coordinates[index]);
          assert.ok(marker);
          assert.equal(runtime.getState().providerMapOverlays[containerId][0], route);
        }
        const runner = runtime.getState().providerRunnerMarkers[containerId];
        runtime.destroyProviderMapInstance(containerId);
        assert.equal(await runtime.waitForProviderMapDestruction(containerId), true);
        assert.equal(instance.destroyed, true);
        assert.equal(instance.events.length, 0);
        assert.equal(surface.events.length, 0);
        assert.equal(surface.parentNode, null);
        assert.equal(runtime.getState().providerMapOverlays[containerId].length, 0);
        assert.equal(runtime.getProviderMapInstance(containerId), undefined);
        if (provider === 'baidu') assert.equal(runner.animation, null);
        else assert.equal(runner.moveStopped, true);
      }
    }
  }
});

test('legacy initialization failure releases the created SDK before replacing its native host with a placeholder', async () => {
  let failedInstance;
  const runtime = createRuntime('tencent', { tencentSdkOptions: { beforeDestroy: (instance) => { failedInstance = instance; } } });
  const container = runtime.getDocument().getElementById('map-container');
  const append = container.appendChild;
  container.appendChild = function (child) {
    if (child.dataset?.providerMapControlOverlay) throw new Error('isolated control creation failure');
    return append.call(this, child);
  };
  assert.equal(runtime.initProviderMap('map-container'), false);
  await runtime.waitForProviderMapDestruction('map-container');
  await Promise.resolve();
  assert.ok(failedInstance?.destroyed);
  assert.equal(failedInstance.__providerSurface.parentNode, null);
  assert.equal(runtime.getProviderMapInstance('map-container'), undefined);
  assert.match(container.innerHTML, /isolated control creation failure/);
});

test('legacy detached single and multi controls cannot change a replacement map', async () => {
  for (const containerId of ['map-container', 'multi-map-container']) {
    const runtime = createRuntime('tencent', { strictDocumentIds: true });
    runtime.initProviderMap(containerId, containerId === 'multi-map-container');
    const buttonId = containerId === 'map-container' ? 'zoom-in' : 'multi-zoom-in';
    const oldButton = runtime.getDocument().getElementById(buttonId);
    const oldClick = oldButton.events.find((event) => event.eventName === 'click').handler;
    runtime.destroyProviderMapInstance(containerId);
    await runtime.waitForProviderMapDestruction(containerId);
    runtime.initProviderMap(containerId, containerId === 'multi-map-container');
    const replacement = runtime.getProviderMapInstance(containerId);
    const zoom = replacement.zoom;
    oldClick();
    assert.equal(replacement.zoom, zoom, containerId);
    assert.equal(oldButton.events.length, 0, containerId);
  }
});

function collectTencentMarkerSvgs(runtime, containerId) {
  return (runtime.getState().providerMapOverlays[containerId] || [])
    .filter((overlay) => overlay?.options?.geometries?.[0]?.styleId === 'marker')
    .map((marker) => decodeTencentMarkerStyleSvg(marker));
}

function decodeProviderDataSvg(src) {
  assert.match(src || '', /^data:image\/svg\+xml;charset=UTF-8,/);
  return decodeURIComponent(String(src).split(',')[1] || '');
}

function findTencentMarkerByTitle(runtime, containerId, title) {
  return (runtime.getState().providerMapOverlays[containerId] || [])
    .find((overlay) => overlay?.options?.geometries?.[0]?.properties?.title === title);
}

function distanceMeters(a, b) {
  const earthRadius = 6378137;
  const toRad = (value) => Number(value) * Math.PI / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
  return 2 * earthRadius * Math.asin(Math.sqrt(h));
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
      assert.deepEqual(instance.zoomByCalls, []);
      assert.equal(instance.zoom, 17);
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

test('gcj02 to wgs84 conversion round-trips provider coordinates within centimeters', () => {
  const runtime = createRuntime('tianditu');
  const samples = [
    { lng: 113.390342, lat: 22.527403 },
    { lng: 116.397128, lat: 39.916527 },
    { lng: 121.4737, lat: 31.2304 },
  ];

  for (const gcj of samples) {
    const wgs = runtime.gcj02ToWgs84(gcj.lng, gcj.lat);
    const roundTrip = runtime.wgs84ToGcj02(wgs.lng, wgs.lat);
    assert.ok(
      distanceMeters(gcj, roundTrip) < 0.02,
      `${JSON.stringify(gcj)} should round-trip within 2cm`,
    );
  }
});

test('tencent provider preserves amap gcj02 coordinates without applying datum offset', () => {
  const runtime = createRuntime('tencent');
  const samples = [
    { lng: 113.390342, lat: 22.527403 },
    { lng: 116.397128, lat: 39.916527 },
    { lng: 121.4737, lat: 31.2304 },
  ];

  assert.equal(runtime.initProviderMap('map-container', false), true);

  for (const gcj of samples) {
    const originalLng = gcj.lng;
    const converted = runtime.convertGcj02ToProviderCoordinates('tencent', gcj);
    assert.notStrictEqual(converted, gcj);
    assert.ok(
      distanceMeters(gcj, converted) < 0.02,
      `Tencent should not offset GCJ-02 input: ${JSON.stringify(gcj)}`,
    );
    const roundTrip = runtime.convertMapCoordinatesToGcj02('tencent', converted);
    assert.notStrictEqual(roundTrip, converted);
    assert.ok(
      distanceMeters(gcj, roundTrip) < 0.02,
      `Tencent GCJ-02 round-trip should remain unchanged: ${JSON.stringify(gcj)}`,
    );

    const convertedFromArray = runtime.convertGcj02ToProviderCoordinates('tencent', [
      gcj.lng,
      gcj.lat,
    ]);
    assert.deepEqual(convertedFromArray, gcj);
    convertedFromArray.lng += 1;
    assert.equal(gcj.lng, originalLng);

    const marker = runtime.addProviderMarker('map-container', gcj, {
      title: `marker-${gcj.lng}`,
      label: `marker-${gcj.lng}`,
    });
    const position = marker.options.geometries[0].position;
    assert.equal(position.lng, gcj.lng);
    assert.equal(position.lat, gcj.lat);
  }
});

test('initProviderMap restores desktop controls after provider map replaces static content', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider, {
      strictDocumentIds: true,
      baiduGlOnly: provider === 'baidu',
    });
    const doc = runtime.getDocument();
    const mapContainer = doc.getElementById('map-container');

    assert.equal(doc.getElementById('zoom-in'), null, provider);
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    const controlOverlay = mapContainer.children.find(
      (child) => String(child.innerHTML).includes('reset-view-btn'),
    );
    assert.ok(controlOverlay, `${provider} should append the top-right reset/zoom controls`);
    assert.match(controlOverlay.className, /top-4 right-3/, provider);
    assert.ok(doc.getElementById('zoom-in'), provider);
    assert.ok(doc.getElementById('zoom-out'), provider);
    assert.ok(doc.getElementById('reset-view-btn'), provider);
  }
});

test('baidu provider initializes v4 BMap with default BD09 and 3d view controls', () => {
  const runtime = createRuntime('baidu', { baiduGlOnly: true });

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const instance = runtime.getProviderMapInstance('map-container');
  assert.ok(instance instanceof runtime.getWindow().BMap.Map);
  assert.equal(runtime.getWindow().BMap.coordType, undefined);
  assert.equal(instance.options.showControls, false);
  assert.equal(instance.options.enableRotate, true);
  assert.equal(instance.options.enableTilt, true);
  assert.equal(instance.options.displayOptions.building, true);
  assert.equal(instance.scrollWheelEnabled, true);
  assert.equal(instance.rotateGesturesEnabled, true);
  assert.equal(instance.tiltGesturesEnabled, true);
  assert.equal(instance.rotateEnabled, true);
  assert.equal(instance.tiltEnabled, true);
  assert.equal(instance.zoom, 18);
  assert.equal(instance.tilt, 55);
  assert.equal(instance.heading, 0);
  const viewControl = instance.controls.find(
    (control) => control instanceof runtime.getWindow().BMap.NavigationControl3D,
  );
  assert.ok(viewControl);
  assert.equal(viewControl.options.anchor, 'top-left');
  assert.equal(viewControl.options.offset.width, 12);
  assert.equal(viewControl.options.offset.height, 12);
});

test('provider maps keep app zoom controls at the amap position', () => {
  const cases = [
    ['baidu', 'showControls'],
  ];

  for (const [provider, optionName] of cases) {
    const runtime = createRuntime(provider, {
      baiduGlOnly: provider === 'baidu',
      strictDocumentIds: true,
    });
    const doc = runtime.getDocument();
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    const instance = runtime.getProviderMapInstance('map-container');
    assert.equal(instance.options[optionName], false, provider);
    const controlOverlay = doc
      .getElementById('map-container')
      .children.find((child) => String(child.innerHTML).includes('reset-view-btn'));
    assert.ok(controlOverlay, provider);
    assert.match(controlOverlay.className, /top-4 right-3/, provider);
    assert.match(controlOverlay.className, /z-\[1000\]/, provider);
  }

  const tencentRuntime = createRuntime('tencent', { strictDocumentIds: true });
  const tencentDoc = tencentRuntime.getDocument();
  assert.equal(tencentRuntime.initProviderMap('map-container', false), true, 'tencent');
  const tencentInstance = tencentRuntime.getProviderMapInstance('map-container');
  assert.equal(tencentInstance.options.showControl, true, 'tencent keeps sdk native view control enabled');
  const tencentControlOverlay = tencentDoc
    .getElementById('map-container')
    .children.find((child) => String(child.innerHTML).includes('reset-view-btn'));
  assert.ok(tencentControlOverlay, 'tencent');
  assert.match(tencentControlOverlay.className, /top-4 right-3/, 'tencent');
  assert.match(tencentControlOverlay.className, /z-\[1000\]/, 'tencent');
});

test('tencent provider removes sdk zoom and scale controls while keeping native rotation', () => {
  const runtime = createRuntime('tencent', {
    strictDocumentIds: true,
    tencentSdkOptions: { injectDefaultControls: true },
  });
  const doc = runtime.getDocument();

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const instance = runtime.getProviderMapInstance('map-container');
  const defaults = runtime.getWindow().TMap.constants.DEFAULT_CONTROL_ID;
  assert.deepEqual(instance.removedControlIds, [defaults.SCALE, defaults.ZOOM]);
  assert.deepEqual(instance.controls.map((control) => control.id), [defaults.ROTATION]);
  assert.equal(
    instance.getControl(defaults.ROTATION).position,
    runtime.getWindow().TMap.constants.CONTROL_POSITION.TOP_LEFT,
  );

  const surface = runtime.getProviderMapSurface('map-container');
  assert.deepEqual(
    surface.children
      .filter((child) => child.dataset?.tencentNativeControl)
      .map((child) => child.dataset.tencentNativeControl),
    [defaults.ROTATION],
  );
});

test('tencent provider zoom label follows sdk zoom changes', () => {
  const runtime = createRuntime('tencent', { strictDocumentIds: true });
  const doc = runtime.getDocument();

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const instance = runtime.getProviderMapInstance('map-container');
  const zoomLabel = doc.getElementById('zoom-level');
  assert.equal(zoomLabel.textContent, '17');

  const zoomEvent = instance.events.find((event) => event.eventName === 'zoom');
  assert.ok(zoomEvent, 'tencent maps should bind sdk zoom events');
  instance.setZoom(18);
  zoomEvent.handler();
  assert.equal(zoomLabel.textContent, '18');
});

test('baidu and tianditu provider zoom labels follow sdk zoom changes', () => {
  const cases = [
    ['baidu', { baiduGlOnly: true }, 18.5, 'zoomend'],
    ['tianditu', {}, 17.5, 'zoomend'],
  ];

  for (const [provider, options, nextZoom, eventName] of cases) {
    const runtime = createRuntime(provider, { ...options, strictDocumentIds: true });
    const doc = runtime.getDocument();

    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    const instance = runtime.getProviderMapInstance('map-container');
    const zoomLabel = doc.getElementById('zoom-level');
    assert.notEqual(zoomLabel.textContent, String(nextZoom), provider);

    const zoomEvent = instance.events.find((event) => event.eventName === eventName);
    assert.ok(zoomEvent, `${provider} maps should bind sdk ${eventName} events`);
    instance.setZoom(nextZoom);
    zoomEvent.handler();
    assert.equal(zoomLabel.textContent, String(nextZoom), provider);
  }
});

test('running background tasks lock map provider and defer newer provider config', () => {
  const runtime = createRuntime('tencent', { strictDocumentIds: true });
  const getAppConfig = () => runtime.getWindow().APP_CONFIG;

  assert.equal(getAppConfig().map_provider, 'tencent');

  runtime.syncMapProviderConfigFromInitialData({
    map_provider: 'baidu',
    map_providers: {
      baidu: { provider: 'baidu', display_name: '百度地图', ak: 'new-baidu-ak' },
    },
    task_status: { status: 'running', map_provider: 'tencent' },
  });

  assert.equal(getAppConfig().map_provider, 'tencent');
  assert.equal(getAppConfig().map_providers.baidu.ak, 'new-baidu-ak');
  assert.equal(runtime.getPendingMapProviderRuntimeConfig().map_provider, 'baidu');

  assert.equal(runtime.applyPendingMapProviderConfigIfAny(), false);
  assert.equal(getAppConfig().map_provider, 'tencent');

  runtime.syncMapProviderConfigFromInitialData({
    task_status: { status: 'stopped' },
  });
  assert.equal(runtime.applyPendingMapProviderConfigIfAny(), true);
  assert.equal(getAppConfig().map_provider, 'baidu');
});

test('legacy initialization accepts either proxy state and preserves it when omitted', () => {
  const runtime = createRuntime('tencent');
  const config = runtime.getWindow().APP_CONFIG;
  runtime.syncMapProviderConfigFromInitialData({ frontend_proxy_enabled: true });
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, true);
  runtime.syncMapProviderConfigFromInitialData({ map_provider: 'tencent' });
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, true);
  runtime.syncMapProviderConfigFromInitialData({ frontend_proxy_enabled: false });
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, false);
  assert.equal(runtime.getWindow().APP_CONFIG.map_providers.tencent.map_key, config.map_providers.tencent.map_key);
});

test('a proxy-only configuration change waits for the running map and retains explicit false', () => {
  const runtime = createRuntime('tencent');
  runtime.getWindow().APP_CONFIG.frontend_proxy_enabled = false;
  assert.equal(runtime.queuePendingMapProviderConfig({ frontend_proxy_enabled: true }), true);
  runtime.setSingleRunProgressVisualActive(true);
  assert.equal(runtime.applyPendingMapProviderConfigIfAny(), false);
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, false);
  runtime.setSingleRunProgressVisualActive(false);
  assert.equal(runtime.applyPendingMapProviderConfigIfAny(), true);
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, true);
  assert.equal(runtime.queuePendingMapProviderConfig({ frontend_proxy_enabled: false }), true);
  assert.equal(runtime.getPendingMapProviderRuntimeConfig().frontend_proxy_enabled, false);
  assert.equal(runtime.applyPendingMapProviderConfigIfAny(), true);
  assert.equal(runtime.getWindow().APP_CONFIG.frontend_proxy_enabled, false);
});

test('syncing sanitized provider config preserves an already hydrated map key', () => {
  const runtime = createRuntime('tencent');
  const getAppConfig = () => runtime.getWindow().APP_CONFIG;

  runtime.syncMapProviderConfigFromInitialData({
    map_provider: 'tencent',
    map_providers: {
      tencent: {
        provider: 'tencent',
        display_name: '腾讯地图',
        coordinate_system: 'gcj02',
        business_coordinate_system: 'gcj02',
      },
    },
  });

  assert.equal(getAppConfig().map_providers.tencent.map_key, 'tencent-key');
});

test('running background tasks without recorded provider preserve current provider', () => {
  const runtime = createRuntime('amap', { strictDocumentIds: true });
  const getAppConfig = () => runtime.getWindow().APP_CONFIG;

  runtime.syncMapProviderConfigFromInitialData({
    map_provider: 'tianditu',
    task_status: { status: 'running' },
  });

  assert.equal(getAppConfig().map_provider, 'amap');
  assert.equal(runtime.getPendingMapProviderRuntimeConfig().map_provider, 'tianditu');
});

test('provider maps initialize SDKs on an isolated surface below app controls', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider, {
      baiduGlOnly: provider === 'baidu',
      strictDocumentIds: true,
    });
    const doc = runtime.getDocument();
    const container = doc.getElementById('map-container');

    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    const surface = runtime.getProviderMapSurface('map-container');
    assert.ok(surface, `${provider} should create an SDK-only map surface`);
    assert.equal(surface.parentNode, container, `${provider} surface should stay inside outer map container`);
    assert.match(surface.className, /absolute/, provider);
    assert.match(surface.className, /inset-0/, provider);

    const instance = runtime.getProviderMapInstance('map-container');
    if (provider === 'tencent') {
      assert.equal(instance.container, surface);
    } else {
      assert.equal(instance.containerId, surface.id);
    }

    const controlOverlay = container.children.find(
      (child) => String(child.innerHTML).includes('reset-view-btn'),
    );
    assert.ok(controlOverlay, `${provider} should keep app controls on the outer container`);
    assert.equal(controlOverlay.parentNode, container, provider);
    assert.notEqual(controlOverlay.parentNode, surface, provider);
  }
});

test('tencent provider keeps the sdk native rotation control at the top left', () => {
  const runtime = createRuntime('tencent', {
    strictDocumentIds: true,
    tencentSdkOptions: { injectDefaultControls: true },
  });
  const doc = runtime.getDocument();

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const instance = runtime.getProviderMapInstance('map-container');
  const defaults = runtime.getWindow().TMap.constants.DEFAULT_CONTROL_ID;
  const rotation = instance.getControl(defaults.ROTATION);
  assert.ok(rotation, 'tencent native rotation control should remain mounted');
  assert.equal(rotation.position, runtime.getWindow().TMap.constants.CONTROL_POSITION.TOP_LEFT);
  assert.deepEqual(instance.removedControlIds, [defaults.SCALE, defaults.ZOOM]);
  assert.equal(instance.options.showControl, true);
  assert.equal(doc.getElementById('provider-3d-view-btn'), null);

  const surface = runtime.getProviderMapSurface('map-container');
  assert.deepEqual(
    surface.children
      .filter((child) => child.dataset?.tencentNativeControl)
      .map((child) => child.dataset.tencentNativeControl),
    [defaults.ROTATION],
  );
});

test('baidu provider uses the sdk native 3d navigation control without app-level custom overlay', () => {
  const runtime = createRuntime('baidu', { baiduGlOnly: true, strictDocumentIds: true });
  const doc = runtime.getDocument();
  const container = doc.getElementById('map-container');

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const instance = runtime.getProviderMapInstance('map-container');
  const viewControl = instance.controls.find(
    (control) => control instanceof runtime.getWindow().BMap.NavigationControl3D,
  );
  assert.ok(viewControl);
  assert.equal(viewControl.options.offset.width, 12);
  assert.equal(viewControl.options.offset.height, 12);
  assert.equal(doc.getElementById('provider-3d-view-btn'), null);
  assert.equal(
    container.children.some((child) => String(child.innerHTML).includes('provider-3d-view-btn')),
    false,
  );
});

test('native 3d providers remove stale app-level custom 3d overlays during init', () => {
  const cases = [
    ['tencent', { tencentSdkOptions: { injectDefaultControls: true } }],
    ['baidu', { baiduGlOnly: true }],
  ];

  for (const [provider, options] of cases) {
    const runtime = createRuntime(provider, { ...options, strictDocumentIds: true });
    const doc = runtime.getDocument();
    const container = doc.getElementById('map-container');
    const staleOverlay = doc.createElement('div');
    staleOverlay.dataset.providerMapViewControl = 'true';
    staleOverlay.className = 'absolute top-4 left-3';
    staleOverlay.innerHTML = `
      <button id="provider-3d-view-btn" title="3D视角">3D</button>
    `;
    container.appendChild(staleOverlay);

    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    assert.equal(staleOverlay.parentNode, null, provider);
    assert.equal(
      container.children.some((child) => String(child.innerHTML).includes('provider-3d-view-btn')),
      false,
      provider,
    );
  }
});

test('tianditu provider supports right-button drag panning on the SDK surface', () => {
  const runtime = createRuntime('tianditu', { strictDocumentIds: true });
  const doc = runtime.getDocument();

  assert.equal(runtime.initProviderMap('map-container', false), true);

  const surface = runtime.getProviderMapSurface('map-container');
  const instance = runtime.getProviderMapInstance('map-container');
  const down = surface.events.find((event) => event.eventName === 'mousedown');
  const move = doc.events.find((event) => event.eventName === 'mousemove');
  const up = doc.events.find((event) => event.eventName === 'mouseup');
  assert.ok(down);
  assert.ok(move);
  assert.ok(up);

  let prevented = 0;
  const eventBase = {
    button: 2,
    preventDefault() {
      prevented += 1;
    },
    stopPropagation() {},
  };
  down.handler({ ...eventBase, clientX: 100, clientY: 100 });
  move.handler({ ...eventBase, clientX: 112, clientY: 92 });
  up.handler({ ...eventBase, clientX: 112, clientY: 92 });

  assert.deepEqual(instance.panByCalls, [{ x: 12, y: -8 }]);
  assert.ok(prevented >= 2);
});

test('fitProviderMapToLastRoute resets provider maps to the default view without a drawn route', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider, { baiduGlOnly: provider === 'baidu' });
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    const instance = runtime.getProviderMapInstance('map-container');

    assert.equal(runtime.fitProviderMapToLastRoute('map-container'), true, provider);

    if (provider === 'tencent') {
      assert.equal(instance.zoom, 17);
      assert.equal(instance.pitch, 55);
      assert.equal(instance.rotation, 0);
      assert.equal(instance.center.lng, 113.390342);
      assert.equal(instance.center.lat, 22.527403);
    } else if (provider === 'tianditu') {
      assert.equal(instance.centerAndZoomCalls.length, 2);
      assert.equal(instance.zoom, 17);
      assert.ok(Math.abs(instance.center.lng - 113.390342) > 0.0001);
      assert.ok(Math.abs(instance.center.lat - 22.527403) > 0.0001);
    } else {
      assert.equal(instance.centerAndZoomCalls.length, 2);
      assert.equal(instance.zoom, 18);
      assert.equal(instance.tilt, 55);
      assert.equal(instance.heading, 0);
    }
  }
});

test('provider maps reset the active task view after two idle minutes following user interaction', () => {
  const cases = [
    ['tencent', 'dragstart', 17],
    ['tianditu', 'dragstart', 17],
    ['baidu', 'dragstart', 18],
  ];

  for (const [provider, eventName, expectedZoom] of cases) {
    const runtime = createRuntime(provider, {
      baiduGlOnly: provider === 'baidu',
      strictDocumentIds: true,
    });

    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    runtime.syncMapProviderConfigFromInitialData({
      task_status: { status: 'running', map_provider: provider },
    });

    const instance = runtime.getProviderMapInstance('map-container');
    instance.setZoom(11);

    const interactionEvent = instance.events.find((event) => event.eventName === eventName);
    assert.ok(interactionEvent, `${provider} should bind sdk interaction events`);
    interactionEvent.handler();

    const timers = runtime.getScheduledTimeouts();
    const timer = timers[timers.length - 1];
    assert.equal(timer.delay, 120000, provider);
    assert.equal(instance.zoom, 11, provider);

    runtime.runLastScheduledTimeout();
    assert.equal(instance.zoom, expectedZoom, provider);
  }
});

test('provider map dom interactions schedule the idle reset during active tasks', () => {
  const cases = [
    ['tencent', 17],
    ['tianditu', 17],
    ['baidu', 18],
  ];

  for (const [provider, expectedZoom] of cases) {
    const runtime = createRuntime(provider, {
      baiduGlOnly: provider === 'baidu',
      strictDocumentIds: true,
    });

    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    runtime.syncMapProviderConfigFromInitialData({
      task_status: { status: 'running', map_provider: provider },
    });

    const instance = runtime.getProviderMapInstance('map-container');
    const container = runtime.getDocument().getElementById('map-container');
    instance.setZoom(11);

    const wheelEvent = container.events.find((event) => event.eventName === 'wheel');
    assert.ok(wheelEvent, `${provider} should bind dom wheel interactions`);
    wheelEvent.handler();

    const timers = runtime.getScheduledTimeouts();
    const timer = timers[timers.length - 1];
    assert.equal(timer.delay, 120000, provider);

    runtime.runLastScheduledTimeout();
    assert.equal(instance.zoom, expectedZoom, provider);
  }
});

test('provider maps suppress the browser context menu so right drag reaches the sdk', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider, { baiduGlOnly: provider === 'baidu' });
    const container = runtime.getDocument().getElementById('map-container');
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
    const contextMenuEvent = container.events.find((event) => event.eventName === 'contextmenu');
    assert.ok(contextMenuEvent, provider);

    let prevented = false;
    contextMenuEvent.handler({
      preventDefault() {
        prevented = true;
      },
    });
    assert.equal(prevented, true, provider);
  }
});

test('provider runner markers update current position in place on non-amap maps', () => {
  const providers = ['tencent', 'tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider);
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);

    const firstMarker = runtime.updateProviderRunnerMarker('map-container', { lng: 113.39, lat: 22.52 });
    const secondMarker = runtime.updateProviderRunnerMarker('map-container', { lng: 113.40, lat: 22.53 });

    assert.ok(firstMarker, `${provider} first runner marker should be created`);
    assert.ok(secondMarker, `${provider} second runner marker should be created`);
    if (provider === 'tencent') {
      assert.equal(firstMarker, secondMarker, 'tencent runner marker should be updated in place');
      assert.equal(firstMarker.map, runtime.getState().providerMapInstances['map-container']);
      assert.equal(firstMarker.geometryUpdateCount, 1);
      assert.equal(firstMarker.options.geometries[0].position.lat, 22.53);
      assert.equal(firstMarker.options.geometries[0].position.lng, 113.40);
      assert.equal(firstMarker.options.geometries[0].id, 'map-container');
    } else {
      assert.equal(firstMarker, secondMarker, `${provider} runner marker should be updated in place`);
      assert.equal(firstMarker.positionUpdateCount, 1);
      assert.ok(firstMarker.position, `${provider} runner marker should keep a position`);
      const expected = runtime.convertGcj02ToProviderCoordinates(provider, { lng: 113.40, lat: 22.53 });
      assert.ok(distanceMeters(firstMarker.position, expected) < 0.001, `${provider} marker setter converts GCJ exactly once`);
    }
    assert.equal(Object.keys(runtime.getState().providerRunnerMarkers).length, 1, provider);
  }
});

test('tencent multi-account runner markers update in place and keep stable colors', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('multi-map-container', true), true);

  runtime.multi_updateRunnerPosition('alice', 113.39, 22.52, 'Alice');
  const firstMarker = runtime.getState().providerRunnerMarkers['multi-map-container:alice'];
  const aliceColor = runtime.resolveMultiAccountRunnerColor('alice');
  assert.ok(firstMarker);

  runtime.multi_updateRunnerPosition('alice', 113.40, 22.53, 'Alice');
  const secondMarker = runtime.getState().providerRunnerMarkers['multi-map-container:alice'];

  assert.equal(secondMarker, firstMarker);
  assert.equal(secondMarker.map, runtime.getState().providerMapInstances['multi-map-container']);
  assert.equal(secondMarker.geometryUpdateCount, 1);
  assert.equal(secondMarker.options.geometries[0].position.lat, 22.53);
  assert.equal(secondMarker.options.geometries[0].position.lng, 113.40);
  assert.equal(secondMarker.options.geometries[0].id, 'multi-map-container:alice');
  assert.equal(runtime.resolveMultiAccountRunnerColor('alice'), aliceColor);

  runtime.multi_updateRunnerPosition('bob', 113.41, 22.54, 'Bob');
  assert.notEqual(runtime.resolveMultiAccountRunnerColor('bob'), aliceColor);
});

test('tianditu and baidu checkpoint markers expose visible point names', () => {
  const providers = ['tianditu', 'baidu'];

  for (const provider of providers) {
    const runtime = createRuntime(provider);
    assert.equal(runtime.initProviderMap('map-container', false), true, provider);
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
        [113.40, 22.53],
      ],
    });

    runtime.drawOnMap_signature();

    const overlays = runtime.getState().providerMapOverlays['map-container'] || [];
    if (provider === 'tianditu') {
      const marker = overlays.find((overlay) => overlay?.options?.title === '教学楼');
      assert.ok(marker, 'tianditu marker should retain title metadata');
      assert.match(
        decodeProviderDataSvg(marker.options.icon?.options?.iconUrl),
        /教学楼/,
      );
    } else {
      const marker = overlays.find((overlay) => overlay?.options?.title === '教学楼');
      assert.ok(marker, 'baidu marker should retain title metadata');
      assert.match(marker.label?.content || '', /教学楼/);
    }
  }
});

test('amap execution route keeps a single current segment', () => {
  const runtime = createRuntime('amap');
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 1,
    current_point_index: 3,
    target_point_names: '点1|点2|点3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.395, 22.525],
      [113.400, 22.530],
    ],
  });

  runtime.updateRunnerPosition(113.385, 22.515, 100, 1, 1000, false, 3);

  const runPolylines = runtime.getState().polylines.run;
  assert.ok(Array.isArray(runPolylines));
  const colors = runPolylines.map((polyline) => polyline.options.strokeColor);
  assert.equal(colors.filter((color) => color === '#0284c7').length, 1);
  assert.ok(colors.includes('#94a3b8'));
  assert.ok(colors.includes('#ef4444'));
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
  const originalCheckpoint = findTencentMarkerByTitle(runtime, 'map-container', '教学楼');
  const originalRoute = runtime.getState().providerMapOverlays['map-container'].find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.equal(markerSvgs.some((svg) => svg.includes('起点') || svg.includes('终点')), false);
  assert.ok(markerSvgs.some((svg) => svg.includes('教学楼') && svg.includes('#059669')));
  assert.ok(markerSvgs.some((svg) => svg.includes('操场') && svg.includes('#059669')));

  runtime.updateRunnerPosition(113.392, 22.522, 100, 1, 1000);

  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  assert.equal(findTencentMarkerByTitle(runtime, 'map-container', '教学楼'), originalCheckpoint);
  assert.ok(runtime.getState().providerMapOverlays['map-container'].includes(originalRoute));
  assert.ok(runtime.getState().providerRunnerMarkers['map-container']);
  markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.some((svg) => svg.includes('教学楼') && svg.includes('#94a3b8')));
  assert.ok(markerSvgs.some((svg) => svg.includes('操场') && svg.includes('#0284c7')));
  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'completed'));
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'current'));
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

  runtime.updateRunnerPosition(113.395, 22.525, 100, 1, 1000, false, 3);

  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.ok(routeLayer);
  assert.equal(routeLayer.options.styles.completed.options.color, '#94a3b8');
  assert.equal(routeLayer.options.styles.current.options.color, '#0284c7');
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'completed'));
  assert.ok(routeLayer.options.geometries.some((geometry) => geometry.styleId === 'current'));
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
  runtime.updateRunnerPosition(113.391, 22.521, 100, 0, 1000);

  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  const markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.some((svg) => svg.includes('求知路3') && svg.includes('#94a3b8')));
  assert.equal(markerSvgs.some((svg) => svg.includes('求知路3') && svg.includes('#0284c7')), false);
});

test('tencent checkpoint and route progress follow executed route index when sequence lags', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    current_point_index: 6,
    target_point_names: '求知路1|南门3|田径场3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.395, 22.525],
      [113.400, 22.530],
      [113.405, 22.535],
    ],
  });

  runtime.updateRunnerPosition(113.400, 22.530, 100, 1, 1000, false, 6);

  const markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.some((svg) => svg.includes('南门3') && svg.includes('#94a3b8')));
  assert.ok(markerSvgs.some((svg) => svg.includes('田径场3') && svg.includes('#0284c7')));
  assert.equal(markerSvgs.some((svg) => svg.includes('南门3') && svg.includes('#0284c7')), false);
  assert.equal(markerSvgs.some((svg) => svg.includes('田径场3') && svg.includes('#059669')), false);

  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  const completedSegment = routeLayer.options.geometries.find((geometry) => geometry.styleId === 'completed');
  const currentSegment = routeLayer.options.geometries.find((geometry) => geometry.styleId === 'current');
  assert.ok(completedSegment);
  assert.ok(currentSegment);
  assert.equal(completedSegment.paths.at(-1).lng, 113.400);
  assert.equal(currentSegment.paths[0].lng, 113.400);
  assert.equal(routeLayer.options.styles.current.options.color, '#0284c7');
});

test('route progress advances past checkpoint boundaries and ends with a completed route', () => {
  const cases = [
    {
      pointIndex: 2,
      targetSequence: 0,
      expected: [
        { styleId: 'completed', longitudes: [113.375, 113.380] },
        { styleId: 'current', longitudes: [113.380, 113.385, 113.390] },
        { styleId: 'active', longitudes: [113.390, 113.395] },
      ],
    },
    {
      pointIndex: 4,
      targetSequence: 1,
      expected: [
        { styleId: 'completed', longitudes: [113.375, 113.380, 113.385, 113.390] },
        { styleId: 'current', longitudes: [113.390, 113.395] },
      ],
    },
    {
      pointIndex: 5,
      targetSequence: 2,
      expected: [
        { styleId: 'completed', longitudes: [113.375, 113.380, 113.385, 113.390, 113.395] },
      ],
    },
  ];

  for (const { pointIndex, targetSequence, expected } of cases) {
    const runtime = createRuntime('tencent');
    assert.equal(runtime.initProviderMap('map-container', false), true);
    const route = [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.395, 22.525],
    ];
    runtime.setCurrentRunData({
      status: 0,
      target_sequence: targetSequence + 1,
      target_points: [[113.380, 22.510], [113.390, 22.520]],
      run_coords: route,
    });

    const [lng, lat] = route[pointIndex - 1];
    runtime.updateRunnerPosition(lng, lat, 100, targetSequence, 1000, false, pointIndex);

    const routeLayer = runtime.getState().providerMapOverlays['map-container']
      .find((overlay) => overlay.options?.id === 'provider-route-map-container');
    assert.ok(routeLayer, `route should exist at point ${pointIndex}`);
    assert.deepEqual(
      routeLayer.options.geometries.map((geometry) => ({
        styleId: geometry.styleId,
        longitudes: geometry.paths.map((point) => point.lng),
      })),
      expected,
      `segments should meet at point ${pointIndex} and cover the full route`,
    );
    const runner = runtime.getState().providerRunnerMarkers['map-container'];
    assert.equal(runner.options.geometries[0].position.lng, lng);
    assert.equal(runner.options.geometries[0].position.lat, lat);
  }
});

test('generic provider task route colors completed segments from executed route index', () => {
  const runtime = createRuntime('baidu');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    current_point_index: 4,
    target_point_names: '点1|点2|点3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
  });

  runtime.updateRunnerPosition(113.390, 22.520, 100, 1, 1000, false, 4);

  const routePolylines = runtime
    .getState()
    .providerMapOverlays['map-container']
    .filter((overlay) => Array.isArray(overlay.points));
  assert.ok(routePolylines.length >= 2);
  assert.equal(routePolylines[0].options.strokeColor, '#94a3b8');
  assert.ok(routePolylines.some((polyline) => polyline.options.strokeColor === '#0284c7'));
});

test('amap run route uses progress colors while execution is active', () => {
  const runtime = createRuntime('amap');
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    current_point_index: 4,
    target_point_names: '点1|点2|点3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.400, 22.530],
      [113.405, 22.535],
    ],
  });

  runtime.updateRunnerPosition(113.390, 22.520, 100, 1, 1000, false, 4);

  const runPolylines = runtime.getState().polylines.run;
  assert.ok(Array.isArray(runPolylines));
  const colors = runPolylines.map((polyline) => polyline.options.strokeColor);
  assert.ok(colors.includes('#94a3b8'));
  assert.ok(colors.includes('#0284c7'));
  assert.ok(colors.includes('#ef4444'));
  assert.equal(runtime.getState().map.overlays.includes(runtime.getState().runnerMarker), true);
});

test('stopping execution resets provider map visuals without clearing realtime state', () => {
  const runtime = createRuntime('tencent');
  assert.equal(runtime.initProviderMap('map-container', false), true);
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    current_point_index: 4,
    current_position: { lng: 113.390, lat: 22.520 },
    target_point_names: '点1|点2|点3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
  });

  runtime.updateRunnerPosition(113.390, 22.520, 100, 1, 1000, false, 4);
  assert.ok(runtime.getState().providerRunnerMarkers['map-container']);

  runtime.onRunStopped();

  assert.deepEqual(runtime.getCurrentRunData().current_position, { lng: 113.390, lat: 22.520 });
  assert.equal(runtime.getCurrentRunData().current_point_index, 4);
  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  assert.equal(Object.keys(runtime.getState().providerRunnerMarkers).length, 0);
  const routeLayer = runtime
    .getState()
    .providerMapOverlays['map-container']
    .find((overlay) => overlay.options?.id === 'provider-route-map-container');
  assert.ok(routeLayer);
  assert.equal(routeLayer.options.styles.route.options.color, '#ef4444');
  assert.ok(routeLayer.options.geometries.every((geometry) => geometry.styleId === 'route'));
  const markerSvgs = collectTencentMarkerSvgs(runtime, 'map-container');
  assert.ok(markerSvgs.every((svg) => !svg.includes('#94a3b8') && !svg.includes('#0284c7')));
  assert.equal(runtime.getState().singleRunProgressVisualActive, false);
});

test('stopping execution resets amap visuals without clearing realtime state', () => {
  const runtime = createRuntime('amap');
  runtime.setCurrentRunData({
    status: 0,
    target_sequence: 2,
    current_point_index: 4,
    current_position: { lng: 113.390, lat: 22.520 },
    target_point_names: '点1|点2|点3',
    target_points: [
      [113.380, 22.510],
      [113.390, 22.520],
      [113.400, 22.530],
    ],
    run_coords: [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.400, 22.530],
      [113.405, 22.535],
    ],
  });

  runtime.updateRunnerPosition(113.390, 22.520, 100, 1, 1000, false, 4);
  assert.ok(runtime.getState().runnerMarker);

  runtime.onRunStopped();

  assert.deepEqual(runtime.getCurrentRunData().current_position, { lng: 113.390, lat: 22.520 });
  assert.equal(runtime.getCurrentRunData().current_point_index, 4);
  assert.equal(runtime.getCurrentRunData().target_sequence, 2);
  assert.equal(runtime.getState().runnerMarker, null);
  const runPolylines = runtime.getState().polylines.run;
  assert.ok(Array.isArray(runPolylines));
  assert.equal(runPolylines.length, 1);
  assert.equal(runPolylines[0].options.strokeColor, '#ef4444');
  assert.deepEqual(
    runPolylines[0].options.path.map((point) => [point.lng, point.lat]),
    [
      [113.375, 22.505],
      [113.380, 22.510],
      [113.385, 22.515],
      [113.390, 22.520],
      [113.400, 22.530],
      [113.405, 22.535],
    ],
  );
  assert.ok(runtime.getState().markers.every((marker) => marker.options.content.includes('bg-emerald-600')));
  assert.equal(runtime.getState().singleRunProgressVisualActive, false);
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
  assert.ok(mobileMarkerSvgs.some((svg) => svg.includes('图书馆') && svg.includes('#059669')));
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

test('legacy route updates keep provider coordinates, overlays and viewport stable across progress boundaries', () => {
  const route = Array.from({ length: 7 }, (_, i) => [113.390 + i * 0.001, 22.520]);
  for (const provider of ['baidu', 'tianditu', 'tencent']) {
    const runtime = createRuntime(provider);
    assert.equal(runtime.initProviderMap('map-container'), true);
    runtime.setSingleRunProgressVisualActive(true);
    const original = structuredClone(route);
    const line = runtime.drawProviderRouteOnMap('map-container', route, { showEndpoints: false });
    const instance = runtime.getProviderMapInstance('map-container');
    const fitCount = provider === 'tencent' ? instance.fitBoundsCalls.length : instance.setViewportCalls.length;
    const firstLine = Array.isArray(line) ? line[0] : line;
    const data = { status: 0, current_point_index: 3, run_coords: route, target_points: [route[0], route[4], route[6]] };
    assert.equal(runtime.updateProviderRouteProgressSegmentsInPlace('map-container', data), true, provider);
    assert.ok(runtime.getState().providerMapOverlays['map-container'].includes(firstLine), `${provider} retains first line`);
    const lines = runtime.getState().providerMapOverlays['map-container'];
    const current = provider === 'tencent'
      ? line.options.geometries.find((segment) => segment.styleId === 'current').paths
      : (provider === 'baidu'
          ? lines.find((segment) => segment.options.strokeColor === '#0284c7').points
          : lines.find((segment) => segment.options.color === '#0284c7').position);
    const expected = runtime.convertGcj02ToProviderCoordinates(provider, { lng: route[2][0], lat: route[2][1] });
    assert.ok(distanceMeters(current[0], expected) < 0.001, `${provider} progress setter converts GCJ once`);
    assert.equal(runtime.updateProviderRouteProgressSegmentsInPlace('map-container', { ...data, current_point_index: 7 }), true, provider);
    const differentRoute = route.map(([lng, lat]) => [lng + 0.01, lat]);
    assert.equal(runtime.updateProviderRouteProgressSegmentsInPlace('map-container', { ...data, run_coords: differentRoute }), false, `${provider} refuses another task geometry`);
    assert.deepEqual(route, original, `${provider} does not alter execution coordinates`);
    assert.equal(provider === 'tencent' ? instance.fitBoundsCalls.length : instance.setViewportCalls.length, fitCount, `${provider} preserves viewport`);
  }
});

test('provider viewport accepts business GCJ coordinates and never converts cached fit coordinates twice', () => {
  for (const provider of ['baidu', 'tianditu']) {
    const runtime = createRuntime(provider);
    runtime.initProviderMap('map-container');
    const coord = { lng: 113.390342, lat: 22.527403 };
    const expected = runtime.convertGcj02ToProviderCoordinates(provider, coord);
    runtime.fitProviderMapToCoordinates('map-container', [coord]);
    runtime.addProviderMarker('map-container', coord);
    runtime.fitProviderMapToLastRoute('map-container');
    for (const points of runtime.getProviderMapInstance('map-container').setViewportCalls) {
      assert.ok(distanceMeters(points[0], expected) < 0.001, `${provider} converts viewport boundary exactly once`);
    }
  }
});

test('legacy progress keeps route separator gaps and declines unsupported SDK setters', () => {
  const route = [[113.39, 22.52], [113.391, 22.52], [0, 0], [113.40, 22.53], [113.401, 22.53]];
  const runtime = createRuntime('baidu');
  runtime.initProviderMap('map-container');
  runtime.setSingleRunProgressVisualActive(true);
  const lines = runtime.drawProviderRouteOnMap('map-container', route, { showEndpoints: false });
  const data = { status: 0, current_point_index: 4, run_coords: route, target_points: [route[0], route[4]] };
  assert.equal(runtime.updateProviderRouteProgressSegmentsInPlace('map-container', data), true);
  for (const line of runtime.getState().providerMapOverlays['map-container'].filter((overlay) => overlay.points)) {
    for (let index = 1; index < line.points.length; index += 1) {
      assert.ok(distanceMeters(line.points[index - 1], line.points[index]) < 500, 'must not bridge separator or draw zero coordinate');
    }
  }
  lines[0].setPath = undefined;
  assert.equal(runtime.updateProviderRouteProgressSegmentsInPlace('map-container', data), false);
});

test('legacy baidu and tianditu checkpoints keep identity and update color when execution starts', () => {
  const route = Array.from({ length: 7 }, (_, i) => [113.390 + i * 0.001, 22.520]);
  for (const provider of ['baidu', 'tianditu']) {
    const runtime = createRuntime(provider);
    runtime.initProviderMap('map-container');
    runtime.setCurrentRunData({ status: 0, run_coords: route, target_points: [route[0], route[4], route[6]], target_point_names: '起始楼|运动场|终点楼' });
    runtime.drawOnMap_signature();
    const original = runtime.getState().providerMapOverlays['map-container'].find((overlay) => overlay.options.title === '起始楼');
    runtime.updateRunnerPosition(route[2][0], route[2][1], 100, 1, 1000, false, 3);
    const updated = runtime.getState().providerMapOverlays['map-container'].find((overlay) => overlay.options.title === '起始楼');
    assert.equal(updated, original, provider);
    if (provider === 'baidu') assert.equal(updated.label.style.backgroundColor, '#94a3b8');
    else assert.match(decodeURIComponent(updated.options.icon.options.iconUrl), /#94a3b8/);
  }
});

test('legacy SDK loading times out and can be retried without accepting BMapGL as v4', async () => {
  const runtime = createRuntime('baidu', { preloadSdks: false });
  runtime.getWindow().BMapGL = createBaiduSdk();
  const first = runtime.loadActiveMapProviderRuntime('baidu');
  assert.equal(runtime.getDocument().appendedScripts.length, 1);
  const rejected = assert.rejects(first, /超时/);
  runtime.runLastScheduledTimeout();
  await rejected;
  const second = runtime.loadActiveMapProviderRuntime('baidu');
  assert.equal(runtime.getDocument().appendedScripts.length, 2);
  runtime.getWindow().BMap = createBaiduSdk();
  runtime.getWindow().__onBaiduMapApiLoaded();
  assert.equal(await second, runtime.getWindow().BMap);
});

test('legacy tianditu teardown removes document drag listeners before another SDK takes the surface', () => {
  const runtime = createRuntime('tianditu');
  runtime.initProviderMap('map-container');
  const document = runtime.getDocument();
  assert.ok(document.events.some((event) => event.eventName === 'mousemove'));
  runtime.destroyProviderMapInstance('map-container');
  assert.ok(document.events.every((event) => event.eventName !== 'mousemove' && event.eventName !== 'mouseup'));
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
      expectedSrc: 'https://api.map.baidu.com/api?v=4.0&ak=baidu-ak&callback=__onBaiduMapApiLoaded',
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
