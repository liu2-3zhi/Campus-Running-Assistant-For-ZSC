import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(resolve(import.meta.dirname, '..', 'scripts/legacy-reminders.js'), 'utf8')
const SESSION_ID = '11111111-1111-4111-8111-111111111111'

function deferred() {
  let resolvePromise
  const promise = new Promise((resolve) => { resolvePromise = resolve })
  return { promise, resolve: resolvePromise }
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve))
}

function createHarness(fetchImpl, swalImpl = () => Promise.resolve(), authLoginVisible = false) {
  const fired = []
  const intervals = new Map()
  let nextIntervalId = 1
  const timeouts = new Map()
  let nextTimeoutId = 1
  let currentPopup = null
  let closeCount = 0
  const context = vm.createContext({
    sessionUUID: SESSION_ID,
    window: { editormd: null },
    document: {
      getElementById() { return null },
      querySelector() { return null },
      head: { appendChild() {} },
      body: { appendChild() {}, removeChild() {} },
      createElement() { return { style: {}, innerHTML: '' } },
    },
    fetch: fetchImpl,
    Swal: {
      fire(options) {
        fired.push(options)
        currentPopup = { classList: { contains: (name) => name === 'reminder-alert-popup' } }
        return swalImpl(options)
      },
      getPopup() { return currentPopup },
      isVisible() { return currentPopup !== null },
      close() { closeCount += 1; currentPopup = null },
    },
    AbortController,
    setInterval(callback) {
      const id = nextIntervalId++
      intervals.set(id, callback)
      return id
    },
    clearInterval(id) { intervals.delete(id) },
    setTimeout(callback) { const id = nextTimeoutId++; timeouts.set(id, callback); return id },
    clearTimeout(id) { timeouts.delete(id) },
    escapeHtml: (value) => String(value),
    isAuthLoginViewVisible: () => authLoginVisible,
    addAdminViewOriginSessionHeader: (headers) => headers,
    console: { log() {}, warn() {}, error() {} },
  })
  vm.runInContext(source, context)
  return {
    context,
    fired,
    intervals,
    timeouts,
    get closeCount() { return closeCount },
    setPopup(popup) { currentPopup = popup },
  }
}

function remindersResponse(reminders) {
  return { ok: true, status: 200, json: async () => ({ success: true, reminders }) }
}

test('reminders do not fetch before authenticated startup', async () => {
  let fetchCount = 0
  const harness = createHarness(async () => {
    fetchCount += 1
    return remindersResponse([{ id: 'old', title: 'old', message: 'old' }])
  })

  await harness.context.checkAndShowReminders()
  assert.equal(fetchCount, 0)
  assert.equal(harness.fired.length, 0)
})

test('authenticated multi-account school login view does not suppress reminders', async () => {
  let fetchCount = 0
  const harness = createHarness(async () => {
    fetchCount += 1
    return remindersResponse([])
  }, () => Promise.resolve(), true)
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  assert.equal(fetchCount, 1)
})

test('visible system authentication form blocks reminder checks', async () => {
  let fetchCount = 0
  const harness = createHarness(async () => {
    fetchCount += 1
    return remindersResponse([])
  })
  harness.context.document.getElementById = (id) => id === 'auth-login-container'
    ? { getClientRects: () => [{}] }
    : null
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  assert.equal(fetchCount, 0)
})

test('stopping reminders discards a response that arrives after logout', async () => {
  const response = deferred()
  const harness = createHarness(() => response.promise)
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  harness.context.stopReminderChecker()
  response.resolve(remindersResponse([{ id: 'late', title: 'late', message: 'late' }]))
  await flush()

  assert.equal(harness.fired.length, 0)
  assert.equal(harness.intervals.size, 0)
})

test('overlapping checks queue reminders instead of replacing the active alert', async () => {
  const firstAlert = deferred()
  const secondAlert = deferred()
  const alerts = [firstAlert, secondAlert]
  const responses = [
    remindersResponse([
      { id: 'a', title: 'A', message: 'A' },
      { id: 'b', title: 'B', message: 'B' },
    ]),
    remindersResponse([{ id: 'c', title: 'C', message: 'C' }]),
  ]
  const harness = createHarness(async () => responses.shift(), () => alerts.shift()?.promise ?? Promise.resolve())
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  assert.equal(harness.fired.length, 1)

  await harness.context.checkAndShowReminders()
  assert.equal(harness.fired.length, 1)
  firstAlert.resolve()
  await flush()
  assert.equal(harness.fired.length, 2)
  secondAlert.resolve()
  await flush()
  assert.equal(harness.fired.length, 3)
  assert.deepEqual(harness.fired.map((alert) => alert.title.replace(/ \(\d+\/\d+\)$/, '')), ['A', 'B', 'C'])
})

test('stopping reminders never closes a non-reminder login alert', () => {
  const harness = createHarness(async () => remindersResponse([]))
  harness.context.startReminderChecker(SESSION_ID)
  harness.setPopup({ classList: { contains: () => false } })
  harness.context.stopReminderChecker()
  assert.equal(harness.closeCount, 0)
})

test('failed logout restart does not repeat acknowledged reminders', async () => {
  const harness = createHarness(async () => remindersResponse([{ id: 'seen', title: 'Seen', message: 'Seen' }]))
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  assert.equal(harness.fired.length, 1)
  harness.context.stopReminderChecker(true)
  harness.context.startReminderChecker(SESSION_ID, true)
  await flush()
  assert.equal(harness.fired.length, 1)
})

test('a queued reminder appears soon after another alert closes', async () => {
  const harness = createHarness(async () => remindersResponse([{ id: 'queued', title: 'Queued', message: 'Queued' }]))
  harness.setPopup({ classList: { contains: () => false } })
  harness.context.startReminderChecker(SESSION_ID)
  await flush()
  assert.equal(harness.fired.length, 0)
  assert.equal(harness.timeouts.size, 1)
  harness.setPopup(null)
  const [id, callback] = [...harness.timeouts.entries()][0]
  harness.timeouts.delete(id)
  callback()
  await flush()
  assert.equal(harness.fired.length, 1)
})
