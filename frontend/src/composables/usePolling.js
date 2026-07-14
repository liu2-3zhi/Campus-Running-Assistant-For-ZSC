import { onUnmounted, ref } from 'vue'

export function usePolling(fn, intervalMs = 30000) {
  const timer = ref(null)
  const isActive = ref(false)

  function start() {
    stop()
    isActive.value = true
    timer.value = setInterval(fn, intervalMs)
  }

  function stop() {
    if (timer.value) {
      clearInterval(timer.value)
      timer.value = null
    }
    isActive.value = false
  }

  onUnmounted(stop)

  return { start, stop, isActive }
}
