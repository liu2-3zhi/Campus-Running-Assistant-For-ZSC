import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const MAIN_SOURCE = readFileSync(
  resolve(PROJECT_ROOT, 'scripts/main.js'),
  'utf8',
)

const ORIGIN_SESSION = '11111111-1111-4111-8111-111111111111'
const CURRENT_SESSION = '22222222-2222-4222-8222-222222222222'

function extractSection(startMarker, endMarker) {
  const start = MAIN_SOURCE.indexOf(startMarker)
  assert.notEqual(start, -1, `missing marker: ${startMarker}`)
  const end = MAIN_SOURCE.indexOf(endMarker, start)
  assert.notEqual(end, -1, `missing end marker: ${endMarker}`)
  return MAIN_SOURCE.slice(start, end)
}

/** 提取返回按钮相关的解析/校验函数并在受控作用域里执行。 */
function buildReturnStateHarness({
  storedOrigin = ORIGIN_SESSION,
  currentSession = CURRENT_SESSION,
  fetchResult = { success: true, uuid_type: 'unknown' },
  fetchImpl = null,
} = {}) {
  const resolverSection = extractSection(
    'function isUsableClientSessionUUID(value) {',
    'function isAdminLikeLegacyUser() {',
  )
  const returnStateSection = extractSection(
    'function returnToAdminSession() {',
    'function initDraggableAdminBtn() {',
  )

  const storage = new Map()
  if (storedOrigin) {
    storage.set('admin_return_origin', storedOrigin)
  }
  const overlay = {
    hidden: true,
    classList: {
      add(name) {
        if (name === 'hidden') overlay.hidden = true
      },
      remove(name) {
        if (name === 'hidden') overlay.hidden = false
      },
    },
  }
  const fetchCalls = []

  const globals = {
    console: { log() {}, info() {}, warn() {}, error() {} },
    logMessage_Info() {},
    logMessage_Warning() {},
    logMessage_Error() {},
    localStorage: {
      getItem(key) {
        return storage.has(key) ? storage.get(key) : null
      },
      setItem(key, value) {
        storage.set(key, value)
      },
      removeItem(key) {
        storage.delete(key)
      },
    },
    sessionStorage: { getItem: () => null, setItem() {} },
    window: { location: { pathname: `/uuid=${currentSession}`, href: '' } },
    document: {
      getElementById(id) {
        return id === 'admin-return-overlay' ? overlay : null
      },
    },
    sessionUUID: currentSession,
    authSessionUUID: null,
    currentUserData: { group: 'super_admin' },
    getUUIDFromURL: () => currentSession,
    buildLegacyUiPath: (path = '/') => path,
    initDraggableAdminBtn() {},
    fetch: async (url, options) => {
      fetchCalls.push({ url, options })
      if (fetchImpl) {
        return fetchImpl(url, options)
      }
      return { ok: true, json: async () => fetchResult }
    },
  }

  const factory = new Function(
    ...Object.keys(globals),
    `${resolverSection}
     ${returnStateSection}
     return { checkAdminReturnState, clearAdminReturnOriginState,
              getStoredAdminReturnOriginSession,
              getAdminViewOriginSessionUUID, verifyAdminReturnOriginSession };`,
  )
  const api = factory(...Object.values(globals))

  return { api, storage, overlay, fetchCalls, globals }
}

test('stale admin return origin is cleared when the origin session is gone', async () => {
  const harness = buildReturnStateHarness({
    fetchResult: { success: true, uuid_type: 'unknown' },
  })

  harness.api.checkAdminReturnState()
  // 先按记录显示按钮，同时就必须发起来源会话校验（异步确认是否存在）。
  assert.equal(harness.overlay.hidden, false)
  assert.equal(harness.fetchCalls.length, 1)
  assert.equal(harness.fetchCalls[0].url, '/auth/check_uuid_type')
  assert.deepEqual(JSON.parse(harness.fetchCalls[0].options.body), {
    uuid: ORIGIN_SESSION,
  })

  await harness.api.verifyAdminReturnOriginSession(
    ORIGIN_SESSION,
    CURRENT_SESSION,
  )

  assert.equal(harness.storage.has('admin_return_origin'), false)
  assert.equal(harness.overlay.hidden, true)
})

test('live admin return origin keeps the button and the stored record', async () => {
  const harness = buildReturnStateHarness({
    fetchResult: { success: true, uuid_type: 'system_account' },
  })

  harness.api.checkAdminReturnState()
  await harness.api.verifyAdminReturnOriginSession(
    ORIGIN_SESSION,
    CURRENT_SESSION,
  )

  assert.equal(harness.storage.get('admin_return_origin'), ORIGIN_SESSION)
  assert.equal(harness.overlay.hidden, false)
})

test('origin check is skipped when the current session is the origin', async () => {
  const harness = buildReturnStateHarness({ currentSession: ORIGIN_SESSION })

  harness.api.checkAdminReturnState()
  await harness.api.verifyAdminReturnOriginSession(
    ORIGIN_SESSION,
    ORIGIN_SESSION,
  )

  assert.equal(harness.fetchCalls.length, 0)
  assert.equal(harness.overlay.hidden, true)
  assert.equal(harness.storage.has('admin_return_origin'), false)
})

test('origin check is not repeated for the same page session', async () => {
  const harness = buildReturnStateHarness({
    fetchResult: { success: true, uuid_type: 'unknown' },
  })

  harness.api.checkAdminReturnState()
  await harness.api.verifyAdminReturnOriginSession(
    ORIGIN_SESSION,
    CURRENT_SESSION,
  )
  await harness.api.verifyAdminReturnOriginSession(
    ORIGIN_SESSION,
    CURRENT_SESSION,
  )

  assert.equal(harness.fetchCalls.length, 1)
})

test('fresh login and new session clear the stored admin return origin', () => {
  const clearCalls = MAIN_SOURCE.split('clearAdminReturnOriginState(').length - 1

  // 登录成功（含 2FA）、创建新会话、来源会话失效三处都必须清理记录。
  assert.ok(clearCalls >= 6, `expected clear call sites, got ${clearCalls}`)
  const loginSection = extractSection(
    'async function handleAuthLogin(isMobile_use = false) {',
    'themeBackgroundLoginSyncInFlight = true;',
  )
  assert.match(loginSection, /clearAdminReturnOriginState\(/)
  assert.match(
    MAIN_SOURCE,
    /function clearAdminReturnOriginState\(reason = ""\)/,
  )
  assert.match(
    MAIN_SOURCE,
    /verifyAdminReturnOriginSession\(originSession, currentUUID\)/,
  )
})
