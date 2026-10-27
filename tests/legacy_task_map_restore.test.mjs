import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const runtimeSource = readFileSync(new URL('../scripts/legacy-app-runtime.js', import.meta.url), 'utf8')
function extractFunction(name, text = source) {
  const start = text.indexOf(`function ${name}(`)
  assert.ok(start >= 0, `${name} must exist`)
  const end = text.indexOf('\n}', start)
  return `${text.slice(text.slice(0, start).endsWith('async ') ? start - 6 : start, end + 2)}\n`
}

function createRuntime() {
  const requests = []
  const positions = []
  const context = vm.createContext({
    currentTasks: [{}, {}, {}], currentRunData: { task_index: 0 }, selectedTaskIndex: 0,
    sessionUUID: 'A', singleProcessedPoints: 0, singleTotalPoints: 0, runAccumulatedMs: 0,
    singleRunProgressVisualActive: false, activeTaskMapProviderLock: null,
    logMessage_Info() {}, logMessage_Error() {}, logMessage_Debug() {},
    updateDashboard() {}, drawOnMap() {}, loadHistory() {}, updateSingleProgress() {}, renderTaskList() {}, drawMarkers() {},
    normalizeSupportedMapProvider: value => value || '', getActiveMapProvider: () => 'baidu',
    $: () => ({ classList: { add() {}, remove() {} }, children: [] }),
    startBackgroundTaskPolling() {}, updateMobileTaskUI() {},
    showModalAlert() {}, refreshTasks() {},
    updateRunnerPosition(...args) { positions.push(args) },
    callPythonAPI: (method, index) => new Promise(resolve => requests.push({ method, index, resolve })),
    callPythonAPI_raw: async () => ({ success: false }),
    clearInterval() {},
  })
  const helperStart = source.indexOf('const legacyRunnerExecutionState =')
  const helperEnd = source.indexOf('function updateRunnerPosition(', helperStart)
  vm.runInContext(`let pollingTaskMapRequest = 0; let pollingTaskMapPending = null; let backgroundTaskStatusRequest = 0; let backgroundTaskPollInterval = null; let backgroundTaskStartTime = 0;\n${source.slice(helperStart, helperEnd)}\n${extractFunction('getLegacyTaskMapSnapshotKey')}${extractFunction('forceLoadTaskDataForPolling')}${extractFunction('stopBackgroundTaskPolling')}${extractFunction('getLegacyActiveTaskIndex')}${extractFunction('mergeLegacyRunnerProgress')}${extractFunction('pollBackgroundTaskStatus')}${extractFunction('checkBackgroundTaskOnLoad')}${extractFunction('restoreMobileTaskState', runtimeSource)}`, context)
  return { context, requests, positions }
}

test('a new legacy execution clears completed display status and previous progress', () => {
  const { context } = createRuntime()
  context.currentRunData = { task_index: 0, status: 1, current_point_index: 90 }
  context.acceptLegacyRunnerExecution({ execution_id: 'new', execution_started_at: 2, task_index: 0 }, true)
  assert.equal(context.currentRunData.status, 'running')
  assert.equal(context.currentRunData.current_point_index, 0)
})

test('legacy polling restores read-only snapshots and ignores an older task response', async () => {
  const { context, requests } = createRuntime()
  context.selectedTaskIndex = 1
  const old = context.forceLoadTaskDataForPolling(1)
  context.selectedTaskIndex = 2
  const current = context.forceLoadTaskDataForPolling(2)
  assert.deepEqual(requests.map(request => request.method), ['get_task_map_snapshot', 'get_task_map_snapshot'])
  requests[1].resolve({ success: true, details: { current_point_index: 2, target_sequence: 1, run_coords: [[114, 23], [115, 23]] } })
  await current
  requests[0].resolve({ success: true, details: { current_point_index: 90, run_coords: [[113, 22]] } })
  await old
  assert.equal(context.currentRunData.task_index, 2)
  assert.equal(context.currentRunData.current_point_index, 2)
  assert.equal(context.currentRunData.target_sequence, 2)
  assert.equal(context.singleProcessedPoints, 2)
})

