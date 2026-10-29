import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const source = await readFile(new URL('../scripts/map-request-proxy.js', import.meta.url), 'utf8')
const TOKEN_A = 'A'.repeat(43)
const TOKEN_B = 'B'.repeat(43)

function harness({ worker = false } = {}) {
  const calls = []
  const timers = new Map()
  let sequence = 0
  let reply = async () => ({ success: true, expires_in: 1800, context_token: TOKEN_A })
  const surface = {
    location: { origin: 'https://app.test', href: worker ? 'blob:https://app.test/worker' : 'https://app.test/' },
    URL, Request,
    Worker: class Worker { constructor(url, options) { this.url = url; this.options = options } },
    fetch: async (url, options) => {
      calls.push([url, options])
      return { ok: true, json: () => reply() }
    },
    setTimeout(callback, delay) { const id = ++sequence; timers.set(id, { callback, delay }); return id },
    clearTimeout(id) { timers.delete(id) },
    ...(!worker ? { document: {} } : {}),
  }
  const context = vm.createContext({ [worker ? 'self' : 'window']: surface, URL, Request })
  vm.runInContext(source, context)
  return { surface, calls, timers, api: surface.ZXMapRequestProxy, reply: callback => { reply = callback } }
}

test('profile initialization and renewal retain the same opaque context and configuration identity', async () => {
  const { api, calls, timers } = harness()
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' })
  assert.deepEqual(JSON.parse(calls[0][1].body), { pin_context: true, map_config_id: 'front-one' })
  assert.equal(api.getConfig().contextToken, TOKEN_A)
  assert.equal(api.rewriteUrl('https://webapi.amap.com/maps?key=front'),
    `/map-proxy/amap/https/webapi.amap.com/maps?key=front&__map_context=${TOKEN_A}`)
  const refresh = [...timers.values()].find(timer => timer.delay > 30000)
  assert.ok(refresh)
  await refresh.callback()
  assert.deepEqual(JSON.parse(calls.at(-1)[1].body), { pin_context: true, map_config_id: 'front-one', context_token: TOKEN_A })
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' })
  assert.equal(JSON.parse(calls.at(-1)[1].body).context_token, TOKEN_A)
})

test('new page or different profile obtains a fresh context while previous rewritten URLs retain their token', async () => {
  const current = harness()
  await current.api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' })
  const oldUrl = current.api.rewriteUrl('https://webapi.amap.com/maps?key=first')
  current.reply(async () => ({ success: true, expires_in: 1800, context_token: TOKEN_B }))
  await current.api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-two' })
  assert.deepEqual(JSON.parse(current.calls.at(-1)[1].body), { pin_context: true, map_config_id: 'front-two' })
  assert.equal(current.api.rewriteUrl(oldUrl), oldUrl)
  assert.ok(current.api.rewriteUrl('https://webapi.amap.com/maps?key=second').endsWith(TOKEN_B))
  const fresh = harness()
  await fresh.api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-two' })
  assert.deepEqual(JSON.parse(fresh.calls[0][1].body), { pin_context: true, map_config_id: 'front-two' })
})

test('a new authenticated actor never renews a previous actors profile context', async () => {
  const { api, calls } = harness()
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor-one', map_config_id: 'front-one' })
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor-two', map_config_id: 'front-one' })
  assert.deepEqual(JSON.parse(calls.at(-1)[1].body), { pin_context: true, map_config_id: 'front-one' })
})

test('context is appended to server-rewritten URLs and worker dependencies without duplication', () => {
  for (const worker of [false, true]) {
    const { api } = harness({ worker })
    api.install({ enabled: true, provider: 'amap', contextToken: TOKEN_A })
    const rewritten = api.rewriteUrl('https://app.test/map-proxy/amap/https/webapi.amap.com/dependency.js')
    assert.equal(rewritten, `https://app.test/map-proxy/amap/https/webapi.amap.com/dependency.js?__map_context=${TOKEN_A}`)
    assert.equal(api.rewriteUrl(rewritten), rewritten)
    assert.ok(api.rewriteUrl('https://webapi.amap.com/dependency.js').endsWith(`?__map_context=${TOKEN_A}`))
  }
})

test('a departed initialization cannot replace the current profile token', async () => {
  const { api, reply } = harness()
  let finishOld
  reply(() => new Promise(resolve => { finishOld = resolve }))
  const old = api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' })
  await new Promise(resolve => setImmediate(resolve))
  reply(async () => ({ success: true, expires_in: 1800, context_token: TOKEN_B }))
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-two' })
  finishOld({ success: true, expires_in: 1800, context_token: TOKEN_A })
  assert.equal((await old).stale, true)
  assert.equal(api.getConfig().contextToken, TOKEN_B)
})

