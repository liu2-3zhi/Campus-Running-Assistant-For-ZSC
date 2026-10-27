import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'

function loadSource(path, globals, exported) {
  const source = readFileSync(resolve(path), 'utf8').replace(/^import .*\r?\n/gm, '').replace(/export (const|function) /g, '$1 ')
  return vm.runInNewContext(`${source}\n${exported}`, globals)
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

test('a per-task completion keeps polling until the whole batch finishes', async () => {
  let onRunningChanged
  let status = { status: 'running' }
  const app = { isRunning: true, addRoutePlanningFailures(rows) { this.rows = rows } }
  const bg = loadSource('frontend/src/composables/useBackgroundTask.js', {
    ref: value => ({ value }), onUnmounted() {}, watch: (_source, callback) => { onRunningChanged = callback },
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
