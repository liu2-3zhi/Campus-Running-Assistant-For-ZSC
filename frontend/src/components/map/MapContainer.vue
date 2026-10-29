<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMapStore } from '@/stores/map'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { gcj02ToBd09, bd09ToGcj02, gcj02ToWgs84, wgs84ToGcj02 } from '@/utils/coordinates'
import { routePoint, ROUTE_COLORS, buildTaskRoutePresentation } from '@/utils/routeProgress'
import MapPlaceholder from './MapPlaceholder.vue'
import MapControls from './MapControls.vue'

const props = defineProps({
  containerId: { type: String, default: 'map-container' },
  isMultiAccount: { type: Boolean, default: false },
})

const mapStore = useMapStore()
const app = useAppStore()
const auth = useAuthStore()
let lastFittedTask = null
let displayedTask = null

const mapReady = ref(false)
const showPlaceholder = ref(false)
const placeholderError = ref('')
const zoomLevel = ref(17)

let map = null
let markers = []
let polylines = []
let taskLines = new Map()
let taskMarkers = new Map()
let zoomHandler = null
let completeHandler = null
let boundProvider = null
let initialization = 0
let disposed = false
let licenseObserver = null
let licenseTimer = null
let mapHost = null
let pendingDestruction = null
let disposing = false
let cancelReadiness = null
let baiduRealm = null
const tencentLabelStates = new WeakMap()
const pendingLabelReleases = new Set()
const hostPrefix = Math.random().toString(36).slice(2, 10)
const DEFAULT_CENTER = [113.390342, 22.527403]
const DEFAULT_ZOOM = 17
const BAIDU_DEFAULT_ZOOM = 18

function nativeMapHost() {
  if (mapHost) return mapHost
  const container = document.getElementById(props.containerId)
  if (!container) throw new Error('地图容器不存在')
  const host = document.createElement('div')
  host.id = `${props.containerId}-sdk-${hostPrefix}-${initialization}`
  host.style.width = '100%'
  host.style.height = '100%'
  container.appendChild(host)
  mapHost = host
  return host
}

function ownsMap(instance, generation) {
  return !disposed && !disposing && generation === initialization && map === instance
}

// --- 交互式绘制状态 ---
let clickHandler = null       // 当前绑定的地图点击回调
let boundClickProvider = null // 记录绑定时的 provider，用于正确解绑
let draftPolyline = null      // 草稿折线实例（独立于普通 overlays 单独管理）

// --- Script loader utility ---
function loadScript(src, id) {
  return new Promise((resolve, reject) => {
    let existing = document.getElementById(id)
    // The request proxy rewrites script.src; retain the requested URL for cache identity.
    if (existing?.src && (existing.dataset?.sourceUrl || existing.src) !== src) { existing.remove(); existing = null }
    if (existing?.dataset?.loaded === 'true') { resolve(); return }
    const script = existing || document.createElement('script')
    const timer = setTimeout(() => finish(new Error('地图 SDK 加载超时')), 20000)
    function finish(error) {
      clearTimeout(timer)
      script.onload = null
      script.onerror = null
      if (error) { script.remove?.(); reject(error) }
      else { if (script.dataset) script.dataset.loaded = 'true'; resolve() }
    }
    script.id = id
    if (script.dataset) script.dataset.sourceUrl = src
    script.src = src
    script.onload = () => finish()
    script.onerror = () => finish(new Error('地图 SDK 脚本加载失败'))
    if (!existing) document.head.appendChild(script)
  })
}

function sdkDeadline(promise) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('地图 SDK 初始化超时')), 20000)
    Promise.resolve(promise).then(resolve, reject).finally(() => clearTimeout(timer))
  })
}

function waitForTencentIdle(instance, generation) {
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = error => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      instance.off('idle', onIdle)
      if (cancelReadiness === cancel) cancelReadiness = null
      if (error) reject(error)
      else resolve()
    }
    const onIdle = () => { if (ownsMap(instance, generation)) finish() }
    const cancel = () => finish(new Error('地图初始化已取消'))
    const timer = setTimeout(() => finish(new Error('腾讯地图初始化超时，请重试')), 5000)
    cancelReadiness = cancel
    instance.on('idle', onIdle)
  })
}

// --- Remove Amap license overlay ---
function removeAmapLicenseOverlay() {
  function tryRemove() {
    const allDivs = document.querySelectorAll('div')
    allDivs.forEach(div => {
      const style = div.style
      if (
        style.position === 'absolute' &&
        (style.zIndex === '9999' || style.zIndex === '99999') &&
        div.textContent && div.textContent.includes('经识别')
      ) {
        div.remove()
      }
    })
  }

  tryRemove()

  const container = document.getElementById(props.containerId)
  if (!container) return

  licenseObserver = new MutationObserver(() => {
    tryRemove()
  })
  licenseObserver.observe(container, { childList: true, subtree: true })

  if (licenseTimer) clearTimeout(licenseTimer)
  licenseTimer = setTimeout(() => {
    if (licenseObserver) {
      licenseObserver.disconnect()
      licenseObserver = null
    }
  }, 10000)
}

