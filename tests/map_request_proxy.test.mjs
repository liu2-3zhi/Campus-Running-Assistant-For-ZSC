import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import test from 'node:test'

const source = await readFile(new URL('../scripts/map-request-proxy.js', import.meta.url), 'utf8')

function createHarness() {
  class FakeXHR {
    open(...args) { this.openArgs = args }
  }
  class FakeElement {
    constructor() { this.attributes = {} }
    setAttribute(name, value) { this.attributes[name] = String(value) }
    get innerHTML() { return this._innerHTML || '' }
    set innerHTML(value) { this._innerHTML = String(value) }
  }
  class FakeStyle {
    setProperty(name, value, priority) { this.lastProperty = [name, value, priority] }
    get cssText() { return this._cssText || '' }
    set cssText(value) { this._cssText = String(value) }
    get backgroundImage() { return this._backgroundImage || '' }
    set backgroundImage(value) { this._backgroundImage = String(value) }
  }
  class FakeScript extends FakeElement {
    get src() { return this._src || '' }
    set src(value) { this._src = String(value) }
  }
  class FakeImage extends FakeElement {
    get src() { return this._src || '' }
    set src(value) { this._src = String(value) }
  }
  class FakeLink extends FakeElement {
    get href() { return this._href || '' }
    set href(value) { this._href = String(value) }
  }
  class FakeWorker {
    constructor(url, options) { this.url = url; this.options = options }
  }
  const requests = []
  const timers = new Map()
  let nextTimer = 0
  const document = {
    write(...args) { this.written = args },
    writeln(...args) { this.written = args },
  }
  const window = {
    location: { origin: 'https://app.example.test' },
    fetch(...args) { requests.push(args); return Promise.resolve('ok') },
    XMLHttpRequest: FakeXHR,
    Element: FakeElement,
    CSSStyleDeclaration: FakeStyle,
    HTMLScriptElement: FakeScript,
    HTMLImageElement: FakeImage,
    HTMLLinkElement: FakeLink,
    Worker: FakeWorker,
    document,
    URL,
    Request,
    setTimeout(callback, delay) { const id = ++nextTimer; timers.set(id, { callback, delay }); return id },
    clearTimeout(id) { timers.delete(id) },
  }
  const context = vm.createContext({ window, document, URL, Request, Object, Array, String, RegExp, Error })
  vm.runInContext(source, context)
  return { window, document, requests, timers, api: window.ZXMapRequestProxy, FakeXHR, FakeScript, FakeImage, FakeLink, FakeWorker, FakeElement, FakeStyle }
}

test('routes allowlisted vendor URLs through same-origin proxy and preserves path/query without fragments', () => {
  const { api } = createHarness()
  assert.equal(typeof api.rewriteUrl, 'function')
  for (const [provider, url] of [
    ['amap', 'https://webapi.amap.com/maps?v=2.0&key=public#fragment'],
    ['amap', 'http://webrd03.is.autonavi.com/tile?x=1'],
    ['tencent', 'https://apis.map.qq.com/ws/direction/v1/?callback=cb'],
    ['baidu', 'https://online2.map.bdimg.com/tile?x=1'],
    ['tianditu', 'https://t7.tianditu.gov.cn/DataServer?T=vec_w&x=1'],
  ]) {
    assert.equal(api.rewriteUrl(url, { enabled: true, provider, basePath: '/map-proxy' }),
      `/map-proxy/${provider}/https/${new URL(url).host}${new URL(url).pathname}${new URL(url).search}`)
  }
})

test('covers the shared explicit numbered CDN host rules for all providers', () => {
  const { api } = createHarness()
  const cases = [
    ['amap', 'https://wprd04.is.autonavi.com/tile'],
    ['amap', 'https://webst01.is.autonavi.com/tile'],
    ['tencent', 'https://rt3.map.gtimg.com/tile'],
    ['tencent', 'https://p0.map.gtimg.com/tile'],
    ['baidu', 'https://shangetu3.map.bdimg.com/tile'],
    ['baidu', 'https://maponline0.bdimg.com/tile'],
    ['baidu', 'https://d2.map.baidu.com/tile'],
    ['tianditu', 'https://t4.tianditu.com/DataServer'],
    ['tianditu', 'https://api.tianditu.com/DataServer'],
  ]
  for (const [provider, url] of cases) {
    assert.match(api.rewriteUrl(url, { enabled: true, provider, basePath: '/map-proxy' }), new RegExp(`/map-proxy/${provider}/https/`))
  }
  assert.equal(api.rewriteUrl('https://web05.is.autonavi.com/tile', { enabled: true, provider: 'amap' }), 'https://web05.is.autonavi.com/tile')
})

