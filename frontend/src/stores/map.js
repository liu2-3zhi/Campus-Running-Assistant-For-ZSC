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
  }
})
