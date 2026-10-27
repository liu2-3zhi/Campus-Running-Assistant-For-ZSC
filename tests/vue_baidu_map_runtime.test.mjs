import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '../frontend/node_modules/@vue/compiler-sfc/dist/compiler-sfc.esm-browser.js'
import { ref } from '../frontend/node_modules/vue/dist/vue.esm-browser.prod.js'
import * as coordinates from '../frontend/src/utils/coordinates.js'
import * as routeProgress from '../frontend/src/utils/routeProgress.js'

function createRuntime({ proxyInitialize } = {}) {
  const created = []
  const removed = []
  const listeners = new Map()
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
    constructor() { this.overlays = []; this.coordTypeAtCreation = sdk.coordType; this.zoom = 18 }
    centerAndZoom(point, zoom) { this.center = point; this.zoom = zoom }
    enableScrollWheelZoom() {}
    addEventListener(event, callback) { listeners.set(event, callback) }
    removeEventListener(event, callback) { if (listeners.get(event) === callback) listeners.delete(event) }
    addOverlay(overlay) { this.overlays.push(overlay) }
    removeOverlay(overlay) { removed.push(overlay); this.overlays = this.overlays.filter(value => value !== overlay) }
    clearOverlays() { removed.push(...this.overlays); this.overlays = [] }
    getViewport(points) { return { center: points[0], zoom: this.zoom } }
    getZoom() { return this.zoom }
    destroy() { this.destroyed = true }
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
  const store = { activeProvider: 'baidu', mapConfig: { baiduKey: 'test-ak' }, isDrawing: false, draftPoints: [],
    setMapInstance(value) { this.map = value }, addDraftPoint(point) { this.draftPoints.push(point) },
  }
  const auth = {
    sessionUUID: '11111111-1111-4111-8111-111111111111',
    getSessionHeaderValue() { return this.sessionUUID },
    getAdminOriginHeaderValue() { return '' },
  }
  const unmount = []
  const source = readFileSync(new URL('../frontend/src/components/map/MapContainer.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'baidu-runtime', genDefaultAs: 'component' }).content
  const dependencies = {
    ref, watch() {}, onMounted() {}, onUnmounted(callback) { unmount.push(callback) }, nextTick: async () => {},
    useMapStore: () => store, useAppStore: () => app, useAuthStore: () => auth,
    MapPlaceholder: {}, MapControls: {}, window: { BMap: sdk, BMAP_COORD_GCJ02: 2,
      ...(proxyInitialize ? { ZXMapRequestProxy: { initialize: proxyInitialize } } : {}),
    },
    BMAP_COORD_GCJ02: 2,
    ...coordinates, ...routeProgress,
    document: { getElementById: () => ({ style: {} }), createElement: () => ({ textContent: '', outerHTML: '<span>点</span>' }) },
    setTimeout, clearTimeout, console,
  }
  const setup = new Function(...Object.keys(dependencies), `${script.replace(/^import .*$/gm, '')}\nreturn component.setup`)(...Object.values(dependencies))
  const panel = setup({ containerId: 'map', isMultiAccount: false }, { expose() {} })
  return { panel, app, store, sdk, created, removed, listeners, unmount }
}

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
    if (disposed) unmount[0]()
    else panel.initialization++
    resolveProxy()
    await pending
    assert.equal(store.map, null)
    assert.equal(panel.mapReady.value, false)
  }
})
