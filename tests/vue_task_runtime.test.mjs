import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { parse, compileScript } from '../frontend/node_modules/@vue/compiler-sfc/dist/compiler-sfc.esm-browser.js'
import { ref, computed, reactive } from '../frontend/node_modules/vue/dist/vue.esm-browser.prod.js'
import * as coordinates from '../frontend/src/utils/coordinates.js'

const taskDataUrl = new URL('../frontend/src/components/main/taskData.js', import.meta.url)
const taskData = existsSync(taskDataUrl) ? await import(taskDataUrl) : {}

function componentSetup(path, dependencies, props = {}) {
  const source = readFileSync(new URL(`../frontend/src/${path}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'task-runtime', genDefaultAs: 'component' }).content
  return new Function(...Object.keys(dependencies), `${script.replace(/^import .*$/gm, '')}\nreturn component.setup`)(...Object.values(dependencies))(props, { expose() {} })
}

function taskPanel(app, api = {}) {
  const dependencies = {
    ref, computed,
    useAppStore: () => app,
    useMapStore: () => ({ isDrawing: false }),
    callAPI: api.callAPI || (async () => ({ success: true })),
    callRawAPI: api.callRawAPI || (async () => ({ success: true })),
    AppModal: {}, TaskDetails: {},
    ...taskData,
  }
  return componentSetup('components/main/TaskPanel.vue', dependencies)
}

function makeApp() {
  return {
    tasks: [{ run_name: '晨跑', status: 0 }, { run_name: '晚跑', status: 1 }],
    selectedTaskIndex: -1, runData: null, isRunning: false,
    addLog() {},
  }
}

test('task labels accept the numeric status returned by the backend', () => {
  const panel = taskPanel(makeApp())
  assert.equal(panel.statusLabel(1), '已完成')
  assert.equal(panel.statusLabel(0), '未完成')
})

test('selecting an online task fetches its details and updates the dashboard data', async () => {
  const app = makeApp()
  const calls = []
  const details = { run_name: '晨跑', target_points: [[120, 30]], total_run_distance_m: 2100 }
  const panel = taskPanel(app, { callAPI: async (...args) => { calls.push(args); return { success: true, details } } })
  await panel.selectTask(0)
  assert.deepEqual(calls, [['get_task_details', 0]])
  assert.equal(app.selectedTaskIndex, 0)
  assert.equal(app.runData.run_name, '晨跑')
  assert.deepEqual(app.runData.target_points, [[120, 30]])
})

test('a running task cannot be replaced from the task list', async () => {
  const app = makeApp()
  app.selectedTaskIndex = 0
  app.isRunning = true
  const panel = taskPanel(app)
  await panel.selectTask(1)
  assert.equal(app.selectedTaskIndex, 0)
})

test('failed task details preserve the previous selection and details', async () => {
  const app = makeApp()
  app.selectedTaskIndex = 0
  app.runData = { run_name: '晨跑' }
  const panel = taskPanel(app, { callAPI: async () => ({ success: false, message: '获取任务详情失败' }) })
  await panel.selectTask(1)
  assert.equal(app.selectedTaskIndex, 0)
  assert.deepEqual(app.runData, { run_name: '晨跑' })
})

test('mobile start preserves the legacy automatic route generation behavior', async () => {
  const app = makeApp()
  app.selectedTaskIndex = 0
  const calls = []
  const panel = componentSetup('components/main/MobileControlPanel.vue', {
    ref, computed, reactive, useAppStore: () => app,
    callAPI: async () => ({ success: true }),
    callRawAPI: async (...args) => { calls.push(args); return { success: true } },
    checkOverdueBeforeStartByCurrentMode: async () => true,
    AppModal: {}, ...taskData,
  })
  await panel.startTask()
  assert.deepEqual(calls[0], ['/api/background_task/start', 'POST', { task_indices: [0], auto_generate: true }])
  assert.equal(app.isRunning, true)
})

for (const provider of ['amap', 'tencent', 'tianditu', 'baidu']) {
  test(`${provider} renders selected task routes, retains segment breaks, and does not mutate execution coordinates`, () => {
    const added = []
    let fits = 0
    class Point { constructor(lng, lat) { this.lng = lng; this.lat = lat } }
    class LatLng { constructor(lat, lng) { this.lng = lng; this.lat = lat } }
    class Overlay {
      constructor(...args) { this.args = args; if (!Array.isArray(args[0]) && args[0]?.map) added.push(this) }
      setMap() {} setTitle() {} setLabel() {}
    }
    class Bounds { extend() {} }
    const sdk = { Marker: Overlay, Polyline: Overlay, Label: Overlay, Point, LngLat: Point, LngLatBounds: Bounds }
    const map = {
      add: value => added.push(value), addOverLay: value => added.push(value), addOverlay: value => added.push(value),
      remove() {}, removeOverLay() {}, clearOverlays() {},
      setFitView() { fits++ }, fitBounds() { fits++ }, setViewport() { fits++ },
      getViewport: () => ({ center: new Point(120, 30), zoom: 17 }), centerAndZoom() { fits++ },
    }
    const app = makeApp()
    app.selectedTaskIndex = 0
    app.runData = {
      task_index: 0,
      recommended_coords: [[120, 30], [120.01, 30.01], [0, 0], [120.02, 30.02], [120.03, 30.03]],
      run_coords: [[120, 30, 1000], [120.01, 30.01, 1000]],
      target_points: [[120, 30]], target_point_names: '起跑点',
    }
    const before = JSON.stringify(app.runData)
    const watched = []
    const panel = componentSetup('components/map/MapContainer.vue', {
      ref, watch: (...args) => watched.push(args), onMounted() {}, onUnmounted() {}, nextTick: async () => {},
      useAppStore: () => app, useMapStore: () => ({ activeProvider: provider, isDrawing: false }),
      MapPlaceholder: {}, MapControls: {}, ...coordinates,
      window: { AMap: sdk, T: sdk, BMapGL: sdk, TMap: { LatLng, LatLngBounds: Bounds, MultiMarker: Overlay, MultiPolyline: Overlay, PolylineStyle: Overlay, MultiLabel: Overlay, LabelStyle: Overlay } },
      document: { createElement: () => ({ textContent: '', outerHTML: '<span>起跑点</span>' }) },
    }, { isMultiAccount: false, containerId: 'map' })
    panel.map = map
    panel.mapReady.value = true
    panel.renderTask()
    assert.ok(added.length >= 4, 'two recommended segments, the generated route and checkpoint must be visible')
    const paths = added.map(overlay => Array.isArray(overlay.args[0])
      ? overlay.args[0]
      : overlay.args[0]?.path || overlay.args[0]?.geometries?.[0]?.paths).filter(Boolean)
    assert.equal(paths.length, 3, 'the separator must produce two independent recommended lines')
    assert.ok(paths.every(path => path.length === 2))
    assert.ok(paths.flat().every(point => point.lng !== 0 && point.lat !== 0))
    assert.equal(fits, 1)
    app.runData.current_distance = 100
    panel.renderTask()
    assert.equal(fits, 1, 'progress updates must preserve the user viewport')
    delete app.runData.current_distance
    assert.equal(JSON.stringify(app.runData), before)
    assert.ok(watched.some(([source]) => Array.isArray(source) && source[0]() === app.runData), 'task data must drive rendering')
  })
}