// --- Provider initialization ---
async function initAmap() {
  const generation = initialization
  const config = mapStore.mapConfig
  if (!config.amapKey) {
    showPlaceholder.value = true
    return
  }

  try {
    await loadScript('https://webapi.amap.com/loader.js', 'amap-loader')
    if (disposed || generation !== initialization) return

    const security = { ...(window._AMapSecurityConfig || {}) }
    if (config.amapSecurityJsCode) security.securityJsCode = config.amapSecurityJsCode
    else if (window.__appAmapSecurityCode && security.securityJsCode === window.__appAmapSecurityCode) delete security.securityJsCode
    window._AMapSecurityConfig = security
    window.__appAmapSecurityCode = config.amapSecurityJsCode || ''

    const AMapLoader = window.AMapLoader
    if (!AMapLoader) {
      throw new Error('AMapLoader 未加载')
    }
    const signature = `${config.amapKey}:${config.amapSecurityJsCode || ''}`
    if (window.__appAmapSignature && window.__appAmapSignature !== signature) AMapLoader.reset?.()
    window.__appAmapSignature = signature

    const AMap = await sdkDeadline(AMapLoader.load({
      key: config.amapKey,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar'],
    }))

    await nextTick()
    if (disposed || generation !== initialization) return

    const container = nativeMapHost()
    map = new AMap.Map(container, {
      zoom: DEFAULT_ZOOM,
      center: DEFAULT_CENTER,
      resizeEnable: true,
    })

    const instance = map
    completeHandler = () => {
      if (ownsMap(instance, generation)) removeAmapLicenseOverlay()
    }
    map.on('complete', completeHandler)

    zoomHandler = () => {
      if (ownsMap(instance, generation)) zoomLevel.value = Math.round(instance.getZoom())
    }
    map.on('zoomchange', zoomHandler)

    zoomLevel.value = Math.round(map.getZoom())
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    if (disposed || generation !== initialization) return
    console.error('[MapContainer] 高德地图加载失败:', e)
    placeholderError.value = e.message || '高德地图加载失败'
    showPlaceholder.value = true
  }
}

async function initTencent() {
  const generation = initialization
  const config = mapStore.mapConfig
  if (!config.tencentKey) {
    showPlaceholder.value = true
    return
  }

  try {
    await loadScript(
      `https://map.qq.com/api/gljs?v=1.exp&key=${config.tencentKey}`,
      'tencent-map-sdk'
    )

    await nextTick()
    if (disposed || generation !== initialization) return

    const TMap = window.TMap
    if (!TMap) {
      throw new Error('腾讯地图 SDK 未加载')
    }

    const container = nativeMapHost()

    map = new TMap.Map(container, {
      center: new TMap.LatLng(DEFAULT_CENTER[1], DEFAULT_CENTER[0]),
      zoom: DEFAULT_ZOOM,
    })

    const instance = map
    zoomHandler = () => {
      if (ownsMap(instance, generation)) zoomLevel.value = Math.round(instance.getZoom())
    }
    map.on('zoom', zoomHandler)

    await waitForTencentIdle(instance, generation)
    if (!ownsMap(instance, generation)) return
    zoomLevel.value = Math.round(instance.getZoom())
    mapStore.setMapInstance(instance)
    mapReady.value = true
  } catch (e) {
    if (disposed || generation !== initialization) return
    try { await destroyMap() } catch (_) {}
    if (disposed || generation !== initialization) return
    console.error('[MapContainer] 腾讯地图加载失败:', e)
    placeholderError.value = e.message || '腾讯地图加载失败'
    showPlaceholder.value = true
  }
}

async function initTianditu() {
  const generation = initialization
  const config = mapStore.mapConfig
  if (!config.tiandituKey) {
    showPlaceholder.value = true
    return
  }

  try {
    await loadScript(
      `https://api.tianditu.gov.cn/api?v=4.0&tk=${config.tiandituKey}`,
      'tianditu-map-sdk'
    )

    await nextTick()
    if (disposed || generation !== initialization) return

    const T = window.T
    if (!T) {
      throw new Error('天地图 SDK 未加载')
    }

    const container = nativeMapHost()
    map = new T.Map(container.id)
    map.centerAndZoom(
      new T.LngLat(...providerPoint(DEFAULT_CENTER)),
      DEFAULT_ZOOM,
    )

    const instance = map
    zoomHandler = () => {
      if (ownsMap(instance, generation)) zoomLevel.value = instance.getZoom()
    }
    map.addEventListener('zoomend', zoomHandler)

    zoomLevel.value = map.getZoom()
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    if (disposed || generation !== initialization) return
    console.error('[MapContainer] 天地图加载失败:', e)
    placeholderError.value = e.message || '天地图加载失败'
    showPlaceholder.value = true
  }
}

