import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PROJECT_ROOT = resolve(import.meta.dirname, '..')
const LEGACY_SOURCE = readFileSync(resolve(PROJECT_ROOT, 'scripts/main.js'), 'utf8')

function extractLegacyRuntimeBlock() {
  const start = LEGACY_SOURCE.indexOf('const LEGACY_MAP_KEY_RUNTIME_NAMESPACE')
  const end = LEGACY_SOURCE.indexOf('function createLegacyPublicConfigSnapshot', start)
  assert.notEqual(start, -1, 'legacy runtime loader block should exist')
  assert.notEqual(end, -1, 'legacy runtime loader block should have a stable end marker')
  return LEGACY_SOURCE.slice(start, end)
}

function createLegacyRuntimeHarness({
  fetchImpl,
  timeoutImpl,
  activeSessionId = '',
  storedSessionId = '',
  urlSessionId = '',
} = {}) {
  const appendedScripts = []
  const windowObject = {
    location: { pathname: '/' },
    sessionStorage: {
      getItem() {
        return storedSessionId
      },
    },
  }
  let context
  const document = {
    querySelectorAll(selector) {
      if (selector !== 'script[data-map-key-runtime="1"]') return []
      return appendedScripts.filter((script) => script.dataset?.mapKeyRuntime === '1')
    },
    createElement(tagName) {
      return {
        tagName,
        dataset: {},
        async: false,
        src: '',
        text: '',
        textContent: '',
        remove() {
          const index = appendedScripts.indexOf(this)
          if (index !== -1) appendedScripts.splice(index, 1)
        },
      }
    },
    head: {
      appendChild(script) {
        appendedScripts.push(script)
        const inlineSource = script.text || script.textContent
        if (inlineSource) {
          vm.runInContext(inlineSource, context)
          return
        }
        if (script.src && typeof script.onerror === 'function') {
          setImmediate(() => script.onerror(new Error('external script loading is not supported in this harness')))
        }
      },
    },
  }

  context = vm.createContext({
    window: windowObject,
    document,
    fetch: fetchImpl || (async () => {
      throw new Error('unexpected fetch')
    }),
    setTimeout: timeoutImpl || ((handler) => {
      handler()
      return 1
    }),
    clearTimeout() {},
    console,
    sessionUUID: activeSessionId,
    isUsableClientSessionUUID(value) {
      return /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(
        String(value || '').trim(),
      )
    },
    getUUIDFromURL() {
      return urlSessionId
    },
    addAdminViewOriginSessionHeader(headers) {
      return headers
    },
  })
  windowObject.window = windowObject
  windowObject.document = document

  vm.runInContext(`
${extractLegacyRuntimeBlock()}
globalThis.__legacyRuntimeExports = {
  getLegacyMapKeyRuntimeUrl,
  getLegacyMapKeyRuntimeSessionId,
  loadLegacyMapKeyRuntime,
  hydrateMapProviderSecretsForLegacy,
};
`, context)

  return {
    appendedScripts,
    context,
    window: windowObject,
    api: context.__legacyRuntimeExports,
  }
}

test('legacy runtime loader prefers the target URL session over stale admin state', () => {
  const adminSessionId = '11111111-1111-4111-8111-111111111111'
  const targetSessionId = '22222222-2222-4222-8222-222222222222'
  const { api } = createLegacyRuntimeHarness({
    activeSessionId: adminSessionId,
    storedSessionId: adminSessionId,
    urlSessionId: targetSessionId,
  })

  assert.equal(api.getLegacyMapKeyRuntimeSessionId(), targetSessionId)
})

test('legacy runtime loader fetches script with explicit session header before hydrating map keys', async () => {
  const sessionId = '41473ebe-61ff-4f71-aa13-2620c13057a4'
  const fetchCalls = []
  const { api, window } = createLegacyRuntimeHarness({
    fetchImpl: async (url, options) => {
      fetchCalls.push({ url, options })
      return {
        ok: true,
        status: 200,
        text: async () => `
window.__MAP_KEY_RUNTIME__ = Object.freeze({
  version: 'runtime-v1',
  decryptMapProviderKeys: async function (_bundle, explicitSessionId) {
    window.__decryptSessionId = explicitSessionId;
    return { amap: { js_key: 'decrypted-key' } };
  },
});
`,
      }
    },
  })

  const hydrated = await api.hydrateMapProviderSecretsForLegacy({
    map_provider_key_bundle: {
      available: true,
      runtime_script: '/api/map_key_runtime.js?v=runtime-v1',
      runtime_version: 'runtime-v1',
    },
    map_providers: {
      amap: { provider: 'amap' },
    },
  }, sessionId)

  assert.equal(fetchCalls.length, 1)
  assert.equal(fetchCalls[0].url, '/api/map_key_runtime.js?v=runtime-v1')
  assert.equal(fetchCalls[0].options.credentials, 'include')
  assert.equal(fetchCalls[0].options.cache, 'no-store')
  assert.equal(fetchCalls[0].options.headers['X-Session-ID'], sessionId)
  assert.equal(window.__decryptSessionId, sessionId)
  assert.equal(hydrated.map_providers.amap.js_key, 'decrypted-key')
})

test('legacy runtime loader retries a transient 404 once before using the runtime script', async () => {
  const sessionId = '41473ebe-61ff-4f71-aa13-2620c13057a4'
  const fetchCalls = []
  const retryDelays = []
  const { api } = createLegacyRuntimeHarness({
    timeoutImpl: (handler, delay) => {
      retryDelays.push(delay)
      handler()
      return 1
    },
    fetchImpl: async (url, options) => {
      fetchCalls.push({ url, options })
      if (fetchCalls.length === 1) {
        return {
          ok: false,
          status: 404,
          text: async () => '',
        }
      }
      return {
        ok: true,
        status: 200,
        text: async () => `
window.__MAP_KEY_RUNTIME__ = Object.freeze({
  version: 'runtime-v2',
  decryptMapProviderKeys: async function () { return {}; },
});
`,
      }
    },
  })

  await api.loadLegacyMapKeyRuntime({
    runtime_script: '/api/map_key_runtime.js?v=runtime-v2',
    runtime_version: 'runtime-v2',
  }, sessionId)

  assert.equal(fetchCalls.length, 2)
  assert.equal(fetchCalls[0].options.headers['X-Session-ID'], sessionId)
  assert.equal(fetchCalls[1].options.headers['X-Session-ID'], sessionId)
  assert.deepEqual(retryDelays, [100])
})
