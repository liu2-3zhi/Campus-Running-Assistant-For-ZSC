import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { join, resolve } from 'node:path'
import { readAdminFixtureAsset } from './browser_admin_fixture.mjs'

const require = createRequire(import.meta.url)
const frontendRequire = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium } = require('playwright')
const { parse, compileScript } = frontendRequire('@vue/compiler-sfc')
const { parse: parseJavaScript } = frontendRequire('@babel/parser')
const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const read = path => readFile(join(root, path), 'utf8')
const mainSource = await read('scripts/main.js')
const adminSource = await read('scripts/legacy-admin-config.js')
const mobileSource = await read('scripts/legacy-mobile-multi.js')
const paymentSource = await read('scripts/legacy-payment-user.js')

function functions(source, names) {
  const wanted = new Set(names)
  const nodes = parseJavaScript(source).program.body.filter(node =>
    node.type === 'FunctionDeclaration' && wanted.has(node.id.name))
  assert.equal(nodes.length, wanted.size, `all production functions must be found: ${names}`)
  return nodes.map(node => source.slice(node.start, node.end)).join('\n')
}

const modeStart = mainSource.indexOf('let IS_OFFLINE = null;')
const modeEnd = mainSource.indexOf('let authSessionUUID', modeStart)
assert.ok(modeStart >= 0 && modeEnd > modeStart)
const legacyMode = mainSource.slice(modeStart, modeEnd)
const legacyConfig = functions(mainSource, ['loadSystemConfig']) + '\n' + functions(adminSource, [
  'escapeHtml', 'normalizeBackendPageOrigin', 'useCurrentMapPageOrigin',
  'toggleMapTileCacheSettings', 'saveSystemConfig',
  'getMapConfigProviderDetails', 'normalizeLegacyMapConfigSettings', 'escapeMapConfigAttribute',
  'renderMapConfigCard', 'renderMapConfigCards', 'validateMapConfigOrigin', 'syncMapConfigCardOptions',
  'initMapConfigCardsSort', 'addMapConfigCard', 'removeMapConfigCard', 'moveMapConfigCard',
  'readMapConfigCards', 'copyMapConfigEditorState',
]) + '\n' + functions(mobileSource, ['copyAdminContentToMobile'])
const legacyPayment = functions(paymentSource, ['checkOverdueBeforeStart'])
const { descriptor, errors: parseErrors } = parse(await read('frontend/src/components/admin/AdminConfig.vue'))
assert.deepEqual(parseErrors, [])
const compiledConfig = compileScript(descriptor, { id: 'cache-config-browser', inlineTemplate: true }).content
  .replaceAll("'@/services/api'", "'/fixture/api.js'")
  .replaceAll("'@/services/mapBackendOrigin'", "'/fixture/origin.js'")
  .replaceAll("'@/utils/mapConfigProfiles'", "'/fixture/profiles.js'")
  .replaceAll("'./MapConfigCards.vue'", "'/fixture/MapConfigCards.js'")
const cardsDescriptor = parse(await read('frontend/src/components/admin/MapConfigCards.vue')).descriptor
const compiledCards = compileScript(cardsDescriptor, { id: 'map-config-cards-browser', inlineTemplate: true }).content
  .replaceAll("'@/services/mapBackendOrigin'", "'/fixture/origin.js'")
  .replaceAll("'@/utils/mapConfigProfiles'", "'/fixture/profiles.js'")
const paymentModule = (await read('frontend/src/composables/usePayment.js'))
  .replaceAll("'@/services/api'", "'/fixture/api.js'")
  .replaceAll("'@/stores/auth'", "'/fixture/auth.js'")
  .replaceAll("'@/stores/app'", "'/fixture/app.js'")
  .replaceAll("'@/utils/sanitizeSvg'", "'/fixture/sanitize.js'")
