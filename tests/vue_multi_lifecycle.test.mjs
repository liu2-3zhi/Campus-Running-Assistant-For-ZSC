import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const vue = require('vue')
const { defineStore, createPinia } = require('pinia')
const { parse, compileScript } = require('@vue/compiler-sfc')
const appSource = readFileSync(new URL('../frontend/src/stores/app.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export const useAppStore', 'const useAppStore')
const source = readFileSync(new URL('../frontend/src/views/MultiAccountView.vue', import.meta.url), 'utf8')
const script = compileScript(parse(source).descriptor, { id: 'multi-lifecycle-test' }).content
const componentCode = script.replace(/^import\s+(.+?)\s+from\s+['"](.+?)['"];?\s*$/gm, (_, names, module) => {
  if (module.endsWith('.vue')) return `const ${names} = {}`
  return names.startsWith('{') ? `const ${names} = dependencies` : `const ${names} = dependencies.${names}`
}).replace('export default', 'const component =')

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

function setup(t, { alreadyMulti = false, deferMethod, failMethod, failure = 'response' } = {}) {
  const app = vm.runInNewContext(`${appSource}\nuseAppStore`, { ...vue, defineStore })(createPinia())
  const auth = vue.reactive({ sessionUUID: 'session-A' })
  // Mirror App.vue's synchronous business-session binding, including A -> B -> A generations.
  const stopBinding = vue.watch(() => auth.sessionUUID, session => app.bindBusinessSession(session), { immediate: true, flush: 'sync' })
  t.after(stopBinding)
  const mounted = [], unmounted = [], calls = [], socketEvents = []
  const pending = deferred(), started = deferred()
  const hydratePending = deferred()
  let activeSubscriptions = 0
  const responseFor = method => {
    if (method === 'get_session_mode_info') return { success: true, is_multi_account_mode: alreadyMulti, is_offline_mode: false, global_params: { task_interval: 47 }, accounts: [] }
    if (method === 'enter_multi_account_mode') return { success: true, params: { task_interval: 23 }, is_offline_mode: false }
    if (method === 'get_initial_data') return { success: true, is_offline_mode: false, map_providers: {} }
    if (method === 'multi_get_all_accounts_status') return { success: true, accounts: [{ username: 'account-A' }] }
    if (method === 'multi_get_all_config_users') return { success: true, users: ['user-A'] }
    throw new Error(`Unexpected initialization method: ${method}`)
  }
  const dependencies = {
    ...vue, onMounted: fn => mounted.push(fn), onUnmounted: fn => unmounted.push(fn), watch() {},
    useRouter: () => ({}), useAppStore: () => app, useAuthStore: () => auth,
    useMapStore: () => ({ setConfig() {}, setProvider() {} }), useNotificationStore: () => ({}),
    paramDefs: [], paramGroups: [], checkOverdueBeforeStart: async () => true,
    consumeOverdueForceOverride: () => ({}), callRawAPI: async () => ({ success: true }),
    callAPI: async method => {
      calls.push([method, auth.sessionUUID])
      if (method === failMethod) {
        if (failure === 'throw') throw new Error('initialization unavailable')
        return { success: false, message: 'initialization unavailable' }
      }
      if (method === deferMethod) { started.resolve(); await pending.promise }
      return responseFor(method)
    },
    hydrateMapProviderSecrets: async data => {
      calls.push(['hydrateMapProviderSecrets', auth.sessionUUID])
      if (deferMethod === 'hydrateMapProviderSecrets') { started.resolve(); await hydratePending.promise }
      return data
    },
    onWebSocketStatus: listener => {
      activeSubscriptions++
      socketEvents.push('subscribe')
      listener(false)
      return () => { activeSubscriptions--; socketEvents.push('unsubscribe') }
    },
    connectWebSocket: () => socketEvents.push('connect'),
    disconnectWebSocket: () => socketEvents.push('disconnect'),
    isWebSocketConnected: () => false,
  }
  const component = vm.runInNewContext(`${componentCode}\ncomponent`, {
    dependencies, console, setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {}, window: {},
  })
  const state = component.setup({}, { expose() {} })
  return {
    app, auth, state, calls, socketEvents,
    mount: () => mounted[0](), unmount: () => unmounted.forEach(fn => fn()),
    started: started.promise,
    release: () => { pending.resolve(); hydratePending.resolve() },
    get activeSubscriptions() { return activeSubscriptions },
  }
}

test('a direct multi-account mount releases the global loading overlay after initialization', async t => {
  const ctx = setup(t)
  assert.equal(ctx.app.isLoading, true)
  await ctx.mount()
  assert.equal(ctx.app.isLoading, false)
  assert.equal(ctx.app.multiAccounts[0].username, 'account-A')
})

test('refreshing an existing multi-account session restores its parameters without re-entering its mode', async t => {
  const ctx = setup(t, { alreadyMulti: true })
  await ctx.mount()
  assert.equal(ctx.calls.some(([method]) => method === 'enter_multi_account_mode'), false)
  assert.equal(ctx.state.globalParams.task_interval, 47)
  assert.equal(ctx.app.isLoading, false)
})

test('a session outside multi-account mode enters it before loading its accounts', async t => {
  const ctx = setup(t)
  await ctx.mount()
  assert.deepEqual(ctx.calls.slice(0, 2).map(([method]) => method), ['get_session_mode_info', 'enter_multi_account_mode'])
  assert.equal(ctx.state.globalParams.task_interval, 23)
})

for (const failure of ['response', 'throw']) {
  for (const failMethod of ['get_session_mode_info', 'enter_multi_account_mode']) {
    test(`${failMethod} ${failure} failure releases the current multi-account loading overlay`, async t => {
      const ctx = setup(t, { failMethod, failure })
      await ctx.mount()
      assert.equal(ctx.app.isLoading, false)
      assert.equal(ctx.app.logs.some(entry => entry.msg.includes('initialization unavailable')), true)
      assert.equal(ctx.socketEvents.includes('connect'), false)
    })
  }
}

for (const deferMethod of ['get_session_mode_info', 'enter_multi_account_mode', 'get_initial_data', 'hydrateMapProviderSecrets', 'multi_get_all_accounts_status', 'multi_get_all_config_users']) {
  for (const invalidation of ['unmount', 'session-change', 'session-A-B-A']) {
    test(`late ${deferMethod} initialization cannot continue after ${invalidation}`, async t => {
      const ctx = setup(t, { deferMethod })
      const initialization = ctx.mount()
      await Promise.race([ctx.started, initialization.then(() => assert.fail(`initialization never reached ${deferMethod}`))])
      if (invalidation === 'unmount') ctx.unmount()
      else {
        ctx.auth.sessionUUID = 'session-B'
        if (invalidation === 'session-A-B-A') ctx.auth.sessionUUID = 'session-A'
      }
      // This belongs to the new view. The obsolete finally must not clear it.
      ctx.app.isLoading = true
      const callsAtInvalidation = ctx.calls.length
      const accountsAtInvalidation = JSON.stringify(ctx.app.multiAccounts)
      const usersAtInvalidation = JSON.stringify(ctx.app.users)
      const logsAtInvalidation = JSON.stringify(ctx.app.logs)
      ctx.release()
      await initialization
      assert.equal(ctx.calls.length, callsAtInvalidation, 'the old mount must not launch more requests or hydration')
      assert.equal(JSON.stringify(ctx.app.multiAccounts), accountsAtInvalidation)
      assert.equal(JSON.stringify(ctx.app.users), usersAtInvalidation)
      assert.equal(JSON.stringify(ctx.app.logs), logsAtInvalidation)
      assert.equal(ctx.activeSubscriptions, 0)
      assert.equal(ctx.socketEvents.includes('connect'), false)
      assert.equal(ctx.app.isLoading, true)
    })
  }
}
