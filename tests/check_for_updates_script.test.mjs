import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/Check_for_updates.js', import.meta.url), 'utf8')
const latestVersion = 'test-version-123'

function run({ storedVersion = '', apiOk = true, apiVersion = latestVersion, storageFails = false, storageWriteFails = false, apiFails = false, anotherTabVersion, pendingApi = false, readyState = 'loading' } = {}) {
  const requests = []
  const replacements = []
  const cacheDeletes = []
  const written = []
  let unregisterCount = 0
  const storage = new Map([['siteVersion', storedVersion]])
  const context = vm.createContext({
    document: {
      currentScript: { dataset: {} },
      readyState,
      getElementById: () => written.length ? {} : null,
      write: (html) => written.push(html),
    },
    window: {
      caches: {},
      location: {
        href: 'https://example.test/uuid=demo?keep=1#section',
        replace: (url) => replacements.push(url),
      },
    },
    navigator: {
      serviceWorker: {
        getRegistrations: async () => [{ unregister: async () => { unregisterCount++ } }],
      },
    },
    caches: {
      keys: async () => ['old-cache'],
      delete: async (name) => cacheDeletes.push(name),
    },
    localStorage: {
      getItem(key) {
        if (storageFails) throw new Error('Storage unavailable')
        return storage.get(key)
      },
      setItem(key, value) {
        if (storageFails || storageWriteFails) throw new Error('Storage unavailable')
        storage.set(key, value)
      },
    },
    fetch: async (url, options) => {
      requests.push({ url, options })
      if (url === '/api/version.json') {
        if (anotherTabVersion) storage.set('siteVersion', anotherTabVersion)
        if (pendingApi) return new Promise(() => {})
        if (apiFails) throw new Error('offline')
        return { ok: apiOk, status: apiOk ? 200 : 503, json: async () => ({ version: apiVersion }) }
      }
      return { ok: true }
    },
    console: { log() {} },
    URL,
    Date: class extends Date { static now() { return 1234567890 } },
  })
  vm.runInContext(source, context)
  return { context, requests, replacements, cacheDeletes, get unregisterCount() { return unregisterCount }, storage, written }
}

function scriptUrl(result) {
  assert.equal(result.written.length, 1)
  assert.match(result.written[0], /defer=""/)
  return new URL(result.written[0].match(/src="([^"]+)"/)[1], 'https://example.test/')
}

const settle = () => new Promise((resolve) => setImmediate(resolve))

test('main.js uses localStorage version before any API response, retaining parser defer', async () => {
  const result = run({ storedVersion: latestVersion })
  const url = scriptUrl(result)
  assert.equal(url.pathname, '/scripts/main.js')
  assert.equal(url.searchParams.get('version'), latestVersion)
  await settle()
  assert.equal(result.requests[0].options.cache, 'no-store')
  assert.deepEqual(result.replacements, [])
})

test('first visit uses a temporary cache key and saves API version for the next load', async () => {
  const result = run()
  assert.equal(scriptUrl(result).searchParams.get('version'), '1234567890')
  await settle()
  assert.equal(result.storage.get('siteVersion'), latestVersion)
  assert.deepEqual(result.replacements, [])
  const nextLoad = run({ storedVersion: result.storage.get('siteVersion') })
  assert.equal(scriptUrl(nextLoad).searchParams.get('version'), latestVersion)
  await settle()
})

test('new version is saved before cache cleanup and reload', async () => {
  const result = run({ storedVersion: 'old-version' })
  assert.equal(scriptUrl(result).searchParams.get('version'), 'old-version')
  await settle()
  assert.equal(result.storage.get('siteVersion'), latestVersion)
  assert.equal(result.replacements.length, 1)
  const url = new URL(result.replacements[0])
  assert.equal(url.pathname, '/uuid=demo')
  assert.equal(url.searchParams.get('keep'), '1')
  assert.equal(url.hash, '#section')
  assert.ok(url.searchParams.has('__cache_bust'))
  assert.deepEqual(result.cacheDeletes, ['old-cache'])
  assert.equal(result.unregisterCount, 1)
})

test('another tab updating storage does not hide a version change for the loaded script', async () => {
  const result = run({ storedVersion: 'old-version', anotherTabVersion: latestVersion })
  await settle()
  assert.equal(result.replacements.length, 1)
})

test('unavailable storage does not prevent script loading or cause reload loops', async () => {
  const result = run({ storageFails: true })
  assert.equal(scriptUrl(result).searchParams.get('version'), '1234567890')
  await settle()
  assert.deepEqual(result.replacements, [])
})

test('failed, blank or pending version API never blocks main.js loading', async () => {
  for (const options of [{ apiOk: false }, { apiVersion: '' }, { apiFails: true }, { pendingApi: true }]) {
    const result = run({ storedVersion: 'known-version', ...options })
    assert.equal(scriptUrl(result).searchParams.get('version'), 'known-version')
    await settle()
    assert.deepEqual(result.replacements, [])
  }
})

test('readable but unwritable storage does not cause a repeated version reload', async () => {
  const result = run({ storedVersion: 'old-version', storageWriteFails: true })
  await settle()
  assert.equal(scriptUrl(result).searchParams.get('version'), 'old-version')
  assert.equal(result.storage.get('siteVersion'), 'old-version')
  assert.deepEqual(result.replacements, [])
})

test('version from storage is URL encoded, not interpreted as script markup', async () => {
  const value = 'test" onload="bad &demo#hash'
  const result = run({ storedVersion: value, apiVersion: value })
  assert.equal(scriptUrl(result).searchParams.get('version'), value)
  assert.doesNotMatch(result.written[0], /onload="/)
  await settle()
})

test('repeated updater execution does not load main twice', async () => {
  const result = run({ storedVersion: latestVersion })
  vm.runInContext(source, result.context)
  assert.equal(result.written.length, 1)
  await settle()
})

test('executing updater after parsing does not overwrite the document', async () => {
  const result = run({ readyState: 'complete', storedVersion: latestVersion })
  assert.equal(result.written.length, 0)
  await settle()
})

test('index loads the updater once at the former deferred main entry point', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.equal((html.match(/src="\/scripts\/Check_for_updates\.js[^\"]*"/g) || []).length, 1)
  const loaderPosition = html.indexOf('src="/scripts/Check_for_updates.js')
  assert.ok(loaderPosition > html.indexOf('src="/api/cdn/sortable"'))
  assert.ok(loaderPosition < html.indexOf('href="/editor.md/css/editormd.css"'))
  assert.doesNotMatch(html, /<script[^>]+src="\/scripts\/main\.js(?:[?\"])/)
  assert.doesNotMatch(html, /frontend_asset_version/)
})