const distIndex = await read('dist/index.html')
const stylesheet = distIndex.match(/href="([^\"]+\.css)"/)?.[1]
assert.ok(stylesheet, 'use the built application stylesheet')
const importMap = '<script type="importmap">{"imports":{"vue":"/fixture/vue.js","pinia":"/fixture/pinia.js"}}</script>'
const head = `<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="${stylesheet}">${importMap}`
const modules = new Map([
  ['/fixture/AdminConfig.js', compiledConfig],
  ['/fixture/MapConfigCards.js', compiledCards],
  ['/fixture/profiles.js', await read('frontend/src/utils/mapConfigProfiles.js')],
  ['/fixture/sortable.js', await read('cache/cdn/sortable.min.js')],
  ['/fixture/origin.js', await read('frontend/src/services/mapBackendOrigin.js')],
  ['/fixture/app.js', await read('frontend/src/stores/app.js')],
  ['/fixture/payment.js', paymentModule],
  ['/fixture/auth.js', 'export const useAuthStore = () => ({ sessionUUID: "isolated-business-session" })'],
  ['/fixture/sanitize.js', 'export const sanitizeSvg = value => value'],
  ['/fixture/api.js', `export async function callRawAPI(path, method='GET', data=null) {
    const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' },
      ...(method !== 'GET' && data !== null ? { body: JSON.stringify(data) } : {}) });
    if (!response.ok) throw new Error('Fixture HTTP ' + response.status);
    return response.json();
  }
  export const callAPI = (name, ...args) => callRawAPI('/api/' + name, 'POST', { args });`],
  ['/fixture/vue.js', await read('frontend/node_modules/vue/dist/vue.esm-browser.prod.js')],
  ['/fixture/pinia.js', (await read('frontend/node_modules/pinia/dist/pinia.esm-browser.js'))
    .replace("import { setupDevtoolsPlugin } from '@vue/devtools-api';", 'const setupDevtoolsPlugin = () => {};')],
])
const vueEntry = `import { createApp } from 'vue';
  import { createPinia, setActivePinia } from 'pinia';
  import AdminConfig from '/fixture/AdminConfig.js';
  import { useAppStore } from '/fixture/app.js';
  import { checkOverdueBeforeStart } from '/fixture/payment.js';
  import { callAPI } from '/fixture/api.js';
  const pinia = createPinia(); setActivePinia(pinia);
  const app = useAppStore(); app.bindBusinessSession('isolated-business-session');
  const context = app.captureBusinessContext();
  const initial = await callAPI('get_initial_data');
  if (!app.applyBusinessMode(initial, context)) throw new Error('Offline mode did not restore');
  createApp(AdminConfig).use(pinia).mount('#app');
  document.querySelector('#offline-check').onclick = async () => {
    const allowed = await checkOverdueBeforeStart('NULL');
    document.querySelector('#offline-result').textContent = allowed ? 'allowed' : 'blocked';
  };
  window.fixtureReady = true;`
modules.set('/fixture/vue-entry.js', vueEntry)
const legacyEntry = `const sessionUUID = 'isolated-business-session';
  const configLoadState = {};
  const $ = id => document.getElementById(id);
  const ensureConfigLoaded = () => configLoadState.system === true;
  const setButtonLoading = () => {};
  const showButtonSuccess = () => {};
  const showButtonError = (_button, message) => { throw new Error(message); };
  const showModalAlert = (message, title) => { if (title === '保存失败') throw new Error(message); };
  const restoreHealthScrollPositions = () => {};
  const getActiveMapProvider = () => 'amap';
  const normalizeSupportedMapProvider = value => value;
  const getAuthenticatedSessionHeaderValue = () => sessionUUID;
  const hydrateMapProviderSecretsForLegacy = async value => value;
  const queuePendingMapProviderConfig = () => true;
  const callPythonAPI = async name => (await fetch('/api/' + name, { method: 'POST' })).json();
  ${legacyMode}
  ${legacyConfig}
  ${legacyPayment}
  window.startFixture = async mobile => {
    const context = captureLegacyBusinessContext();
    const initial = await callPythonAPI('get_initial_data');
    if (!applyLegacyBusinessMode(initial, context)) throw new Error('Offline mode did not restore');
    await loadSystemConfig();
    if (!configLoadState.system) throw new Error('Legacy config did not load');
    if (mobile) {
      copyAdminContentToMobile('config', 'mobile-admin-config-content-panel');
      document.querySelector('#admin-config-panel_modal').hidden = true;
    }
    document.querySelector('#offline-check').onclick = async () => {
      const allowed = await checkOverdueBeforeStart('NULL');
      document.querySelector('#offline-result').textContent = allowed ? 'allowed' : 'blocked';
    };
    window.fixtureReady = true;
  };`
