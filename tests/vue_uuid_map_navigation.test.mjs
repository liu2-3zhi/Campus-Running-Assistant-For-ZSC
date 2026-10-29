import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { parse } = require('@babel/parser')

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const readBackend = () =>
  [read('main.py'), read('web_server.py').replaceAll('_main().', '')].join('\n\n')

test('Vue main and multi routes retain the active business UUID', () => {
  const router = read('frontend/src/router/index.js')
  const loginView = read('frontend/src/views/LoginView.vue')

  assert.match(router, /path: '\/uuid=:uuid\/app'/)
  assert.match(router, /path: '\/uuid=:uuid\/multi'/)
  assert.match(loginView, /name: 'main', params: \{ uuid: sessionId \}/)
  assert.match(loginView, /name: 'multi', params: \{ uuid: sessionId \}/)
  assert.match(loginView, /router\.replace\(\{ name: 'session', params: \{ uuid: sessionId \} \}\)/)
})

test('returning from single and multi account keeps the business session', () => {
  const mainView = read('frontend/src/views/MainView.vue')
  const multiView = read('frontend/src/views/MultiAccountView.vue')

  assert.match(mainView, /name: 'session', params: \{ uuid: sessionId \}/)
  assert.doesNotMatch(
    mainView.slice(mainView.indexOf('async function handleBack'), mainView.indexOf('// ── Lifecycle')),
    /callAPI\('logout'\)/,
  )
  assert.match(multiView, /authStore\.getAuthenticatedSessionHeaderValue\(\)/)
  assert.match(multiView, /name: 'session', params: \{ uuid: sessionId \}/)
  assert.match(mainView, /window\.location\.assign\(target\)/)
  assert.match(multiView, /window\.location\.assign\(target\)/)
})

test('multi account hydrates map provider secrets before rendering its map', () => {
  const multiView = read('frontend/src/views/MultiAccountView.vue')

  assert.match(multiView, /hydrateMapProviderSecrets/)
  assert.match(multiView, /await hydrateMapProviderSecrets\(/)
  assert.match(multiView, /mapStore\.setConfig\(/)
  assert.match(multiView, /mapStore\.setProvider\(/)
})

for (const [path, functionName] of [
  ['frontend/src/views/MainView.vue', 'loadInitialData'],
  ['frontend/src/views/MultiAccountView.vue', 'loadMapProviderConfig'],
]) {
  test(`${path} clears previous profile credentials when the selected profile has empty keys`, async () => {
    const source = read(path).match(/<script setup>([\s\S]*?)<\/script>/)[1]
    const node = parse(source, { sourceType: 'module' }).program.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === functionName)
    assert.ok(node, 'test the production map-loading function')
    let payload
    const app = {
      captureBusinessContext: () => 'business', isCurrentBusinessContext: () => true,
      applyBusinessMode() {}, addRoutePlanningFailures() {}, addLog() {},
    }
    const auth = { sessionUUID: 'business-session', applyAuthInfo() {} }
    const mapStore = {
      config: {}, activeProvider: '',
      setConfig(config) { Object.assign(this.config, config) },
      setProvider(provider) { this.activeProvider = provider },
    }
    const context = vm.createContext({
      app, appStore: app, auth, authStore: auth, mapStore, viewMounted: true,
      callAPI: async () => payload, hydrateMapProviderSecrets: async value => value,
    })
    vm.runInContext(source.slice(node.start, node.end), context)
    const load = () => vm.runInContext(`${functionName}()`, context)
    payload = { map_provider: 'amap', map_providers: {
      amap: { js_key: 'first-key', security_js_code: 'first-code' }, tencent: { map_key: 'old-tencent' },
      tianditu: { token: 'old-tianditu' }, baidu: { ak: 'old-baidu' },
    } }
    await load()
    assert.equal(mapStore.config.amapKey, 'first-key')
    payload = { map_provider: 'amap', map_config_id: 'empty-amap', map_providers: {
      amap: { js_key: '', security_js_code: '' }, tencent: { provider: 'tencent' },
    } }
    await load()
    assert.deepEqual(JSON.parse(JSON.stringify(mapStore.config)), {
      amapKey: '', amapSecurityJsCode: '', tencentKey: '', tiandituKey: '', baiduKey: '', frontendProxyEnabled: false,
      frontendConfigId: 'empty-amap',
    })
    payload = { map_provider: 'tencent', frontend_proxy_enabled: true, map_providers: { tencent: { map_key: 'selected-tencent' } } }
    await load()
    assert.equal(mapStore.activeProvider, 'tencent')
    assert.equal(mapStore.config.tencentKey, 'selected-tencent')
    assert.equal(mapStore.config.amapKey, '')
    assert.equal(mapStore.config.frontendProxyEnabled, true)
    assert.equal(mapStore.config.frontendConfigId, '')
  })
}

test('Vue maps use the legacy default center instead of Beijing', () => {
  const mapContainer = read('frontend/src/components/map/MapContainer.vue')

  assert.match(mapContainer, /const DEFAULT_CENTER = \[113\.390342, 22\.527403\]/)
  assert.doesNotMatch(mapContainer, /116\.397428/)
  assert.doesNotMatch(mapContainer, /39\.90923/)
})

test('map runtime script carries the session UUID and backend accepts it', () => {
  const runtime = read('frontend/src/services/mapKeyRuntime.js')
  const backend = readBackend()

  assert.match(runtime, /session_id/)
  assert.match(runtime, /getAuthenticatedSessionHeaderValue/)
  assert.match(backend, /request\.args\.get\("session_id", ""\)/)
})

test('inline session management exposes session selection and deletion', () => {
  const loginView = read('frontend/src/views/LoginView.vue')
  const backend = readBackend()

  assert.match(loginView, /async function selectInlineSession/)
  assert.match(loginView, /async function deleteInlineSession/)
  assert.match(loginView, /sessionDisplayName\(session\)/)
  assert.match(loginView, /@click="selectInlineSession\(session\)"/)
  assert.match(loginView, /@click="deleteInlineSession\(session\)"/)
  assert.match(backend, /"auth_username": auth_username,\s*"username": auth_username/s)
})

test('guest login sends its generated UUID and returns to a UUID URL', () => {
  const authPanel = read('frontend/src/components/login/AuthPanel.vue')

  assert.match(authPanel, /'X-Session-ID': anonSessionId/)
  assert.match(authPanel, /session_id: data\.session_id \|\| anonSessionId/)
})

test('legacy admin config panel renders and saves the default UI option', () => {
  const legacyScript =
    `${read('scripts/main.js')}\n${read('scripts/legacy-admin-config.js')}\n${read('scripts/legacy-mobile-multi.js')}`

  assert.match(legacyScript, /"Config",\s*"default_ui",\s*"默认 UI",\s*"select"/s)
  assert.match(legacyScript, /Config: \{\s*default_ui: \$\("config-Config-default_ui"\)\.value,/s)
  assert.match(
    legacyScript,
    /case "config":[\s\S]*loadSystemConfig\(\)\.then\(\(\) => copyAdminContentToMultiPanel\("config"\)\)/,
  )
})
