import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { ref, reactive, watch, nextTick } from '../frontend/node_modules/vue/dist/vue.esm-browser.prod.js'
import { extractMultiMapWatcher } from './multi_map_ui_browser_fixture.mjs'

const productionSource = await readFile(new URL('../frontend/src/views/MultiAccountView.vue', import.meta.url), 'utf8')

test('multi-account real SDK fixture extracts the production marker watcher and rejects changed boundaries', () => {
  const watcher = extractMultiMapWatcher(productionSource)
  assert.ok(productionSource.includes(watcher))
  assert.match(watcher, /mapComp\.removeOverlay\(marker\)/)
  assert.match(watcher, /markerMap !== mapStore\.mapInstance/)
  assert.throws(() => extractMultiMapWatcher('const replaced = true'), /watcher not found/)
  assert.throws(() => extractMultiMapWatcher('const multiMapRef = ref(null)\n</script>'), /contract changed/)
})

test('the extracted watcher tests native marker identity, removal and reconstruction after map replacement', async () => {
  const mapStore = reactive({isMapReady: false, mapInstance: null})
  const appStore = reactive({multiPositions: {}})
  const setup = new Function('ref', 'watch', 'mapStore', 'appStore', extractMultiMapWatcher(productionSource) + '\nreturn {multiMapRef, markers: () => accountMarkers}')
  let stopWatch
  const controls = setup(ref, (...args) => { stopWatch = watch(...args); return stopWatch }, mapStore, appStore)
  let creations = 0
  const removed = []
  controls.multiMapRef.value = {
    addMarker(point) { return {point, id: ++creations} },
    updateMarker(marker, point) { marker.point = point },
    removeOverlay(marker) { removed.push(marker.id) }, fitView() {},
  }
  try {
    mapStore.mapInstance = {id: 'A'}
    mapStore.isMapReady = true
    appStore.multiPositions = {first: {lon: 113, lat: 22}, second: {lon: 114, lat: 23}}
    await nextTick()
    const original = controls.markers().get('first')
    assert.equal(creations, 2)
    for (let index = 0; index < 10; index++) {
      appStore.multiPositions = {first: {lon: 113 + index * .001, lat: 22}, second: {lon: 114, lat: 23}}
      await nextTick()
    }
    assert.equal(controls.markers().get('first'), original)
    assert.equal(creations, 2)
    appStore.multiPositions = {first: {lon: 113, lat: 22}}
    await nextTick()
    assert.equal(controls.markers().size, 1)
    assert.equal(removed.length, 1)
    mapStore.mapInstance = {id: 'C'}
    await nextTick()
    assert.equal(creations, 3)
    assert.notEqual(controls.markers().get('first'), original)
    appStore.multiPositions = {}
    await nextTick()
    assert.equal(controls.markers().size, 0)
  } finally { stopWatch?.() }
})

test('legacy multi-account fixture calls production multi marker functions and waits for asynchronous map readiness', async () => {
  const source = await readFile(new URL('./legacy_multi_map_browser_fixture.js', import.meta.url), 'utf8')
  assert.match(source, /legacy-multi-accounts\.js/)
  assert.match(source, /multi_updateRunnerPosition\(username,/)
  assert.match(source, /multi_removeRunnerMarker\(username\)/)
  assert.match(source, /await waitForProviderMapReady\(containerId\)/)
  assert.doesNotMatch(source, /new (?:TMap\.MultiMarker|BMap\.Marker|T\.Marker)/)
})
