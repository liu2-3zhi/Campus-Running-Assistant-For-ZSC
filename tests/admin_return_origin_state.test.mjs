import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const MAIN_SOURCE = readFileSync(
  resolve(PROJECT_ROOT, 'scripts/main.js'),
  'utf8',
)

const ORIGIN_SESSION = '11111111-1111-4111-8111-111111111111'
const CURRENT_SESSION = '22222222-2222-4222-8222-222222222222'
const NEW_SESSION = '33333333-3333-4333-8333-333333333333'
const AUTH_SESSION = '44444444-4444-4444-8444-444444444444'

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

  const context = vm.createContext(globals)
  const api = vm.runInContext(
    `${resolverSection}
     ${returnStateSection}
     ({ checkAdminReturnState, clearAdminReturnOriginState,
              getStoredAdminReturnOriginSession,
              getAdminViewOriginSessionUUID, verifyAdminReturnOriginSession });`,
    context,
  )

  return { api, storage, overlay, fetchCalls, globals, context }
}

function buildSessionTransitionHarness(responses) {
  const errors = []
  const harness = buildReturnStateHarness({
    fetchImpl: async url => {
      const expected = responses.shift()
      if (!expected) {
        errors.push(`unexpected request: ${url}`)
        return { ok: false, json: async () => ({ success: false }) }
      }
      const [expectedUrl, result] = expected
      if (url !== expectedUrl) {
        errors.push(`expected request ${expectedUrl}, got ${url}`)
      }
      return { ok: true, json: async () => result }
    },
  })
  const elements = new Map()
  const values = {
    'auth-username': 'admin',
    'auth-password': 'test-password',
    'auth-login-captcha': 'test-captcha',
  }
  function getElement(id) {
    if (!elements.has(id)) {
      const classes = new Set(id === 'auth-sms-section' ? ['hidden'] : [])
      elements.set(id, {
        value: values[id] || '',
        focus() {},
        classList: {
          add: name => classes.add(name),
          remove: name => classes.delete(name),
          contains: name => classes.has(name),
        },
      })
    }
    return elements.get(id)
  }
  const redirects = []
  harness.overlay.hidden = false
  Object.assign(harness.globals, {
    $: getElement,
    authLoginInProgress: false,
    authRequestGeneration: 0,
    themeBackgroundLoginSyncInFlight: false,
    currentAuthUsername: '',
    currentUserIsGuest: false,
    currentSessionInfo: { maxSessions: -1, currentCount: 0 },
    isMobileMode: false,
    captchaIds_login: 'test-captcha-id',
    captchaIds_mobile_login: 'test-mobile-captcha-id',
    capturePreLoginBackgroundSnapshot() {},
    getBackgroundPreviewPayload: () => ({}),
    syncThemeFromServer: async () => {},
    setButtonLoading() {},
    showButtonSuccess() {},
    showButtonError: (...args) => errors.push(args),
    showAuthSuccess() {},
    refreshCaptcha() {},
    logMessage_Error: (...args) => errors.push(args),
    setTimeout() {},
    updateSessionCountDisplay() {},
    updateAdminSessionCountDisplay() {},
    updateAdminSessionCountDisplayInline() {},
    generateUUID: () => NEW_SESSION,
    jsShowConfirm: async () => true,
    closeSessionPicker() {},
    Swal: { fire: async () => ({}), close() {} },
  })
  harness.globals.window.location.replace = path => redirects.push({
    path,
    hasOrigin: harness.storage.has('admin_return_origin'),
    overlayHidden: harness.overlay.hidden,
  })
  const handlers = vm.runInContext(
    `${extractSection('function ensureAuthLoginSessionUUID() {', 'const AUTH_CONTEXT_API_METHODS =')}
     ${extractSection('async function handleAuthLogin(isMobile_use = false) {', 'function handlePhoneNotRegisteredRedirect(')}
     ${extractSection('async function handle2FAVerify() {', 'async function handleAuthRegister(')}
     ${extractSection('async function createNewSessionFromPicker() {', 'async function deleteSessionFromPicker(')}
     ({ handleAuthLogin, handle2FAVerify, createNewSessionFromPicker });`,
    harness.context,
  )
  return { ...harness, handlers, elements, errors, redirects, responses }
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

for (const [name, result, expectedSession] of [
  ['business session', { session_id: NEW_SESSION, auth_session_id: AUTH_SESSION }, NEW_SESSION],
  ['authentication session only', { auth_session_id: AUTH_SESSION }, null],
]) {
  test(`fresh login with ${name} clears the stored admin return origin`, async () => {
    const harness = buildSessionTransitionHarness([
      ['/auth/login', { success: true, ...result }],
    ])

    await harness.handlers.handleAuthLogin()

    assert.deepEqual(harness.errors, [])
    assert.equal(harness.responses.length, 0)
    assert.equal(harness.globals.sessionUUID, expectedSession)
    assert.equal(harness.globals.authSessionUUID, AUTH_SESSION)
    assert.equal(harness.storage.has('admin_return_origin'), false)
    assert.equal(harness.overlay.hidden, true)
  })

  test(`2FA login with ${name} clears the origin after verification`, async () => {
    const harness = buildSessionTransitionHarness([
      ['/auth/login', { success: true, requires_2fa: true, two_fa_challenge: 'test-challenge' }],
      ['/auth/2fa/verify_login', { success: true, ...result }],
    ])

    await harness.handlers.handleAuthLogin()
    assert.equal(harness.storage.get('admin_return_origin'), ORIGIN_SESSION)
    assert.equal(harness.overlay.hidden, false)
    assert.equal(harness.globals.window.temp2FAChallenge, 'test-challenge')

    harness.elements.get('auth-2fa-code').value = '123456'
    await harness.handlers.handle2FAVerify()

    assert.deepEqual(harness.errors, [])
    assert.equal(harness.responses.length, 0)
    assert.equal(harness.globals.sessionUUID, expectedSession)
    assert.equal(harness.globals.authSessionUUID, AUTH_SESSION)
    assert.equal(harness.storage.has('admin_return_origin'), false)
    assert.equal(harness.overlay.hidden, true)
    assert.equal(harness.globals.window.temp2FAChallenge, undefined)
  })
}

test('creating a new session clears the stored admin return origin before redirecting', async () => {
  const harness = buildSessionTransitionHarness([
    ['/auth/user/sessions', { success: true, max_sessions: -1, sessions: [] }],
    ['/auth/user/create_session_persistence', { success: true, session_id: NEW_SESSION }],
  ])

  await harness.handlers.createNewSessionFromPicker()

  assert.deepEqual(harness.errors, [])
  assert.equal(harness.responses.length, 0)
  assert.equal(harness.globals.sessionUUID, NEW_SESSION)
  assert.equal(harness.storage.has('admin_return_origin'), false)
  assert.equal(harness.overlay.hidden, true)
  assert.deepEqual(harness.redirects, [{
    path: `/uuid=${NEW_SESSION}`,
    hasOrigin: false,
    overlayHidden: true,
  }])
})
