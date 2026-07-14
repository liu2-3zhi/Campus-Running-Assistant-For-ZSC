import { computed } from 'vue'
import { useNetworkStore } from '@/stores/network'

export function useNetwork() {
  const network = useNetworkStore()

  const isOffline = computed(() => network.isInErrorState)

  function guardApiCall(fn) {
    return async (...args) => {
      if (network.isInErrorState) {
        console.warn('[网络] 网络错误状态中，跳过 API 调用')
        return null
      }
      return fn(...args)
    }
  }

  return { isOffline, guardApiCall }
}
