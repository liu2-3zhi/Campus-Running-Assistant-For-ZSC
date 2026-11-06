import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const vueSource = read('frontend/src/services/socket.js')
const legacySource = read('scripts/legacy-app-runtime.js')
const mainSource = read('scripts/main.js')
const multiSource = read('scripts/legacy-multi-accounts.js')
const mainView = read('frontend/src/views/MainView.vue')
const multiView = read('frontend/src/views/MultiAccountView.vue')
const settle = () => new Promise(resolve => setImmediate(resolve))

function extract(source, name) {
  const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'))
  assert.notEqual(start, -1, name)
  return source.slice(start, source.indexOf('\n}', start) + 2)
}

function createClock() {
  let now = 0, nextId = 0
  const timers = new Map()
  const schedule = (callback, delay, interval = 0) => {
    const id = ++nextId
    timers.set(id, { callback, at: now + delay, interval })
    return id
  }
  return {
    timers,
    Date: class extends Date { static now() { return now } },
    setTimeout: (callback, delay) => schedule(callback, delay),
    clearTimeout: id => timers.delete(id),
    setInterval: (callback, delay) => schedule(callback, delay, delay),
    clearInterval: id => timers.delete(id),
    tick(delay) {
      const target = now + delay
      while (true) {
        const next = [...timers].filter(([, timer]) => timer.at <= target)
          .sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0]
        if (!next) break
        const [id, timer] = next
        now = timer.at
        if (timer.interval) timer.at += timer.interval
        else timers.delete(id)
        timer.callback()
      }
      now = target
    },
  }
}

function setup(kind, { synchronousConnect = false } = {}) {
  const clock = createClock(), clients = [], transitions = []
  const auth = { sessionUUID: 'session-A' }
  const context = vm.createContext({
    ...clock, console: { info() {}, warn() {} },
    sessionUUID: auth.sessionUUID,
    verificationCodesSocketHealthy: false, isInNetworkErrorState: false,
    logMessage_Info() {}, logMessage_Warning() {}, logMessage_Error() {},
    getAdminViewOriginSessionUUID: () => '', refreshUserList() {},
    stopVerificationCodesPollingFallback() {}, syncVerificationCodesPollingByModalState() {},
    syncUserListPollingBySocketState() {
      transitions.push(vm.runInContext('!!socket?.connected', context))
    },
    syncMultiAccountAutoRefreshBySocketState() {},
    useAuthStore: () => auth, useAppStore: () => ({}),
    io: options => {
      const events = new Map()
      const client = {
        events,
        connected: false, io: { opts: { ...options } }, attempts: 0, closes: 0, emitted: [],
        on(event, callback) { events.set(event, callback) },
        emit(event, payload) { this.emitted.push({ event, payload, at: clock.Date.now() }) },
        receive(event, payload) { events.get(event)?.(payload) },
        connect() { this.attempts++; if (synchronousConnect) this.establish() },
        establish() { this.connected = true; this.receive('connect') },
        disconnect() {
          this.closes++
          const wasConnected = this.connected
          this.connected = false
          if (wasConnected) this.receive('disconnect', 'io client disconnect')
        },
        removeAllListeners() { events.clear() },
      }
      clients.push(client)
      return client
    },
  })
  const source = kind === 'Vue'
    ? vueSource.replace(/^import .*$/gm, '').replace(/export function /g, 'function ')
      .replace("import('@/services/api')", 'Promise.resolve({ callAPI: async () => null })')
    : legacySource.slice(legacySource.indexOf('let socket = null;'), legacySource.indexOf('function enhanceMapInteraction('))
  const runtime = vm.runInContext(`${source}\n({ connectWebSocket${kind === 'Vue' ? ', disconnectWebSocket, disableReconnection, enableReconnection, onWebSocketStatus, isWebSocketConnected' : ''} })`, context)
  if (kind === 'Vue') runtime.onWebSocketStatus(value => transitions.push(value))
  return { clock, clients, context, runtime, transitions, auth }
}

