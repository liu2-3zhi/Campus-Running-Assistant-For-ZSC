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

function setupComponent(path, overrides = {}, props = {}) {
  const source = readFileSync(new URL(`../frontend/src/${path}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'runtime-test' }).content
  const mounted = []
  const emitted = []
  const calls = []
  const app = { users: [], multiAccounts: [], multiStatus: {}, multiPositions: {}, logs: [], pythonParams: {}, multiGlobalButtons: {}, addLog(msg, level) { this.logs.push({ msg, level }) } }
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
