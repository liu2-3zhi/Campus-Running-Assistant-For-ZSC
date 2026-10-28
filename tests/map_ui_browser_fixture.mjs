// Compile the production Vue map component in memory for opt-in real SDK checks.
import { build } from '../frontend/node_modules/vite/dist/node/index.js'
import vue from '../frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('../frontend', import.meta.url))
const source = `
import { createApp, h, nextTick, ref, toRaw, watch } from 'vue'
import { createPinia } from 'pinia'
import MapContainer from '@/components/map/MapContainer.vue'
import { useMapStore } from '@/stores/map'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { gcj02ToBd09, gcj02ToWgs84 } from '@/utils/coordinates'

window.mountMapAcceptance = async ({provider, key, securityJsCode, sessionId, frontendProxyEnabled = true}) => {
  await window.mapAcceptance?.destroy()
  const pinia = createPinia()
  const mapStore = useMapStore(pinia)
  const app = useAppStore(pinia)
  const auth = useAuthStore(pinia)
  auth.sessionUUID = sessionId
  mapStore.setProvider(provider)
  mapStore.setConfig({[provider + 'Key']: key, amapSecurityJsCode: securityJsCode || '', frontendProxyEnabled})
  const overlays = new Set()
  let nativeMap
  let cameraWrites = 0
  let destroyed = false
  const restorers = []
  const patchedMaps = new WeakSet()
  const patchMethod = (object, name, wrap) => {
    const original = object[name]
    const replacement = wrap(original)
    object[name] = replacement
    restorers.push(() => { if (object[name] === replacement) object[name] = original })
  }
  const proxyInitialization = {started: 0, completed: 0, rejected: 0, pending: 0, lastError: ''}
  if (typeof window.ZXMapRequestProxy?.initialize === 'function') {
    patchMethod(window.ZXMapRequestProxy, 'initialize', original => async function (...args) {
      proxyInitialization.started++
      proxyInitialization.pending++
      try {
        const result = await original.apply(this, args)
        proxyInitialization.completed++
        return result
      } catch (error) {
        proxyInitialization.rejected++
        proxyInitialization.lastError = String(error?.message || error).slice(0, 600)
        throw error
      } finally { proxyInitialization.pending-- }
    })
  }
  const patchMap = instance => {
    nativeMap = toRaw(instance)
    if (patchedMaps.has(nativeMap)) return
    patchedMaps.add(nativeMap)
    for (const method of ['setFitView', 'setCenter', 'setZoom', 'setViewport', 'centerAndZoom', 'fitBounds']) {
      if (typeof nativeMap[method] !== 'function') continue
      patchMethod(nativeMap, method, original => function (...args) { cameraWrites++; return original.apply(this, args) })
    }
    for (const method of ['add', 'addOverlay', 'addOverLay']) {
      if (typeof nativeMap[method] !== 'function') continue
      patchMethod(nativeMap, method, original => function (value, ...args) {
        for (const item of Array.isArray(value) ? value : [value]) overlays.add(item)
        return original.call(this, value, ...args)
      })
    }
    for (const method of ['remove', 'removeOverlay', 'removeOverLay']) {
      if (typeof nativeMap[method] !== 'function') continue
      patchMethod(nativeMap, method, original => function (value, ...args) {
        for (const item of Array.isArray(value) ? value : [value]) overlays.delete(item)
        return original.call(this, value, ...args)
      })
    }
  }
  const stop = watch(() => mapStore.mapInstance, value => { if (value) patchMap(value) }, {flush: 'sync'})
  const component = ref(null)
  const vm = createApp({render: () => h(MapContainer, {ref: component})})
  vm.use(pinia)
  vm.mount('#map-ui')
  const coords = [[116.397128,39.916527],[116.397428,39.916527],[116.397728,39.916527],[116.398128,39.916527],[116.398528,39.916527]]
  const expectedPoint = point => {
    if (provider === 'baidu') return Object.values(gcj02ToBd09(...point))
    if (provider === 'tianditu') {
      const converted = gcj02ToWgs84(...point)
      const native = new window.T.LngLat(converted.lng, converted.lat)
      return [native.getLng(), native.getLat()]
    }
    return point
  }
  const readPoint = point => {
    if (!point) return null
    if (Array.isArray(point)) return point
    return [typeof point.getLng === 'function' ? point.getLng() : point.lng, typeof point.getLat === 'function' ? point.getLat() : point.lat]
  }
  const nativeSnapshot = () => {
    const lines = [], points = []
    const ownedOverlays = component.value?.getAcceptanceOverlays?.() || []
    for (const overlay of new Set([...overlays, ...ownedOverlays])) {
      if (typeof overlay.getGeometries === 'function') {
        if (overlay.getMap?.() === null) continue
        for (const geometry of overlay.getGeometries()) {
          if (geometry.paths) lines.push(geometry.paths.map(readPoint))
          else if (geometry.position) points.push(readPoint(geometry.position))
        }
      } else if (typeof overlay.getPath === 'function') {
        if (overlay.getMap?.() === null) continue
        lines.push(overlay.getPath().map(readPoint))
      } else if (typeof overlay.getLngLats === 'function') {
        if (overlay.getMap?.() === null) continue
        lines.push(overlay.getLngLats().map(readPoint))
      } else if (provider === 'tianditu' && typeof overlay.getLngLat === 'function') points.push(readPoint(overlay.getLngLat()))
      else if (typeof overlay.getPosition === 'function') points.push(readPoint(overlay.getPosition()))
      else if (typeof overlay.getLngLat === 'function') points.push(readPoint(overlay.getLngLat()))
    }
    return {lines, points, center: readPoint(nativeMap.getCenter()), zoom: nativeMap.getZoom(), cameraWrites,
      ownedOverlayCount: ownedOverlays.length, ownedOverlayTypes: ownedOverlays.map(value => value?.constructor?.name || typeof value)}
  }
  window.mapAcceptance = {
    ready: () => !destroyed && mapStore.isMapReady && !!document.querySelector('#map-container')?.clientWidth,
    debugState: () => {
      const container = document.querySelector('#map-container')
      const placeholder = document.querySelector('#map-ui .legacy-map-placeholder')
      const style = placeholder ? getComputedStyle(placeholder) : null
      const instance = mapStore.mapInstance || nativeMap
      return {
        map_ready: !!mapStore.isMapReady,
        active_provider: mapStore.activeProvider,
        map_instance_present: !!mapStore.mapInstance,
        placeholder_visible: !!placeholder && style.display !== 'none' && style.visibility !== 'hidden' && placeholder.getClientRects().length > 0,
        placeholder_text: placeholder?.textContent?.slice(0, 600) || '',
        container_width: container?.clientWidth || 0,
        container_height: container?.clientHeight || 0,
        sdk_t_present: !!window.T,
        native_destroy_type: typeof instance?.destroy,
        native_remove_type: typeof instance?.remove,
        native_clear_overlays_type: typeof instance?.clearOverLays,
        proxy_initialize_started: proxyInitialization.started,
        proxy_initialize_completed: proxyInitialization.completed,
        proxy_initialize_rejected: proxyInitialization.rejected,
        proxy_initialize_pending: proxyInitialization.pending,
        proxy_initialize_last_error: proxyInitialization.lastError,
        destroyed,
      }
    },
    seed: async (taskIndex = 0, pointIndex = 0) => {
      app.selectedTaskIndex = taskIndex
      app.runData = {task_index: taskIndex, run_coords: coords, target_points: [coords[2], coords[4]], target_point_names: '中点|终点', point_index: pointIndex, current_point_index: pointIndex}
      if (pointIndex) Object.assign(app.runData, {current_lon: coords[pointIndex - 1][0], current_lat: coords[pointIndex - 1][1]})
      await nextTick()
      return nativeSnapshot()
    },
    progress: async index => {
      app.runData = {...app.runData, point_index: index, current_point_index: index, current_lon: coords[index - 1][0], current_lat: coords[index - 1][1]}
      await nextTick()
      const snapshot = nativeSnapshot()
      snapshot.expectedRunner = expectedPoint(coords[index - 1])
      snapshot.businessPoint = app.runData.run_coords[index - 1]
      return snapshot
    },
    finish: async () => { app.runData = {...app.runData, status: 1}; await nextTick(); return nativeSnapshot() },
    destroy: async () => {
      if (destroyed) return
      destroyed = true
      stop()
      const whenDisposed = component.value?.whenDisposed
      try { vm.unmount(); await whenDisposed?.() }
      finally {
        for (const restore of restorers.reverse()) restore()
        overlays.clear()
      }
      return {instrumentation_restored: true}
    },
    expectedPoint,
  }
}
`
const virtualId = resolve(root, 'map-ui-acceptance-entry.js')
export function exposeAcceptanceOverlays(code) {
  if (!code.includes('defineExpose({')) throw new Error('map component exposure not found')
  return code.replace('defineExpose({', 'defineExpose({\n  getAcceptanceOverlays: () => [...markers, ...polylines],')
}
const result = await build({
  configFile: false, root, logLevel: 'silent',
  resolve: {alias: {'@': resolve(root, 'src')}},
  plugins: [{name: 'map-ui-native-overlays', enforce: 'pre', transform(code, id) {
    return id.includes('/src/components/map/MapContainer.vue') && (!id.includes('?') || id.includes('type=script'))
      ? exposeAcceptanceOverlays(code) : null
  }}, vue(), {name: 'map-ui-acceptance', resolveId: id => id === virtualId ? '\0' + id : null, load: id => id === '\0' + virtualId ? source : null}],
  build: {write: false, minify: false, cssCodeSplit: false, rolldownOptions: {input: virtualId, output: {format: 'es', entryFileNames: 'map-ui.js', chunkFileNames: 'fixture/[name]-[hash].js'}}},
})
const output = Array.isArray(result) ? result.flatMap(item => item.output) : result.output
process.stdout.write(JSON.stringify({files: Object.fromEntries(output.filter(item => item.type === 'chunk').map(item => [item.fileName, item.code])), css: output.filter(item => item.fileName.endsWith('.css')).map(item => item.source).join('\n')}))