test('covers observed secondary SDK and tile hosts without broad domain matching', () => {
  const { api } = createHarness()
  const cases = [
    ['amap', 'https://jsapi.amap.com/maps?v=2.0'],
    ['amap', 'https://jsapi-data1.amap.com/resource.js'],
    ['amap', 'https://jsapi-data5.amap.com/resource.js'],
    ['amap', 'https://o4.amap.com/resource.js'],
    ['tencent', 'https://confinfo.map.qq.com/config'],
    ['tencent', 'https://mapstyle.qpic.cn/style.json'],
    ['tencent', 'https://vectorsdk.map.qq.com/worker.js'],
    ['baidu', 'https://apimaponline0.bdimg.com/tile'],
    ['baidu', 'https://apimaponline3.bdimg.com/tile'],
    ['baidu', 'https://dlswbr.baidu.com/resource.js'],
    ['baidu', 'https://miao.baidu.com/resource.js'],
    ['baidu', 'https://webmap0.bdimg.com/tile'],
    ['tianditu', 'https://api.tianditu.gov.cn/api?v=4.0'],
  ]
  for (const [provider, url] of cases) {
    assert.match(api.rewriteUrl(url, { enabled: true, provider, basePath: '/map-proxy' }), new RegExp(`/map-proxy/${provider}/https/`))
  }
  for (const [provider, url] of [
    ['amap', 'https://jsapi-data6.amap.com/resource.js'],
    ['tencent', 'https://fake.map.qq.com/config'],
    ['baidu', 'https://apimaponline4.bdimg.com/tile'],
    ['tianditu', 'https://other.tianditu.gov.cn/api'],
  ]) {
    assert.equal(api.rewriteUrl(url, { enabled: true, provider }).startsWith('/map-proxy/'), false)
  }
})

test('leaves application APIs, unknown hosts, IPs, custom ports, and non-http schemes untouched', () => {
  const { api } = createHarness()
  for (const url of [
    '/api/tasks', 'https://api.example.test/map', 'https://notwebapi.amap.com/maps',
    'https://webapi.amap.com.evil.test/maps', 'https://webapi.amap.com:8443/maps',
    'https://127.0.0.1/maps', 'data:text/javascript,alert(1)', 'blob:https://app.example.test/id',
  ]) assert.equal(api.rewriteUrl(url, { enabled: true, provider: 'amap', basePath: '/map-proxy' }), url)
  assert.equal(api.rewriteUrl('https://user:pass@webapi.amap.com/maps', { enabled: true, provider: 'amap' }), 'https://user:pass@webapi.amap.com/maps')
})

test('does not re-proxy same-origin proxy URLs and retains original provider for old SDK instances', () => {
  const { api } = createHarness()
  const config = { enabled: true, provider: 'baidu', basePath: '/map-proxy' }
  const proxied = '/map-proxy/baidu/https/api.map.baidu.com/api?v=4.0&ak=x'
  assert.equal(api.rewriteUrl(proxied, config), proxied)
  const original = api.rewriteUrl('https://api.map.baidu.com/api?v=4.0&ak=x', config)
  assert.equal(api.rewriteUrl(original, { ...config, provider: 'tencent' }), original)
})

