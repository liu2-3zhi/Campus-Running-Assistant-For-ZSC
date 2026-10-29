import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import { normalizeBackendPageOrigin } from '../frontend/src/services/mapBackendOrigin.js'
import { normalizeMapConfigProfiles, serializeMapConfigProfiles } from '../frontend/src/utils/mapConfigProfiles.js'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { ref, computed, reactive, watch } = require('vue')

test('Vue map configuration saves optional security code in the provider object', async () => {
  const source = fs.readFileSync(new URL('../frontend/src/components/admin/AdminConfig.vue', import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  let saved
  const context = vm.createContext({ ref, computed, reactive, watch, normalizeBackendPageOrigin, normalizeMapConfigProfiles, serializeMapConfigProfiles, onMounted() {},
    callRawAPI: async (_url, _method, body) => { saved = body; return { success: true } },
  })
  vm.runInContext(script, context)
  vm.runInContext("applyConfig({Map:{provider:'amap',providers:{amap:{js_key:'example-key',security_js_code:'example-code'},baidu:{ak:'example-ak'}}}})", context)
  await vm.runInContext('saveConfig()', context)
  assert.equal(saved.Map.configs.find(item => item.provider === 'amap').security_js_code, 'example-code')
  assert.equal(saved.Map.configs.find(item => item.provider === 'baidu').ak, 'example-ak')
  vm.runInContext("configForm.Map.configs.find(item => item.provider === 'amap').security_js_code = ''", context)
  await vm.runInContext('saveConfig()', context)
  assert.equal(saved.Map.configs.find(item => item.provider === 'amap').security_js_code, '')
})

test('legacy SDK load sees the security code before AMapLoader.load', async () => {
  const source = fs.readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
  const begin = source.indexOf('function loadAMapOnce() {')
  const end = source.indexOf('async function ensureSingleMap()', begin)
  let observed
  const window = {}
  const context = vm.createContext({ window, AMapReady: false, AMapInstance: null, amapLoadingPromise: null,
    AMAP_API_KEY: 'example-key', getActiveMapProvider: () => 'amap',
    getMapProviderConfig: () => ({ security_js_code: 'example-code' }),
    AMapLoader: { load: async () => { observed = window._AMapSecurityConfig?.securityJsCode; return {} } },
    logMessage_Info() {}, logMessage_Error() {},
  })
  vm.runInContext(source.slice(begin, end), context)
  await vm.runInContext('loadAMapOnce()', context)
  assert.equal(observed, 'example-code')
})

test('public config events do not contain the optional security code', () => {
  const source = fs.readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
  const begin = source.indexOf('function createLegacyPublicConfigSnapshot(')
  const end = source.indexOf('function applyLegacyAppConfig(', begin)
  const snapshot = vm.runInNewContext(`${source.slice(begin, end)}\ncreateLegacyPublicConfigSnapshot({ map_providers: { amap: { js_key: 'example-key', security_js_code: 'example-code' } } })`)
  assert.ok(!JSON.stringify(snapshot).includes('example-code'))
})
