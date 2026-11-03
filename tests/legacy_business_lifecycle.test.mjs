import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))
const SESSION_A = '11111111-1111-4111-8111-111111111111'
const SESSION_B = '22222222-2222-4222-8222-222222222222'
const flush = () => new Promise(resolve => setImmediate(resolve))

function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

function createHarness() {
  const elements = new Map()
  const requests = []
  const timers = []
  const notices = []
  const rendered = []
  const baseColors = []
  const element = id => {
    if (!elements.has(id)) {
      let text = id === 'login-button' ? '立即登录' : ''
      let html = text
      const classes = new Set()
      elements.set(id, {
        value: id === 'username-entry' ? 'student-a' : '', disabled: false, dataset: {},
        get textContent() { return text },
        set textContent(value) { text = String(value); html = text },
        get innerHTML() { return html },
        set innerHTML(value) { html = String(value); text = html.replace(/<[^>]*>/g, '') },
        classList: {
          add(...names) { names.forEach(name => classes.add(name)) },
          remove(...names) { names.forEach(name => classes.delete(name)) },
          contains(name) { return classes.has(name) },
        },
      })
    }
    return elements.get(id)
  }
  const noop = () => {}
  const context = vm.createContext({
    console, sessionUUID: SESSION_A, currentTasks: [], currentUserData: {}, currentSessionUA: '',
    window: {}, pythonParams: {},
    $: element,
    document: { createElement() { return context.lastInput = { click() {} } } },
    setTimeout(callback, delay) { timers.push({ callback, delay }); return timers.length },
    callPythonAPI(method, ...args) {
      const response = deferred()
      requests.push({ method, args, ...response })
      return response.promise
    },
    getApiRequestSessionHeaderValue: () => context.sessionUUID,
    showModalAlert: (...args) => notices.push(args),
    swal: { fire: (...args) => notices.push(args) },
    logMessage_Info: noop, logMessage_Error: noop, logMessage_Debug: noop,
    getStoredAdminReturnOriginSession: () => '', clearAdminReturnOriginState: noop,
    hydrateMapProviderSecretsForLegacy: async value => value,
    syncThemeFromServer: async () => {},
    syncMapProviderConfigFromInitialData: noop, getActiveMapProviderApiKey: () => '',
    getActiveMapProvider: () => 'amap', showMissingMapProviderKeyModal: noop,
    showMainApp: noop, updateDashboard: noop,
    setBaseColor: (...args) => baseColors.push(args),
    renderTaskList() { rendered.push(Array.from(context.currentTasks)) },
    fetchNotifications: async () => {},
  })
  vm.runInContext([
    section('let isRefreshingTasks = false;', 'async function ensureLegacyBusinessMode()'),
    section('function setButtonLoading(', 'const captchaDimensions ='),
    section('async function onLogin()', 'async function onLogout()'),
    section('async function refreshTasks()', 'function renderTaskList()'),
    section('async function fetchNotifications(', 'let notificationAutoRefreshTimer'),
    section('async function importTask()', 'async function onConfirmAutoGenerate()'),
  ].join('\n'), context)
  context.captureLegacyBusinessContext()
  return {
    context, element, requests, notices, rendered, baseColors,
    runTimers(delay) {
      const ready = timers.filter(timer => timer.delay === delay)
      for (const timer of ready) timers.splice(timers.indexOf(timer), 1)
      ready.forEach(timer => timer.callback())
    },
    changeMode() { context.captureLegacyBusinessContext(true) },
    busy: () => vm.runInContext('isRefreshingTasks', context),
  }
}

test('an unsuccessful import cancels pending login and restores the login button', async () => {
  const h = createHarness()
  const login = h.context.onLogin()
  assert.equal(h.element('login-button').disabled, true)
  await h.context.importTask()
  const imported = h.context.lastInput.onchange({ target: { files: [{ text: async () => '{invalid json' }] } })
  await flush()
  h.requests[1].resolve({ success: false, message: '导入失败' })
  await imported
  h.requests[0].resolve({ success: true })
  await login
  assert.equal(h.element('login-button').disabled, false)
  assert.equal(h.element('login-button').textContent, '立即登录')
  assert.equal(h.element('login-button').classList.contains('cursor-not-allowed'), false)
  assert.equal(h.notices.length, 1, 'an obsolete login must not display its own result')
})

test('a rejected login request releases the button and retains the original rejection', async () => {
  const h = createHarness()
  const failure = new Error('connection interrupted')
  const login = h.context.onLogin()
  const rejected = assert.rejects(login, error => error === failure)
  h.requests[0].reject(failure)
  await rejected
  assert.equal(h.element('login-button').disabled, false)
  assert.equal(h.element('login-button').textContent, '立即登录')
})