test('fetch handles strings, URL objects, and Request objects without losing init or Request metadata', async () => {
  const { window, requests, FakeXHR, api } = createHarness()
  api.install({ enabled: true, provider: 'tencent', basePath: '/map-proxy' })
  const init = { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{"x":1}', credentials: 'include' }
  await window.fetch('https://apis.map.qq.com/ws/test?callback=cb', init)
  assert.equal(requests[0][0], '/map-proxy/tencent/https/apis.map.qq.com/ws/test?callback=cb')
  assert.equal(requests[0][1], init)
  await window.fetch(new URL('https://api.map.baidu.com/api?v=4.0'), { method: 'GET' })
  assert.equal(requests[1][0], '/map-proxy/baidu/https/api.map.baidu.com/api?v=4.0')
  const request = new Request('https://api.map.baidu.com/route', { method: 'POST', headers: { 'x-test': 'yes' }, body: 'payload' })
  await window.fetch(request)
  assert.ok(requests[2][0] instanceof Request)
  assert.equal(requests[2][0].url, 'https://app.example.test/map-proxy/baidu/https/api.map.baidu.com/route')
  assert.equal(requests[2][0].method, 'POST')
  assert.equal(requests[2][0].headers.get('x-test'), 'yes')
  assert.equal(await requests[2][0].text(), 'payload')
})

test('XHR, script/image/link setters, setAttribute, Worker and document.write are narrowly rewritten', () => {
  const { window, document, api, FakeXHR, FakeScript, FakeImage, FakeLink, FakeWorker } = createHarness()
  api.install({ enabled: true, provider: 'tianditu', basePath: '/map-proxy' })
  const xhr = new window.XMLHttpRequest()
  xhr.open('POST', 'https://api.tianditu.gov.cn/drive?tk=x', false, 'user', 'pass')
  assert.deepEqual(Array.from(xhr.openArgs), ['POST', '/map-proxy/tianditu/https/api.tianditu.gov.cn/drive?tk=x', false, 'user', 'pass'])
  const script = new FakeScript()
  script.src = 'https://webapi.amap.com/maps?v=2.0'
  assert.equal(script.src, '/map-proxy/amap/https/webapi.amap.com/maps?v=2.0')
  script.setAttribute('src', 'https://apis.map.qq.com/a.js')
  assert.equal(script.attributes.src, '/map-proxy/tencent/https/apis.map.qq.com/a.js')
  const image = new FakeImage()
  image.src = 'https://t0.tianditu.gov.cn/DataServer?x=1'
  assert.equal(image.src, '/map-proxy/tianditu/https/t0.tianditu.gov.cn/DataServer?x=1')
  const link = new FakeLink()
  link.href = 'https://api.map.baidu.com/style.css'
  assert.equal(link.href, '/map-proxy/baidu/https/api.map.baidu.com/style.css')
  link.setAttribute('href', 'https://business.example.test/style.css')
  assert.equal(link.attributes.href, 'https://business.example.test/style.css')
  const worker = new window.Worker('https://webapi.amap.com/worker.js', { type: 'module', name: 'maps' })
  assert.ok(worker instanceof FakeWorker)
  assert.equal(worker.url, '/map-proxy/amap/https/webapi.amap.com/worker.js')
  assert.equal(worker.options.name, 'maps')
  document.write('<script src="https://api.map.baidu.com/maps?v=4.0"></script><img src="https://images.example.test/a.png">')
  assert.match(document.written[0], /\/map-proxy\/baidu\/https\/api\.map\.baidu\.com\/maps\?v=4\.0/)
  assert.match(document.written[0], /https:\/\/images\.example\.test\/a\.png/)
  document.writeln('<script src=https://webapi.amap.com/worker.js></script>')
  assert.match(document.written[0], /src=\/map-proxy\/amap\/https\/webapi\.amap\.com\/worker\.js/)
})

test('rewrites SDK innerHTML images and inline CSS before native resource loading', () => {
  const { api, FakeElement, FakeStyle } = createHarness()
  api.install({ enabled: true, provider: 'tianditu', basePath: '/map-proxy' })
  const logo = 'http://api.tianditu.gov.cn/v4.0/image/logo.png'
  const proxied = '/map-proxy/tianditu/https/api.tianditu.gov.cn/v4.0/image/logo.png'
  const element = new FakeElement()
  element.innerHTML = `<img src="${logo}" style="background-image:url(${logo})">`
  assert.equal(element.innerHTML, `<img src="${proxied}" style="background-image:url(${proxied})">`)
  element.setAttribute('style', `background:url('${logo}'); color:red`)
  assert.equal(element.attributes.style, `background:url('${proxied}'); color:red`)
  const style = new FakeStyle()
  style.cssText = `background-image:url("${logo}")`
  assert.equal(style.cssText, `background-image:url("${proxied}")`)
  style.backgroundImage = `url(${logo})`
  assert.equal(style.backgroundImage, `url(${proxied})`)
  style.setProperty('background-image', `url(${logo})`, 'important')
  assert.deepEqual(style.lastProperty, ['background-image', `url(${proxied})`, 'important'])
  element.innerHTML = '<img src="https://unrelated.example/image.png">'
  assert.equal(element.innerHTML, '<img src="https://unrelated.example/image.png">')
  api.install({ enabled: false, provider: 'tianditu' })
  element.innerHTML = `<img src="${logo}">`
  assert.equal(element.innerHTML, `<img src="${logo}">`)
})

test('Blob workers prepend proxy hooks while preserving options, revocation and native restoration', () => {
  const { window, api, FakeWorker } = createHarness()
  const blobs = []
  const revoked = []
  class FakeBlob { constructor(parts, options) { this.parts = parts; this.options = options; blobs.push(this) } }
  class LocalURL extends URL {
    static createObjectURL(blob) { return `blob:https://app.example.test/${blobs.indexOf(blob)}` }
    static revokeObjectURL(url) { revoked.push(url) }
  }
  window.Blob = FakeBlob
  window.URL = LocalURL
  const nativeCreate = LocalURL.createObjectURL
  const nativeRevoke = LocalURL.revokeObjectURL
  api.install({ enabled: true, provider: 'baidu' })
  const originalBlob = new FakeBlob(['importScripts("https://api.map.baidu.com/worker.js")'], { type: 'text/javascript' })
  const originalUrl = LocalURL.createObjectURL(originalBlob)
  const options = { name: 'map-worker', type: 'classic' }
  const worker = new window.Worker(originalUrl, options)
  assert.ok(worker instanceof FakeWorker)
  assert.notEqual(worker.url, originalUrl)
  assert.equal(worker.options, options)
  assert.equal(blobs[1].parts[1], originalBlob)
  assert.match(blobs[1].parts[0], /createMapRequestProxy/)
  assert.equal(revoked.includes(worker.url), true)
  LocalURL.revokeObjectURL(originalUrl)
  assert.equal(revoked.includes(originalUrl), true)
  api.install({ enabled: false, provider: 'baidu' })
  assert.equal(LocalURL.createObjectURL, nativeCreate)
  assert.equal(LocalURL.revokeObjectURL, nativeRevoke)
  assert.equal(window.Worker, FakeWorker)
})

test('repeated install keeps one hook layer, can switch config, and disabling restores natives', async () => {
  const { window, requests, api, FakeXHR } = createHarness()
  const nativeFetch = window.fetch
  const nativeOpen = FakeXHR.prototype.open
  api.install({ enabled: true, provider: 'amap', basePath: '/map-proxy' })
  const firstFetchWrapper = window.fetch
  api.install({ enabled: true, provider: 'tencent', basePath: '/map-proxy' })
  assert.equal(window.fetch, firstFetchWrapper)
  await window.fetch('https://apis.map.qq.com/ws/a')
  assert.equal(requests[0][0], '/map-proxy/tencent/https/apis.map.qq.com/ws/a')
  api.install({ enabled: false, provider: 'tencent', basePath: '/map-proxy' })
  assert.equal(window.fetch, nativeFetch)
  assert.equal(FakeXHR.prototype.open, nativeOpen)
  const element = new (window.HTMLScriptElement)()
  element.src = 'https://webapi.amap.com/maps'
  assert.equal(element.src, 'https://webapi.amap.com/maps')
  await window.fetch('https://apis.map.qq.com/ws/a')
  assert.equal(requests[1][0], 'https://apis.map.qq.com/ws/a')
  api.install({ enabled: true, provider: 'amap', basePath: '/map-proxy' })
  await window.fetch('https://webapi.amap.com/maps')
  assert.equal(requests[2][0], '/map-proxy/amap/https/webapi.amap.com/maps')
  api.install({ enabled: false, provider: 'amap', basePath: '/map-proxy' })
  assert.equal(window.fetch, nativeFetch)
})

test('enabled proxy bootstraps an authenticated context and installs URL hooks', async () => {
  const { window, api } = createHarness()
  const calls = []
  window.fetch = async (...args) => {
    calls.push(args)
    return { ok: true, json: async () => ({ success: true, expires_in: 1800 }) }
  }
  const result = await api.initialize({ enabled: true, provider: 'baidu', sessionId: 'target-session', originSessionId: 'admin-origin' })
  assert.equal(result.enabled, true)
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], '/api/map-proxy/context')
  assert.equal(calls[0][1].method, 'POST')
  assert.equal(calls[0][1].credentials, 'include')
  assert.equal(calls[0][1].headers['X-Session-ID'], 'target-session')
  assert.equal(calls[0][1].headers['X-Admin-Origin-Session-ID'], 'admin-origin')
  assert.equal(api.rewriteUrl('https://api.map.baidu.com/api?v=4.0', api.getConfig()), '/map-proxy/baidu/https/api.map.baidu.com/api?v=4.0')
})