async function initBaidu() {
  const generation = initialization
  const config = mapStore.mapConfig
  if (!config.baiduKey) {
    showPlaceholder.value = true
    return
  }

  let realm
  try {
    await nextTick()
    if (disposed || generation !== initialization) return
    if (!window.ZXMapRequestProxy?.createBaiduMapFrame) throw new Error('百度地图隔离运行时未加载')
    realm = window.ZXMapRequestProxy.createBaiduMapFrame({ host: nativeMapHost(), key: config.baiduKey })
    baiduRealm = realm
    await realm.ready
    if (disposed || generation !== initialization || baiduRealm !== realm) { realm.dispose(); return }
    const BMap = realm.sdk
    map = new BMap.Map(realm.container)
    map.__baiduRealm = realm
    map.centerAndZoom(
      new BMap.Point(...providerPoint(DEFAULT_CENTER)),
      BAIDU_DEFAULT_ZOOM,
    )
    map.enableScrollWheelZoom(true)
    if (BMap.NavigationControl3D) map.addControl(new BMap.NavigationControl3D())

    const instance = map
    zoomHandler = () => {
      if (ownsMap(instance, generation)) zoomLevel.value = instance.getZoom()
    }
    map.addEventListener('zoomend', zoomHandler)

    zoomLevel.value = map.getZoom()
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    realm?.dispose()
    if (disposed || generation !== initialization) return
    await destroyMap()
    console.error('[MapContainer] 百度地图加载失败:', e)
    placeholderError.value = e.message || '百度地图加载失败'
    showPlaceholder.value = true
  }
}

// --- Map initialization dispatcher ---
async function initMap() {
  const generation = ++initialization
  mapReady.value = false
  showPlaceholder.value = false
  placeholderError.value = ''
  try {
    await destroyMap()
  } catch (error) {
    if (!disposed && generation === initialization) {
      placeholderError.value = error.message || '地图释放失败，请重试'
      showPlaceholder.value = true
    }
    return
  }
  if (disposed || generation !== initialization) return
  disposing = false

  const provider = mapStore.activeProvider
  boundProvider = provider
  const proxy = window.ZXMapRequestProxy
  if (proxy) {
    try {
      await proxy.initialize({
        map_config_id: mapStore.mapConfig.frontendConfigId,
        enabled: mapStore.mapConfig.frontendProxyEnabled === true,
        provider,
        sessionId: auth.getSessionHeaderValue?.('get_initial_data') || auth.sessionUUID || '',
        originSessionId: auth.getAdminOriginHeaderValue?.(auth.sessionUUID || '') || '',
      })
    } catch (error) {
      if (!disposed && generation === initialization) {
        placeholderError.value = error?.message || '地图代理初始化失败'
        showPlaceholder.value = true
      }
      return
    }
  } else if (mapStore.mapConfig.frontendProxyEnabled === true) {
    placeholderError.value = '地图代理脚本未加载'
    showPlaceholder.value = true
    return
  }
  if (disposed || generation !== initialization) return
  switch (provider) {
    case 'amap':
      await initAmap()
      break
    case 'tencent':
      await initTencent()
      break
    case 'tianditu':
      await initTianditu()
      break
    case 'baidu':
      await initBaidu()
      break
    default:
      showPlaceholder.value = true
      placeholderError.value = `不支持的地图提供商: ${provider}`
  }
  if (!disposed && generation === initialization && mapReady.value && mapStore.isDrawing) bindDrawingClick()
}

function destroyMap() {
  cancelReadiness?.()
  if (!map) {
    baiduRealm?.dispose()
    baiduRealm = null
    mapHost?.remove()
    mapHost = null
    return pendingDestruction || Promise.resolve()
  }
  disposing = true
  mapReady.value = false
  const instance = map
  const provider = boundProvider || mapStore.activeProvider
  const host = mapHost
  const realm = baiduRealm
  baiduRealm = null
  unbindDrawingClick()
  if (map && zoomHandler) {
    try {
      if (boundProvider === 'amap' || boundProvider === 'tencent') map.off(boundProvider === 'amap' ? 'zoomchange' : 'zoom', zoomHandler)
      else map.removeEventListener('zoomend', zoomHandler)
    } catch (_) {}
  }
  zoomHandler = null
  if (map && completeHandler) { try { map.off('complete', completeHandler) } catch (_) {} }
  completeHandler = null
  if (licenseObserver) { licenseObserver.disconnect(); licenseObserver = null }
  if (licenseTimer) { clearTimeout(licenseTimer); licenseTimer = null }
  clearOverlays()
  // 重置绘制相关引用（地图即将销毁，旧句柄无需再解绑，直接置空以防悬挂）
  clickHandler = null
  boundClickProvider = null
  draftPolyline = null
  setDrawingCursor(false)
  map = null
  mapHost = null
  if (mapStore.mapInstance === instance) mapStore.setMapInstance(null)
  lastFittedTask = null
  displayedTask = null
  let released = false
  let promise
  const releaseNative = () => new Promise((resolve, reject) => {
    let settled = false
    let timer
    const finish = error => {
      if (released) return
      clearTimeout(timer)
      if (error) {
        if (!settled) { settled = true; reject(error) }
        // Keep the host and destroyed listener: a timeout is not a release.
        return
      }
      released = true
      if (provider === 'tencent') instance.off?.('destroyed', onDestroyed)
      host?.remove()
      if (pendingDestruction === promise) pendingDestruction = null
      if (!settled) { settled = true; resolve() }
    }
    const onDestroyed = () => finish()
    const waitForDestroyed = provider === 'tencent' && typeof instance.destroy === 'function' && typeof instance.on === 'function'
    if (waitForDestroyed) {
      instance.on('destroyed', onDestroyed)
      timer = setTimeout(() => finish(new Error('地图释放超时，请重试')), 5000)
    }
    try {
      if (provider === 'tianditu') instance.clearOverLays?.()
      if (realm) realm.dispose()
      else instance.destroy?.()
      if (!waitForDestroyed) finish()
    } catch (error) { finish(error) }
  })
  const labels = [...pendingLabelReleases]
  if (labels.length) {
    // Report the deadline without cancelling the late SDK cleanup.
    const releasing = Promise.all(labels).then(releaseNative)
    promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('腾讯地图文字图层释放超时，请重试')), 5000)
      releasing.then(value => { clearTimeout(timer); resolve(value) }, error => { clearTimeout(timer); reject(error) })
    })
  } else promise = releaseNative()
  pendingDestruction = promise
  promise.then(() => { if (pendingDestruction === promise) pendingDestruction = null }, () => {})
  return promise
}