for (const kind of ['Vue', 'legacy']) {
  test(`${kind}: sends heartbeats every 500ms and immediately reconnects after 2s without ACK`, async () => {
    const ctx = setup(kind)
    ctx.runtime.connectWebSocket()
    const client = ctx.clients[0]
    client.establish()
    await settle()
    ctx.clock.tick(1500)
    assert.deepEqual(client.emitted.filter(item => item.event === 'heartbeat' && item.at > 0).map(item => item.at), [500, 1000, 1500])
    ctx.clock.tick(499)
    assert.equal(client.closes, 0)
    ctx.clock.tick(1)
    assert.equal(client.closes, 1)
    assert.equal(client.attempts, 2)
    assert.equal(ctx.transitions.at(-1), false, 'disconnect listeners must activate the polling fallback before reconnecting')
    assert.equal(ctx.clock.timers.size, 0, 'the lost connection must release its heartbeat timers')
    ctx.clock.tick(30000)
    assert.equal(client.attempts, 2, 'Socket.IO owns further retries, without an extra reconnect loop')
    client.establish()
    await settle()
    assert.equal(ctx.transitions.at(-1), true)
    ctx.clock.tick(2000)
    assert.equal(client.closes, 2, 'reconnecting starts a fresh watchdog')
  })

  test(`${kind}: every ACK renews the exact 2s deadline independently of the send interval`, async () => {
    const ctx = setup(kind)
    ctx.runtime.connectWebSocket()
    const client = ctx.clients[0]
    client.establish()
    await settle()
    for (let index = 0; index < 8; index++) {
      ctx.clock.tick(index === 0 ? 625 : 500)
      client.receive('heartbeat_ack', { ts: 123 })
    }
    assert.equal(client.closes, 0)
    ctx.clock.tick(1999)
    assert.equal(client.closes, 0)
    ctx.clock.tick(1)
    assert.equal(client.closes, 1, 'must not wait until the next 500ms heartbeat tick')
  })

  test(`${kind}: deliberate disconnect cancels both timers and ignores a late ACK`, async () => {
    const ctx = setup(kind)
    ctx.runtime.connectWebSocket()
    const client = ctx.clients[0]
    client.establish()
    await settle()
    client.disconnect()
    client.receive('heartbeat_ack', {})
    assert.equal(ctx.clock.timers.size, 0)
    ctx.clock.tick(10000)
    assert.equal(client.attempts, 1)
  })

  test(`${kind}: event listeners exist before a synchronous connection succeeds`, async () => {
    const ctx = setup(kind, { synchronousConnect: true })
    ctx.runtime.connectWebSocket()
    await settle()
    assert.equal(ctx.transitions.at(-1), true)
    ctx.clock.tick(2000)
    assert.equal(ctx.clients[0].closes, 1)
  })

  test(`${kind}: replacing a pending connection closes it and ignores its late events`, async () => {
    const ctx = setup(kind)
    ctx.runtime.connectWebSocket()
    const old = ctx.clients[0]
    const oldAck = old.events.get('heartbeat_ack')
    const oldDisconnect = old.events.get('disconnect')
    ctx.runtime.connectWebSocket()
    const current = ctx.clients[1]
    assert.equal(old.closes, 1)
    current.establish()
    await settle()
    ctx.clock.tick(750)
    oldAck({})
    oldDisconnect('transport close')
    ctx.clock.tick(1250)
    assert.equal(current.closes, 1, 'the old connection must not renew or stop the current watchdog')
  })

  test(`${kind}: cancelled timers from a previous connection run cannot close the reconnected socket`, async () => {
    const ctx = setup(kind)
    ctx.runtime.connectWebSocket()
    const client = ctx.clients[0]
    client.establish()
    await settle()
    const oldCallbacks = [...ctx.clock.timers.values()].map(timer => timer.callback)
    client.disconnect()
    client.establish()
    await settle()
    const heartbeatCount = client.emitted.length
    oldCallbacks.forEach(callback => callback())
    assert.equal(client.emitted.length, heartbeatCount)
    assert.equal(client.closes, 1)
    ctx.clock.tick(2000)
    assert.equal(client.closes, 2, 'the current watchdog still works')
  })
}

test('Vue: network-error pause clears timers and does not revive the connection', async () => {
  const ctx = setup('Vue')
  ctx.runtime.connectWebSocket()
  const client = ctx.clients[0]
  client.establish()
  await settle()
  ctx.runtime.disableReconnection()
  ctx.clock.tick(10000)
  assert.equal(ctx.clock.timers.size, 0)
  assert.equal(client.attempts, 1)
  ctx.runtime.enableReconnection()
  assert.equal(client.attempts, 2)
})