modules.set('/fixture/legacy-entry.js', legacyEntry)

let config
let saved
let requests
const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://127.0.0.1').pathname
  try {
    if (modules.has(path)) {
      res.writeHead(200, { 'Content-Type': 'application/javascript', 'X-Content-Type-Options': 'nosniff' }).end(modules.get(path))
      return
    }
    if (path.startsWith('/api/')) {
      let raw = ''
      for await (const chunk of req) raw += chunk
      requests.push(path)
      let result
      if (path === '/api/admin/config/load') result = { success: true, config }
      else if (path === '/api/admin/config/save') {
        config = JSON.parse(raw)
        saved.push(structuredClone(config))
        result = { success: true }
      } else if (path === '/api/get_initial_data' || path === '/api/get_session_mode_info') {
        result = { success: true, is_offline_mode: true }
      } else if (path === '/api/frontend-config') result = { success: true }
      else { res.writeHead(404, { 'Content-Type': 'application/json' }).end('{"success":false}'); return }
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }).end(JSON.stringify(result))
      return
    }
    if (path === '/vue' || path === '/legacy') {
      const mobile = new URL(req.url, 'http://127.0.0.1').searchParams.get('mobile') === '1'
      const content = path === '/vue'
        ? '<div id="app"></div><script type="module" src="/fixture/vue-entry.js"></script>'
        : `<div id="admin-config-panel_modal"><div id="admin-config-form"></div><button id="admin-save-config_modal" onclick="saveSystemConfig(this)">保存配置</button></div><div id="mobile-admin-config-content-panel"></div><script src="/fixture/sortable.js"></script><script src="/fixture/legacy-entry.js"></script><script>startFixture(${mobile});</script>`
      res.writeHead(200, { 'Content-Type': 'text/html' }).end(`<!doctype html><html><head>${head}</head><body style="padding:16px"><button id="offline-check">离线执行前检查</button><output id="offline-result"></output>${content}</body></html>`)
      return
    }
    if (path === '/favicon.ico') { res.writeHead(204).end(); return }
    const asset = await readAdminFixtureAsset(path, { root, dist: join(root, 'dist') })
    res.writeHead(asset.status, { 'Content-Type': asset.contentType, 'X-Content-Type-Options': 'nosniff' }).end(asset.body)
  } catch (error) {
    res.writeHead(500, { 'Content-Type': 'text/plain' }).end(String(error))
  }
})

export async function createMapConfigBrowserFixture(initialConfig) {
  config = structuredClone(initialConfig)
  saved = []
  requests = []
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  return {
    base: `http://127.0.0.1:${server.address().port}`,
    get saved() { return saved },
    get requests() { return requests },
    setConfig(value) { config = structuredClone(value); saved = []; requests = [] },
    async close() { await new Promise(resolve => server.close(resolve)); assert.equal(server.listening, false) },
  }
}