// --- Public methods ---
function fitView(coords) {
  if (!map || !coords || coords.length === 0) return
  coords = coords.map(providerPoint).filter(Boolean)
  if (!coords.length) return

  const provider = boundProvider || mapStore.activeProvider
  if (provider === 'amap') {
    map.setFitView()
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (!TMap) return
    const bounds = new TMap.LatLngBounds()
    coords.forEach(c => {
      bounds.extend(new TMap.LatLng(c[1], c[0]))
    })
    map.fitBounds(bounds, { ease: { duration: 0 } })
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return
    map.setViewport(coords.map(c => new T.LngLat(c[0], c[1])))
  } else if (provider === 'baidu') {
    const BMap = map.__baiduRealm?.sdk
    if (!BMap) return
    const points = coords.map(c => new BMap.Point(c[0], c[1]))
    map.setViewport(points, { enableAnimation: false })
  }
}

function addMarker(pos, opts = {}) {
  if (!map || !pos) return null
  pos = providerPoint(pos)
  if (!pos) return null

  const provider = boundProvider || mapStore.activeProvider
  let marker = null

  if (provider === 'amap') {
    const AMap = window.AMap
    if (!AMap) return null
    marker = new AMap.Marker({
      position: new AMap.LngLat(pos[0], pos[1]),
      title: opts.title || '',
      ...opts,
    })
    if (opts.title && typeof marker.setLabel === 'function') {
      const label = document.createElement('span')
      label.textContent = opts.title
      if (label.style && opts.color) { label.style.backgroundColor = opts.color; label.style.color = '#fff' }
      marker.__labelElement = label
      marker.setLabel({ content: label, direction: 'top' })
    }
    map.add(marker)
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (!TMap) return null
    const geometryId = opts.id || `marker_${Date.now()}`
    const labelGeometryId = `${geometryId}-name`
    marker = new TMap.MultiMarker({
      map,
      geometries: [{
        position: new TMap.LatLng(pos[1], pos[0]),
        id: geometryId,
      }],
    })
    marker.__geometryId = geometryId
    marker.__labelGeometryId = labelGeometryId
    if (opts.title && TMap.MultiLabel && TMap.LabelStyle) {
      marker.__label = new TMap.MultiLabel({
        map,
        styles: { name: new TMap.LabelStyle({ color: '#ffffff', backgroundColor: opts.color || '#059669', padding: '4px 8px', borderRadius: 12, offset: { x: 0, y: -35 } }) },
        geometries: [{ id: labelGeometryId, styleId: 'name', position: new TMap.LatLng(pos[1], pos[0]), content: opts.title }],
      })
      trackTencentLabel(marker.__label)
      markers.push(marker.__label)
    }
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return null
    marker = new T.Marker(new T.LngLat(pos[0], pos[1]), { title: opts.title || '' })
    map.addOverLay(marker)
    if (opts.title) {
      if (T.Label) {
        const label = new T.Label({ text: opts.title, position: new T.LngLat(pos[0], pos[1]) })
        label.setBackgroundColor?.(opts.color || '#10b981')
        map.addOverLay(label)
        marker.__label = label
        markers.push(label)
      }
    }
  } else if (provider === 'baidu') {
    const BMap = map.__baiduRealm?.sdk
    if (!BMap) return null
    marker = new BMap.Marker(new BMap.Point(pos[0], pos[1]))
    map.addOverlay(marker)
    if (opts.title) {
      marker.setTitle(opts.title)
      if (BMap.Label) {
        const label = document.createElement('span')
        label.textContent = opts.title
        marker.setLabel(new BMap.Label(label.outerHTML))
        marker.getLabel?.()?.setStyle?.({ backgroundColor: opts.color || '#10b981', color: '#fff', borderColor: opts.color || '#10b981' })
      }
    }
  }

  if (marker) markers.push(marker)
  return marker
}