for (const sdk of ['AMap', 'TMap', 'T', 'BMap']) {
  for (const initialMode of [true, false]) {
    test(`${sdk} mode changes reload once without replacing the active hooks or context (${initialMode})`, async () => {
      const { window, document, api, timers } = createHarness()
      const calls = []
      const originalUrl = 'https://app.example.test/?uuid=target-session#map'
      window.location.href = originalUrl
      let reloads = 0
      window.location.reload = function () { assert.equal(this, window.location); reloads++ }
      document.cookie = 'auth_token=unchanged; session_id=administrator-origin'
      window.fetch = async (...args) => {
        calls.push(args)
        return { ok: true, json: async () => ({ success: true, expires_in: 1800 }) }
      }
      await api.initialize({ enabled: initialMode, provider: 'baidu', sessionId: 'target-session', originSessionId: 'administrator-origin' })
      window[sdk] = { Map: class Map {} }
      const activeFetch = window.fetch
      const activeTimer = [...timers.entries()]
      const contextCalls = calls.length
      for (let attempt = 0; attempt < 2; attempt++) {
        await assert.rejects(api.initialize({ enabled: !initialMode, provider: 'baidu', sessionId: 'other-session' }), /模式.*刷新/)
      }
      await assert.rejects(api.initialize({ enabled: initialMode, provider: 'baidu', sessionId: 'target-session' }), /刷新/)
      assert.equal(reloads, 1)
      assert.equal(api.getConfig().enabled, initialMode)
      assert.equal(window.fetch, activeFetch)
      assert.deepEqual([...timers.entries()], activeTimer)
      assert.equal(calls.length, contextCalls, 'changing mode must not bootstrap a different context before reload')
      assert.equal(window.location.href, originalUrl)
      assert.equal(document.cookie, 'auth_token=unchanged; session_id=administrator-origin')
      await window.fetch('https://api.map.baidu.com/tile')
      assert.equal(calls.at(-1)[0], initialMode ? '/map-proxy/baidu/https/api.map.baidu.com/tile' : 'https://api.map.baidu.com/tile')
    })
  }
}

