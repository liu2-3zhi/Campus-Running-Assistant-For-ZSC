import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import { createTaskMapRestorer } from '../frontend/src/utils/taskMapRestore.js'

function loadSource(path, globals, exported) {
  const source = readFileSync(resolve(path), 'utf8').replace(/^import .*\r?\n/gm, '').replace(/export (const|function) /g, '$1 ')
  return vm.runInNewContext(`${source}\n${exported}`, { createTaskMapRestorer, ...globals })
}

test('a detailed failure replaces its socket hint and is not repeated', () => {
  const store = loadSource('frontend/src/stores/app.js', {
    defineStore: (_, factory) => factory, ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
  }, 'useAppStore()')
  store.addLog('generic', 'ERROR', 'Backend', 'd1')
  store.addRoutePlanningFailures([{ diagnostic_id: 'd1', provider: 'amap', message: 'INVALID_USER_KEY', segment: 2, error_code: '10001' }])
  store.addRoutePlanningFailures([{ diagnostic_id: 'd1', provider: 'amap', message: 'INVALID_USER_KEY' }])
  store.addLog('generic', 'ERROR', 'Backend', 'd1')
  assert.equal(store.logs.value.length, 1)
  assert.match(store.logs.value[0].msg, /INVALID_USER_KEY/)
  assert.match(store.logs.value[0].msg, /路段：2；错误码：10001/)
})

test('legacy diagnostics upgrade the same line in desktop and mobile logs', () => {
  const source = readFileSync(resolve('scripts/main.js'), 'utf8')
  const begin = source.indexOf('const routeDiagnosticMessages = new Map();')
  const end = source.indexOf('function logMessage(msg,', begin)
  const areas = Object.fromEntries(['log-text', 'multi-log-text', 'mobile-log-text'].map(id => [id, { value: '' }]))
  const report = vm.runInNewContext(`${source.slice(begin, end)}\n({ displayRoutePlanningNotification, displayRoutePlanningFailures })`, {
    document: { getElementById: id => areas[id] },
    logMessage: message => Object.values(areas).forEach(area => { area.value += message + '\n' }),
  })
  report.displayRoutePlanningNotification({ msg: 'generic d1', diagnostic_id: 'd1' })
  report.displayRoutePlanningFailures([{ diagnostic_id: 'd1', provider: 'amap', message: 'INVALID_USER_KEY', segment: 2, error_code: '10001' }])
  report.displayRoutePlanningFailures([{ diagnostic_id: 'd1', provider: 'amap', message: 'INVALID_USER_KEY' }])
  report.displayRoutePlanningNotification({ msg: 'generic d1', diagnostic_id: 'd1' })
  for (const area of Object.values(areas)) {
    assert.match(area.value, /INVALID_USER_KEY/)
    assert.match(area.value, /路段：2；错误码：10001/)
    assert.equal(area.value.trim().split('\n').length, 1)
  }
})

test('provider error explanations and hints remain readable next to the original code', () => {
  const store = loadSource('frontend/src/stores/app.js', {
    defineStore: (_, factory) => factory, ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
  }, 'useAppStore()')
  store.addRoutePlanningFailures([{ diagnostic_id: 'scode', provider: 'amap', message: 'INVALID_USER_SCODE', error_explanation: '安全码未通过验证', error_hint: '检查安全密钥与 Key 是否配套' }])
  assert.match(store.logs.value[0].msg, /INVALID_USER_SCODE；安全码未通过验证；检查安全密钥与 Key 是否配套/)
  store.bindBusinessSession('B')
  store.bindBusinessSession('C')
  assert.equal(store.logs.value.length, 0, 'departed session diagnostics must not appear in another session')
})

test('position updates retain processed indices and clear geometry when the batch advances', () => {
  const store = loadSource('frontend/src/stores/app.js', {
    defineStore: (_, factory) => factory, ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
  }, 'useAppStore()')
  store.selectedTaskIndex.value = 2
  store.runData.value = { task_index: 2, run_coords: [[113, 22]], current_point_index: 3 }
  store.handlePositionUpdate({ task_index: 5, point_index: 4, lon: 114, lat: 23, distance: 0 })
  assert.equal(store.runData.value.current_point_index, 4)
  assert.equal(store.runData.value.run_coords, undefined)
  assert.equal(store.runData.value.current_distance, 0)
  store.handlePositionUpdate({ task_index: 5, point_index: 2, lon: 115, lat: 24 })
  assert.equal(store.runData.value.current_lon, 114, 'late progress must not move the runner backwards')
})

