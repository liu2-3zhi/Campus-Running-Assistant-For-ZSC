import test from 'node:test'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readAdminFixtureAsset } from './browser_admin_fixture.mjs'
import { readFile } from 'node:fs/promises'

const root = fileURLToPath(new URL('..', import.meta.url))
const fixture = { root, dist: resolve(root, 'dist') }

test('admin browser fixture serves the real proxy script with JavaScript MIME', async () => {
  const response = await readAdminFixtureAsset('/scripts/map-request-proxy.js', fixture)
  assert.equal(response.status, 200)
  assert.equal(response.contentType, 'application/javascript')
  assert.match(String(response.body), /ZXMapRequestProxy/)
  assert.doesNotMatch(String(response.body), /^<!doctype html>/i)
})

test('admin browser fixture never returns SPA HTML for missing scripts or traversal', async () => {
  for (const path of ['/scripts/missing.js', '/frontend/assets/missing.js', '/frontend/missing.js', '/frontend/assets/../../index.html', '/other']) {
    const response = await readAdminFixtureAsset(path, fixture)
    assert.equal(response.status, 404, path)
    assert.equal(response.contentType, 'text/plain')
  }
})

test('admin browser fixture only falls back to HTML for supported application pages', async () => {
  for (const path of ['/frontend/', '/frontend/uuid=11111111-1111-4111-8111-111111111111', '/frontend/multi/uuid=22222222-2222-4222-8222-222222222222']) {
    const response = await readAdminFixtureAsset(path, fixture)
    assert.equal(response.status, 200, path)
    assert.equal(response.contentType, 'text/html')
  }
})

test('Vue map acceptance observes owned overlays without replacing SDK constructors', async () => {
  const source = await readFile(resolve(root, 'tests/map_ui_browser_fixture.mjs'), 'utf8')
  const body = source.match(/export function exposeAcceptanceOverlays\(code\) \{([\s\S]+?)\n\}/)[1]
  const expose = new Function('code', body)
  const original = 'defineExpose({ fitView })'
  assert.equal(expose(original), 'defineExpose({\n  getAcceptanceOverlays: () => [...markers, ...polylines], fitView })')
  assert.throws(() => expose('changed component'), /exposure not found/)
  assert.doesNotMatch(source, /new Proxy\(Original/)
  assert.match(source, /component\.value\?\.getAcceptanceOverlays\?\.\(\)/)
})

test('legacy acceptance teardown rejects failed SDK destruction and retains its container', async () => {
  const source = await readFile(resolve(root, 'tests/legacy_map_browser_fixture.js'), 'utf8')
  const body = source.match(/destroy: async \(\) => \{([\s\S]*?)\n      \},/)[1]
  const invoke = new Function('context', `return (async () => {
    let destroyed = false
    const {provider, nativeMap, host, destroyProviderMapInstance, waitForProviderMapDestruction} = context
    const containerId = 'fixture-map', originals = new Map(), window = {}
    const clearTaskMapAutoResetTimer = () => {}, clearProviderMapOverlays = () => {}
    ${body}
  })()`)
  for (const failingStage of ['destroy', 'wait']) {
    let removed = false
    const context = {provider: 'tencent', nativeMap: {}, host: {remove() { removed = true }},
      destroyProviderMapInstance: async () => failingStage !== 'destroy',
      waitForProviderMapDestruction: async () => failingStage !== 'wait'}
    await assert.rejects(invoke(context), /destruction failed/)
    assert.equal(removed, false, 'unreleased SDK host must remain attached')
  }
})

test('native SDK control defaults to immediate microtasks and releases actual label types', async () => {
  const source = await readFile(resolve(root, 'tests/browser_map_sdk_control.py'), 'utf8')
  const nativeRound = new Function(`return (${source.match(/NATIVE_ROUND = """([\s\S]+?)"""/)[1]})`)()
  let frames = 0, labels = 0, labelReleases = 0
  const previous = {document: globalThis.document, TMap: globalThis.TMap, BMap: globalThis.BMap, requestAnimationFrame: globalThis.requestAnimationFrame}
  class NativeMap {
    on(name, callback) { this.destroyed = callback }
    off() {}
    destroy() { this.destroyed?.() }
    centerAndZoom() {}
    fitBounds() {}
    addOverlay() {}
    clearOverlays() { labelReleases++ }
  }
  class Layer { on() {} off() {} setGeometries() {} setStyles() {} setMap() {} stopMove() {} destroy() {} setPath() {} }
  class Marker extends Layer { setPosition() {} setTitle() {} setLabel(label) { this.label = label } getLabel() { return this.label } }
  class Label extends Layer { constructor() { super(); labels++ } destroy() { labelReleases++ } setStyle() {} }
  try {
    globalThis.document = {body: {appendChild() {}}, createElement: () => ({style: {}, remove() {}, outerHTML: '<span>fixture</span>'})}
    globalThis.requestAnimationFrame = callback => { frames++; callback() }
    globalThis.TMap = {Map: NativeMap, MultiPolyline: Layer, MultiMarker: Marker, MultiLabel: Label, LabelStyle: class {}, PolylineStyle: class {}, LatLng: class {}, LatLngBounds: class { extend() {} }}
    globalThis.BMap = {Map: NativeMap, Polyline: Layer, Marker, Label, Point: class {}}
    for (const provider of ['tencent', 'baidu']) {
      const row = await nativeRound({provider})
      assert.equal(row.progress_updates, 10)
      assert.equal(row.functional_pass, true)
    }
    assert.equal(frames, 0, 'default control must not add animation-frame waits absent in the UI')
    assert.equal(labels, 7, 'native controls must create every task label in both pacing modes')
    assert.equal(labelReleases, 7, 'native controls must release every task label')
    await nativeRound({provider: 'tencent', frameSteps: true})
    assert.equal(frames, 11, 'frame-based pacing remains an explicit diagnostic control')
  } finally {
    Object.assign(globalThis, previous)
  }
})
