import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const runtimeSource = readFileSync(new URL('../scripts/legacy-app-runtime.js', import.meta.url), 'utf8')
const mainSource = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const SESSION_A = '11111111-1111-4111-8111-111111111111'
const SESSION_B = '22222222-2222-4222-8222-222222222222'
const businessContextSource = mainSource.slice(
  mainSource.indexOf('let IS_OFFLINE = null;'),
  mainSource.indexOf('async function ensureLegacyBusinessMode()'),
)
const initializationSource = runtimeSource.slice(0, runtimeSource.indexOf('async function restoreMobileTaskState()'))

function createHarness({ mobile = false, guest = false, pathname = `/uuid=${SESSION_A}`, initialSession = null } = {}) {
  const elements = new Map()
  const events = []
  const notices = []
  let resetCount = 0
  let modeQuery = async () => ({ success: true, is_multi_account_mode: false, is_offline_mode: false })
  const element = id => {
    if (!elements.has(id)) {
      const classes = new Set(id.includes('login-container') ? ['hidden'] : [])
      elements.set(id, {
        id, style: {}, value: '', children: [],
        classList: {
          add(...names) { names.forEach(name => classes.add(name)) },
          remove(...names) { names.forEach(name => classes.delete(name)) },
          contains(name) { return classes.has(name) },
        },
        appendChild(child) { this.children.push(child) },
        addEventListener() {},
      })
    }
    return elements.get(id)
  }
  const noop = () => {}
  const context = vm.createContext({
    sessionUUID: initialSession,
    window: { location: { pathname } },
    document: { getElementById: element, createElement: element },
    $: element,
    console: Object.fromEntries(['info', 'log', 'warn', 'error'].map(level => [level, (...args) => events.push({ level, args })])),
    Date,
    setTimeout: () => 1,
    clearTimeout: noop,
    isMobileMode: mobile,
    appInitialized: false,
    cdnErrorTimer: null,
    themeBackgroundAuthStateResolved: false,
    themeBackgroundAuthenticatedSession: false,
    currentThemeConfig: {},
    currentThemeStyle: 'default',
    availableThemeStyles: [],
    pythonParams: {},
    currentUserData: {},
    currentUserIsGuest: false,
    currentAuthUsername: null,
    Swal: { fire: async notice => { notices.push(notice); return { isConfirmed: false } } },
    detectMobileDevice: () => mobile,
    getCachedThemePreference: () => 'light',
    getCachedThemeStyle: () => 'default',
    resolveThemeRequestSessionUUID: () => pathname.match(/uuid=([^/]+)/)?.[1] || '',
    withLegacyInitializationTimeout: promise => Promise.resolve(promise),
    fetch: async () => ({ status: 200, json: async () => ({ success: true, uuid_type: guest ? 'guest' : 'system_account' }) }),
    checkAuthStatus: async () => {
      context.captureLegacyBusinessContext()
      return true
    },
    loadInitialData: async () => {
      context.captureLegacyBusinessContext()
      return { success: true, users: [], is_authenticated: true, is_guest: guest, auth_group: 'user' }
    },
    callPythonAPI: async method => {
      assert.equal(method, 'get_session_mode_info')
      return modeQuery()
    },
    getInitialDataFailureNotice: () => null,
    getLegacyActorIdentity: () => ({ auth_username: 'initialization-test' }),
    resetUI: () => { resetCount++; element('login-container').classList.add('hidden') },
    showAuthLogin: () => element('auth-login-container').classList.remove('hidden'),
    logMessage_Info: (...args) => events.push({ level: 'info', args }),
    logMessage_Error: (...args) => notices.push(args),
    logMessage_Warning: (...args) => events.push({ level: 'warn', args }),
    ...Object.fromEntries([
      'applyTheme', 'setThemeStyle', 'ensureThemeStylesLoaded', 'checkAdminReturnState',
      'applyThemeBackgroundAssignment', 'applyThemeGlobalEnvironmentVariables',
      'connectWebSocket', 'syncMapProviderConfigFromInitialData', 'renderThemeStyleButtons',
      'syncThemeFromServer', 'createParamInputs', 'onParamChange', 'onUserChange',
      'updateMobileNavVisibility', 'initializeInlineAdminPanel', 'loadMobileSessionsList',
      'ensureActiveMapProviderRuntimeIfNeeded', 'refreshUserList',
      'bindImmediateRefreshForUserSelects', 'onConfirmAmapKey',
      'startSessionValidityCheck', 'startReminderChecker', 'clearLogoutElsewhereOverlay',
    ].map(name => [name, noop])),
  })
  vm.runInContext(businessContextSource + '\n' + initializationSource, context)
  return {
    context, element, notices, events,
    get resetCount() { return resetCount },
    setModeQuery(query) { modeQuery = query },
    offlineMode: () => vm.runInContext('IS_OFFLINE', context),
  }
}