test('stopping and rerunning the same task ignores old batch progress and lifecycle events', () => {
  const store = loadSource('frontend/src/stores/app.js', {
    defineStore: (_, factory) => factory, ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
  }, 'useAppStore()')
  store.beginRunnerExecution({ execution_id: 'old', execution_started_at: 1, task_index: 2 })
  store.handlePositionUpdate({ execution_id: 'old', task_index: 2, point_index: 90, lon: 114, lat: 23 })
  store.beginRunnerExecution({ execution_id: 'new', execution_started_at: 2, task_index: 2 })
  store.isRunning.value = true
  assert.equal(store.runData.value.current_point_index, 0)
  store.handlePositionUpdate({ execution_id: 'old', task_index: 2, point_index: 99, lon: 115, lat: 24 })
  store.handleRunStopped({ execution_id: 'old' })
  store.handleTaskCompleted({ execution_id: 'old', task_index: 2 })
  store.beginRunnerExecution({ execution_id: 'old', execution_started_at: 1, task_index: 2 })
  store.handlePositionUpdate({ execution_id: 'new', task_index: 2, point_index: 1, lon: 113, lat: 22, elapsed_time: 3 })
  assert.equal(store.activeExecutionId.value, 'new')
  assert.equal(store.runData.value.current_point_index, 1)
  assert.equal(store.runData.value.current_lon, 113)
  assert.equal(store.runData.value.duration, 3)
  assert.equal(store.isRunning.value, true)
})

test('legacy runner batches reset progress and reject old same-task messages', () => {
  const source = readFileSync(resolve('scripts/main.js'), 'utf8')
  const start = source.indexOf('const legacyRunnerExecutionState =')
  const end = source.indexOf('function updateRunnerPosition(', start)
  const context = vm.createContext({ currentRunData: { task_index: 2, current_point_index: 99 }, singleProcessedPoints: 99, runAccumulatedMs: 10000 })
  vm.runInContext(`${source.slice(start, end)}\nglobalThis.accept = acceptLegacyRunnerExecution`, context)
  assert.equal(context.accept({ execution_id: 'old', execution_started_at: 1, task_index: 2 }, true), true)
  context.currentRunData.current_point_index = 99
  assert.equal(context.accept({ execution_id: 'new', execution_started_at: 2, task_index: 2 }, true), true)
  assert.equal(context.currentRunData.current_point_index, 0)
  assert.equal(context.accept({ execution_id: 'old', execution_started_at: 1, task_index: 2 }, true), false)
  assert.equal(context.accept({ execution_id: 'old', task_index: 2, point_index: 100 }), false)
  assert.equal(context.accept({ execution_id: 'new', task_index: 2, point_index: 1 }), true)
})

test('legacy in-page relogin clears the batch and rejects the departed execution', () => {
  const source = readFileSync(resolve('scripts/main.js'), 'utf8')
  const helperStart = source.indexOf('const legacyRunnerExecutionState =')
  const helperEnd = source.indexOf('function updateRunnerPosition(', helperStart)
  const sessionStart = source.indexOf('function setActiveLegacySession(')
  const sessionEnd = source.indexOf('const AUTH_CONTEXT_API_METHODS', sessionStart)
  const context = vm.createContext({
    sessionUUID: 'A', authSessionUUID: 'A', sessionStorage: { setItem() {} },
    isUsableClientSessionUUID: value => !!value, getAdminViewOriginSessionUUID: () => '',
    currentRunData: { task_index: 2, current_point_index: 99 }, singleProcessedPoints: 99, runAccumulatedMs: 10000,
  })
  vm.runInContext(`${source.slice(helperStart, helperEnd)}\n${source.slice(sessionStart, sessionEnd)}\nObject.assign(globalThis, { accept: acceptLegacyRunnerExecution, reset: resetLegacyRunnerExecution, setSession: setActiveLegacySession })`, context)
  context.accept({ execution_id: 'old', execution_started_at: 100, task_index: 2 }, true)
  context.setSession('A')
  assert.equal(context.accept({ execution_id: 'old', task_index: 2 }), true, 'unchanged UUID keeps its execution')
  context.setSession('B')
  assert.equal(context.accept({ execution_id: 'old', execution_started_at: 100, task_index: 2 }, true), false)
  assert.equal(context.accept({ execution_id: 'new', execution_started_at: 1, task_index: 2 }, true), true, 'new session must not inherit the previous session timestamp')
  context.reset()
  assert.equal(context.accept({ execution_id: 'new', execution_started_at: 1, task_index: 2 }, true), false, 'logout rejects late packets')
  assert.equal(context.accept({ execution_id: 'relogin', execution_started_at: 2, task_index: 2 }, true), true)
})