test('a login cancelled while applying its theme releases the button', async () => {
  const h = createHarness()
  const theme = deferred()
  h.context.syncThemeFromServer = () => theme.promise
  const login = h.context.onLogin()
  h.requests[0].resolve({ success: true, is_offline_mode: false })
  await flush()
  h.changeMode()
  theme.resolve()
  await login
  assert.equal(h.element('login-button').disabled, false)
  assert.equal(h.element('login-button').textContent, '立即登录')
})

test('an obsolete login cannot release a newer login button or replace its original label', async () => {
  const h = createHarness()
  const first = h.context.onLogin()
  const second = h.context.onLogin()
  h.requests[0].resolve({ success: false, message: 'old failure' })
  await first
  assert.equal(h.element('login-button').disabled, true)
  assert.match(h.element('login-button').textContent, /登录中/)
  assert.equal(h.notices.length, 0)
  h.requests[1].resolve({ success: false, message: 'current failure' })
  await second
  assert.match(h.element('login-button').textContent, /登录失败/, 'finally must retain the current failure feedback')
  h.runTimers(2000)
  assert.equal(h.element('login-button').disabled, false)
  assert.equal(h.element('login-button').textContent, '立即登录')
})

for (const [method, message, delay] of [
  ['showButtonSuccess', '登录成功', 1500],
  ['showButtonError', '登录失败', 2000],
]) {
  test(`${method} does not release a later loading state when its timer runs`, () => {
    const h = createHarness()
    h.context.setButtonLoading('login-button', true, '登录中...')
    h.context[method]('login-button', message)
    h.context.setButtonLoading('login-button', true, '登录中...')
    assert.equal(h.element('login-button').classList.contains('!bg-green-600'), false)
    assert.equal(h.element('login-button').classList.contains('!bg-red-600'), false)
    h.runTimers(delay)
    assert.equal(h.element('login-button').disabled, true)
    assert.match(h.element('login-button').textContent, /登录中/)
  })

  test(`${method} still restores a button when no newer state supersedes it`, () => {
    const h = createHarness()
    h.context.setButtonLoading('login-button', true, '登录中...')
    h.context[method]('login-button', message)
    assert.match(h.element('login-button').textContent, new RegExp(message))
    h.runTimers(delay)
    assert.equal(h.element('login-button').disabled, false)
    assert.equal(h.element('login-button').textContent, '立即登录')
  })
}

for (const firstSucceeded of [false, true]) {
  test(`a second login restores the resting label before the first ${firstSucceeded ? 'success' : 'failure'} feedback timer fires`, async () => {
    const h = createHarness()
    const first = h.context.onLogin()
    h.requests[0].resolve(firstSucceeded ? {
      success: true, is_offline_mode: false, userInfo: { name: 'student-a', student_id: '123' },
      cached_notifications: { unreadCount: 0, notices: [{ title: 'notice' }] },
    } : { success: false, message: 'first failure' })
    if (firstSucceeded) {
      await flush()
      h.requests[1].resolve({ success: true, tasks: [] })
    }
    await first
    const nextRequest = h.requests.length
    const second = h.context.onLogin()
    h.requests[nextRequest].resolve({ success: false, message: 'second failure' })
    await second
    assert.match(h.element('login-button').textContent, /登录失败/)
    h.runTimers(1500)
    h.runTimers(2000)
    assert.equal(h.element('login-button').disabled, false)
    assert.equal(h.element('login-button').textContent, '立即登录')
  })
}

test('a login cancelled during task refresh leaves the newer page notifications and overlay untouched', async () => {
  const h = createHarness()
  const login = h.context.onLogin()
  h.requests[0].resolve({
    success: true, is_offline_mode: false, userInfo: { name: 'student-a', student_id: '123' },
    cached_notifications: { unreadCount: 3, notices: [{ title: 'old notice' }] },
  })
  await flush()
  assert.equal(h.requests[1].method, 'load_tasks')
  h.changeMode()
  h.element('notification-badge').textContent = 'new badge'
  h.element('notification-badge').classList.remove('hidden')
  h.element('show-admin-panel').classList.add('hidden')
  h.element('loading-overlay').classList.remove('hidden')
  h.context.window.currentNotifications = [{ title: 'new notice' }]
  h.requests[1].resolve({ success: true, tasks: [] })
  await login
  assert.equal(h.element('notification-badge').textContent, 'new badge')
  assert.equal(h.element('notification-badge').classList.contains('hidden'), false)
  assert.equal(h.element('show-admin-panel').classList.contains('hidden'), true)
  assert.equal(h.element('loading-overlay').classList.contains('hidden'), false)
  assert.deepEqual(h.context.window.currentNotifications, [{ title: 'new notice' }])
  assert.deepEqual(h.baseColors, [])
})