function drawPolyline(path, opts = {}) {
  if (!map || !path || path.length < 2) return null
  path = path.map(providerPoint).filter(Boolean)
  if (path.length < 2) return null

  const provider = mapStore.activeProvider
  let polyline = null
  const color = opts.color || '#2563eb'
  const weight = opts.weight || 4

  if (provider === 'amap') {
    const AMap = window.AMap
    if (!AMap) return null
    polyline = new AMap.Polyline({
      path: path.map(p => new AMap.LngLat(p[0], p[1])),
      strokeColor: color,
      strokeWeight: weight,
      strokeOpacity: opts.opacity || 0.8,
      ...opts,
    })
    map.add(polyline)
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (!TMap) return null
    const geometryId = opts.id || `polyline_${Date.now()}_${polylines.length}`
    polyline = new TMap.MultiPolyline({
      map,
      styles: {
        style: new TMap.PolylineStyle({
          color,
          width: weight,
        }),
      },
      geometries: [{
        id: geometryId,
        styleId: 'style',
        paths: path.map(p => new TMap.LatLng(p[1], p[0])),
      }],
    })
    polyline.__geometryId = geometryId
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return null
    polyline = new T.Polyline(
      path.map(p => new T.LngLat(p[0], p[1])),
      { color, weight, opacity: opts.opacity || 0.8 }
    )
    map.addOverLay(polyline)
  } else if (provider === 'baidu') {
    const BMap = map.__baiduRealm?.sdk
    if (!BMap) return null
    polyline = new BMap.Polyline(
      path.map(p => new BMap.Point(p[0], p[1])),
      { strokeColor: color, strokeWeight: weight, strokeOpacity: opts.opacity || 0.8 }
    )
    map.addOverlay(polyline)
  }

  if (polyline) polylines.push(polyline)
  return polyline
}

function clearOverlays() {
  const provider = boundProvider || mapStore.activeProvider

  if (provider === 'amap' && map) {
    markers.forEach(m => { try { map.remove(m) } catch (_) {} })
    polylines.forEach(p => { try { map.remove(p) } catch (_) {} })
  } else if (provider === 'tencent') {
    markers.forEach(releaseTencentOverlay)
    polylines.forEach(releaseTencentOverlay)
  } else if (provider === 'tianditu' && map) {
    markers.forEach(m => { try { map.removeOverLay(m) } catch (_) {} })
    polylines.forEach(p => { try { map.removeOverLay(p) } catch (_) {} })
  } else if (provider === 'baidu' && map) {
    markers.forEach(m => { try { map.removeOverlay(m) } catch (_) {} })
    polylines.forEach(p => { try { map.removeOverlay(p) } catch (_) {} })
  }

  markers = []
  polylines = []
  taskLines.clear()
  taskMarkers.clear()
}

// Task coordinates are GCJ-02; conversion only affects the map display.
function providerPoint(point) {
  const normalized = routePoint(point)
  if (!normalized) return null
  const [lng, lat] = normalized
  if (mapStore.activeProvider === 'baidu') {
    const converted = gcj02ToBd09(lng, lat)
    return [converted.lng, converted.lat]
  }
  if (mapStore.activeProvider === 'tianditu') {
    const converted = gcj02ToWgs84(lng, lat)
    return [converted.lng, converted.lat]
  }
  return [lng, lat]
}

function taskCoordinates(data) {
  if (!data) return []
  return [...(data.run_coords || []), ...(data.target_points || []), ...(data.draft_coords || []), ...(data.recommended_coords || [])].map(routePoint).filter(Boolean)
}

function drawTaskSegments(coords, options) {
  let segment = []
  for (const point of coords || []) {
    const converted = routePoint(point)
    if (converted) segment.push(converted)
    else {
      drawPolyline(segment, options)
      segment = []
    }
  }
  drawPolyline(segment, options)
}