test('legacy same-task executions and route readiness changes restore newly generated geometry', async () => {
  const { context, requests } = createRuntime()
  let redraws = 0
  context.drawOnMap = () => { redraws++ }
  context.acceptLegacyRunnerExecution({ execution_id: 'old', execution_started_at: 1, task_index: 0 }, true)
  const first = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  requests[0].resolve({ success: true, route_ready: true, details: { current_point_index: 0, run_coords: [[113, 22], [114, 22]] } })
  await first
  context.acceptLegacyRunnerExecution({ execution_id: 'new', execution_started_at: 2, task_index: 0 }, true)
  await context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: false })
  assert.equal(context.currentRunData.run_coords.length, 0)
  const afterClear = redraws
  await context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: false })
  assert.equal(redraws, afterClear, 'pending route polling must not repeatedly redraw or issue snapshot requests')
  assert.equal(requests.length, 1)
  const next = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 2)
  requests[1].resolve({ success: true, route_ready: true, details: { current_point_index: 0, run_coords: [[115, 23], [116, 23]] } })
  await next
  assert.equal(context.currentRunData.run_coords[0][0], 115)
  await context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 2, 'ordinary progress polling must reuse the restored geometry')
  context.acceptLegacyRunnerExecution({ execution_id: 'third', execution_started_at: 3, task_index: 0 }, true)
  const third = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 3, 'a new execution must restore geometry even when its task index is unchanged')
  requests[2].resolve({ success: true, route_ready: true, details: { current_point_index: 0, run_coords: [[117, 24], [118, 24]] } })
  await third
  assert.equal(context.currentRunData.run_coords[0][0], 117)
})

test('legacy snapshot merging retains newer websocket progress in the same execution', async () => {
  const { context, requests } = createRuntime()
  context.acceptLegacyRunnerExecution({ execution_id: 'batch', execution_started_at: 1, task_index: 0 }, true)
  const pending = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  context.currentRunData = { task_index: 0, status: 'running', current_point_index: 3,
    current_position: { lng: 115, lat: 22 }, distance_covered_m: 50, target_sequence: 2 }
  requests[0].resolve({ success: true, route_ready: true, details: { current_point_index: 1,
    current_position: { lon: 113, lat: 22 }, distance_covered_m: 10, target_sequence: 0,
    run_coords: [[113, 22], [114, 22], [115, 22]] } })
  await pending
  assert.equal(context.currentRunData.current_point_index, 3)
  assert.equal(context.currentRunData.current_position.lng, 115)
  assert.equal(context.currentRunData.distance_covered_m, 50)
  assert.equal(context.currentRunData.target_sequence, 2)
  assert.equal(context.singleProcessedPoints, 3)
})

test('legacy polling retains the newer runner and dashboard progress after a slow snapshot', async () => {
  const { context, requests, positions } = createRuntime()
  context.callPythonAPI_raw = async () => ({ success: true, task_status: { status: 'running', execution_id: 'batch', execution_started_at: 1,
    active_task_index: 0, route_ready: true, singleProcessedPoints: 1, singleTotalPoints: 3, current_distance_m: 10,
    checked_targets_count: 1, current_position: { lon: 113, lat: 22, distance: 10, target_sequence: 0, point_index: 1 } } })
  const pending = context.pollBackgroundTaskStatus()
  await new Promise(resolve => setImmediate(resolve))
  context.currentRunData = { task_index: 0, status: 'running', current_point_index: 3,
    current_position: { lng: 115, lat: 22 }, distance_covered_m: 50, target_sequence: 2 }
  requests[0].resolve({ success: true, route_ready: true, details: { current_point_index: 1,
    current_position: { lon: 113, lat: 22 }, distance_covered_m: 10, target_sequence: 0,
    run_coords: [[113, 22], [114, 22], [115, 22]] } })
  await pending
  assert.equal(positions[0][0], 115)
  assert.equal(positions[0][6], 3)
  assert.equal(context.singleProcessedPoints, 3)
  assert.equal(context.currentRunData.distance_covered_m, 50)
  assert.equal(context.currentRunData.target_sequence, 2)
})

