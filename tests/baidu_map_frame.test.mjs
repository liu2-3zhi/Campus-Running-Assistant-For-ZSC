import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/map-request-proxy.js', import.meta.url), 'utf8')

function runtime({ deferred = false } = {}) {
  const frames = [], scripts = [], timers = new Map(), installs = []
  const host = { appendChild(frame) { frame.parentNode = this; frames.push(frame) } }
  const sdk = { Map: class {} }
  const window = { location: { origin: 'https://app.example.test', href: 'https://app.example.test/uuid=private-session' },
    setTimeout(callback) { const id = timers.size + 1; timers.set(id, callback); return id },
    clearTimeout(id) { timers.delete(id) },
    document: { createElement(type) {
      assert.equal(type, 'iframe')
      const frame = { style: {}, dataset: {}, setAttribute() {}, remove() { this.parentNode = null } }
      const child = { document: {
        getElementById() { return { id: 'baidu-map' } },
        createElement() { return {} },
        head: { appendChild(script) {
          scripts.push(script.src)
          if (script.src.includes('map-request-proxy.js')) {
            child.ZXMapRequestProxy = { install(config) { installs.push(config) } }; script.onload()
          } else {
            child.BMap = sdk
            if (!deferred) child.__zxBaiduReady()
          }
        } },
      } }
      frame.contentWindow = child
      queueMicrotask(() => frame.onload?.())
      return frame
    } },
  }
  vm.runInNewContext(source, { window, URL, Object, String, Error, Promise, Set })
  return { api: window.ZXMapRequestProxy, window, host, frames, scripts, sdk, installs, timers }
}

test('each Baidu map receives a separate SDK realm without importing its SDK into the parent', async () => {
  const r = runtime()
  const first = r.api.createBaiduMapFrame({ host: r.host, key: 'test-ak' })
  const second = r.api.createBaiduMapFrame({ host: r.host, key: 'test-ak' })
  await Promise.all([first.ready, second.ready])
  assert.equal(first.sdk, r.sdk)
  assert.notEqual(first.window, second.window)
  assert.equal(r.window.BMap, undefined)
  assert.equal(first.frame.referrerPolicy, 'origin')
  assert.doesNotMatch(first.frame.srcdoc, /private-session|test-ak|https?:/)
  assert.match(first.frame.srcdoc, /name="referrer" content="origin"/)
  const firstFrame = first.frame
  first.dispose()
  assert.equal(first.window, null, 'disposed map references must not retain the iframe window')
  assert.equal(first.frame, null, 'disposed map handles must not retain the iframe element')
  assert.equal(firstFrame.parentNode, null)
  assert.ok(second.frame.parentNode)
  second.dispose()
  assert.equal(r.timers.size, 0)
})

test('Baidu frame installs the current proxy mode before loading the SDK', async () => {
  const r = runtime()
  r.api.install({ enabled: true, provider: 'baidu' })
  const frame = r.api.createBaiduMapFrame({ host: r.host, key: 'test-ak' })
  await frame.ready
  assert.equal(r.installs[0].enabled, true)
  assert.match(r.scripts[0], /^https:\/\/app\.example\.test\/scripts\/map-request-proxy\.js$/)
  assert.match(r.scripts[1], /api\.map\.baidu\.com\/api\?v=4\.0/)
  frame.dispose()
})

test('disposing an unfinished Baidu realm cancels readiness and a late SDK callback cannot restore it', async () => {
  const r = runtime({ deferred: true })
  const frame = r.api.createBaiduMapFrame({ host: r.host, key: 'test-ak' })
  await Promise.resolve()
  const callback = frame.window.__zxBaiduReady
  const iframe = frame.frame
  frame.dispose()
  await assert.rejects(frame.ready, /已取消/)
  callback?.()
  assert.equal(frame.sdk, null)
  assert.equal(frame.frame, null)
  assert.equal(iframe.parentNode, null)
})

test('Baidu SDK deadline removes its entire realm and exposes a retryable error', async () => {
  const r = runtime({ deferred: true })
  const frame = r.api.createBaiduMapFrame({ host: r.host, key: 'test-ak' })
  await Promise.resolve()
  const iframe = frame.frame
  r.timers.values().next().value()
  await assert.rejects(frame.ready, /加载超时/)
  assert.equal(frame.frame, null)
  assert.equal(iframe.parentNode, null)
  assert.equal(r.timers.size, 0)
})
