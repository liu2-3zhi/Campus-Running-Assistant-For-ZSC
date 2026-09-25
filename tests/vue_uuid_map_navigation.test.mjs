import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

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

test('Vue maps use the legacy default center instead of Beijing', () => {
  const mapContainer = read('frontend/src/components/map/MapContainer.vue')

  assert.match(mapContainer, /const DEFAULT_CENTER = \[113\.390342, 22\.527403\]/)
  assert.doesNotMatch(mapContainer, /116\.397428/)
  assert.doesNotMatch(mapContainer, /39\.90923/)
})

test('map runtime script carries the session UUID and backend accepts it', () => {
  const runtime = read('frontend/src/services/mapKeyRuntime.js')
  const backend = read('main.py')

  assert.match(runtime, /session_id/)
  assert.match(runtime, /getAuthenticatedSessionHeaderValue/)
  assert.match(backend, /request\.args\.get\("session_id", ""\)/)
})

test('inline session management exposes session selection and deletion', () => {
  const loginView = read('frontend/src/views/LoginView.vue')
  const backend = read('main.py')

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
  const legacyScript = read('scripts/main.js')

  assert.match(legacyScript, /"Config",\s*"default_ui",\s*"默认 UI",\s*"select"/s)
  assert.match(legacyScript, /Config: \{\s*default_ui: \$\("config-Config-default_ui"\)\.value,/s)
  assert.match(
    legacyScript,
    /case "config":[\s\S]*loadSystemConfig\(\)\.then\(\(\) => copyAdminContentToMultiPanel\("config"\)\)/,
  )
})