for (const mobile of [false, true]) {
  for (const guest of [false, true]) {
    test(`${mobile ? 'mobile' : 'desktop'} ${guest ? 'guest' : 'system'} UUID initialization finishes and releases the loading overlay`, async () => {
      const harness = createHarness({ mobile, guest })
      await harness.context.initializeApp()

      assert.deepEqual(harness.notices, [])
      assert.equal(harness.resetCount, 1, 'initialization must not reject its own resolved URL session')
      assert.equal(harness.context.sessionUUID, SESSION_A)
      assert.equal(harness.offlineMode(), false)
      assert.equal(harness.element(mobile ? 'mobile-login-container' : 'login-container').classList.contains('hidden'), false)
      assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
      assert.equal(harness.element('mobile-loading-overlay').classList.contains('hidden'), true)
      assert.ok(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'))
    })
  }
}

test('a newly selected UUID replaces the previous session before initialization context is captured', async () => {
  const harness = createHarness({ initialSession: SESSION_B })
  await harness.context.initializeApp()
  assert.deepEqual(harness.notices, [])
  assert.equal(harness.context.sessionUUID, SESSION_A)
  assert.equal(harness.resetCount, 1)
  assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
})

for (const returnToOriginal of [false, true]) {
  test(`a delayed initialization cannot reset the UI after ${returnToOriginal ? 'A to B to A navigation' : 'switching to another session'}`, async () => {
    const harness = createHarness()
    let releaseModeQuery
    let enteredModeQuery
    const entered = new Promise(resolve => { enteredModeQuery = resolve })
    harness.setModeQuery(() => {
      enteredModeQuery()
      return new Promise(resolve => { releaseModeQuery = resolve })
    })
    const pending = harness.context.initializeApp()
    await entered
    harness.context.sessionUUID = SESSION_B
    harness.context.captureLegacyBusinessContext()
    if (returnToOriginal) {
      harness.context.sessionUUID = SESSION_A
      harness.context.captureLegacyBusinessContext()
    }
    harness.element('loading-overlay').classList.add('hidden')
    harness.element('mobile-loading-overlay').classList.add('hidden')
    releaseModeQuery({ success: true, is_multi_account_mode: false, is_offline_mode: true })
    await pending

    assert.deepEqual(harness.notices, [])
    assert.equal(harness.resetCount, 0)
    assert.equal(harness.offlineMode(), null)
    assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true, 'an obsolete initialization must not restore the overlay')
    assert.equal(harness.element('mobile-loading-overlay').classList.contains('hidden'), true)
    assert.equal(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'), false)
  })
}

test('the root page without a UUID still shows system login and releases the overlay', async () => {
  const harness = createHarness({ pathname: '/' })
  await harness.context.initializeApp()
  assert.deepEqual(harness.notices, [])
  assert.equal(harness.resetCount, 0)
  assert.equal(harness.element('auth-login-container').classList.contains('hidden'), false)
  assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
})
