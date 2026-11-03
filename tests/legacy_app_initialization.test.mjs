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
      const classes = new Set(id.includes('login-container') || ['main-app', 'mobile-main-app', 'multi-account-app', 'mobile-multi-account-app'].includes(id) ? ['hidden'] : [])
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
    resetUI: () => {
      resetCount++
      vm.runInContext('legacyBusinessGeneration++; IS_OFFLINE = null;', context)
      element('main-app').classList.add('hidden')
      element('login-container').classList.remove('hidden')
      context.currentUserData = {}
    },
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

function createMultiAccountHarness(options = {}) {
  const harness = createHarness(options)
  const apiCalls = []
  const renderedAccounts = []
  const refreshStarts = []
  const accounts = [{ username: 'running-school-account', name: '正在执行的账号', status_text: '执行中', summary: {}, params: {} }]
  const globalParams = { theme_base_color: '#123456', run_only_incomplete: true }
  const initialDataLoader = harness.context.loadInitialData
  const originalApi = harness.context.callPythonAPI
  harness.setModeQuery(async () => ({
    success: true, is_multi_account_mode: true, is_offline_mode: false,
    global_params: globalParams, accounts, multi_account_count: 1,
  }))
  harness.context.loadInitialData = async (...args) => ({
    ...await initialDataLoader(...args), is_multi_account_mode: true, accounts,
  })
  harness.context.callPythonAPI = async (method, ...args) => {
    apiCalls.push({ method, args })
    if (method === 'get_session_mode_info') return originalApi(method, ...args)
    if (method === 'enter_multi_account_mode') {
      return options.enterResult || { success: false, message: '任务正在执行中，请先停止任务再切换模式。' }
    }
    if (method === 'multi_get_all_config_users') return { success: true, users: ['running-school-account'] }
    if (method === 'set_multi_run_only_incomplete') return { success: true }
    assert.fail(`unexpected API method: ${method}`)
  }
  Object.assign(harness.context, {
    multiAccountMap: null,
    AMapInstance: null,
    getActiveMapProvider: () => 'local',
    switchMobilePanel() {},
    initProviderMap() {},
    onGlobalParamChange() {},
    updateParamInputs() {},
    updateMultiGlobalButtons() {},
    setBaseColor() {},
    renderMultiAccountList: value => renderedAccounts.push(value),
    startMultiAccountAutoRefresh: interval => refreshStarts.push(interval),
  })
  return { harness, apiCalls, renderedAccounts, refreshStarts, accounts, globalParams }
}