test('dynamic module dependencies resolve against the upstream directory and stay inside the vendor proxy', () => {
  const { api } = harness({ worker: true })
  api.install({ enabled: true, provider: 'amap', contextToken: TOKEN_A })
  const base = `https://app.test/map-proxy/amap/https/webapi.amap.com/deep/parts/module.js?__map_context=${TOKEN_A}&__map_module=1`
  assert.equal(api.rewriteModuleUrl('../child.js', base),
    `https://app.test/map-proxy/amap/https/webapi.amap.com/deep/child.js?__map_context=${TOKEN_A}&__map_module=1`)
  assert.equal(api.rewriteModuleUrl('../../../../root.js', base),
    `https://app.test/map-proxy/amap/https/webapi.amap.com/root.js?__map_context=${TOKEN_A}&__map_module=1`)
  assert.equal(api.rewriteModuleUrl('external-package', base), 'external-package')
  assert.equal(api.rewriteModuleUrl('https://outside.test/module.js', base), 'https://outside.test/module.js')
})

test('module Worker entry URLs are explicitly tagged instead of relying on browser fetch mode', () => {
  const { api, surface } = harness()
  api.install({ enabled: true, provider: 'amap', contextToken: TOKEN_A })
  const worker = new surface.Worker('https://webapi.amap.com/worker.mjs', { type: 'module' })
  const url = new URL(worker.url)
  assert.equal(url.origin, 'https://app.test')
  assert.equal(url.searchParams.get('__map_context'), TOKEN_A)
  assert.equal(url.searchParams.get('__map_module'), '1')
})

test('tracked Blob module workers stop before construction while classic Blob workers keep their proxy hooks', () => {
  const { api, surface } = harness()
  const blobs = []
  let constructed = 0
  surface.Worker = class Worker { constructor(url) { constructed += 1; this.url = url } }
  surface.Blob = class Blob { constructor(parts) { this.parts = parts; blobs.push(this) } }
  surface.URL = class LocalURL extends URL {
    static createObjectURL(blob) { return `blob:https://app.test/${blobs.indexOf(blob)}` }
    static revokeObjectURL() {}
  }
  api.install({ enabled: true, provider: 'amap', contextToken: TOKEN_A })
  const blob = new surface.Blob(["import 'https://webapi.amap.com/direct.mjs'"])
  const url = surface.URL.createObjectURL(blob)
  assert.throws(() => new surface.Worker(url, { type: 'module' }), /暂不支持 Blob 模块 Worker/)
  assert.equal(constructed, 0)
  assert.equal(blobs.length, 1)
  new surface.Worker(url, { type: 'classic' })
  assert.equal(constructed, 1)
  assert.equal(blobs.length, 2)
  assert.ok(blobs[1].parts[0].includes(TOKEN_A))
})

test('legacy profile migration retains the initial opaque context once the server returns a stable profile ID', async () => {
  const { api, calls, reply } = harness()
  reply(async () => ({ success: true, expires_in: 1800, context_token: TOKEN_A, map_config_id: 'legacy-amap' }))
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor' })
  assert.deepEqual(JSON.parse(calls[0][1].body), { pin_context: true })
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'legacy-amap' })
  assert.equal(JSON.parse(calls.at(-1)[1].body).context_token, TOKEN_A)
})

test('expired context reloads once, stops retries and never switches an existing SDK to the current origin', async () => {
  const { api, surface, timers, calls } = harness()
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' })
  surface.AMap = { Map() {} }
  let reloads = 0
  surface.location.reload = () => { reloads += 1 }
  surface.fetch = async (url, options) => {
    calls.push([url, options])
    return { ok: false, status: 409, json: async () => ({ message: 'expired' }) }
  }
  const refresh = [...timers.values()].find(timer => timer.delay > 30000)
  assert.ok(refresh)
  timers.clear()
  await refresh.callback()
  assert.equal(reloads, 1)
  assert.equal(timers.size, 0)
  assert.equal(api.getConfig().contextToken, TOKEN_A)
  await assert.rejects(api.initialize({ enabled: true, provider: 'amap', sessionId: 'actor', map_config_id: 'front-one' }), /上下文.*失效.*刷新/)
  assert.equal(reloads, 1)
  assert.ok(api.rewriteUrl('https://webapi.amap.com/maps').endsWith(TOKEN_A))
  assert.equal(JSON.parse(calls.at(-1)[1].body).context_token, TOKEN_A)
})
