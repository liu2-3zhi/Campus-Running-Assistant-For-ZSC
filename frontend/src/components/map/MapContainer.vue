<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useMapStore } from '@/stores/map'
import MapPlaceholder from './MapPlaceholder.vue'
import MapControls from './MapControls.vue'

const props = defineProps({
  containerId: { type: String, default: 'map-container' },
  isMultiAccount: { type: Boolean, default: false },
})

const mapStore = useMapStore()

const mapReady = ref(false)
const showPlaceholder = ref(false)
const placeholderError = ref('')
const zoomLevel = ref(13)

let map = null
let markers = []
let polylines = []
let licenseObserver = null

// --- Script loader utility ---
function loadScript(src, id) {
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.id = id
    script.src = src
    script.onload = resolve
    script.onerror = () => reject(new Error(`加载脚本失败: ${src}`))
    document.head.appendChild(script)
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

  setTimeout(() => {
    if (licenseObserver) {
      licenseObserver.disconnect()
      licenseObserver = null
    }
  }, 10000)
}

// --- Provider initialization ---
async function initAmap() {
  const config = mapStore.mapConfig
  if (!config.amapKey) {
    showPlaceholder.value = true
    return
  }

  try {
    await loadScript('https://webapi.amap.com/loader.js', 'amap-loader')

    if (config.amapSecurityKey) {
      window._AMapSecurityConfig = {
        securityJsCode: config.amapSecurityKey,
      }
    }

    const AMapLoader = window.AMapLoader
    if (!AMapLoader) {
      throw new Error('AMapLoader 未加载')
    }

    const AMap = await AMapLoader.load({
      key: config.amapKey,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar'],
    })

    await nextTick()

    const container = document.getElementById(props.containerId)
    if (!container) {
      throw new Error('地图容器不存在')
    }

    map = new AMap.Map(props.containerId, {
      zoom: 13,
      center: [116.397428, 39.90923],
      resizeEnable: true,
    })

    map.on('complete', () => {
      removeAmapLicenseOverlay()
    })

    map.on('zoomchange', () => {
      zoomLevel.value = Math.round(map.getZoom())
    })

    zoomLevel.value = Math.round(map.getZoom())
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    console.error('[MapContainer] 高德地图加载失败:', e)
    placeholderError.value = e.message || '高德地图加载失败'
    showPlaceholder.value = true
  }
}

async function initTencent() {
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

    const TMap = window.TMap
    if (!TMap) {
      throw new Error('腾讯地图 SDK 未加载')
    }

    const container = document.getElementById(props.containerId)
    if (!container) {
      throw new Error('地图容器不存在')
    }

    map = new TMap.Map(container, {
      center: new TMap.LatLng(39.90923, 116.397428),
      zoom: 13,
    })

    map.on('zoom_changed', () => {
      zoomLevel.value = Math.round(map.getZoom())
    })

    zoomLevel.value = Math.round(map.getZoom())
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    console.error('[MapContainer] 腾讯地图加载失败:', e)
    placeholderError.value = e.message || '腾讯地图加载失败'
    showPlaceholder.value = true
  }
}

async function initTianditu() {
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

    const T = window.T
    if (!T) {
      throw new Error('天地图 SDK 未加载')
    }

    const container = document.getElementById(props.containerId)
    if (!container) {
      throw new Error('地图容器不存在')
    }

    map = new T.Map(props.containerId)
    map.centerAndZoom(new T.LngLat(116.397428, 39.90923), 13)

    map.addEventListener('zoomend', () => {
      zoomLevel.value = map.getZoom()
    })

    zoomLevel.value = map.getZoom()
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    console.error('[MapContainer] 天地图加载失败:', e)
    placeholderError.value = e.message || '天地图加载失败'
    showPlaceholder.value = true
  }
}