test('a login cancelled during the real notification refresh leaves the newer page state untouched', async () => {
  const h = createHarness()
  const login = h.context.onLogin()
  h.requests[0].resolve({ success: true, is_offline_mode: false, userInfo: { name: 'student-a', student_id: '123' } })
  await flush()
  h.requests[1].resolve({ success: true, tasks: [] })
  await flush()
  assert.equal(h.requests[2].method, 'get_notifications')
  h.changeMode()
  h.element('notification-badge').textContent = 'new badge'
  h.element('notification-badge').classList.remove('hidden')
  h.context.window.currentNotifications = [{ title: 'new notice' }]
  h.element('show-admin-panel').classList.add('hidden')
  h.element('loading-overlay').classList.remove('hidden')
  h.requests[2].resolve({ success: true, unreadCount: 8, notices: [{ title: 'old notice' }] })
  await login
  assert.equal(h.element('notification-badge').textContent, 'new badge')
  assert.equal(h.element('notification-badge').classList.contains('hidden'), false)
  assert.deepEqual(h.context.window.currentNotifications, [{ title: 'new notice' }])
  assert.equal(h.element('show-admin-panel').classList.contains('hidden'), true)
  assert.equal(h.element('loading-overlay').classList.contains('hidden'), false)
  assert.deepEqual(h.baseColors, [])
})

test('a rejected notification request from an old context cannot hide the new badge', async () => {
  const h = createHarness()
  const pending = h.context.fetchNotifications()
  h.changeMode()
  h.element('notification-badge').classList.remove('hidden')
  h.requests[0].reject(new Error('old request failed'))
  assert.equal(await pending, null)
  assert.equal(h.element('notification-badge').classList.contains('hidden'), false)
})

test('a first task response from an old business context cannot replace current tasks', async () => {
  const h = createHarness()
  const refresh = h.context.refreshTasks()
  h.changeMode()
  h.context.currentTasks = [{ name: 'offline task' }]
  h.requests[0].resolve({ success: true, tasks: [{ name: 'old online task' }] })
  await refresh
  assert.deepEqual(h.context.currentTasks, [{ name: 'offline task' }])
  assert.deepEqual(h.rendered, [])
  assert.equal(h.element('refresh-button').disabled, false)
})

test('a retry task response from an old business context cannot replace current tasks', async () => {
  const h = createHarness()
  const refresh = h.context.refreshTasks()
  h.requests[0].resolve({ success: false })
  await flush()
  h.runTimers(300)
  await flush()
  assert.equal(h.requests.length, 2)
  h.changeMode()
  h.context.currentTasks = [{ name: 'new offline task' }]
  h.requests[1].resolve({ success: true, tasks: [{ name: 'old retry task' }] })
  await refresh
  assert.deepEqual(h.context.currentTasks, [{ name: 'new offline task' }])
  assert.deepEqual(h.rendered, [])
})

test('a business context change during retry delay prevents the old retry request', async () => {
  const h = createHarness()
  const refresh = h.context.refreshTasks()
  h.requests[0].resolve({ success: false })
  await flush()
  h.changeMode()
  h.runTimers(300)
  await flush()
  // Settle an unwanted retry as well so a failing test leaves no pending operation.
  if (h.requests[1]) h.requests[1].resolve({ success: false })
  await refresh
  assert.equal(h.requests.length, 1)
})

test('a new session can refresh before the previous session request completes', async () => {
  const h = createHarness()
  const oldRefresh = h.context.refreshTasks()
  h.context.sessionUUID = SESSION_B
  const newRefresh = h.context.refreshTasks()
  assert.equal(h.requests.length, 2, 'the old session busy flag must not block a new session')
  h.requests[0].resolve({ success: true, tasks: [{ name: 'old task' }] })
  await oldRefresh
  assert.equal(h.busy(), true, 'the old finally must not clear the new request busy flag')
  assert.equal(h.element('refresh-button').disabled, true)
  h.requests[1].resolve({ success: true, tasks: [{ name: 'new task' }] })
  await newRefresh
  assert.deepEqual(h.context.currentTasks, [{ name: 'new task' }])
  assert.equal(h.busy(), false)
  assert.equal(h.element('refresh-button').disabled, false)
})

test('duplicate task refreshes in the same context still share the busy guard', async () => {
  const h = createHarness()
  const first = h.context.refreshTasks()
  await h.context.refreshTasks()
  assert.equal(h.requests.length, 1)
  h.requests[0].resolve({ success: true, tasks: [] })
  await first
  assert.equal(h.busy(), false)
})