test('first initialization and changes before a Map constructor loads do not reload', async () => {
  const { window, api, timers } = createHarness()
  let reloads = 0
  window.location.reload = () => { reloads++ }
  window.fetch = async () => ({ ok: true, json: async () => ({ success: true, expires_in: 1800 }) })
  window.BMap = { loading: true }
  await api.initialize({ enabled: false, provider: 'baidu' })
  await api.initialize({ enabled: true, provider: 'baidu', sessionId: 'target' })
  await api.initialize({ enabled: false, provider: 'baidu' })
  assert.equal(reloads, 0)
  assert.equal(api.getConfig().enabled, false)
  assert.equal(timers.size, 0)

  const another = createHarness()
  another.window.BMap = { Map: class Map {} }
  const first = await another.api.initialize({ enabled: false, provider: 'baidu' })
  assert.equal(first.enabled, false, 'a preexisting SDK does not turn the first initialization into a mode change')
})

test('an unchanged enabled mode allows loaded SDK session changes without reload', async () => {
  const { window, api } = createHarness()
  const calls = []
  let reloads = 0
  window.location.reload = () => { reloads++ }
  window.TMap = { Map: class Map {} }
  window.fetch = async (...args) => {
    calls.push(args)
    return { ok: true, json: async () => ({ success: true, expires_in: 1800 }) }
  }
  for (const sessionId of ['administrator-origin', 'target-B', 'target-C']) {
    await api.initialize({ enabled: true, provider: 'tencent', sessionId, originSessionId: 'administrator-origin' })
  }
  assert.equal(reloads, 0)
  assert.deepEqual(calls.map(([_url, options]) => options.headers['X-Session-ID']), ['administrator-origin', 'target-B', 'target-C'])
  assert.ok(calls.every(([_url, options]) => options.headers['X-Admin-Origin-Session-ID'] === 'administrator-origin'))
})

for (const reloadFailure of ['missing', 'throws']) {
  test(`a loaded SDK mode change fails clearly when reload ${reloadFailure}`, async () => {
    const { window, api } = createHarness()
    const nativeFetch = window.fetch
    await api.initialize({ enabled: false, provider: 'tencent' })
    window.TMap = { Map: class Map {} }
    if (reloadFailure === 'throws') window.location.reload = () => { throw new Error('navigation unavailable') }
    await assert.rejects(api.initialize({ enabled: true, provider: 'tencent' }), /刷新.*手动刷新/)
    assert.equal(api.getConfig().enabled, false)
    assert.equal(window.fetch, nativeFetch)
  })
}

