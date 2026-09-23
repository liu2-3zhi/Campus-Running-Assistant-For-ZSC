import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import { paramDefs, paramGroups } from '../frontend/src/utils/legacyParams.js'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { parse, compileScript } = require('@vue/compiler-sfc')
const vue = require('vue')

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
    useAuthStore: () => auth, useAppStore: () => app,
    useMapStore: () => ({}), useNotificationStore: () => ({}),
    callAPI: async (method, ...args) => { calls.push([method, ...args]); return { success: true } },
    callRawAPI: async (method, ...args) => { calls.push([method, ...args]); return { success: true } },
    connectWebSocket() {}, disconnectWebSocket() {},
    isWebSocketConnected: () => false,
    onWebSocketStatus: listener => { listener(false); return () => {} },
    checkOverdueBeforeStart: async () => true, paramDefs, paramGroups,
    Swal: { fire: async () => ({ isConfirmed: true }) },
    ...overrides,
  }
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
  const ctx = setupComponent('views/LoginView.vue', {
    callAPI: async (...args) => {
      assert.equal(args[0], 'import_task_data')
      assert.equal(args[1], '{"tasks":[]}')
      return { success: true, tasks: [{ id: 'offline-task' }], userInfo: { name: '离线用户' } }
    },
  }, { uuid: '' })
  await ctx.state.handleImportFile({ target: { files: [{ text: async () => '{"tasks":[]}' }] } })
  assert.equal(ctx.app.tasks[0].id, 'offline-task')
})