async function initBaidu() {
  const config = mapStore.mapConfig
  if (!config.baiduKey) {
    showPlaceholder.value = true
    return
  }

  try {
    // Baidu map requires a callback
    await new Promise((resolve, reject) => {
      if (window.BMap || window.BMapGL) {
        resolve()
        return
      }
      window.__baiduMapCallback = () => {
        resolve()
        delete window.__baiduMapCallback
      }
      loadScript(
        `https://api.map.baidu.com/api?v=3.0&ak=${config.baiduKey}&callback=__baiduMapCallback`,
        'baidu-map-sdk'
      ).catch(reject)
    })

    await nextTick()

    const BMap = window.BMap || window.BMapGL
    if (!BMap) {
      throw new Error('百度地图 SDK 未加载')
    }

    const container = document.getElementById(props.containerId)
    if (!container) {
      throw new Error('地图容器不存在')
    }

    map = new BMap.Map(props.containerId)
    map.centerAndZoom(new BMap.Point(116.397428, 39.90923), 13)
    map.enableScrollWheelZoom(true)

    map.addEventListener('zoomend', () => {
      zoomLevel.value = map.getZoom()
    })

    zoomLevel.value = map.getZoom()
    mapStore.setMapInstance(map)
    mapReady.value = true
  } catch (e) {
    console.error('[MapContainer] 百度地图加载失败:', e)
    placeholderError.value = e.message || '百度地图加载失败'
    showPlaceholder.value = true
  }
}

// --- Map initialization dispatcher ---
async function initMap() {
  mapReady.value = false
  showPlaceholder.value = false
  placeholderError.value = ''
  destroyMap()

  const provider = mapStore.activeProvider
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
}

function destroyMap() {
  clearOverlays()
  if (map) {
    try {
      if (typeof map.destroy === 'function') {
        map.destroy()
      }
    } catch (_) {}
    map = null
  }
  mapStore.setMapInstance(null)
}

// --- Public methods ---
function fitView(coords) {
  if (!map || !coords || coords.length === 0) return

  const provider = mapStore.activeProvider
  if (provider === 'amap') {
    map.setFitView()
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (!TMap) return
    const bounds = new TMap.LatLngBounds()
    coords.forEach(c => {
      bounds.extend(new TMap.LatLng(c[1], c[0]))
    })
    map.fitBounds(bounds)
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return
    const bounds = new T.LngLatBounds()
    coords.forEach(c => {
      bounds.extend(new T.LngLat(c[0], c[1]))
    })
    map.setViewport(coords.map(c => new T.LngLat(c[0], c[1])))
  } else if (provider === 'baidu') {
    const BMap = window.BMap || window.BMapGL
    if (!BMap) return
    const points = coords.map(c => new BMap.Point(c[0], c[1]))
    const viewport = map.getViewport(points)
    map.centerAndZoom(viewport.center, viewport.zoom)
  }
}

function addMarker(pos, opts = {}) {
  if (!map || !pos) return null

  const provider = mapStore.activeProvider
  let marker = null

  if (provider === 'amap') {
    const AMap = window.AMap
    if (!AMap) return null
    marker = new AMap.Marker({
      position: new AMap.LngLat(pos[0], pos[1]),
      title: opts.title || '',
      ...opts,
    })
    map.add(marker)
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (!TMap) return null
    marker = new TMap.MultiMarker({
      map,
      geometries: [{
        position: new TMap.LatLng(pos[1], pos[0]),
        id: opts.id || `marker_${Date.now()}`,
      }],
    })
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return null
    marker = new T.Marker(new T.LngLat(pos[0], pos[1]))
    map.addOverLay(marker)
    if (opts.title) {
      marker.setTitle(opts.title)
    }
  } else if (provider === 'baidu') {
    const BMap = window.BMap || window.BMapGL
    if (!BMap) return null
    marker = new BMap.Marker(new BMap.Point(pos[0], pos[1]))
    map.addOverlay(marker)
    if (opts.title) {
      marker.setTitle(opts.title)
    }
  }

  if (marker) markers.push(marker)
  return marker
}

