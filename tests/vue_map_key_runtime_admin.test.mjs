import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../frontend/src/services/mapKeyRuntime.js', import.meta.url), 'utf8')
  .replace(/^import .*\n/gm, '').replace('export async function', 'async function')

function harness(fetchImpl) {
  const auth = {
    sessionUUID: 'target-b',
    getSessionHeaderValue() { return this.sessionUUID },
    getAuthenticatedSessionHeaderValue() { return 'admin-a' },
    getAdminOriginHeaderValue() { return 'admin-a' },
  }
  const scripts = []
  let context
  const window = {}
  const document = {
    querySelectorAll() { return scripts },
    createElement() { return { dataset: {}, remove() {} } },
    head: { appendChild(script) {
      scripts.push(script)
      vm.runInContext(script.text || script.textContent, context)
      script.onload?.()
    } },
  }
  context = vm.createContext({ window, document, fetch: fetchImpl, useAuthStore: () => auth, setTimeout, clearTimeout, AbortController })
  vm.runInContext(`${source}\nglobalThis.hydrate = hydrateMapProviderSecrets`, context)
  return { auth, context, scripts }
}

const bundle = {
  map_provider_key_bundle: { available: true, runtime_version: 'version-b', runtime_script: '/api/map_key_runtime.js' },
  map_providers: { amap: { provider: 'amap' } },
}

const runtimeScript = `window.__MAP_KEY_RUNTIME__ = {
  version: 'version-b',
  async decryptMapProviderKeys(bundle, session, origin) {
    window.decryptContext = [session, origin];
    return { amap: { js_key: 'target-key' } };
  }
}`

test('Vue admin view loads and decrypts keys in the target business session with verified origin header', async () => {
  const requests = []
  const { context } = harness(async (url, options) => {
    requests.push({ url, options })
    return { ok: true, text: async () => runtimeScript }
  })
  const result = await context.hydrate(bundle)
  assert.equal(requests.length, 1)
  assert.match(requests[0].url, /session_id=target-b/)
  assert.equal(requests[0].options.headers['X-Session-ID'], 'target-b')
  assert.equal(requests[0].options.headers['X-Admin-Origin-Session-ID'], 'admin-a')
  assert.equal(requests[0].options.credentials, 'include')
  assert.deepEqual(Array.from(context.window.decryptContext), ['target-b', 'admin-a'])
  assert.equal(result.map_providers.amap.js_key, 'target-key')
})

test('Vue rejects a runtime response after switching the business session', async () => {
  let resolveFetch
  const { auth, context, scripts } = harness(() => new Promise((resolve) => { resolveFetch = resolve }))
  const pending = context.hydrate(bundle)
  auth.sessionUUID = 'target-c'
  resolveFetch({ ok: true, text: async () => runtimeScript })
  await assert.rejects(pending, /会话/)
  assert.equal(scripts.length, 0)
})