test('legacy polls share a slow snapshot for the same session, execution and task', async () => {
  const { context, requests, positions } = createRuntime()
  let point = 1
  context.callPythonAPI_raw = async () => ({ success: true, task_status: {
    status: 'running', execution_id: 'batch', execution_started_at: 1,
    active_task_index: 0, route_ready: true, singleProcessedPoints: point,
    singleTotalPoints: 3, current_position: { lon: 113 + point, lat: 22, point_index: point },
  } })
  const polls = []
  for (point = 1; point <= 3; point++) {
    polls.push(context.pollBackgroundTaskStatus())
    await new Promise(resolve => setImmediate(resolve))
  }
  assert.equal(requests.length, 1, 'later status polls must reuse the in-flight geometry request')
  requests[0].resolve({ success: true, route_ready: true, details: {
    current_point_index: 0, run_coords: [[113, 22], [114, 22], [115, 22]],
  } })
  await Promise.all(polls)
  assert.equal(context.currentRunData.run_coords.length, 3)
  assert.equal(positions.length, 1, 'only the newest poll may publish runner progress')
  assert.equal(positions[0][0], 116)
  assert.equal(positions[0][6], 3)
})

test('legacy snapshot failure releases the shared request so the next poll can retry', async () => {
  const { context, requests } = createRuntime()
  const first = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  const same = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 1)
  requests[0].resolve({ success: false, message: 'temporary' })
  assert.deepEqual(await Promise.all([first, same]), [false, false])
  const retry = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 2)
  requests[1].resolve({ success: true, route_ready: true, details: { run_coords: [[113, 22]] } })
  assert.equal(await retry, true)
})

test('legacy route regeneration invalidates a shared snapshot without blocking its replacement', async () => {
  const { context, requests } = createRuntime()
  context.acceptLegacyRunnerExecution({ execution_id: 'batch', execution_started_at: 1, task_index: 0 }, true)
  const stale = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  const shared = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  await context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: false })
  const replacement = context.forceLoadTaskDataForPolling(0, { status: 'running', route_ready: true })
  assert.equal(requests.length, 2)
  requests[0].resolve({ success: true, route_ready: true, details: { run_coords: [[113, 22]] } })
  assert.deepEqual(await Promise.all([stale, shared]), [false, false])
  const newest = context.forceLoadTaskDataForPolling(0, { status: 'completed', route_ready: true })
  assert.equal(requests.length, 2, 'finishing an invalidated request must not release its replacement')
  requests[1].resolve({ success: true, route_ready: true, details: { run_coords: [[115, 23]] } })
  assert.deepEqual(await Promise.all([replacement, newest]), [true, true])
  assert.equal(context.currentRunData.run_coords[0][0], 115)
  assert.equal(context.currentRunData.status, 'completed')
})

test('legacy AMap progress does not count a polled position twice', () => {
  const { context } = createRuntime()
  Object.assign(context, {
    getActiveMapProvider: () => 'amap', map: {}, AMapInstance: { LngLat: class { constructor(lng, lat) { this.lng = lng; this.lat = lat } } },
    document: { getElementById: () => null }, runnerMarker: { setPosition() {} }, ensureRunnerMarker() {}, drawOnMap_signature() {},
    resolveRouteProgressIndex: data => data.current_point_index - 1, resolveRunnerTargetSequence: () => 1,
    currentRunData: { current_point_index: 2, target_sequence: 1, run_coords: [[113, 22], [114, 22], [115, 22]] },
    singleProcessedPoints: 2, singleRunProgressVisualActive: true,
  })
  vm.runInContext(extractFunction('updateRunnerPosition'), context)
  context.updateRunnerPosition(114, 22, 20, 0, 0, false, 2)
  context.updateRunnerPosition(114, 22, 20, 0, 0, false, 2)
  assert.equal(context.singleProcessedPoints, 2)
})

test('legacy same-task restart and session changes reject an in-flight snapshot', async () => {
  for (const changeSession of [false, true]) {
    const { context, requests } = createRuntime()
    context.acceptLegacyRunnerExecution({ execution_id: 'old', execution_started_at: 1, task_index: 2 }, true)
    context.selectedTaskIndex = 2
    const old = context.forceLoadTaskDataForPolling(2)
    if (changeSession) context.sessionUUID = 'B'
    else context.acceptLegacyRunnerExecution({ execution_id: 'new', execution_started_at: 2, task_index: 2 }, true)
    requests[0].resolve({ success: true, details: { current_point_index: 90, run_coords: [[113, 22]] } })
    assert.equal(await old, false)
    assert.notEqual(context.currentRunData.current_point_index, 90)
  }
})

