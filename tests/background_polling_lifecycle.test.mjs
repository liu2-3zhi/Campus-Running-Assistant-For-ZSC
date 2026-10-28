import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import { createTaskMapRestorer } from '../frontend/src/utils/taskMapRestore.js'

const vue = createRequire(new URL('../frontend/package.json', import.meta.url))('vue')

const settle = () => new Promise(resolve => setImmediate(resolve))

function loadSource(path, globals, exported) {
  const source = readFileSync(path, 'utf8').replace(/^import .*\r?\n/gm, '').replace(/export (?=(?:async )?(?:function|const) )/g, '')
  return vm.runInNewContext(`${source}\n${exported}`, globals)
}

function createClock() {
  let now = 0
  let nextId = 0
  const timers = new Map()
  return {
    timers,
    setTimeout(callback, delay) { const id = ++nextId; timers.set(id, { callback, at: now + delay }); return id },
    clearTimeout(id) { timers.delete(id) },
    async tick(delay) {
      const target = now + delay
      while (true) {
        const next = [...timers].filter(([, timer]) => timer.at <= target).sort((a, b) => a[1].at - b[1].at)[0]
        if (!next) break
        const [id, timer] = next
        now = timer.at
        timers.delete(id)
        timer.callback()
        await settle()
      }
      now = target
      await settle()
    },
  }
}

function createPolling({ loadSnapshot = async () => ({ success: false }), ignoreAbort = false, reactiveWatchers = false, initiallyRunning = true } = {}) {
  const clock = createClock()
  const requests = []
  const watchers = []
  let unmount
  const makeReactive = reactiveWatchers ? vue.reactive : value => value
  const auth = makeReactive({ sessionUUID: 'B', adminOriginSession: 'A' })
  const app = makeReactive({ isRunning: initiallyRunning, addRoutePlanningFailures(rows) { this.failures = rows } })
  const scope = reactiveWatchers ? vue.effectScope() : null
  const initialize = () => loadSource('frontend/src/composables/useBackgroundTask.js', {
    AbortController,
    Date,
    ref: reactiveWatchers ? vue.ref : value => ({ value }),
    watch: (source, callback, options) => {
      watchers.push({ source, callback })
      if (reactiveWatchers) return vue.watch(source, callback, options)
    },
    onUnmounted: callback => { unmount = callback },
    useAuthStore: () => auth,
    useAppStore: () => app,
    createTaskMapRestorer,
    callAPI: loadSnapshot,
    callRawAPI: (url, method, body, options) => new Promise((resolve, reject) => {
      const request = { url, method, body, options, resolve, reject }
      requests.push(request)
      if (options.signal && !ignoreAbort) options.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
    }),
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
    setInterval: (callback, delay) => clock.setTimeout(function repeat() { callback(); clock.setTimeout(repeat, delay) }, delay),
    clearInterval: clock.clearTimeout,
  }, 'useBackgroundTask()')
  const bg = scope ? scope.run(initialize) : initialize()
  return { bg, clock, requests, auth, app, watchers, unmount: () => { unmount(); scope?.stop() } }
}

const response = (status = 'running', last_update = 1, extra = {}) => ({ success: true, task_status: { status, last_update, ...extra } })

test('manual status queries share one request and do not start a polling loop', async () => {
  const { bg, requests, clock } = createPolling()
  const first = bg.pollStatus()
  const second = bg.pollStatus()
  assert.equal(first, second)
  assert.equal(requests.length, 1)
  requests[0].resolve(response())
  await first
  assert.equal(bg.taskStatus.value.last_update, 1)
  assert.equal(bg.isPolling.value, false)
  assert.equal(clock.timers.size, 0)
})

test('a manual running status backfill does not activate the real Vue running watcher', async () => {
  const { bg, requests, app, clock, unmount } = createPolling({ reactiveWatchers: true, initiallyRunning: false })
  try {
    const pending = bg.pollStatus()
    requests[0].resolve(response('running', 1))
    await pending
    await vue.nextTick()
    assert.equal(app.isRunning, true, 'the manual query must still update the displayed execution state')
    assert.equal(bg.isPolling.value, false)
    assert.equal(requests.length, 1)
    await clock.tick(6000)
    assert.equal(requests.length, 1)
    assert.equal(clock.timers.size, 0)
  } finally {
    unmount()
  }
})

