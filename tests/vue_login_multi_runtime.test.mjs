import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import { paramDefs, paramGroups } from '../frontend/src/utils/legacyParams.js'
import { isRestorableSessionUUIDResponse } from '../frontend/src/utils/validation.js'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { parse, compileScript } = require('@vue/compiler-sfc')
const vue = require('vue')
const { defineStore, createPinia } = require('pinia')
const themeSource = readFileSync(new URL('../frontend/src/stores/theme.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export const useThemeStore', 'const useThemeStore')
const appSource = readFileSync(new URL('../frontend/src/stores/app.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export const useAppStore', 'const useAppStore')

function setupComponent(path, overrides = {}, props = {}) {
  const source = readFileSync(new URL(`../frontend/src/${path}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'runtime-test' }).content
  const mounted = []
  const emitted = []
  const calls = []
  const useAppStore = vm.runInNewContext(`${appSource}\nuseAppStore`, { ...vue, defineStore })
  const app = useAppStore(createPinia())
  const auth = { sessionUUID: 'session-id', isAuthenticated: false, getAuthenticatedSessionHeaderValue: () => 'session-id', setLoginResult() {} }
  const dependencies = {
    ...vue,
    onMounted: callback => mounted.push(callback), onUnmounted() {}, watch() {},
    useRouter: () => ({ push() {}, replace() {} }),
    useRoute: () => ({ params: {}, query: {} }),
    useAuthStore: () => auth, useAppStore: () => app,
    useMapStore: () => ({}), useNotificationStore: () => ({}),
    callAPI: async (method, ...args) => { calls.push([method, ...args]); return { success: true } },
    callRawAPI: async (method, ...args) => { calls.push([method, ...args]); return { success: true } },
    connectWebSocket() {}, disconnectWebSocket() {},
    isWebSocketConnected: () => false,
    onWebSocketStatus: listener => { listener(false); return () => {} },
    checkOverdueBeforeStart: async () => true, paramDefs, paramGroups, isRestorableSessionUUIDResponse,
    consumeOverdueForceOverride: () => ({ bypass_overdue: false, waive_charge: false }),
    Swal: { fire: async () => ({ isConfirmed: true }) },
    ...overrides,
  }
  const useThemeStore = vm.runInNewContext(`${themeSource}\nuseThemeStore`, {
    ...vue, defineStore,
    callAPI: (...args) => dependencies.callAPI(...args),
    useAuthStore: () => auth,
    document: { getElementById: () => null },
  })
  const theme = useThemeStore(createPinia())
  dependencies.useThemeStore ??= () => theme
  const code = script.replace(/^import\s+(.+?)\s+from\s+['"](.+?)['"];?\s*$/gm, (_, names, module) => {
    if (module.endsWith('.vue')) return `const ${names} = {}`
    if (!names.startsWith('{')) return `const ${names} = dependencies.${names}`
    return `const ${names} = dependencies`
  }).replace('export default', 'const component =')
  const context = { dependencies, console, setTimeout, clearTimeout, setInterval: () => 1, clearInterval() {}, window: { Swal: dependencies.Swal }, crypto: { randomUUID: () => 'new-session' }, ...overrides.globals }
  const component = vm.runInNewContext(`${code}\ncomponent`, context)
  const state = component.setup(props, { expose() {}, emit: (...args) => emitted.push(args) })
  return { state, calls, app, auth, mounted, emitted }
}

test('school login accepts the backend string user list and displays its current UA', async () => {
  const ctx = setupComponent('components/login/SessionLogin.vue', {
    callAPI: async method => method === 'get_initial_data'
      ? { users: ['student-a', 'student-b'], last_user: 'student-b', ua: 'saved-device' }
      : { ua: 'saved-device' },
  }, { initialData: {} })
  await ctx.state.loadUserCombo()
  assert.equal(ctx.state.userList.value[0].username, 'student-a')
  assert.equal(ctx.state.selectedUser.value, 'student-b')
  assert.equal(ctx.state.userAgent.value, 'saved-device')
})

test('a session picker inside a view chain selects by navigation without rotating tokens', async () => {
  const viewed = []
  const ctx = setupComponent('components/login/SessionPicker.vue', {
    useAuthStore: () => ({ adminOriginSession: 'origin-a', beginAdminView: target => { viewed.push(target); return true } }),
    globals: { fetch: () => { throw new Error('view chains must not call switch_session') } },
  })
  await ctx.state.selectSession('target-c')
  assert.deepEqual(viewed, ['target-c'])
  assert.deepEqual(ctx.emitted, [['session-selected', 'target-c']])
})

test('a refreshed viewed UUID restores the administrator before loading its session controls', async () => {
  const events = []
  const auth = {
    sessionUUID: 'target-b', adminOriginSession: 'origin-a',
    applyAuthInfo(data) { events.push('apply-actor'); this.adminViewContext = data.admin_view_context },
    getAuthenticatedSessionHeaderValue() { return this.adminViewContext?.session_id || this.sessionUUID },
  }
  const ctx = setupComponent('views/LoginView.vue', {
    useAuthStore: () => auth,
    useRoute: () => ({ params: { uuid: 'target-b' } }),
    callRawAPI: async () => ({ success: true, uuid_type: 'system_account' }),
    callAPI: async method => { events.push(method); return { success: true, admin_view_context: { session_id: 'origin-a', auth_username: 'admin-a', auth_group: 'admin', view_all_sessions: true } } },
    globals: {
      sessionStorage: { setItem() {} },
      fetch: async (_, options) => { events.push(`sessions:${options.headers['X-Session-ID']}`); return { json: async () => ({ sessions: [] }) } },
    },
  })
  await ctx.state.checkUUID('target-b')
  assert.deepEqual(events, ['get_initial_data', 'apply-actor', 'sessions:origin-a'])
  assert.equal(ctx.state.viewMode.value, 'school-login')
})

test('a failed viewed UUID initialization retains the administrator return context', async () => {
  const auth = { sessionUUID: 'target-b', adminOriginSession: 'origin-a' }
  const ctx = setupComponent('views/LoginView.vue', {
    useAuthStore: () => auth,
    useRoute: () => ({ params: { uuid: 'target-b' } }),
    callRawAPI: async () => ({ success: true, uuid_type: 'system_account' }),
    callAPI: async () => { throw new Error('来源验证失败') },
    globals: { sessionStorage: { setItem() {} }, fetch: () => { throw new Error('must not load session controls') } },
  })
  await ctx.state.checkUUID('target-b')
  assert.equal(ctx.state.viewMode.value, 'error')
  assert.equal(ctx.state.errorMsg.value, '来源验证失败')
  assert.equal(auth.adminOriginSession, 'origin-a')
})

test('late initialization for a previous viewed UUID cannot apply its actor or page', async () => {
  let resolveData
  let initialStarted
  const started = new Promise(resolve => { initialStarted = resolve })
  const route = { params: { uuid: 'target-b' } }
  const auth = { sessionUUID: 'target-b', adminOriginSession: 'origin-a', applyAuthInfo() { throw new Error('must not apply stale actor') } }
  const ctx = setupComponent('views/LoginView.vue', {
    useAuthStore: () => auth, useRoute: () => route,
    callRawAPI: async () => ({ success: true, uuid_type: 'system_account' }),
    callAPI: () => new Promise(resolve => { resolveData = resolve; initialStarted() }),
    globals: { sessionStorage: { setItem() {} }, fetch: () => { throw new Error('must not load stale controls') } },
  })
  const pending = ctx.state.checkUUID('target-b')
  await Promise.race([started, pending.then(() => assert.fail('view initialization must request administrator context'))])
  route.params.uuid = 'target-c'
  auth.sessionUUID = 'target-c'
  resolveData({ success: true })
  await pending
  assert.equal(auth.sessionUUID, 'target-c')
  assert.equal(ctx.state.viewMode.value, 'loading')
})

test('random UA comes from the backend and is the value shown in the form', async () => {
  const calls = []
  const ctx = setupComponent('components/login/SessionLogin.vue', {
    callAPI: async (...args) => { calls.push(args); return 'server-generated-device' },
  }, { initialData: {} })
  await ctx.state.randomUA()
  assert.deepEqual(calls, [['generate_new_ua']])
  assert.equal(ctx.state.userAgent.value, 'server-generated-device')
})

test('a late credential response cannot fill another selected user', async () => {
  let resolveFirst
  const ctx = setupComponent('components/login/SessionLogin.vue', {
    callAPI: (_, { username }) => username === 'first'
      ? new Promise(resolve => { resolveFirst = resolve })
      : Promise.resolve({ password: 'second-password', ua: 'second-device' }),
  }, { initialData: {} })
  ctx.state.loginForm.username = 'first'
  const first = ctx.state.autoFillPassword()
  ctx.state.loginForm.username = 'second'
  await ctx.state.autoFillPassword()
  resolveFirst({ password: 'first-password', ua: 'first-device' })
  await first
  assert.equal(ctx.state.loginForm.password, 'second-password')
  assert.equal(ctx.state.userAgent.value, 'second-device')
})

test('multi-account controls use the backend methods and arguments', async () => {
  const ctx = setupComponent('views/MultiAccountView.vue')
  ctx.app.multiAccounts = [{ username: 'student-a' }]
  await ctx.state.loadAccounts()
  await ctx.state.startAll()
  await ctx.state.stopAll()
  await ctx.state.startAccount({ username: 'student-a' })
  await ctx.state.stopAccount({ username: 'student-a' })
  await ctx.state.refreshAccount({ username: 'student-a' })
  await ctx.state.syncRunOnlyIncomplete()
  const methods = ctx.calls.map(call => call[0])
  for (const method of ['multi_get_all_accounts_status', 'multi_start_all_accounts', 'multi_stop_all_accounts', 'multi_start_single_account', 'multi_stop_single_account', 'multi_refresh_single_status']) {
    assert.ok(methods.includes(method), `missing backend call ${method}`)
  }
  const startAll = ctx.calls.find(call => call[0] === 'multi_start_all_accounts')
  assert.equal(startAll[1].run_only_incomplete, true)
  assert.equal(ctx.calls.find(call => call[0] === 'set_multi_run_only_incomplete')[1].flag, true)
})

test('stop-all cancels selected accounts still waiting for their startup delay', async () => {
  let releaseDelay
  let delayStarted
  const delayed = new Promise(resolve => { delayStarted = resolve })
  const ctx = setupComponent('views/MultiAccountView.vue', {
    globals: { setTimeout(callback) { releaseDelay = callback; delayStarted(); return 1 } },
  })
  ctx.state.selectedIds.value.add('student-a')
  const pendingStart = ctx.state.startSelected()
  await delayed
  await ctx.state.stopAll()
  releaseDelay()
  await pendingStart

  assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts'])
  assert.equal(ctx.app.logs.some(log => log.msg.startsWith('已启动')), false)
})

test('stop-all prevents the next selected account from starting after a pending start returns', async () => {
  const calls = []
  let releaseStart
  let firstStarted
  const started = new Promise(resolve => { firstStarted = resolve })
  const ctx = setupComponent('views/MultiAccountView.vue', {
    callAPI: async (method, ...args) => {
      calls.push([method, ...args])
      if (method === 'multi_start_single_account' && calls.length === 1) {
        firstStarted()
        return new Promise(resolve => { releaseStart = resolve })
      }
      return { success: true }
    },
  })
  ctx.state.delaySettings.useDelay = false
  ctx.state.selectedIds.value.add('student-a')
  ctx.state.selectedIds.value.add('student-b')
  const pendingStart = ctx.state.startSelected()
  await started
  const pendingStop = ctx.state.stopAll()
  releaseStart({ success: true })
  await Promise.all([pendingStart, pendingStop])

  assert.deepEqual(calls.map(call => call[0]), ['multi_start_single_account', 'multi_stop_all_accounts', 'multi_stop_all_accounts'])
  assert.equal(ctx.app.logs.some(log => log.msg.startsWith('已启动')), false)
})

for (const action of ['startAll', 'startAccount']) {
  test(`stop-all invalidates the pending ${action} eligibility check`, async () => {
    let releaseCheck
    let checkStarted
    const checking = new Promise(resolve => { checkStarted = resolve })
    const ctx = setupComponent('views/MultiAccountView.vue', {
      checkOverdueBeforeStart: () => new Promise(resolve => { releaseCheck = resolve; checkStarted() }),
    })
    ctx.app.multiAccounts = [{ username: 'student-a' }]
    const pendingStart = ctx.state[action]({ username: 'student-a' })
    await checking
    await ctx.state.stopAll()
    releaseCheck(true)
    await pendingStart

    assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts'])
  })
}

test('a fresh Vue multi-account start is allowed after stop-all', async () => {
  const ctx = setupComponent('views/MultiAccountView.vue')
  ctx.app.multiAccounts = [{ username: 'student-a' }]
  await ctx.state.stopAll()
  await ctx.state.startAll()
  assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts', 'multi_start_all_accounts'])
})

for (const action of ['startSelected', 'startAll', 'startAccount']) {
  test(`Vue stop-all catches an already-sent ${action} request handled after its first stop`, async () => {
    const methods = []
    let running = false
    let deliverStart
    let notifyStart
    const dispatched = new Promise(resolve => { notifyStart = resolve })
    const ctx = setupComponent('views/MultiAccountView.vue', {
      callAPI: async method => {
        methods.push(method)
        if (method.startsWith('multi_start_')) {
          notifyStart()
          return new Promise(resolve => { deliverStart = () => { running = true; resolve({ success: true }) } })
        }
        if (method === 'multi_stop_all_accounts') running = false
        return { success: true }
      },
    })
    ctx.app.multiAccounts = [{ username: 'student-a' }]
    ctx.state.delaySettings.useDelay = false
    ctx.state.selectedIds.value.add('student-a')
    const pendingStart = ctx.state[action]({ username: 'student-a' })
    await dispatched
    const pendingStop = ctx.state.stopAll()
    assert.equal(methods.at(-1), 'multi_stop_all_accounts', 'the first stop must dispatch immediately')
    deliverStart()
    await Promise.all([pendingStart, pendingStop])
    assert.equal(running, false, 'the final stop must catch the delayed start')
    assert.equal(methods.filter(method => method === 'multi_stop_all_accounts').length, 2)
  })
}

test('Vue blocks new starts until stop-all has finished', async () => {
  const methods = []
  let finishStop
  const ctx = setupComponent('views/MultiAccountView.vue', {
    callAPI: async method => {
      methods.push(method)
      if (method === 'multi_stop_all_accounts') return new Promise(resolve => { finishStop = resolve })
      return { success: true }
    },
  })
  ctx.app.multiAccounts = [{ username: 'student-a' }]
  ctx.state.selectedIds.value.add('student-a')
  ctx.state.delaySettings.useDelay = false
  const pendingStop = ctx.state.stopAll()
  await ctx.state.startAll()
  await ctx.state.startSelected()
  await ctx.state.startAccount({ username: 'student-a' })
  assert.deepEqual(methods, ['multi_stop_all_accounts'])
  finishStop({ success: true })
  await pendingStop
})

test('Vue reports failure when the final stop after a dispatched start is rejected', async () => {
  let deliverStart
  let notifyStart
  const dispatched = new Promise(resolve => { notifyStart = resolve })
  let stopCount = 0
  const ctx = setupComponent('views/MultiAccountView.vue', {
    callAPI: async method => {
      if (method.startsWith('multi_start_')) {
        notifyStart()
        return new Promise(resolve => { deliverStart = resolve })
      }
      stopCount += 1
      return stopCount === 1 ? { success: true } : { success: false, message: '停止请求未接受' }
    },
  })
  ctx.app.multiAccounts = [{ username: 'student-a' }]
  const pendingStart = ctx.state.startAll()
  await dispatched
  const pendingStop = ctx.state.stopAll()
  deliverStart({ success: true })
  await Promise.all([pendingStart, pendingStop])
  assert.equal(ctx.app.logs.some(log => log.msg === '已发送全部停止指令'), false)
  assert.ok(ctx.app.logs.some(log => log.level === 'ERROR' && log.msg.includes('停止请求未接受')))
})

test('Vue account start skips the current task wait without a new payment preflight', async () => {
  let paymentChecks = 0
  let forceOverrides = 0
  const ctx = setupComponent('views/MultiAccountView.vue', {
    checkOverdueBeforeStart: async () => { paymentChecks += 1; return false },
    consumeOverdueForceOverride: () => { forceOverrides += 1; return { bypass_overdue: true, waive_charge: true } },
    callAPI: async (method, ...args) => {
      ctx.calls.push([method, ...args])
      return { success: true, wait_skipped: true }
    },
  })

  await ctx.state.startAccount({ username: 'student-a', can_skip_wait: true })

  assert.equal(paymentChecks, 0)
  assert.equal(forceOverrides, 0)
  assert.equal(ctx.calls.length, 1)
  assert.equal(ctx.calls[0][0], 'multi_start_single_account')
  assert.equal(ctx.calls[0][1].username, 'student-a')
  assert.equal(ctx.calls[0][1].bypass_overdue, false)
  assert.equal(ctx.calls[0][1].waive_charge, false)
  assert.ok(ctx.app.logs.some(log => log.msg === '已跳过任务间等待'))
})

test('Vue account start retains payment checks unless the backend allows skipping a wait', async () => {
  let paymentChecks = 0
  const ctx = setupComponent('views/MultiAccountView.vue', {
    checkOverdueBeforeStart: async () => { paymentChecks += 1; return false },
  })

  await ctx.state.startAccount({ username: 'student-a', can_skip_wait: false, status_text: '任务间等待 925s' })

  assert.equal(paymentChecks, 1)
  assert.equal(ctx.calls.length, 0)
})

test('Vue account start uses the latest pushed eligibility when the current wait begins and ends', async () => {
  let paymentChecks = 0
  const ctx = setupComponent('views/MultiAccountView.vue', {
    checkOverdueBeforeStart: async () => { paymentChecks += 1; return false },
  })
  ctx.app.multiAccounts = [{ username: 'student-a', can_skip_wait: false }]
  ctx.app.handleMultiStatusUpdate({ username: 'student-a', data: { can_skip_wait: true } })
  await ctx.state.startAccount(ctx.app.multiAccounts[0])
  ctx.app.handleMultiStatusUpdate({ username: 'student-a', data: { can_skip_wait: false } })
  await ctx.state.startAccount(ctx.app.multiAccounts[0])

  assert.equal(paymentChecks, 1)
  assert.equal(ctx.calls.length, 1)
  assert.equal(ctx.calls[0][0], 'multi_start_single_account')
  assert.equal(ctx.calls[0][1].bypass_overdue, false)
  assert.equal(ctx.calls[0][1].waive_charge, false)
})

test('Vue start-all forwards skip-overdue decisions to the backend', async () => {
  const ctx = setupComponent('views/MultiAccountView.vue', {
    checkOverdueBeforeStart: async (_accounts, options) => {
      options.onSkip([{ username: 'student-overdue' }])
      return true
    },
  })
  ctx.app.multiAccounts = [
    { username: 'student-a' },
    { username: 'student-overdue' },
  ]

  await ctx.state.startAll()

  const startAll = ctx.calls.find(call => call[0] === 'multi_start_all_accounts')
  assert.equal(startAll[1].skip_overdue, true)
  assert.equal(startAll[1].bypass_overdue, false)
  assert.equal(startAll[1].waive_charge, false)
})

test('multi-account HTTP refresh restores markers, keeps newer pushed positions and removes deleted accounts', async () => {
  let resolveAccounts
  let removed = false
  const ctx = setupComponent('views/MultiAccountView.vue', {
    callAPI: async method => {
      if (method === 'multi_remove_account') { removed = true; return { success: true } }
      if (method === 'multi_get_all_accounts_status' && removed) return { success: true, accounts: [] }
      return new Promise(resolve => { resolveAccounts = resolve })
    },
  })
  ctx.app.bindBusinessSession('A')
  const initial = ctx.state.loadAccounts()
  resolveAccounts({ success: true, accounts: [{ username: 'first', current_position: { lon: 113, lat: 22 } }] })
  await initial
  assert.equal(ctx.app.multiPositions.first.lon, 113)

  const pending = ctx.state.loadAccounts()
  ctx.app.handleMultiPositionUpdate({ username: 'first', lon: 114, lat: 23 })
  resolveAccounts({ success: true, accounts: [{ username: 'first', current_position: { lon: 112, lat: 21 } }] })
  await pending
  assert.equal(ctx.app.multiPositions.first.lon, 114)
  await ctx.state.removeAccount({ username: 'first' })
  assert.equal(ctx.app.multiAccounts.length, 0)
  assert.equal(Object.keys(ctx.app.multiPositions).length, 0)
})

test('Vue overdue modal offers skip when a partial set can start', () => {
  const source = readFileSync(
    new URL('../frontend/src/composables/usePayment.js', import.meta.url),
    'utf8',
  )

  assert.match(source, /showDenyButton:\s*allowSkip \|\| allowForce/)
  assert.match(source, /跳过欠费账号并开始/)
  assert.match(source, /强制执行/)
  assert.match(source, /if \(result\.isDenied\) return allowForce \? 'force' : 'skip'/)
})

test('backend business failures do not produce success logs or clear manual input', async () => {
  const ctx = setupComponent('views/MultiAccountView.vue', {
    callAPI: async () => ({ success: false, message: '账号不可用' }),
  })
  ctx.state.manualInput.username = 'student-a'
  ctx.state.manualInput.password = 'test-password'
  await ctx.state.addManual()
  assert.equal(ctx.state.manualInput.username, 'student-a')
  assert.ok(ctx.app.logs.some(log => log.level === 'ERROR' && log.msg.includes('账号不可用')))
  assert.equal(ctx.app.logs.some(log => log.msg.startsWith('已添加账号')), false)
})

test('Vue account cards translate the backend Have_Tasks sentinel', () => {
  const ctx = setupComponent('views/MultiAccountView.vue')
  const account = {
    username: 'student-a',
    status_text: 'Have_Tasks',
    summary: {
      not_started: 1,
      unexpired_count: 5,
      unexpired_incomplete_count: 4,
    },
  }
  assert.equal(ctx.state.getAccountStatusText(account), '有 3 个任务可执行')
})

test('offline task import reads JSON and preserves returned tasks before navigating', async () => {
  const navigations = []
  const ctx = setupComponent('views/LoginView.vue', {
    useRouter: () => ({
      push(route) {
        assert.equal(ctx.app.tasks[0].id, 'offline-task')
        assert.equal(ctx.app.selectedTaskIndex, 0)
        assert.equal(ctx.app.isLoading, false)
        navigations.push(route)
      },
      replace() {},
    }),
    callAPI: async (...args) => {
      assert.equal(args[0], 'import_task_data')
      assert.equal(args[1], '{"tasks":[]}')
      return { success: true, tasks: [{ id: 'offline-task' }], userInfo: { name: '离线用户' } }
    },
  }, { uuid: '' })
  await ctx.state.handleImportFile({ target: { files: [{ text: async () => '{"tasks":[]}' }] } })
  assert.equal(ctx.app.tasks[0].id, 'offline-task')
  assert.equal(navigations.length, 1)
  assert.equal(navigations[0].name, 'main')
  assert.equal(navigations[0].params.uuid, 'session-id')
})

test('failed online login preserves imported offline mode and only server success changes it', async () => {
  let response = { success: false, offline: true, message: 'fixture failure' }
  const ctx = setupComponent('components/login/SessionLogin.vue', { callAPI: async () => response })
  ctx.app.bindBusinessSession(ctx.auth.sessionUUID)
  ctx.app.applyBusinessMode({ is_offline_mode: true }, ctx.app.captureBusinessContext())
  ctx.state.loginForm.username = 'fixture-user'
  ctx.state.loginForm.password = 'fixture-pass'
  await ctx.state.handleLogin()
  assert.equal(ctx.app.isOfflineMode, true)
  response = { success: true, is_offline_mode: false }
  await ctx.state.handleLogin()
  assert.equal(ctx.app.isOfflineMode, false)
})

test('an offline file read cannot import into a newly selected business session', async () => {
  let finishRead
  const ctx = setupComponent('views/LoginView.vue')
  const pending = ctx.state.handleImportFile({ target: { files: [{ text: () => new Promise(resolve => { finishRead = resolve }) }] } })
  ctx.auth.sessionUUID = 'new-business-session'
  ctx.app.bindBusinessSession(ctx.auth.sessionUUID)
  finishRead('{}')
  await pending
  assert.equal(ctx.calls.some(([method]) => method === 'import_task_data'), false)
  assert.equal(ctx.app.isOfflineMode, null)
})