for (const [name, source, start, stop, declarations] of [
  ['Vue single-account', mainView, 'startUserRefresh', 'stopUserRefresh', 'let userRefreshTimer = null; let userRefreshRequestId = 0; let viewMounted = true;'],
  ['Vue multi-account', multiView, 'startAutoRefresh', 'stopAutoRefresh', 'let autoRefreshTimer = null; let autoRefreshRequestId = 0; let viewMounted = true;'],
  ['legacy single-account', mainSource, 'startUserListPollingFallback', 'stopUserListPollingFallback', 'let refreshUserListInterval = null; let isInNetworkErrorState = false;'],
  ['legacy verification codes', mainSource, 'startVerificationCodesPollingFallback', 'stopVerificationCodesPollingFallback', 'let verificationCodesPollingTimer = null; let verificationCodesSocketHealthy = false; const VERIFICATION_CODES_POLLING_MS = 30000;'],
]) {
  test(`${name}: falling back starts the first HTTP query immediately and stops it on recovery`, () => {
    const clock = createClock(), calls = []
    let connected = false
    const context = vm.createContext({ ...clock,
      isWebSocketConnected: () => connected,
      refreshUsers: () => calls.push('query'), refreshUserList: () => calls.push('query'),
      pollAccountsFallback: () => calls.push('query'), refreshOpenVerificationCodeModals: () => calls.push('query'),
      logMessage_Info() {},
    })
    const schedule = name === 'Vue multi-account' ? extract(source, 'scheduleAutoRefresh') : ''
    const runtime = vm.runInContext(`${declarations}\n${schedule}\n${extract(source, start)}\n${extract(source, stop)}\n({start: ${start}, stop: ${stop}})`, context)
    runtime.start()
    assert.deepEqual(calls, ['query'], 'must not wait for the regular polling interval')
    runtime.stop()
    connected = true
    clock.tick(30000)
    assert.equal(calls.length, 1)
    assert.equal(clock.timers.size, 0)
  })
}

test('legacy: heartbeat timeout immediately starts both account fallbacks and recovery invalidates their pending work', async () => {
  const ctx = setup('legacy')
  let userQueries = 0, multiQueries = 0, resolveMulti
  ctx.context.refreshUserList = () => { userQueries++ }
  ctx.context.document = { getElementById: () => ({ classList: { contains: () => false } }) }
  ctx.context.console = { log() {}, info() {}, warn() {} }
  ctx.context.loadInitialData = () => {
    multiQueries++
    return new Promise(resolve => { resolveMulti = resolve })
  }
  const helpers = [
    ...['isWebSocketConnected', 'stopUserListPollingFallback', 'startUserListPollingFallback', 'syncUserListPollingBySocketState'].map(name => extract(mainSource, name)),
    ...['clearMultiAccountAutoRefreshTimer', 'startMultiAccountAutoRefresh', 'syncMultiAccountAutoRefreshBySocketState'].map(name => extract(multiSource, name)),
  ].join('\n')
  vm.runInContext(`let refreshUserListInterval = null; let multiAccountAutoRefreshInterval = null;
    let isMultiAccountAutoRefreshRunning = false; let isMultiAccountAutoRefreshDesired = true;
    let multiAccountAutoRefreshGeneration = 0;\n${helpers}`, ctx.context)
  ctx.runtime.connectWebSocket()
  const client = ctx.clients[0]
  client.establish()
  const queriesBeforeTimeout = userQueries
  ctx.clock.tick(2000)
  assert.equal(userQueries, queriesBeforeTimeout + 1)
  assert.equal(multiQueries, 1)
  client.establish()
  resolveMulti({ success: false })
  await settle()
  assert.equal([...ctx.clock.timers.values()].some(timer => timer.interval === 30000), false)
  assert.equal(vm.runInContext('isMultiAccountAutoRefreshRunning', ctx.context), false)
  assert.equal(vm.runInContext('multiAccountAutoRefreshInterval', ctx.context), null)
  client.disconnect()
  vm.runInContext('stopUserListPollingFallback(); clearMultiAccountAutoRefreshTimer();', ctx.context)
  resolveMulti({ success: false })
  await settle()
  assert.equal(ctx.clock.timers.size, 0)
})