for (const mobile of [false, true]) {
  test(`${mobile ? 'mobile' : 'desktop'} restores an executing multi-account session without requesting a mode change`, async () => {
    const { harness, apiCalls, renderedAccounts, refreshStarts, accounts, globalParams } = createMultiAccountHarness({ mobile })
    await harness.context.initializeApp()

    assert.equal(apiCalls.some(({ method }) => method === 'enter_multi_account_mode'), false, 'restoring an existing mode must not switch or stop running tasks')
    assert.deepEqual(harness.notices, [])
    assert.equal(harness.element(mobile ? 'mobile-multi-account-app' : 'multi-account-app').classList.contains('hidden'), false)
    assert.equal(harness.element(mobile ? 'mobile-login-container' : 'login-container').classList.contains('hidden'), true)
    assert.equal(harness.element('main-app').classList.contains('hidden'), true)
    assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
    assert.equal(harness.element('mobile-loading-overlay').classList.contains('hidden'), true)
    assert.deepEqual(harness.context.pythonParams, globalParams)
    assert.deepEqual(renderedAccounts, [accounts])
    assert.deepEqual(refreshStarts, [500])
    assert.ok(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'))
  })
}

for (const phase of ['map runtime', 'config users', 'run settings', 'account list']) {
  for (const outcome of ['resolve', 'reject']) {
    test(`multi-account restoration ignores its delayed ${phase} ${outcome} after switching sessions`, async () => {
      const { harness, renderedAccounts, refreshStarts } = createMultiAccountHarness({ enterResult: { success: true } })
      let release
      let enteredPhase
      const entered = new Promise(resolve => { enteredPhase = resolve })
      const deferred = () => {
        enteredPhase()
        return new Promise((resolve, reject) => { release = outcome === 'resolve' ? resolve : reject })
      }
      if (phase === 'map runtime') {
        harness.context.ensureActiveMapProviderRuntimeIfNeeded = deferred
      } else if (phase === 'account list') {
        const loadInitialData = harness.context.loadInitialData
        harness.context.loadInitialData = options => options?.force ? deferred() : loadInitialData(options)
      } else {
        const callPythonAPI = harness.context.callPythonAPI
        const delayedMethod = phase === 'config users' ? 'multi_get_all_config_users' : 'set_multi_run_only_incomplete'
        harness.context.callPythonAPI = (method, ...args) => method === delayedMethod ? deferred() : callPythonAPI(method, ...args)
      }
      const pending = harness.context.initializeApp()
      await entered
      harness.context.sessionUUID = SESSION_B
      harness.context.captureLegacyBusinessContext()
      harness.element('multi-account-app').classList.add('hidden')
      harness.element('multi-config-user-select').innerHTML = 'session-B-options'
      harness.element('loading-overlay').classList.remove('hidden')
      release(outcome === 'resolve'
        ? { success: true, accounts: [{ username: 'obsolete-session-A' }], users: ['obsolete-session-A'] }
        : new Error('obsolete session request failed'))
      await pending

      assert.equal(harness.element('multi-account-app').classList.contains('hidden'), true, 'the obsolete initialization must not reopen the old mode')
      assert.equal(harness.element('multi-config-user-select').innerHTML, 'session-B-options')
      assert.deepEqual(renderedAccounts, [])
      assert.deepEqual(refreshStarts, [])
      assert.equal(harness.element('loading-overlay').classList.contains('hidden'), false, 'the obsolete initialization must not dismiss the new session loading overlay')
      assert.equal(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'), false)
    })
  }
}

for (const failure of ['throw', 'response']) {
  test(`multi-account restoration keeps the initial account snapshot and releases overlays when its follow-up refresh has a ${failure} failure`, async () => {
    const { harness, renderedAccounts, accounts } = createMultiAccountHarness({ enterResult: { success: true } })
    const loadInitialData = harness.context.loadInitialData
    const synchronizedMapData = []
    harness.context.syncMapProviderConfigFromInitialData = data => synchronizedMapData.push(data)
    harness.context.loadInitialData = options => {
      if (options?.force) {
        if (failure === 'throw') throw new Error('follow-up refresh failed')
        return { success: false, offline: true, message: 'follow-up refresh failed' }
      }
      return loadInitialData(options)
    }
    await harness.context.initializeApp()

    assert.deepEqual(renderedAccounts, [accounts])
    assert.equal(synchronizedMapData.some(data => data.success === false), false)
    assert.equal(harness.element('multi-account-app').classList.contains('hidden'), false)
    assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
    assert.equal(harness.element('mobile-loading-overlay').classList.contains('hidden'), true)
    assert.ok(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'))
  })
}

for (const failure of ['rejection', 'timeout']) {
  test(`multi-account restoration releases overlays after a config-user API ${failure}`, async () => {
    const { harness, renderedAccounts, accounts } = createMultiAccountHarness()
    const callPythonAPI = harness.context.callPythonAPI
    harness.context.callPythonAPI = (method, ...args) => {
      if (method !== 'multi_get_all_config_users') return callPythonAPI(method, ...args)
      return failure === 'timeout' ? new Promise(() => {}) : Promise.reject(new Error('config-user API failed'))
    }
    if (failure === 'timeout') {
      harness.context.withLegacyInitializationTimeout = undefined
      harness.context.setTimeout = (callback, delay) => delay >= 15000 ? setTimeout(callback, 1) : 0
      harness.context.clearTimeout = clearTimeout
    }
    await harness.context.initializeApp()

    assert.equal(harness.element('multi-account-app').classList.contains('hidden'), false)
    assert.equal(harness.element('loading-overlay').classList.contains('hidden'), true)
    assert.equal(harness.element('mobile-loading-overlay').classList.contains('hidden'), true)
    assert.deepEqual(renderedAccounts, [accounts])
    assert.ok(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'))
    if (failure === 'timeout') {
      assert.ok(harness.events.some(({ args }) => args[0] === '[初始化] 阶段超时' && args[1].phase === '多账号配置用户加载'))
    }
  })
}

for (const outcome of ['resolve', 'reject']) {
  test(`multi-account initialization does not dismiss a new session overlay after its final user-list ${outcome}`, async () => {
    const { harness } = createMultiAccountHarness()
    let release
    let enteredRefresh
    const entered = new Promise(resolve => { enteredRefresh = resolve })
    harness.context.refreshUserList = () => {
      enteredRefresh()
      return new Promise((resolve, reject) => { release = outcome === 'resolve' ? resolve : reject })
    }
    const pending = harness.context.initializeApp()
    await entered
    harness.context.sessionUUID = SESSION_B
    harness.context.captureLegacyBusinessContext()
    const overlay = harness.element('loading-overlay')
    overlay.classList.remove('hidden')
    overlay.style.opacity = '1'
    overlay.style.display = 'block'
    release(outcome === 'resolve' ? undefined : new Error('old user-list request failed'))
    await pending

    assert.equal(overlay.classList.contains('hidden'), false)
    assert.equal(overlay.style.opacity, '1')
    assert.equal(overlay.style.display, 'block')
    assert.deepEqual(harness.notices, [])
    assert.equal(harness.events.some(({ args }) => args[0] === '[初始化] initializeApp 完成'), false)
  })
}

for (const mobile of [false, true]) {
  test(`the completed ${mobile ? 'mobile' : 'desktop'} multi-account initialization cannot hide a new session overlay through its delayed callback`, async () => {
    const { harness } = createMultiAccountHarness({ mobile })
    const timers = []
    harness.context.setTimeout = (callback, delay) => { timers.push({ callback, delay }); return timers.length }
    harness.context.restoreMobileTaskState = () => {}
    await harness.context.initializeApp()
    const hideOverlay = timers.find(({ delay }) => delay === (mobile ? 1000 : 500))
    assert.ok(hideOverlay)
    harness.context.sessionUUID = SESSION_B
    harness.context.captureLegacyBusinessContext()
    const overlay = harness.element(mobile ? 'mobile-loading-overlay' : 'loading-overlay')
    overlay.classList.remove('hidden')
    overlay.style.display = 'block'
    hideOverlay.callback()

    assert.equal(overlay.style.display, 'block')
    assert.equal(overlay.classList.contains('hidden'), false)
  })
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