test('a rejected mode change leaves the existing context request active and standalone uninstall available', async () => {
  const { window, api, timers } = createHarness()
  let completeContext
  let contextSignal
  window.AbortController = AbortController
  window.location.reload = () => {}
  const nativeFetch = window.fetch = (_url, options) => {
    contextSignal = options.signal
    return new Promise(resolve => { completeContext = resolve })
  }
  const active = api.initialize({ enabled: true, provider: 'amap', sessionId: 'administrator-origin' })
  window.AMap = { Map: class Map {} }
  await assert.rejects(api.initialize({ enabled: false, provider: 'amap' }), /刷新/)
  assert.equal(contextSignal.aborted, false)
  completeContext({ ok: true, json: async () => ({ success: true, expires_in: 1800 }) })
  await active
  assert.equal(timers.size, 1)
  api.install({ enabled: false, provider: 'amap' })
  assert.equal(window.fetch, nativeFetch)
  assert.equal(timers.size, 0)
})

test('proxy bootstrap failure never falls back to direct vendor URLs', async () => {
  const { window, api } = createHarness()
  const calls = []
  window.fetch = async (url) => { calls.push(url); return { ok: false, status: 401, json: async () => ({ success: false }) } }
  await assert.rejects(api.initialize({ enabled: true, provider: 'amap', sessionId: 'target-session' }), /认证|context|proxy/i)
  assert.equal(api.getConfig().enabled, true)
  await window.fetch('https://webapi.amap.com/maps')
  assert.equal(calls.at(-1), '/map-proxy/amap/https/webapi.amap.com/maps')
})

test('proxy context renews before expiry and a renewal failure retains URL hooks', async () => {
  const { window, api, timers } = createHarness()
  const calls = []
  let allowed = true
  window.fetch = async (url, options) => {
    calls.push([url, options])
    return { ok: allowed, status: allowed ? 200 : 401, json: async () => ({ success: allowed, expires_in: 1800 }) }
  }
  await api.initialize({ enabled: true, provider: 'amap', sessionId: 'target', originSessionId: 'origin' })
  assert.equal(timers.size, 1)
  const first = timers.values().next().value
  assert.ok(first.delay > 0 && first.delay < 1800 * 1000)
  timers.clear()
  await first.callback()
  assert.equal(calls.length, 2)
  assert.equal(calls[1][1].headers['X-Session-ID'], 'target')
  assert.equal(calls[1][1].headers['X-Admin-Origin-Session-ID'], 'origin')
  allowed = false
  const second = timers.values().next().value
  timers.clear()
  await second.callback()
  await window.fetch('https://api.map.baidu.com/api')
  assert.equal(calls.at(-1)[0], '/map-proxy/baidu/https/api.map.baidu.com/api')
  assert.equal(api.getConfig().enabled, true)
  assert.equal(timers.size, 1)
  api.install({ enabled: false, provider: 'amap' })
  assert.equal(timers.size, 0)
})

test('a departed proxy initialization cannot replace the new context or its refresh timer', async () => {
  const { window, api, timers } = createHarness()
  let resolveOld
  const calls = []
  window.fetch = async (url, options) => {
    calls.push([url, options])
    if (options.headers['X-Session-ID'] === 'old') return new Promise(resolve => { resolveOld = resolve })
    return { ok: true, json: async () => ({ success: true, expires_in: 1800 }) }
  }
  const old = api.initialize({ enabled: true, provider: 'amap', sessionId: 'old' })
  await api.initialize({ enabled: true, provider: 'tencent', sessionId: 'new' })
  resolveOld({ ok: false, status: 401 })
  await old
  assert.equal(api.getConfig().provider, 'tencent')
  assert.equal(api.getConfig().enabled, true)
  assert.equal(timers.size, 1)
  const timer = timers.values().next().value
  timers.clear()
  await timer.callback()
  assert.equal(calls.at(-1)[1].headers['X-Session-ID'], 'new')
})

test('rejects path traversal in configured proxy base path', () => {
  const { api } = createHarness()
  assert.throws(() => api.install({ enabled: true, provider: 'amap', basePath: '/map-proxy/../other' }), /basePath/)
})