test('stopping legacy polling prevents an in-flight snapshot from publishing data', async () => {
  const { context, requests } = createRuntime()
  context.selectedTaskIndex = 2
  const pending = context.forceLoadTaskDataForPolling(2)
  context.stopBackgroundTaskPolling()
  requests[0].resolve({ success: true, details: { current_point_index: 90, run_coords: [[113, 22]] } })
  assert.equal(await pending, false)
  assert.equal(context.currentRunData.task_index, 0)
})

for (const restore of ['checkBackgroundTaskOnLoad', 'restoreMobileTaskState']) test(`${restore} restores the active index through a read-only snapshot`, async () => {
  const { context, requests } = createRuntime()
  context.callPythonAPI_raw = async () => ({ success: true, task_status: { status: 'running', active_task_index: 2,
    execution_id: 'batch', execution_started_at: 1, task_indices: [0], current_task_index: 0, route_ready: true,
    singleProcessedPoints: 1, singleTotalPoints: 2 } })
  const pending = context[restore]()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(requests.length, 1)
  assert.equal(requests[0].method, 'get_task_map_snapshot')
  assert.equal(requests[0].index, 2)
  requests[0].resolve({ success: true, details: { status: 1, current_point_index: 1, run_coords: [[113, 22], [114, 22]] } })
  await pending
  assert.equal(context.selectedTaskIndex, 2)
  assert.equal(context.currentRunData.task_index, 2)
  assert.equal(context.currentRunData.status, 'running')
  assert.equal(context.currentRunData.current_point_index, 1)
})

test('legacy overlapping status polls cannot apply old runner progress after a newer task snapshot', async () => {
  const { context, requests, positions } = createRuntime()
  const statuses = [1, 2].map(index => ({ status: 'running', execution_id: 'batch', execution_started_at: 1,
    active_task_index: index, task_indices: [0, 1, 2], current_task_index: index, route_ready: true,
    singleProcessedPoints: 1, singleTotalPoints: 2, current_position: { lon: 113 + index, lat: 22, point_index: 1 } }))
  context.callPythonAPI_raw = async () => ({ success: true, task_status: statuses.shift() })
  const old = context.pollBackgroundTaskStatus()
  await new Promise(resolve => setImmediate(resolve))
  const current = context.pollBackgroundTaskStatus()
  await new Promise(resolve => setImmediate(resolve))
  requests[1].resolve({ success: true, details: { current_point_index: 1, run_coords: [[115, 22], [116, 22]] } })
  await current
  requests[0].resolve({ success: true, details: { current_point_index: 1, run_coords: [[114, 22], [115, 22]] } })
  await old
  assert.equal(context.currentRunData.task_index, 2)
  assert.equal(positions.length, 1)
  assert.equal(positions[0][0], 115)
})

test('legacy pending active task does not fall back to the queue ordinal or restore old data', async () => {
  const { context, requests } = createRuntime()
  context.callPythonAPI_raw = async () => ({ success: true, task_status: { status: 'running', active_task_index: null,
    execution_id: 'batch', execution_started_at: 1, task_indices: [1], current_task_index: 0, route_ready: false } })
  const pending = context.pollBackgroundTaskStatus()
  await new Promise(resolve => setImmediate(resolve))
  if (requests.length) requests[0].resolve({ success: false })
  await pending
  assert.equal(requests.length, 0)
  assert.equal(context.selectedTaskIndex, 0)
})

test('a legacy status without an execution ID cannot stop a known fresh execution', async () => {
  const { context } = createRuntime()
  context.acceptLegacyRunnerExecution({ execution_id: 'new', execution_started_at: 2, task_index: 0 }, true)
  let stops = 0
  context.stopBackgroundTaskPolling = () => { stops++ }
  context.callPythonAPI_raw = async () => ({ success: true, task_status: { status: 'completed' } })
  await context.pollBackgroundTaskStatus()
  assert.equal(stops, 0)
  assert.equal(context.currentRunData.status, 'running')
})