test('real Vue external execution changes can restart polling after manual backfill and a terminal batch', async () => {
  const { bg, requests, app, unmount } = createPolling({ reactiveWatchers: true, initiallyRunning: false })
  try {
    const pending = bg.pollStatus()
    requests[0].resolve(response('running', 1))
    await pending
    await vue.nextTick()
    assert.equal(bg.isPolling.value, false)
    app.isRunning = false
    await vue.nextTick()
    app.activeExecutionId = 'batch-a'
    app.activeExecutionStartedAt = 2
    app.isRunning = true
    await vue.nextTick()
    assert.equal(bg.isPolling.value, true)
    assert.equal(requests.length, 2)
    requests[1].resolve(response('completed', 3, { execution_id: 'batch-a', execution_started_at: 2 }))
    await settle()
    await vue.nextTick()
    assert.equal(bg.isPolling.value, false)
    app.activeExecutionId = 'batch-b'
    app.activeExecutionStartedAt = 4
    app.isRunning = true
    await vue.nextTick()
    assert.equal(bg.isPolling.value, true)
    assert.equal(requests.length, 3)
    requests[2].resolve(response('running', 5, { execution_id: 'batch-b', execution_started_at: 4 }))
    await settle()
    assert.equal(bg.taskStatus.value.execution_id, 'batch-b')
  } finally {
    unmount()
  }
})

test('a slow status response is applied before scheduling the next query three seconds later', async () => {
  const { bg, requests, clock, app } = createPolling()
  bg.startPolling()
  await clock.tick(9000)
  assert.equal(requests.length, 1, 'slow requests must not overlap or invalidate each other')
  requests[0].resolve(response('running', 1, { route_planning_failures: [{ diagnostic_id: 'slow' }] }))
  await settle()
  assert.equal(app.failures[0].diagnostic_id, 'slow')
  await clock.tick(2999)
  assert.equal(requests.length, 1)
  await clock.tick(1)
  assert.equal(requests.length, 2)
  requests[1].resolve(response('completed', 2))
  await settle()
  assert.equal(bg.taskStatus.value.status, 'completed')
  assert.equal(bg.isPolling.value, false)
  assert.equal(clock.timers.size, 0)
})

test('unresolved geometry does not block newer status or terminal diagnostics', async () => {
  let finishSnapshot
  const { bg, requests, clock, app } = createPolling({ loadSnapshot: () => new Promise(resolve => { finishSnapshot = resolve }) })
  bg.startPolling()
  requests[0].resolve(response('running', 1, { active_task_index: 0, route_ready: true }))
  await settle()
  assert.equal(typeof finishSnapshot, 'function')
  await clock.tick(3000)
  assert.equal(requests.length, 2)
  requests[1].resolve(response('error', 2, { active_task_index: 0, route_ready: true, route_planning_failures: [{ diagnostic_id: 'terminal' }] }))
  await settle()
  assert.equal(bg.taskStatus.value.status, 'error')
  assert.equal(app.failures[0].diagnostic_id, 'terminal')
  assert.equal(bg.isPolling.value, false)
  finishSnapshot({ success: true, route_ready: true, details: { run_coords: [[113, 22], [114, 22]] } })
  await settle()
  assert.equal(app.runData.status, 'error')
  assert.equal(app.isRunning, false)
})

test('a thirty second deadline aborts a hung request and polling recovers without clearing the administrator origin', async () => {
  const { bg, requests, clock, auth } = createPolling({ ignoreAbort: true })
  bg.startPolling()
  await clock.tick(29999)
  assert.equal(requests[0].options.signal?.aborted, false)
  await clock.tick(1)
  assert.equal(requests[0].options.signal.aborted, true)
  assert.equal(bg.isPolling.value, true)
  assert.equal(auth.adminOriginSession, 'A')
  await clock.tick(3000)
  assert.equal(requests.length, 2, 'even an adapter ignoring abort cannot hold the single flight forever')
  requests[1].resolve(response('running', 2))
  await settle()
  assert.equal(bg.taskStatus.value.last_update, 2)
  bg.stopPolling()
})

test('a stopped request cannot release a restarted request or schedule a duplicate timer', async () => {
  const { bg, requests, clock } = createPolling({ ignoreAbort: true })
  bg.startPolling()
  const old = bg.pollStatus()
  bg.stopPolling()
  assert.equal(requests[0].options.signal?.aborted, true)
  bg.startPolling()
  const current = bg.pollStatus()
  await old
  assert.equal(current, bg.pollStatus())
  assert.equal(requests.length, 2)
  requests[0].resolve(response('error', 9))
  requests[1].resolve(response('running', 2))
  await current
  assert.equal(bg.taskStatus.value.last_update, 2)
  await clock.tick(3000)
  assert.equal(requests.length, 3)
  bg.stopPolling()
})