function renderTask() {
  if (!mapReady.value || !map || props.isMultiAccount) return
  const data = app.runData
  if (!data) { clearOverlays(); lastFittedTask = null; displayedTask = null; return }
  const taskKey = data.task_index ?? app.selectedTaskIndex
  if (displayedTask !== taskKey) { clearOverlays(); displayedTask = taskKey }
  const presentation = buildTaskRoutePresentation(data)
  const lineSpecs = [...presentation.segments.map(segment => ({ ...segment, color: ROUTE_COLORS[segment.role] }))]
  for (const [kind, color] of [['recommended', '#10b981'], ['draft', '#1f2937']]) {
    let coords = []
    let part = 0
    const flush = () => { if (coords.length > 1) lineSpecs.push({ id: `${kind}-${part++}`, coords, color }); coords = [] }
    for (const point of data[`${kind}_coords`] || []) {
      const normalized = routePoint(point)
      if (normalized) coords.push(normalized)
      else flush()
    }
    flush()
  }
  syncTaskOverlays(taskLines, lineSpecs, spec => drawPolyline(spec.coords, { id: spec.id, color: spec.color, weight: 6 }), (overlay, spec) => updatePolyline(overlay, spec.coords, spec.color, spec.id))
  const markerSpecs = presentation.checkpoints.map(spec => ({ ...spec, color: spec.role === 'remaining' ? '#10b981' : ROUTE_COLORS[spec.role] }))
  if (presentation.runner) markerSpecs.push({ id: 'runner', coords: presentation.runner, title: '当前位置', color: '#2563eb' })
  syncTaskOverlays(taskMarkers, markerSpecs, spec => addMarker(spec.coords, { id: spec.id, title: spec.title, color: spec.color }), (overlay, spec) => updateMarker(overlay, spec.coords, spec))
  const coords = taskCoordinates(data)
  if (lastFittedTask !== taskKey && coords.length) {
    fitView(coords)
    lastFittedTask = taskKey
  }
  if (mapStore.isDrawing) redrawDraft()
}

function syncTaskOverlays(collection, specs, create, update) {
  const wanted = new Set(specs.map(spec => spec.id))
  for (const [id, overlay] of collection) {
    if (!wanted.has(id)) { removeSingleOverlay(overlay); collection.delete(id) }
  }
  for (const spec of specs) {
    const overlay = collection.get(spec.id)
    if (overlay) update(overlay, spec)
    else {
      const created = create(spec)
      if (created) collection.set(spec.id, created)
    }
  }
}

function updateMarker(marker, point, opts = {}) {
  const pos = providerPoint(point)
  if (!marker || !pos) return
  const provider = mapStore.activeProvider
  if (provider === 'amap') marker.setPosition?.(new window.AMap.LngLat(...pos))
  else if (provider === 'tencent') {
    const geometryId = opts.id || marker.__geometryId || 'position'
    const geometry = { id: geometryId, position: new window.TMap.LatLng(pos[1], pos[0]) }
    marker.setGeometries?.([geometry])
    const state = tencentLabelStates.get(marker.__label)
    if (state) state.pending = true
    marker.__label?.setGeometries?.([{ ...geometry, id: opts.id ? `${opts.id}-name` : marker.__labelGeometryId || `${geometryId}-name`, styleId: 'name', content: opts.title || '' }])
  } else if (provider === 'tianditu') {
    marker.setLngLat?.(new window.T.LngLat(...pos))
    marker.__label?.setLngLat?.(new window.T.LngLat(...pos))
  } else if (provider === 'baidu') marker.setPosition?.(new map.__baiduRealm.sdk.Point(...pos))
  const label = marker.getLabel?.() || marker.__label
  label?.setStyle?.({ backgroundColor: opts.color, color: '#fff', borderColor: opts.color })
  label?.setBackgroundColor?.(opts.color)
  if (marker.__labelElement?.style) marker.__labelElement.style.backgroundColor = opts.color
  if (provider === 'tencent' && marker.__label && window.TMap.LabelStyle) marker.__label.setStyles?.({ name: new window.TMap.LabelStyle({ color: '#fff', backgroundColor: opts.color || '#059669', offset: { x: 0, y: -35 } }) })
}

function updatePolyline(polyline, path, color, id) {
  const coords = path.map(providerPoint).filter(Boolean)
  const provider = mapStore.activeProvider
  if (provider === 'amap') { polyline.setPath?.(coords); polyline.setOptions?.({ strokeColor: color }) }
  else if (provider === 'tencent') polyline.setGeometries?.([{ id: id || polyline.__geometryId || 'route', styleId: 'style', paths: coords.map(p => new window.TMap.LatLng(p[1], p[0])) }])
  else if (provider === 'tianditu') { polyline.setLngLats?.(coords.map(p => new window.T.LngLat(...p))); polyline.setColor?.(color) }
  else if (provider === 'baidu') { polyline.setPath?.(coords.map(p => new map.__baiduRealm.sdk.Point(...p))); polyline.setStrokeColor?.(color) }
}

watch([() => app.runData, () => mapReady.value], renderTask, { deep: true })