test('background polling reads nested status and finishes after retaining diagnostics', async () => {
  const app = { isRunning: true, addRoutePlanningFailures(rows) { this.rows = rows }, addLog() {} }
  const auth = { sessionUUID: 'target' }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch() {}, useAppStore: () => app, useAuthStore: () => auth,
    callRawAPI: async () => ({ success: true, task_status: { status: 'error', route_planning_failures: [{ diagnostic_id: 'd2', message: 'reason' }] } }),
    setInterval: () => 1, clearInterval() {},
  }, 'useBackgroundTask()')
  await bg.pollStatus()
  assert.equal(bg.taskStatus.value.status, 'error')
  assert.equal(app.rows[0].diagnostic_id, 'd2')
  assert.equal(app.isRunning, false)
  assert.equal(bg.isPolling.value, false)
})

test('a response from a departed target is ignored', async () => {
  let resolveRequest
  const auth = { sessionUUID: 'old' }
  const app = { isRunning: true, addRoutePlanningFailures() { throw new Error('stale diagnostics') } }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch() {}, useAppStore: () => app, useAuthStore: () => auth,
    callRawAPI: () => new Promise(resolve => { resolveRequest = resolve }), setInterval: () => 1, clearInterval() {},
  }, 'useBackgroundTask()')
  const pending = bg.pollStatus()
  auth.sessionUUID = 'new'
  resolveRequest({ success: true, task_status: { status: 'error', route_planning_failures: [{ diagnostic_id: 'old' }] } })
  await pending
  assert.equal(bg.taskStatus.value, null)
  assert.equal(app.isRunning, true)
})

for (const legacyStatus of [false, true]) test(`a ${legacyStatus ? 'legacy' : 'previous execution'} status cannot stop polling a restarted task`, async () => {
  let resolveRequest
  const auth = { sessionUUID: 'target' }
  const app = { isRunning: true, activeExecutionId: 'old', activeExecutionStartedAt: 1,
    addRoutePlanningFailures() { throw new Error('stale diagnostics') } }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch() {}, useAppStore: () => app, useAuthStore: () => auth,
    callRawAPI: () => new Promise(resolve => { resolveRequest = resolve }),
    setInterval: () => 1, clearInterval() {},
  }, 'useBackgroundTask()')
  bg.startPolling()
  app.activeExecutionId = 'new'
  app.activeExecutionStartedAt = 2
  resolveRequest({ success: true, task_status: { ...(legacyStatus ? {} : { execution_id: 'old', execution_started_at: 1 }), status: 'completed' } })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(app.isRunning, true)
  assert.equal(bg.isPolling.value, true)
  assert.equal(bg.taskStatus.value, null)
})

test('an execution restarted while a terminal status waits for geometry keeps polling', async () => {
  let resolveSnapshot
  const auth = { sessionUUID: 'target' }
  const app = { isRunning: true, activeExecutionId: 'old', activeExecutionStartedAt: 1, addRoutePlanningFailures() {} }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch() {}, useAppStore: () => app, useAuthStore: () => auth,
    callRawAPI: async () => ({ success: true, task_status: { execution_id: 'old', execution_started_at: 1,
      status: 'completed', active_task_index: 2, route_ready: true } }),
    callAPI: () => new Promise(resolve => { resolveSnapshot = resolve }),
    setInterval: () => 1, clearInterval() {},
  }, 'useBackgroundTask()')
  bg.startPolling()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(typeof resolveSnapshot, 'function')
  app.activeExecutionId = 'new'
  app.activeExecutionStartedAt = 2
  app.isRunning = true
  app.runData = { task_index: 2, current_point_index: 0 }
  resolveSnapshot({ success: true, route_ready: true, details: { current_point_index: 90, run_coords: [[113, 22], [114, 22]] } })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(app.isRunning, true)
  assert.equal(bg.isPolling.value, true)
  assert.equal(app.runData.current_point_index, 0)
})

test('a per-task completion keeps polling until the whole batch finishes', async () => {
  let onRunningChanged
  let status = { status: 'running' }
  const app = { isRunning: true, addRoutePlanningFailures(rows) { this.rows = rows } }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch: (_source, callback) => { onRunningChanged ??= callback },
    useAppStore: () => app, useAuthStore: () => ({ sessionUUID: 'target' }),
    callRawAPI: async () => ({ success: true, task_status: status }), setInterval: () => 1, clearInterval() {},
  }, 'useBackgroundTask()')
  bg.startPolling()
  await new Promise(resolve => setImmediate(resolve))
  app.isRunning = false
  onRunningChanged(false)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(bg.isPolling.value, true)
  assert.equal(app.isRunning, true)
  status = { status: 'error', route_planning_failures: [{ diagnostic_id: 'later', message: 'later route failed' }] }
  await bg.pollStatus()
  assert.equal(app.rows[0].diagnostic_id, 'later')
  assert.equal(bg.isPolling.value, false)
})
