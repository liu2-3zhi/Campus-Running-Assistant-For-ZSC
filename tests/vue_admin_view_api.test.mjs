import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function setup(fetch) {
  const applied = []
  const auth = {
    sessionUUID: 'target-b', adminOriginSession: 'origin-a', loginInProgress: true,
    getSessionHeaderValue() { return this.sessionUUID },
    getAuthenticatedSessionHeaderValue() { return this.adminOriginSession || this.sessionUUID },
    getAdminOriginHeaderValue(target) { return target !== this.adminOriginSession ? this.adminOriginSession : '' },
    applyAdminViewContext(data, target) { applied.push([data, target]) },
  }
  const source = readFileSync(new URL('../frontend/src/services/api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replaceAll('export async function', 'async function')
  const context = vm.createContext({ fetch, useAuthStore: () => auth, useNetworkStore: () => ({}), console })
  vm.runInContext(source, context)
  return { auth, applied, run: expression => vm.runInContext(expression, context) }
}

test('viewed business and named requests keep the target and original administrator headers', async () => {
  const calls = []
  const fixture = { success: true, admin_view_context: { session_id: 'origin-a' } }
  const ctx = setup(async (url, options) => {
    calls.push([url, options.headers])
    return { ok: true, json: async () => fixture }
  })
  await ctx.run("callAPI('get_initial_data')")
  await ctx.run("callRawAPI('/api/background_task/status', 'GET', null, { sessionContext: 'business' })")
  for (const [, headers] of calls) {
    assert.equal(headers['X-Session-ID'], 'target-b')
    assert.equal(headers['X-Admin-Origin-Session-ID'], 'origin-a')
  }
  assert.equal(ctx.applied[0][1], 'target-b')
})

test('raw identity requests retain the authenticated administrator context by default', async () => {
  const calls = []
  const ctx = setup(async (url, options) => {
    calls.push([url, options.headers])
    return { ok: true, json: async () => ({ success: true }) }
  })
  await ctx.run("callRawAPI('/api/user/profile', 'GET')")
  assert.equal(calls[0][1]['X-Session-ID'], 'origin-a')
  assert.equal(calls[0][1]['X-Admin-Origin-Session-ID'], undefined)
})

test('a response from a previous target cannot update the administrator context', async () => {
  let respond
  const ctx = setup(() => new Promise(resolve => { respond = resolve }))
  const result = ctx.run("callAPI('get_initial_data')")
  ctx.auth.sessionUUID = 'target-c'
  respond({ ok: true, json: async () => ({ success: true }) })
  await assert.rejects(result, /会话已切换/)
  assert.equal(ctx.applied.length, 0)
})

test('returning to the origin also rejects the viewed target response already in flight', async () => {
  let respond
  const ctx = setup(() => new Promise(resolve => { respond = resolve }))
  const result = ctx.run("callAPI('get_initial_data')")
  ctx.auth.sessionUUID = 'origin-a'
  ctx.auth.adminOriginSession = ''
  respond({ ok: true, json: async () => ({ success: true, auth_username: 'user-b' }) })
  await assert.rejects(result, /会话已切换/)
  assert.equal(ctx.applied.length, 0)
})

test('a replaced origin rejects the old administrator response for the same target', async () => {
  let parse
  let started
  const parsing = new Promise(resolve => { started = resolve })
  const ctx = setup(async () => ({ ok: true, json: () => new Promise(resolve => { parse = resolve; started() }) }))
  const result = ctx.run("callAPI('get_initial_data')")
  await parsing
  ctx.auth.adminOriginSession = 'new-origin-d'
  parse({ success: true, admin_view_context: { session_id: 'origin-a' } })
  await assert.rejects(result, /会话已切换/)
  assert.equal(ctx.applied.length, 0)
})

test('raw authentication requests remain valid across target changes but reject actor changes', async () => {
  let respond
  const ctx = setup(() => new Promise(resolve => { respond = resolve }))
  const first = ctx.run("callRawAPI('/api/user/profile', 'GET')")
  ctx.auth.sessionUUID = 'target-c'
  respond({ ok: true, json: async () => ({ success: true }) })
  await first
  const second = ctx.run("callRawAPI('/api/user/profile', 'GET')")
  ctx.auth.adminOriginSession = 'new-origin-d'
  respond({ ok: true, json: async () => ({ success: true }) })
  await assert.rejects(second, /会话已切换/)
})
