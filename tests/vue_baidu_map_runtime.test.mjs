import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '../frontend/node_modules/@vue/compiler-sfc/dist/compiler-sfc.esm-browser.js'
import { ref, shallowRef, markRaw, computed } from '../frontend/node_modules/vue/dist/vue.esm-browser.prod.js'
import * as coordinates from '../frontend/src/utils/coordinates.js'
import * as routeProgress from '../frontend/src/utils/routeProgress.js'

function createRuntime({ proxyInitialize, documentOverride, provider = 'baidu', deferredDestroy = false, deferredTencentIdle = false, timers = {}, browserWindow } = {}) {
  const created = []
  const removed = []
  const listeners = new Map()
  const mapInstances = []
  const lifecycle = []
  class Point { constructor(lng, lat) { this.lng = lng; this.lat = lat } }
  class Label {
    constructor(content) { this.content = content }
    setStyle(style) { this.style = style }
    setContent(content) { this.content = content }
  }
  class Marker {
    constructor(point, options) { this.point = point; this.options = options; created.push(this) }
    setPosition(point) { this.point = point }
    setTitle(title) { this.title = title }
    setLabel(label) { this.label = label }
    getLabel() { return this.label }
    setIcon(icon) { this.icon = icon }
  }
  class Polyline {
    constructor(path, options) { this.path = path; this.options = options; created.push(this) }
    setPath(path) { this.path = path }
  }
  const sdk = { Point, Marker, Polyline, Label, coordType: null }
  class MapInstance {
    constructor(host) { this.host = host; this.overlays = []; this.coordTypeAtCreation = sdk.coordType; this.zoom = 18; this.events = new Map(); mapInstances.push(this) }
    centerAndZoom(point, zoom) { this.center = point; this.zoom = zoom }
    enableScrollWheelZoom() {}
    addEventListener(event, callback) { listeners.set(event, callback) }
    removeEventListener(event, callback) { if (listeners.get(event) === callback) listeners.delete(event) }
    addOverlay(overlay) { this.overlays.push(overlay) }
    removeOverlay(overlay) { lifecycle.push('remove-overlay'); removed.push(overlay); this.overlays = this.overlays.filter(value => value !== overlay) }
    clearOverlays() { removed.push(...this.overlays); this.overlays = [] }
    getViewport(points) { return { center: points[0], zoom: this.zoom } }
    setViewport(points, options) { this.viewportPoints = points; this.viewportOptions = options }
    getZoom() { return this.zoom }
    on(event, callback) { this.events.set(event, callback) }
    off(event, callback) { if (this.events.get(event) === callback) this.events.delete(event) }
    fitBounds(bounds, options) { this.fitOptions = options }
    destroy() { lifecycle.push('destroy-map'); this.destroyed = true; if (!deferredDestroy) this.events.get('destroyed')?.() }
  }
  class TencentMapInstance extends MapInstance {
    constructor(...args) {
      super(...args)
      if (!deferredTencentIdle) queueMicrotask(() => this.events.get('idle')?.())
    }
  }
  sdk.Map = MapInstance
  const app = {
    selectedTaskIndex: 0, isRunning: false,
    runData: {
      task_index: 0,
      run_coords: [[113.39, 22.52, 1000], [113.391, 22.52, 1000], [113.392, 22.52, 1000], [113.393, 22.52, 1000], [113.394, 22.52, 1000]],
      target_points: [[113.39, 22.52], [113.392, 22.52], [113.394, 22.52]],
      target_point_names: '起点|中点|终点',
    },
  }
  const store = { map: null, activeProvider: provider, mapConfig: { baiduKey: 'test-ak', tencentKey: 'test-key' }, isDrawing: false, draftPoints: [],
    get mapInstance() { return this.map },
    setMapInstance(value) { this.map = value }, addDraftPoint(point) { this.draftPoints.push(point) },
  }
  const auth = {
    sessionUUID: '11111111-1111-4111-8111-111111111111',
    getSessionHeaderValue() { return this.sessionUUID },
    getAdminOriginHeaderValue() { return '' },
  }
  const unmount = []
  const beforeUnmount = []
  const elements = new Map()
  const makeElement = () => ({ style: {}, children: [],
    appendChild(child) { child.parentNode = this; this.children.push(child); elements.set(child.id, child) },
    remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(child => child !== this); this.parentNode = null },
  })
  elements.set('map', makeElement())
  elements.set('tencent-map-sdk', { src: 'https://map.qq.com/api/gljs?v=1.exp&key=test-key', dataset: { loaded: 'true' } })
  class TencentMarker {
    constructor(options) { this.options = options; this.map = options.map; created.push(this) }
    stopMove() { lifecycle.push('stop-marker') }
    setMap(value) { lifecycle.push('detach-marker'); this.map = value }
  }
  class TencentLine {
    constructor(options) { this.options = options; this.map = options.map; created.push(this) }
    setMap(value) { this.map = value }
    destroy() { lifecycle.push('destroy-line'); this.map = null }
  }
  const source = readFileSync(new URL('../frontend/src/components/map/MapContainer.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'baidu-runtime', genDefaultAs: 'component' }).content
  const dependencies = {
    ref, shallowRef, markRaw, watch() {}, onMounted() {}, onBeforeUnmount(callback) { beforeUnmount.push(callback); unmount.push(callback) }, onUnmounted(callback) { unmount.push(callback) }, nextTick: async () => {},
    useMapStore: () => store, useAppStore: () => app, useAuthStore: () => auth,
    MapPlaceholder: {}, MapControls: {}, window: browserWindow || { BMap: sdk, BMAP_COORD_GCJ02: 2,
      TMap: { Map: TencentMapInstance, LatLng: class { constructor(lat, lng) { this.lat = lat; this.lng = lng } },
        LatLngBounds: class { extend() {} }, MultiMarker: TencentMarker, MultiPolyline: TencentLine, PolylineStyle: class {} },
      ...(proxyInitialize ? { ZXMapRequestProxy: { initialize: proxyInitialize } } : {}),
    },
    BMAP_COORD_GCJ02: 2,
    ...coordinates, ...routeProgress,
    document: documentOverride || { getElementById: id => elements.get(id) || null, createElement: () => Object.assign(makeElement(), { textContent: '', outerHTML: '<span>点</span>' }) },
    setTimeout, clearTimeout, ...timers, console,
  }
  const setup = new Function(...Object.keys(dependencies), `${script.replace(/^import .*$/gm, '')}\nreturn component.setup`)(...Object.values(dependencies))
  const panel = setup({ containerId: 'map', isMultiAccount: false }, { expose() {} })
  return { panel, app, store, sdk, created, removed, listeners, unmount, beforeUnmount, mapInstances, lifecycle, elements, window: dependencies.window }
}

test('map cleanup begins before the native host is removed and late events cannot read another instance', async () => {
  const runtime = createRuntime()
  await runtime.panel.initBaidu()
  const map = runtime.store.map
  const lateZoom = runtime.listeners.get('zoomend')
  assert.equal(runtime.beforeUnmount.length, 1)
  runtime.beforeUnmount[0]()
  assert.equal(map.destroyed, true)
  assert.doesNotThrow(() => lateZoom())
  assert.equal(runtime.store.map, null)
})

test('Tencent recreation waits for destroyed and uses a distinct native host', async () => {
  const runtime = createRuntime({ provider: 'tencent', deferredDestroy: true })
  await runtime.panel.initTencent()
  const oldMap = runtime.store.map
  const next = runtime.panel.initMap()
  await Promise.resolve()
  assert.equal(runtime.mapInstances.length, 1, 'old native map must finish destruction first')
  oldMap.events.get('destroyed')?.()
  await next
  assert.equal(runtime.mapInstances.length, 2)
  assert.notEqual(runtime.mapInstances[0].host, runtime.mapInstances[1].host)
  assert.notEqual(runtime.mapInstances[0].host.id, runtime.mapInstances[1].host.id)
  const currentMap = runtime.store.map
  runtime.beforeUnmount[0]?.()
  currentMap.events.get('destroyed')?.()
})

test('Tencent map is not ready until the SDK emits its public idle event', async () => {
  const runtime = createRuntime({ provider: 'tencent', deferredTencentIdle: true })
  const initializing = runtime.panel.initTencent()
  for (let i = 0; i < 5; i++) await Promise.resolve()
  const map = runtime.mapInstances[0]
  assert.ok(map)
  assert.equal(runtime.store.map, null)
  assert.equal(runtime.panel.mapReady.value, false)
  for (let i = 0; i < 10; i++) {
    runtime.app.runData.point_index = i % 5
    runtime.panel.renderTask()
  }
  assert.equal(runtime.created.length, 0, 'progress must not create native layers before idle')
  map.events.get('idle')?.()
  await initializing
  assert.equal(runtime.store.map, map)
  assert.equal(runtime.panel.mapReady.value, true)
  runtime.panel.renderTask()
  assert.ok(runtime.created.length > 0)
  assert.equal(map.events.has('idle'), false)
  await runtime.panel.destroyMap()
})

test('Tencent idle timeout releases the instance and exposes a retryable error', async () => {
  let expire
  const runtime = createRuntime({ provider: 'tencent', deferredTencentIdle: true,
    timers: { setTimeout(callback, delay) { if (delay === 5000) expire = callback; return 1 }, clearTimeout() {} },
  })
  const initializing = runtime.panel.initTencent()
  for (let i = 0; i < 5; i++) await Promise.resolve()
  const instance = runtime.mapInstances[0]
  expire()
  await initializing
  assert.equal(runtime.store.map, null)
  assert.equal(runtime.panel.mapReady.value, false)
  assert.match(runtime.panel.placeholderError.value, /初始化超时/)
  assert.equal(instance.destroyed, true)
  assert.equal(instance.events.has('idle'), false)
})

test('Tencent unmount cancels pending idle and a late callback cannot mark it ready', async () => {
  const runtime = createRuntime({ provider: 'tencent', deferredTencentIdle: true })
  const initializing = runtime.panel.initTencent()
  for (let i = 0; i < 5; i++) await Promise.resolve()
  const instance = runtime.mapInstances[0]
  const lateIdle = instance.events.get('idle')
  runtime.beforeUnmount[0]()
  await initializing
  lateIdle?.()
  assert.equal(runtime.store.map, null)
  assert.equal(runtime.panel.mapReady.value, false)
  assert.equal(instance.events.has('idle'), false)
})

test('Tencent owned lines are destroyed, markers are stopped and detached, and automatic fit has no animation', async () => {
  const runtime = createRuntime({ provider: 'tencent' })
  await runtime.panel.initTencent()
  runtime.panel.drawPolyline([[113.39, 22.52], [113.40, 22.53]])
  runtime.panel.addMarker([113.39, 22.52])
  runtime.panel.fitView([[113.39, 22.52], [113.40, 22.53]])
  assert.equal(runtime.store.map.fitOptions?.ease?.duration, 0)
  await runtime.panel.destroyMap()
  assert.ok(runtime.lifecycle.includes('destroy-line'))
  assert.ok(runtime.lifecycle.includes('stop-marker'))
  assert.ok(runtime.lifecycle.indexOf('destroy-line') < runtime.lifecycle.indexOf('destroy-map'))
})

test('Tencent teardown waits for pending label geometry before destroying the native map', async () => {
  const runtime = createRuntime({ provider: 'tencent' })
  const labels = []
  runtime.window.TMap.LabelStyle = class {}
  runtime.window.TMap.MultiLabel = class {
    constructor() { this.events = new Map(); labels.push(this) }
    on(name, callback) { this.events.set(name, callback) }
    off(name) { this.events.delete(name) }
    setVisible() {}
    destroy() { this.destroyed = true }
  }
  await runtime.panel.initTencent()
  const native = runtime.store.map
  runtime.panel.addMarker([113.39, 22.52], { id: 'runner', title: '当前位置' })
  const releasing = runtime.panel.destroyMap()
  assert.notEqual(native.destroyed, true, 'glyph processing still uses the map atlas')
  assert.notEqual(labels[0].destroyed, true)
  labels[0].events.get('geometry_processed')?.()
  await releasing
  assert.equal(labels[0].destroyed, true)
  assert.equal(native.destroyed, true)
  assert.equal(labels[0].events.size, 0)
})

test('Tencent destruction timeout blocks recreation and retains the old host until destroyed', async () => {
  let deadline
  const runtime = createRuntime({ provider: 'tencent', deferredDestroy: true,
    timers: { setTimeout(callback) { deadline = callback; return 1 }, clearTimeout() {} },
  })
  await runtime.panel.initTencent()
  const oldMap = runtime.store.map
  const host = oldMap.host
  const next = runtime.panel.initMap()
  deadline()
  await next
  assert.match(runtime.panel.placeholderError.value, /释放超时/)
  assert.ok(host.parentNode, 'a timed-out native host must remain attached')
  await runtime.panel.initMap()
  assert.equal(runtime.mapInstances.length, 1, 'timeout cannot enable another native map')
  oldMap.events.get('destroyed')?.()
  assert.equal(host.parentNode, null)
  await runtime.panel.initMap()
  assert.equal(runtime.mapInstances.length, 2)
  const current = runtime.store.map
  runtime.beforeUnmount[0]()
  current.events.get('destroyed')?.()
})

test('Tencent label timeout still completes native cleanup after late geometry and permits retry', async () => {
  let expire
  const runtime = createRuntime({ provider: 'tencent',
    timers: { setTimeout(callback) { expire = callback; return 1 }, clearTimeout() {} },
  })
  let label
  runtime.window.TMap.LabelStyle = class {}
  runtime.window.TMap.MultiLabel = class {
    constructor() { this.events = new Map(); label = this }
    on(name, callback) { this.events.set(name, callback) }
    off(name) { this.events.delete(name) }
    setVisible() {}
    destroy() { this.destroyed = true }
  }
  await runtime.panel.initTencent()
  const native = runtime.store.map
  runtime.panel.addMarker([113.39, 22.52], { title: '当前位置' })
  const next = runtime.panel.initMap()
  expire()
  await next
  assert.match(runtime.panel.placeholderError.value, /释放超时/)
  assert.notEqual(native.destroyed, true)
  label.events.get('geometry_processed')?.()
  for (let i = 0; i < 12; i++) await Promise.resolve()
  assert.equal(label.destroyed, true)
  assert.equal(native.destroyed, true, 'a reported timeout must not cancel eventual native cleanup')
  await runtime.panel.initMap()
  assert.equal(runtime.mapInstances.length, 2)
  await runtime.panel.destroyMap()
})

test('late drawing events from a disposed map cannot add points to a new task', async () => {
  const runtime = createRuntime()
  await runtime.panel.initBaidu()
  runtime.panel.bindDrawingClick()
  const click = runtime.listeners.get('click')
  await runtime.panel.destroyMap()
  click({ latLng: { lng: 113.391, lat: 22.521 } })
  assert.deepEqual(runtime.store.draftPoints, [])
})

test('Tencent removing one task line releases the native layer', async () => {
  const runtime = createRuntime({ provider: 'tencent' })
  await runtime.panel.initTencent()
  const line = runtime.panel.drawPolyline([[113.39, 22.52], [113.40, 22.53]])
  runtime.panel.removeSingleOverlay(line)
  assert.ok(runtime.lifecycle.includes('destroy-line'))
  await runtime.panel.destroyMap()
})

test('Tencent marker updates without a caller id reuse the geometry IDs assigned at creation', async () => {
  const runtime = createRuntime({ provider: 'tencent' })
  await runtime.panel.initTencent()
  runtime.window.TMap.LabelStyle = class {}
  runtime.window.TMap.MultiLabel = class {
    constructor(options) { this.options = options; this.geometries = options.geometries }
    setGeometries(value) { this.geometries = value }
    setStyles() {}
    destroy() {}
  }
  const marker = runtime.panel.addMarker([113.39, 22.52], { title: '当前位置' })
  const markerId = marker.options.geometries[0].id
  const labelId = marker.__label.options.geometries[0].id
  runtime.panel.updateMarker(marker, [113.391, 22.52], { title: '当前位置' })
  assert.equal(marker.options.geometries[0].id, markerId)
  assert.equal(marker.__label.geometries[0].id, labelId)
  assert.equal(labelId, `${markerId}-name`)
})

test('native map instances remain raw in the shared store', () => {
  const source = readFileSync(new URL('../frontend/src/stores/map.js', import.meta.url), 'utf8')
  const useStore = new Function('defineStore', 'ref', 'shallowRef', 'markRaw', 'computed',
    source.replace(/^import .*$/gm, '').replace('export const useMapStore', 'const useMapStore') + '\nreturn useMapStore')(
      (_id, setup) => setup, ref, shallowRef, markRaw, computed)
  const store = useStore()
  const native = { renderer: { mapping: new Map() } }
  store.setMapInstance(native)
  assert.equal(store.mapInstance.value, native)
  assert.equal(store.mapInstance.value.renderer, native.renderer)
})

test('proxy-rewritten loader URL remains cached when the component remounts', async () => {
  let current, appended = 0
  const document = {
    getElementById: () => current,
    createElement: () => ({ dataset: {}, remove() { current = null },
      set src(value) { this.rewrittenUrl = '/map-proxy/amap/https/webapi.amap.com/loader.js' },
      get src() { return this.rewrittenUrl },
    }),
    head: { appendChild(script) { current = script; appended++; queueMicrotask(() => script.onload()) } },
  }
  const { panel } = createRuntime({ documentOverride: document })
  await panel.loadScript('https://webapi.amap.com/loader.js', 'amap-loader')
  await panel.loadScript('https://webapi.amap.com/loader.js', 'amap-loader')
  assert.equal(appended, 1)
})

test('Tianditu checkpoint titles do not require a nonexistent Marker.setTitle method', async () => {
  const { panel, store, window } = createRuntime()
  await panel.initBaidu()
  let marker
  window.T = {
    LngLat: class { constructor(lng, lat) { this.lng = lng; this.lat = lat } },
    Marker: class { constructor(point, options) { this.point = point; this.options = options; marker = this } },
  }
  store.activeProvider = 'tianditu'
  store.map.addOverLay = store.map.addOverlay
  assert.doesNotThrow(() => panel.addMarker([113.39, 22.52], { title: '检查点' }))
  assert.equal(marker.options.title, '检查点')
})

test('Tianditu cleanup uses clearOverLays when the SDK has no destroy or remove method', async () => {
  const runtime = createRuntime({ provider: 'tianditu' })
  await runtime.panel.initBaidu()
  const native = runtime.store.map
  let cleared = false
  native.destroy = undefined
  native.clearOverLays = () => { cleared = true }
  const zoom = runtime.listeners.get('zoomend')
  await runtime.panel.destroyMap()
  assert.equal(cleared, true)
  assert.equal(runtime.elements.get(native.host).parentNode, null)
  assert.equal(runtime.listeners.size, 0)
  assert.doesNotThrow(() => zoom())
})

test('Tianditu deterministic resources survive three progress, task-switch and immediate rebuild cycles', async () => {
  const runtime = createRuntime({ provider: 'tianditu' })
  runtime.store.mapConfig.tiandituKey = 'test-token'
  runtime.elements.set('tianditu-map-sdk', { src: 'https://api.tianditu.gov.cn/api?v=4.0&tk=test-token', dataset: { loaded: 'true' } })
  runtime.window.T = {
    Map: class extends runtime.sdk.Map {
      constructor(...args) { super(...args); this.destroy = undefined }
      addOverLay(value) { this.addOverlay(value) }
      removeOverLay(value) { this.removeOverlay(value) }
      clearOverLays() { this.cleared = true; this.clearOverlays() }
    },
    LngLat: runtime.sdk.Point,
    Marker: class extends runtime.sdk.Marker { setLngLat(value) { this.point = value } },
    Polyline: class extends runtime.sdk.Polyline {
      setLngLats(value) { this.path = value }
      setColor(value) { this.options.color = value }
    },
  }
  const oldHosts = new Set()
  for (let cycle = 0; cycle < 3; cycle++) {
    await runtime.panel.initMap()
    const native = runtime.store.map
    assert.ok(native && !oldHosts.has(native.host))
    oldHosts.add(native.host)
    runtime.app.isRunning = true
    runtime.panel.renderTask()
    for (let index = 0; index < 10; index++) {
      runtime.app.runData.current_point_index = index % 5
      runtime.app.runData.current_location = { lng: 113.39 + index % 5 * .001, lat: 22.52 }
      runtime.panel.renderTask()
    }
    assert.ok(native.overlays.length > 0)
    runtime.app.runData.task_index++
    runtime.panel.renderTask()
    const lateZoom = runtime.listeners.get('zoomend')
    await runtime.panel.destroyMap()
    assert.equal(native.cleared, true)
    assert.equal(native.overlays.length, 0)
    assert.equal(runtime.elements.get(native.host).parentNode, null)
    assert.equal(runtime.listeners.size, 0)
    assert.doesNotThrow(() => lateZoom())
  }
})

test('Baidu v4 keeps default BD09 and converts business coordinates once at SDK boundary', async () => {
  const { panel, store, sdk } = createRuntime()
  await panel.initBaidu()
  const expected = coordinates.gcj02ToBd09(113.39, 22.52)
  assert.equal(store.map?.coordTypeAtCreation, null)
  assert.deepEqual(panel.providerPoint([113.39, 22.52]), [expected.lng, expected.lat])
  assert.equal(store.map.center.lng, coordinates.gcj02ToBd09(113.390342, 22.527403).lng)
  assert.equal(sdk.coordType, null)
})

test('Baidu keeps route overlays and the runner stable across start and successive progress updates', async () => {
  const { panel, app, store, sdk, removed } = createRuntime()
  await panel.initBaidu()
  const original = JSON.stringify(app.runData.run_coords)
  panel.renderTask()
  app.isRunning = true
  app.runData.current_point_index = 1
  app.runData.current_lon = 113.391
  app.runData.current_lat = 22.52
  panel.renderTask()
  const firstLines = store.map.overlays.filter(value => value instanceof sdk.Polyline)
  assert.deepEqual(new Set(firstLines.map(line => line.options.strokeColor)), new Set(['#2563eb', '#ef4444']))
  const runner = store.map.overlays.find(value => value instanceof sdk.Marker && value.title === '当前位置')
  assert.ok(runner)
  const removedBeforeProgress = removed.length
  app.runData.current_point_index = 3
  app.runData.current_lon = 113.393
  panel.renderTask()
  assert.equal(runner.point.lng, coordinates.gcj02ToBd09(113.393, 22.52).lng)
  assert.ok(store.map.overlays.includes(runner), 'runner marker must be updated in place')
  assert.equal(removed.length, removedBeforeProgress + 1, 'only the exhausted remaining line is removed')
  assert.ok(store.map.overlays.some(value => value instanceof sdk.Polyline && value.options.strokeColor === '#9ca3af'))
  assert.equal(JSON.stringify(app.runData.run_coords), original)
})

test('Baidu v4 drawing reads latLng and unmount unbinds events before destroying owned overlays', async () => {
  const { panel, store, listeners, unmount } = createRuntime()
  await panel.initBaidu()
  panel.bindDrawingClick()
  listeners.get('click')({ latLng: { lng: 113.391, lat: 22.521 } })
  assert.deepEqual(store.draftPoints[0], coordinates.bd09ToGcj02(113.391, 22.521))
  panel.renderTask()
  const map = store.map
  unmount[0]()
  assert.equal(map.destroyed, true)
  assert.equal(map.overlays.length, 0)
  assert.equal(listeners.size, 0)
})

test('late proxy initialization cannot recreate a map after unmount or a newer initialization', async () => {
  for (const disposed of [true, false]) {
    let resolveProxy
    const { panel, store, unmount } = createRuntime({ proxyInitialize: () => new Promise(resolve => { resolveProxy = resolve }) })
    const pending = panel.initMap()
    await Promise.resolve()
    if (disposed) unmount[0]()
    else panel.initialization++
    resolveProxy()
    await pending
    assert.equal(store.map, null)
    assert.equal(panel.mapReady.value, false)
  }
})

test('a departed AMap loader cannot reset the SDK or replace the current security configuration', async () => {
  let script, loads = 0, resets = 0
  const browserWindow = { _AMapSecurityConfig: { securityJsCode: 'current-code' }, __appAmapSignature: 'current',
    AMapLoader: { reset() { resets++ }, load() { loads++; return {} } },
  }
  const documentOverride = { getElementById() { return null }, createElement() { return { dataset: {} } },
    head: { appendChild(value) { script = value } },
  }
  const runtime = createRuntime({ browserWindow, documentOverride, provider: 'amap' })
  runtime.store.mapConfig.amapKey = 'departed-key'
  runtime.store.mapConfig.amapSecurityJsCode = 'departed-code'
  const pending = runtime.panel.initAmap()
  runtime.beforeUnmount[0]()
  script.onload()
  await pending
  assert.equal(browserWindow._AMapSecurityConfig.securityJsCode, 'current-code')
  assert.equal(loads, 0)
  assert.equal(resets, 0)
})

test('Baidu SDK callbacks are unique across components with the same initialization generation', async () => {
  const browserWindow = {}
  const scripts = []
  const documentOverride = { getElementById() { return null }, createElement() { return { dataset: {} } },
    head: { appendChild(script) { scripts.push(script) } },
  }
  const first = createRuntime({ browserWindow, documentOverride })
  const oldPending = first.panel.initBaidu()
  const oldName = new URL(scripts[0].src).searchParams.get('callback')
  const oldCallback = browserWindow[oldName]
  first.beforeUnmount[0]()
  const second = createRuntime({ browserWindow, documentOverride })
  const newPending = second.panel.initBaidu()
  const newName = new URL(scripts[1].src).searchParams.get('callback')
  const newCallback = browserWindow[newName]
  second.beforeUnmount[0]()
  oldCallback()
  try {
    assert.equal(browserWindow[newName], newCallback, 'old callback must not delete the current loader')
  } finally {
    newCallback()
    scripts.forEach(script => script.onload?.())
    await Promise.all([oldPending, newPending])
  }
  assert.notEqual(oldName, newName)
})