function drawPolyline(path, opts = {}) {
  if (!map || !path || path.length < 2) return null

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
    polyline = new TMap.MultiPolyline({
      map,
      styles: {
        style: new TMap.PolylineStyle({
          color,
          width: weight,
        }),
      },
      geometries: [{
        styleId: 'style',
        paths: path.map(p => new TMap.LatLng(p[1], p[0])),
      }],
    })
  } else if (provider === 'tianditu') {
    const T = window.T
    if (!T) return null
    polyline = new T.Polyline(
      path.map(p => new T.LngLat(p[0], p[1])),
      { color, weight, opacity: opts.opacity || 0.8 }
    )
    map.addOverLay(polyline)
  } else if (provider === 'baidu') {
    const BMap = window.BMap || window.BMapGL
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
  const provider = mapStore.activeProvider

  if (provider === 'amap' && map) {
    markers.forEach(m => { try { map.remove(m) } catch (_) {} })
    polylines.forEach(p => { try { map.remove(p) } catch (_) {} })
  } else if (provider === 'tencent') {
    markers.forEach(m => { try { m.setMap(null) } catch (_) {} })
    polylines.forEach(p => { try { p.setMap(null) } catch (_) {} })
  } else if (provider === 'tianditu' && map) {
    markers.forEach(m => { try { map.removeOverLay(m) } catch (_) {} })
    polylines.forEach(p => { try { map.removeOverLay(p) } catch (_) {} })
  } else if (provider === 'baidu' && map) {
    try { map.clearOverlays() } catch (_) {}
  }

  markers = []
  polylines = []
}

// --- Zoom controls ---
function handleZoomIn() {
  if (!map) return
  const provider = mapStore.activeProvider
  if (provider === 'amap' || provider === 'tencent') {
    map.setZoom(map.getZoom() + 1)
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
  } else if (provider === 'tianditu') {
    map.zoomOut()
  } else if (provider === 'baidu') {
    map.zoomOut()
  }
}

function handleResetView() {
  if (!map) return
  const provider = mapStore.activeProvider
  if (provider === 'amap') {
    map.setZoomAndCenter(13, [116.397428, 39.90923])
  } else if (provider === 'tencent') {
    const TMap = window.TMap
    if (TMap) {
      map.setCenter(new TMap.LatLng(39.90923, 116.397428))
      map.setZoom(13)
    }
  } else if (provider === 'tianditu') {
    const T = window.T
    if (T) {
      map.centerAndZoom(new T.LngLat(116.397428, 39.90923), 13)
    }
  } else if (provider === 'baidu') {
    const BMap = window.BMap || window.BMapGL
    if (BMap) {
      map.centerAndZoom(new BMap.Point(116.397428, 39.90923), 13)
    }
  }
  zoomLevel.value = 13
}

// --- Watch provider changes ---
watch(() => mapStore.activeProvider, () => {
  initMap()
})

// --- Lifecycle ---
onMounted(() => {
  initMap()
})

onUnmounted(() => {
  if (licenseObserver) {
    licenseObserver.disconnect()
    licenseObserver = null
  }
  destroyMap()
})

// --- Expose public API ---
defineExpose({
  fitView,
  addMarker,
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
      v-show="mapReady"
    ></div>

    <!-- Zoom controls overlay -->
    <MapControls
      v-if="mapReady"
      :zoom-level="zoomLevel"
      @zoom-in="handleZoomIn"
      @zoom-out="handleZoomOut"
      @reset-view="handleResetView"
    />

    <!-- Placeholder when map is not ready -->
    <MapPlaceholder
      v-if="showPlaceholder"
      :provider-name="mapStore.displayName"
      :has-key="!!mapStore.getKeyRequirement().value"
      :error-reason="placeholderError"
    />
  </div>
</template>