export async function runMapCacheConfigSmoke() {
let browser
try {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  try { browser = await chromium.launch({ headless: true }) }
  catch { browser = await chromium.launch({ channel: 'chrome', headless: true }) }
  for (const ui of ['vue', 'legacy']) {
    for (const viewport of [{ width: 1440, height: 980 }, { width: 390, height: 844 }]) {
      config = { Map: { frontend_proxy_enabled: false } }
      saved = []
      requests = []
      const mobile = viewport.width < 768
      const context = await browser.newContext({ viewport })
      const unexpected = []
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === base) return route.continue()
        unexpected.push(route.request().url())
        return route.abort()
      })
      await context.addInitScript(() => {
        window.fixtureUnhandled = []
        window.addEventListener('unhandledrejection', event => window.fixtureUnhandled.push(String(event.reason)))
      })
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', error => errors.push(String(error)))
      const visit = async () => {
        await page.goto(`${base}/${ui}?mobile=${mobile ? 1 : 0}`)
        await page.waitForFunction(() => window.fixtureReady === true)
        await page.getByRole('button', { name: '离线执行前检查', exact: true }).click()
        await page.waitForFunction(() => document.querySelector('#offline-result').textContent === 'allowed')
      }
      await visit()
      const panel = ui === 'vue' ? page.locator('#app') : page.locator(mobile ? '#mobile-admin-config-content-panel' : '#admin-config-panel_modal')
      const input = label => ui === 'vue'
        ? panel.locator('label').filter({ hasText: new RegExp('^' + label.replace(/[()]/g, '\\$&') + '$') }).locator('..').locator('input')
        : panel.locator(`[id="config-Map-${label.includes('时间') ? 'tile_cache_ttl_days' : 'tile_cache_max_size_gb'}"]`)
      const days = input('地图瓦片缓存时间（天）')
      const size = input('地图瓦片缓存最大大小（GB）')
      const toggle = ui === 'vue'
        ? panel.getByRole('switch', { name: '启用地图请求后端代理', exact: true })
        : panel.locator('[id="config-Map-frontend_proxy_enabled"]')
      const setProxy = async enabled => {
        if (ui === 'vue') {
          const current = await toggle.getAttribute('aria-checked') === 'true'
          if (current !== enabled) await toggle.click()
        } else await toggle.selectOption(String(enabled))
        await days.waitFor({ state: enabled ? 'visible' : 'hidden' })
      }
      assert.equal(await days.inputValue(), '20')
      assert.equal(await size.inputValue(), '10')
      assert.equal(await days.isVisible(), false)
      await setProxy(true)
      await days.fill('7')
      await size.fill('1.25')
      await setProxy(false)
      const savedResponse = page.waitForResponse(response => response.url().endsWith('/api/admin/config/save') && response.status() === 200)
      await panel.getByRole('button', { name: '保存配置', exact: true }).click()
      await savedResponse
      assert.equal(saved.length, 1)
      assert.equal(saved[0].Map.frontend_proxy_enabled, false)
      assert.equal(saved[0].Map.tile_cache_ttl_days, 7)
      assert.equal(saved[0].Map.tile_cache_max_size_gb, 1.25)
      await visit()
      assert.equal(await days.isVisible(), false)
      await setProxy(true)
      assert.equal(await days.inputValue(), '7')
      assert.equal(await size.inputValue(), '1.25')
      await setProxy(false)
      await setProxy(true)
      assert.equal(await days.inputValue(), '7')
      assert.equal(await size.inputValue(), '1.25')
      assert.equal(requests.some(path => path === '/api/check_overdue' || path.startsWith('/api/billing/')), false)
      assert.deepEqual(errors, [])
      assert.deepEqual(await page.evaluate(() => window.fixtureUnhandled), [])
      assert.deepEqual(unexpected, [])
      await context.close()
      console.log(`PASS ${ui} ${viewport.width}x${viewport.height}: defaults 20/10, proxy visibility, saved off/on values, restored offline billing bypass`)
    }
  }
} finally {
  await browser?.close()
  await new Promise(resolve => server.close(resolve))
  assert.equal(server.listening, false)
  if (browser) assert.equal(browser.isConnected(), false)
}
}

if (resolve(process.argv[1] || '') === fileURLToPath(import.meta.url)) await runMapCacheConfigSmoke()
