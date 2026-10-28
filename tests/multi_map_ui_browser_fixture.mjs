// Build the production multi-account marker watcher and map component in memory.
import { build } from '../frontend/node_modules/vite/dist/node/index.js'
import vue from '../frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs'
import { readFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('../frontend', import.meta.url))

export function extractMultiMapWatcher(source) {
  const start = source.indexOf('const multiMapRef = ref(null)')
  const end = source.indexOf('</script>', start)
  if (start < 0 || end < 0) throw new Error('Production multi-account marker watcher not found')
  const block = source.slice(start, end).trim()
  if (!block.includes('watch([() => appStore.multiPositions,') || !block.includes('mapComp.updateMarker(')) {
    throw new Error('Production multi-account marker watcher contract changed')
  }
  return block
}

export async function compileMultiMapFixture() {
  const watcher = extractMultiMapWatcher(await readFile(resolve(root, 'src/views/MultiAccountView.vue'), 'utf8'))
  const source = `
import { createApp, h, nextTick, ref } from 'vue'
import { createPinia } from 'pinia'
import MapContainer from '@/components/map/MapContainer.vue'
import { useMapStore } from '@/stores/map'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { gcj02ToBd09, gcj02ToWgs84 } from '@/utils/coordinates'
import { watch } from 'vue'

const readPoint = point => !point ? null : Array.isArray(point) ? point.map(Number) : [
  Number(typeof point.getLng === 'function' ? point.getLng() : point.lng),
  Number(typeof point.getLat === 'function' ? point.getLat() : point.lat),
]
const markerPoint = marker => readPoint(marker?.getGeometries?.()[0]?.position || marker?.getPosition?.() || marker?.getLngLat?.())

window.mountMultiMapAcceptance = async ({provider, key, securityJsCode = '', sessionId, mobile = false, frontendProxyEnabled = true}) => {
  await window.multiMapAcceptance?.destroy()
  const pinia = createPinia()
  const appStore = useAppStore(pinia)
  const mapStore = useMapStore(pinia)
  const authStore = useAuthStore(pinia)
  authStore.sessionUUID = sessionId
  appStore.bindBusinessSession(sessionId)
  appStore.isMultiMode = true
  mapStore.setProvider(provider)
  mapStore.setConfig({[provider + 'Key']: key, amapSecurityJsCode: securityJsCode, frontendProxyEnabled})
  const containerId = mobile ? 'mobile-multi-map-container' : 'multi-map-container'
  let controls
  let destroyed = false
  const component = {
    setup() {
      ${watcher}
      controls = {multiMapRef, getMarkers: () => accountMarkers}
      return () => h(MapContainer, {ref: multiMapRef, containerId, isMultiAccount: true})
    },
  }
  const vm = createApp(component)
  vm.use(pinia)
  vm.mount('#map-ui')
  const expectedPoint = point => {
    if (provider === 'baidu') { const value = gcj02ToBd09(...point); return [value.lng, value.lat] }
    if (provider === 'tianditu') { const value = gcj02ToWgs84(...point); return readPoint(new window.T.LngLat(value.lng, value.lat)) }
    return point
  }
  const identities = new WeakMap()
  let nextIdentity = 0
  const snapshot = () => ({
    provider, sessionId: authStore.sessionUUID, mobile,
    markerIds: [...controls.getMarkers().keys()].sort(),
    markers: Object.fromEntries([...controls.getMarkers()].map(([username, marker]) => {
      if (!identities.has(marker)) identities.set(marker, ++nextIdentity)
      return [username, {point: markerPoint(marker), identity: identities.get(marker)}]
    })),
    businessPositions: JSON.parse(JSON.stringify(appStore.multiPositions)),
    mapReady: !!mapStore.isMapReady,
    hostCount: document.querySelectorAll('#' + containerId + ' > div[id*="-sdk-"]').length,
  })
  window.multiMapAcceptance = {
    ready: () => !destroyed && !!mapStore.isMapReady && !!controls.multiMapRef.value && !!document.getElementById(containerId)?.clientWidth,
    snapshot, expectedPoint,
    seed: async positions => {
      appStore.handleAccountsUpdated({accounts: Object.entries(positions).map(([username, pos]) => ({username, name: pos.name || username, current_position: {lon: pos.lon, lat: pos.lat}}))})
      await nextTick()
      return snapshot()
    },
    update: async (username, position) => {
      appStore.handleMultiPositionUpdate({username, ...position})
      await nextTick()
      return snapshot()
    },
    remove: async username => {
      appStore.handleAccountsUpdated({accounts: appStore.multiAccounts.filter(account => account.username !== username)
        .map(account => ({username: account.username, name: account.name}))})
      await nextTick()
      return snapshot()
    },
    switchSession: async nextSessionId => {
      const oldRequest = appStore.captureMultiAccountsSnapshot()
      authStore.sessionUUID = nextSessionId
      appStore.bindBusinessSession(nextSessionId)
      const acceptedOldSnapshot = appStore.applyMultiAccountsSnapshot([{username: 'departed', current_position: {lon: 116.4, lat: 39.9}}], oldRequest)
      await nextTick()
      return {...snapshot(), acceptedOldSnapshot}
    },
    destroy: async () => {
      if (destroyed) return
      destroyed = true
      const whenDisposed = controls.multiMapRef.value?.whenDisposed
      vm.unmount()
      await whenDisposed?.()
      return {rootEmpty: !document.getElementById(containerId), markersCleared: !mapStore.mapInstance}
    },
  }
}
`
  const virtualId = resolve(root, 'multi-map-acceptance-entry.js')
  const result = await build({
    configFile: false, root, logLevel: 'silent',
    resolve: {alias: {'@': resolve(root, 'src')}},
    plugins: [vue(), {name: 'multi-map-acceptance', resolveId: id => id === virtualId ? '\0' + id : null,
      load: id => id === '\0' + virtualId ? source : null}],
    build: {write: false, minify: false, cssCodeSplit: false,
      rolldownOptions: {input: virtualId, output: {format: 'es', entryFileNames: 'multi-map-ui.js', chunkFileNames: 'fixture/[name]-[hash].js'}}},
  })
  const output = Array.isArray(result) ? result.flatMap(item => item.output) : result.output
  return {files: Object.fromEntries(output.filter(item => item.type === 'chunk').map(item => [item.fileName, item.code])),
    css: output.filter(item => item.fileName.endsWith('.css')).map(item => item.source).join('\n')}
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.stdout.write(JSON.stringify(await compileMultiMapFixture()))
}
