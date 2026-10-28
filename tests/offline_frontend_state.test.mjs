import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const vue = require('vue')
const { defineStore, createPinia } = require('pinia')
const read = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8')

function appStore() {
  const source = read('frontend/src/stores/app.js').replace(/^import .*$/gm, '').replace('export const useAppStore', 'const useAppStore')
  return vm.runInNewContext(source + '\nuseAppStore', { ...vue, defineStore })(createPinia())
}

function paymentRuntime(kind, offline = true) {
  const app = appStore()
  app.bindBusinessSession('target-b')
  if (app.applyBusinessMode) app.applyBusinessMode({ is_offline_mode: offline }, app.captureBusinessContext())
  const requests = []
  const modalCalls = []
  const auth = { sessionUUID: 'target-b', studentId: 'NULL' }
  const context = {
    console, URLSearchParams, setTimeout, clearTimeout,
    window: { Swal: { fire: async options => { modalCalls.push(options); return { isConfirmed: false } }, close() {} } },
    document: { getElementById: () => null, addEventListener() {} },
    useAppStore: () => app, useAuthStore: () => auth,
    callRawAPI: async (...args) => { requests.push(args); return { success: true, has_overdue: false, records: [] } },
    callAPI: async () => ({ success: true, is_offline_mode: offline }),
    sanitizeSvg: value => value,
    IS_OFFLINE: offline, sessionUUID: 'target-b', currentUserData: { student_id: 'NULL' },
    captureLegacyBusinessContext: () => ({ session: 'target-b', generation: 1 }),
    isCurrentLegacyBusinessContext: () => true,
    ensureLegacyBusinessMode: async () => offline,
    addAdminViewOriginSessionHeader(headers) { headers['X-Admin-Origin-Session-ID'] = 'origin-a' },
    fetch: async (...args) => { requests.push(args); return { json: async () => ({ success: true, has_overdue: false, records: [] }) } },
    showModalAlert() {},
  }
  context.Swal = context.window.Swal
  const source = read(kind === 'vue' ? 'frontend/src/composables/usePayment.js' : 'scripts/legacy-payment-user.js')
    .replace(/^import .*$/gm, '').replace(/^export /gm, '')
  vm.createContext(context)
  vm.runInContext(source, context)
  return { app, auth, context, requests, modalCalls }
}

test('business mode stays unknown until a successful explicit server flag and rejects A-B-A responses', () => {
  const app = appStore()
  app.bindBusinessSession('A')
  assert.equal(app.isOfflineMode, null)
  const old = app.captureBusinessContext()
  assert.equal(app.applyBusinessMode({ offline: true, success: false }, old), false)
  assert.equal(app.isOfflineMode, null)
  app.applyBusinessMode({ success: true, is_offline_mode: true }, old)
  assert.equal(app.isOfflineMode, true)
  app.bindBusinessSession('B')
  app.bindBusinessSession('A')
  assert.equal(app.isOfflineMode, null)
  assert.equal(app.applyBusinessMode({ is_offline_mode: false }, old), false)
  assert.equal(app.isOfflineMode, null)
})

for (const kind of ['legacy', 'vue']) {
  test(`${kind} bottom overdue function skips offline before any network or dialog`, async () => {
    const runtime = paymentRuntime(kind)
    assert.equal(await runtime.context.checkOverdueBeforeStart('123456'), true)
    assert.equal(runtime.requests.length, 0)
    assert.equal(runtime.modalCalls.length, 0)
  })

  test(`${kind} explicit NULL or empty account scope never becomes an unfiltered request`, async () => {
    const runtime = paymentRuntime(kind, false)
    assert.equal(await runtime.context.checkOverdueBeforeStart('NULL'), true)
    assert.equal(await runtime.context.checkOverdueBeforeStart([]), true)
    assert.equal(runtime.requests.length, 0)
  })

  test(`${kind} overdue details request only explicit accounts and retain business context`, async () => {
    const runtime = paymentRuntime(kind, false)
    await runtime.context.showOverduePaymentModal([{ school_username: '123456' }, { school_username: '654321' }])
    const [url, ...args] = runtime.requests[0]
    const parsed = new URL(url, 'https://app.test')
    assert.deepEqual(parsed.searchParams.getAll('school_usernames'), ['123456', '654321'])
    if (kind === 'vue') assert.equal(args[2].sessionContext, 'business')
    else assert.equal(args[0].headers['X-Admin-Origin-Session-ID'], 'origin-a')
  })

  test(`${kind} ignores a delayed overdue response after the business session changes`, async () => {
    const runtime = paymentRuntime(kind, false)
    let resolve
    const result = new Promise(done => { resolve = done })
    if (kind === 'vue') runtime.context.callRawAPI = () => result
    else runtime.context.fetch = () => result.then(value => ({ json: async () => value }))
    const pending = runtime.context.checkOverdueBeforeStart('123456')
    await new Promise(done => setImmediate(done))
    if (kind === 'vue') {
      runtime.auth.sessionUUID = 'target-c'
      runtime.app.bindBusinessSession('target-c')
    } else runtime.context.isCurrentLegacyBusinessContext = () => false
    resolve({ success: true, has_overdue: true, overdue_accounts: [{ school_username: '123456' }] })
    assert.equal(await pending, false)
    assert.equal(runtime.modalCalls.length, 0)
  })
}
