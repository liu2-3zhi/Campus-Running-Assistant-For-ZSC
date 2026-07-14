import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useMapStore = defineStore('map', () => {
  const activeProvider = ref('amap') // amap | tencent | tianditu | baidu
  const mapInstance = ref(null)
  const providerInstances = ref({})
  const isMapReady = ref(false)
  const mapConfig = ref({
    amapKey: '',
    amapSecurityKey: '',
    tencentKey: '',
    tiandituKey: '',
    baiduKey: '',
  })

  // --- 交互式路径绘制协调状态（对齐 original 的 isDrawing/draftPath/draftTotalDist）---
  const isDrawing = ref(false)        // 是否处于录制/绘制模式
  const draftPoints = ref([])         // 草稿路径点，元素为 { lng, lat }
  const draftDistance = ref(0)        // 草稿路径累计距离（米），haversine 累加

  // haversine 球面距离（米）。original 使用平面近似 fastDistanceMeters，
  // 这里改用标准 haversine，短距离下二者差异极小，但坐标系差异见报告说明。
  function haversineMeters(lng1, lat1, lng2, lat2) {
    const R = 6371000 // 地球平均半径（米）
    const toRad = (d) => (d * Math.PI) / 180
    const dLat = toRad(lat2 - lat1)
    const dLng = toRad(lng2 - lng1)
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)))
  }

  function startDrawing() {
    clearDraft()
    isDrawing.value = true
  }

  function stopDrawing() {
    isDrawing.value = false
  }

  function clearDraft() {
    draftPoints.value = []
    draftDistance.value = 0
  }

  function addDraftPoint({ lng, lat } = {}) {
    if (lng == null || lat == null) return
    const nLng = Number(lng)
    const nLat = Number(lat)
    if (Number.isNaN(nLng) || Number.isNaN(nLat)) return
    const pts = draftPoints.value
    if (pts.length > 0) {
      const prev = pts[pts.length - 1]
      draftDistance.value += haversineMeters(prev.lng, prev.lat, nLng, nLat)
    }
    pts.push({ lng: nLng, lat: nLat })
  }

  const providerDisplayNames = {
    amap: '高德地图',
    tencent: '腾讯地图',
    tianditu: '天地图',
    baidu: '百度地图',
  }

  const displayName = computed(() => providerDisplayNames[activeProvider.value] || activeProvider.value)

  function setProvider(provider) {
    activeProvider.value = provider
  }

  function setMapInstance(instance) {
    mapInstance.value = instance
    isMapReady.value = !!instance
  }

  function setConfig(config) {
    Object.assign(mapConfig.value, config)
  }

  function getKeyRequirement() {
    const requirements = {
      amap: { field: 'amap_js_api_key', fieldLabel: 'JS API Key', value: mapConfig.value.amapKey },
      tencent: { field: 'tencent_map_key', fieldLabel: 'Key', value: mapConfig.value.tencentKey },
      tianditu: { field: 'tianditu_map_key', fieldLabel: 'Key', value: mapConfig.value.tiandituKey },
      baidu: { field: 'baidu_map_ak', fieldLabel: 'AK', value: mapConfig.value.baiduKey },
    }
    return requirements[activeProvider.value] || requirements.amap
  }

  return {
    activeProvider, mapInstance, providerInstances, isMapReady, mapConfig,
    displayName, setProvider, setMapInstance, setConfig, getKeyRequirement,
    // 绘制协调
    isDrawing, draftPoints, draftDistance,
    startDrawing, stopDrawing, clearDraft, addDraftPoint,
  }
})
