import { ref, onUnmounted } from 'vue'

export function useCountdown(initialSeconds = 60) {
  const remaining = ref(0)
  const isActive = ref(false)
  let timer = null

  function start(seconds = initialSeconds) {
    stop()
    remaining.value = seconds
    isActive.value = true
    timer = setInterval(() => {
      remaining.value--
      if (remaining.value <= 0) {
        stop()
      }
    }, 1000)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    remaining.value = 0
    isActive.value = false
  }

  onUnmounted(stop)

  return { remaining, isActive, start, stop }
}
