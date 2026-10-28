import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const vue = require('vue')
const read = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8')

function adminConfig() {
  const source = read('frontend/src/components/admin/AdminConfig.vue').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const calls = []
  const state = vm.runInNewContext(source + '\n;({sections,configForm,applyConfig,saveConfig,error})', {
    ...vue, watch() {}, onMounted() {},
    callRawAPI: async (...args) => { calls.push(args); return { success: true } },
    normalizeBackendPageOrigin: value => value || '',
  })
  return { state, calls }
}

function legacyConfig(days = 20, size = 10) {
  const calls = []
  const alerts = []
  const fields = new Map()
  const getElement = id => {
    if (!fields.has(id)) fields.set(id, { value: id.endsWith('tile_cache_ttl_days') ? days : id.endsWith('tile_cache_max_size_gb') ? size : '' })
    return fields.get(id)
  }
  const context = vm.createContext({
    console, document: { addEventListener() {}, querySelector: selector => getElement(selector.match(/id="([^"]+)/)[1]), getElementById: getElement },
    ensureConfigLoaded: () => true, setButtonLoading() {}, showButtonError() {},
    sessionUUID: 'business', normalizeBackendPageOrigin: value => value,
    showModalAlert: text => alerts.push(text),
    fetch: async (...args) => { calls.push(args); return { json: async () => ({ success: false, message: 'fixture' }) } },
  })
  vm.runInContext(read('scripts/legacy-admin-config.js'), context)
  return { context, calls, alerts }
}

test('map cache fields have defaults, stay proxy-only, and retain values when proxy is disabled', async () => {
  const { state, calls } = adminConfig()
  state.applyConfig({ Map: {} })
  assert.equal(state.configForm.Map.tile_cache_ttl_days, 20)
  assert.equal(state.configForm.Map.tile_cache_max_size_gb, 10)
  const fields = state.sections.find(section => section.save === 'Map').fields
  assert.equal(fields.find(field => field.key === 'tile_cache_ttl_days').proxyOnly, true)
  assert.equal(fields.find(field => field.key === 'tile_cache_max_size_gb').proxyOnly, true)
  Object.assign(state.configForm.Map, { tile_cache_ttl_days: 7, tile_cache_max_size_gb: 1.25, frontend_proxy_enabled: false })
  await state.saveConfig()
  assert.equal(calls[0][2].Map.tile_cache_ttl_days, 7)
  assert.equal(calls[0][2].Map.tile_cache_max_size_gb, 1.25)
})

for (const [key, invalid] of [['tile_cache_ttl_days', 0], ['tile_cache_ttl_days', 1.2], ['tile_cache_max_size_gb', 0], ['tile_cache_max_size_gb', Infinity], ['tile_cache_max_size_gb', 1.234]]) {
  test(`map cache rejects ${key}=${invalid} before saving`, async () => {
    const { state, calls } = adminConfig()
    state.applyConfig({ Map: {} })
    state.configForm.Map[key] = invalid
    await state.saveConfig()
    assert.equal(calls.length, 0)
    assert.match(state.error.value, /瓦片缓存/)
  })
}

test('legacy configuration saves cache values when proxy is disabled and rejects invalid values', async () => {
  const valid = legacyConfig(7, 1.25)
  await valid.context.saveSystemConfig()
  assert.equal(valid.calls.length, 1)
  const map = JSON.parse(valid.calls[0][1].body).Map
  assert.equal(map.tile_cache_ttl_days, 7)
  assert.equal(map.tile_cache_max_size_gb, 1.25)
  assert.equal(map.frontend_proxy_enabled, false)
  for (const [days, size] of [[0, 10], [1.5, 10], [20, 0], [20, 1.234]]) {
    const invalid = legacyConfig(days, size)
    await invalid.context.saveSystemConfig()
    assert.equal(invalid.calls.length, 0)
    assert.match(invalid.alerts[0], /瓦片缓存/)
  }
})

test('legacy cache visibility changes preserve values in a cloned mobile form', () => {
  const { context } = legacyConfig()
  const settings = { hidden: false, inputValue: 7 }
  const select = { value: 'false', closest: () => ({ querySelector: () => settings }) }
  context.toggleMapTileCacheSettings(select)
  assert.equal(settings.hidden, true)
  select.value = 'true'
  context.toggleMapTileCacheSettings(select)
  assert.equal(settings.hidden, false)
  assert.equal(settings.inputValue, 7)
})
