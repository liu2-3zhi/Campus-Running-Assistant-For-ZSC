import { computed } from 'vue'
import { useAppStore } from '@/stores/app'

export function useMobile() {
  const app = useAppStore()
  const isMobile = computed(() => app.isMobile)

  return { isMobile }
}