test('changing session aborts the departed request while its late response cannot affect the new loop', async () => {
  const { bg, requests, clock, auth, watchers } = createPolling({ ignoreAbort: true })
  bg.startPolling()
  auth.sessionUUID = 'C'
  watchers[1].callback()
  assert.equal(requests[0].options.signal?.aborted, true)
  assert.equal(requests.length, 2)
  requests[0].resolve(response('error', 9))
  requests[1].resolve(response('running', 2))
  await settle()
  assert.equal(bg.taskStatus.value.last_update, 2)
  await clock.tick(3000)
  assert.equal(requests.length, 3)
  bg.stopPolling()
})

test('unmount aborts requests and prevents both state writes and rescheduling', async () => {
  const { bg, requests, clock, unmount } = createPolling({ ignoreAbort: true })
  bg.startPolling()
  unmount()
  assert.equal(requests[0].options.signal?.aborted, true)
  requests[0].resolve(response('error', 1))
  await clock.tick(60000)
  assert.equal(bg.taskStatus.value, null)
  assert.equal(bg.isPolling.value, false)
  assert.equal(requests.length, 1)
  assert.equal(clock.timers.size, 0)
})

test('a transient network failure keeps the polling loop alive', async () => {
  const { bg, requests, clock } = createPolling()
  bg.startPolling()
  requests[0].reject(new Error('temporary connection failure'))
  await settle()
  assert.equal(bg.isPolling.value, true)
  await clock.tick(3000)
  assert.equal(requests.length, 2)
  requests[1].resolve(response('completed', 2))
  await settle()
  assert.equal(bg.isPolling.value, false)
})

test('execution and timestamp guards retain the current batch and latest diagnostics', async () => {
  const { bg, requests, app } = createPolling()
  app.activeExecutionId = 'current'
  app.activeExecutionStartedAt = 2
  const query = async status => {
    const pending = bg.pollStatus()
    requests.at(-1).resolve({ success: true, task_status: status })
    await pending
  }
  await query({ execution_id: 'current', execution_started_at: 2, last_update: 3, status: 'running', route_planning_failures: [{ diagnostic_id: 'current' }] })
  await query({ execution_id: 'old', execution_started_at: 1, last_update: 9, status: 'error', route_planning_failures: [{ diagnostic_id: 'old' }] })
  await query({ execution_id: 'current', execution_started_at: 2, last_update: 2, status: 'completed' })
  assert.equal(bg.taskStatus.value.last_update, 3)
  assert.equal(app.failures[0].diagnostic_id, 'current')
  assert.equal(app.isRunning, true)
})

test('raw API forwards an optional abort signal without changing authentication or business headers', async () => {
  const requests = []
  const auth = {
    sessionUUID: 'C', adminOriginSession: 'A',
    getSessionHeaderValue: () => 'C', getAuthenticatedSessionHeaderValue: () => 'A',
    getAdminOriginHeaderValue: target => target === 'C' ? 'A' : '',
  }
  const callRawAPI = loadSource('frontend/src/services/api.js', {
    useAuthStore: () => auth,
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: true, json: async () => ({ success: true }) } },
  }, 'callRawAPI')
  const controller = new AbortController()
  await callRawAPI('/api/background_task/status', 'GET', null, { sessionContext: 'business', signal: controller.signal })
  assert.equal(requests[0].options.signal, controller.signal)
  assert.equal(requests[0].options.headers['X-Session-ID'], 'C')
  assert.equal(requests[0].options.headers['X-Admin-Origin-Session-ID'], 'A')
  await callRawAPI('/auth/user/sessions')
  assert.equal(requests[1].options.headers['X-Session-ID'], 'A')
  assert.equal(requests[1].options.signal, undefined)
})

test('raw API cancellation aborts an actual response body still being read', async () => {
  const server = createServer((_request, response) => {
    response.writeHead(200, { 'Content-Type': 'application/json' })
    response.write('{"success":')
  })
  let headersReceived
  const ready = new Promise(resolve => { headersReceived = resolve })
  const auth = { getAuthenticatedSessionHeaderValue: () => 'A', getAdminOriginHeaderValue: () => '' }
  const callRawAPI = loadSource('frontend/src/services/api.js', {
    useAuthStore: () => auth,
    fetch: async (...args) => { const response = await fetch(...args); headersReceived(); return response },
  }, 'callRawAPI')
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
    const controller = new AbortController()
    const pending = callRawAPI(`http://127.0.0.1:${server.address().port}/status`, 'GET', null, { signal: controller.signal })
    await ready
    controller.abort()
    await assert.rejects(pending, { name: 'AbortError' })
  } finally {
    server.closeAllConnections()
    await new Promise(resolve => server.close(resolve))
    assert.equal(server.listening, false)
  }
})