// --- Interactive path drawing ---
// 从各 provider 的点击事件对象中提取 { lng, lat }。
// amap 已按任务要求完整实现（e.lnglat.getLng/getLat）；其余 provider 依据各自 SDK
// 常见事件结构尽力实现，未经运行时验证，详见报告。
function extractClickLngLat(provider, e) {
  try {
    if (provider === 'amap') {
      const ll = e && e.lnglat
      if (!ll) return null
      return {
        lng: typeof ll.getLng === 'function' ? ll.getLng() : ll.lng,
        lat: typeof ll.getLat === 'function' ? ll.getLat() : ll.lat,
      }
    } else if (provider === 'tencent') {
      // 腾讯 gljs：点击事件坐标位于 e.latLng（TMap.LatLng，含 getLng/getLat）
      const ll = e && (e.latLng || e.latlng)
      if (!ll) return null
      return {
        lng: typeof ll.getLng === 'function' ? ll.getLng() : ll.lng,
        lat: typeof ll.getLat === 'function' ? ll.getLat() : ll.lat,
      }
    } else if (provider === 'tianditu') {
      // 天地图：click 事件坐标位于 e.lnglat（T.LngLat，含 getLng/getLat）
      const ll = e && e.lnglat
      if (!ll) return null
      return {
        lng: typeof ll.getLng === 'function' ? ll.getLng() : ll.lng,
        lat: typeof ll.getLat === 'function' ? ll.getLat() : ll.lat,
      }
    } else if (provider === 'baidu') {
      // JS API v4 uses latLng; point also supports older event wrappers.
      const p = e && (e.latLng || e.point)
      if (!p) return null
      return { lng: p.lng, lat: p.lat }
    }
  } catch (_) {}
  return null
}

// 移除单个 overlay（草稿折线），并从 polylines 跟踪数组中剔除，避免累积。
function trackTencentLabel(label) {
  if (typeof label.on !== 'function') return
  const state = { pending: true, release: null, finish: null }
  const processed = () => {
    state.pending = false
    state.finish?.()
  }
  label.on('geometry_processed', processed)
  state.processed = processed
  tencentLabelStates.set(label, state)
}

function releaseTencentLabel(label, state) {
  if (state.release) return
  // A pending glyph atlas still belongs to the map, even after a task switch.
  label.setVisible?.(false)
  let finish
  const release = new Promise((resolve, reject) => {
    finish = () => {
      label.off('geometry_processed', state.processed)
      state.finish = null
      try { label.destroy(); resolve() } catch (error) { reject(error) }
    }
    state.finish = finish
  })
  state.release = release
  pendingLabelReleases.add(release)
  release.then(() => pendingLabelReleases.delete(release), () => {})
  if (!state.pending) finish()
}

function releaseTencentOverlay(overlay) {
  const label = tencentLabelStates.get(overlay)
  if (label) { releaseTencentLabel(overlay, label); return }
  if (overlay instanceof window.TMap.MultiMarker) { overlay.stopMove?.(); overlay.setMap(null) }
  else if (typeof overlay.destroy === 'function') overlay.destroy()
  else overlay.setMap(null)
}

function removeSingleOverlay(overlay) {
  if (!overlay) return
  const provider = boundProvider || mapStore.activeProvider
  try {
    if (provider === 'amap' && map) map.remove(overlay)
    else if (provider === 'tencent') releaseTencentOverlay(overlay)
    else if (provider === 'tianditu' && map) map.removeOverLay(overlay)
    else if (provider === 'baidu' && map) map.removeOverlay(overlay)
  } catch (_) {}
  const idx = polylines.indexOf(overlay)
  if (idx !== -1) polylines.splice(idx, 1)
  const markerIndex = markers.indexOf(overlay)
  if (markerIndex !== -1) markers.splice(markerIndex, 1)
  if (overlay.__label) removeSingleOverlay(overlay.__label)
}

// 用已有的 drawPolyline 重绘草稿折线：先清掉旧草稿，再按当前草稿点重画。
function redrawDraft() {
  removeSingleOverlay(draftPolyline)
  draftPolyline = null
  const pts = mapStore.draftPoints
  if (pts && pts.length >= 2) {
    draftPolyline = drawPolyline(
      pts.map(p => [p.lng, p.lat]),
      { color: '#1f2937', weight: 6, opacity: 0.9 }
    )
  }
}

function setDrawingCursor(on) {
  const container = document.getElementById(props.containerId)
  if (container) container.style.cursor = on ? 'crosshair' : ''
}

function bindDrawingClick() {
  if (!map || disposing || disposed || clickHandler) return
  const provider = boundProvider || mapStore.activeProvider
  const instance = map
  const generation = initialization
  clickHandler = (e) => {
    if (!ownsMap(instance, generation)) return
    let pt = extractClickLngLat(provider, e)
    if (!pt || pt.lng == null || pt.lat == null) return
    if (provider === 'baidu') pt = bd09ToGcj02(pt.lng, pt.lat)
    else if (provider === 'tianditu') pt = wgs84ToGcj02(pt.lng, pt.lat)
    mapStore.addDraftPoint({ lng: pt.lng, lat: pt.lat })
    redrawDraft()
  }
  boundClickProvider = provider
  if (provider === 'amap' || provider === 'tencent') {
    map.on('click', clickHandler)
  } else if (provider === 'tianditu' || provider === 'baidu') {
    map.addEventListener('click', clickHandler)
  }
  setDrawingCursor(true)
}

function unbindDrawingClick() {
  if (map && clickHandler && boundClickProvider) {
    try {
      if (boundClickProvider === 'amap' || boundClickProvider === 'tencent') {
        map.off('click', clickHandler)
      } else if (boundClickProvider === 'tianditu' || boundClickProvider === 'baidu') {
        map.removeEventListener('click', clickHandler)
      }
    } catch (_) {}
  }
  clickHandler = null
  boundClickProvider = null
  setDrawingCursor(false)
  removeSingleOverlay(draftPolyline)
  draftPolyline = null
}

// --- Zoom controls ---
function handleZoomIn() {
  if (!map) return
  const provider = mapStore.activeProvider
  if (provider === 'amap' || provider === 'tencent') {
    map.setZoom(map.getZoom() + 1)
    zoomLevel.value = Math.round(map.getZoom())
  } else if (provider === 'tianditu') {
    map.zoomIn()
  } else if (provider === 'baidu') {
    map.zoomIn()
  }
}

function handleZoomOut() {
  if (!map) return
  const provider = mapStore.activeProvider
  if (provider === 'amap' || provider === 'tencent') {
    map.setZoom(map.getZoom() - 1)
    zoomLevel.value = Math.round(map.getZoom())
  } else if (provider === 'tianditu') {
    map.zoomOut()
  } else if (provider === 'baidu') {
    map.zoomOut()
  }
}

function handleResetView() {
  if (!map) return
  const coords = taskCoordinates(app.runData)
  if (coords.length) {
    fitView(coords)
    return
  }
  const provider = mapStore.activeProvider
  if (provider === 'amap') {
    map.setZoomAndCenter(DEFAULT_ZOOM, DEFAULT_CENTER)
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (TMap) {
      map.setCenter(new TMap.LatLng(DEFAULT_CENTER[1], DEFAULT_CENTER[0]))
      map.setZoom(DEFAULT_ZOOM)
    }
  } else if (provider === 'tianditu') {
    const T = window.T
    if (T) {
      map.centerAndZoom(
        new T.LngLat(...providerPoint(DEFAULT_CENTER)),
        DEFAULT_ZOOM,
      )
    }
  } else if (provider === 'baidu') {
    const BMap = map.__baiduRealm?.sdk
    if (BMap) {
      map.centerAndZoom(
        new BMap.Point(...providerPoint(DEFAULT_CENTER)),
        BAIDU_DEFAULT_ZOOM,
      )
    }
  }
  zoomLevel.value = provider === 'baidu' ? BAIDU_DEFAULT_ZOOM : DEFAULT_ZOOM
}

// --- Watch provider changes ---
watch([
  () => mapStore.activeProvider,
  () => mapStore.getKeyRequirement().value,
  () => mapStore.mapConfig.amapSecurityJsCode,
  () => mapStore.mapConfig.frontendProxyEnabled,
  () => mapStore.mapConfig.frontendConfigId,
  () => auth.sessionUUID,
  () => auth.adminOriginSession,
], async () => {
  await initMap()
  // 切换 provider 后若仍处于录制模式，为新地图实例重新绑定绘制点击
  if (mapStore.isDrawing) bindDrawingClick()
})

// --- Watch drawing mode ---
// isDrawing 为 true：给当前地图绑定点击事件收集草稿点并重绘草稿折线；
// 为 false：解绑点击、清除草稿折线并恢复光标。
watch(() => mapStore.isDrawing, (drawing) => {
  if (drawing) bindDrawingClick()
  else unbindDrawingClick()
})

// --- Lifecycle ---
onMounted(() => {
  initMap()
})

onBeforeUnmount(() => {
  disposed = true
  initialization++
  if (licenseObserver) {
    licenseObserver.disconnect()
    licenseObserver = null
  }
  destroyMap().catch(error => console.error('[MapContainer] 地图释放失败:', error))
})

// --- Expose public API ---
defineExpose({
  whenDisposed: () => pendingDestruction || Promise.resolve(),
  fitView,
  zoomIn: handleZoomIn,
  zoomOut: handleZoomOut,
  resetView: handleResetView,
  addMarker,
  updateMarker,
  removeOverlay: removeSingleOverlay,
  drawPolyline,
  clearOverlays,
})
</script>

<template>
  <div class="relative h-full w-full overflow-hidden rounded-xl">
    <!-- Actual map container -->
    <div
      :id="containerId"
      class="map-container h-full w-full"
      :class="{ 'min-h-[300px]': !isMultiAccount, 'min-h-[200px]': isMultiAccount }"
      :style="{ visibility: mapReady ? 'visible' : 'hidden' }"
    ></div>

    <!-- Zoom controls overlay -->
    <MapControls
      :zoom-level="zoomLevel"
      @zoom-in="handleZoomIn"
      @zoom-out="handleZoomOut"
      @reset-view="handleResetView"
    />

    <!-- Placeholder when map is not ready -->
    <MapPlaceholder
      v-if="showPlaceholder"
      class="legacy-map-placeholder"
      :provider-name="mapStore.displayName"
      :has-key="!!mapStore.getKeyRequirement().value"
      :error-reason="placeholderError"
      @retry="initMap"
    />
  </div>
</template>

<style scoped>
.legacy-map-placeholder {
  background: #e2e8f0;
}
</style>
