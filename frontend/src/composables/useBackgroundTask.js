import { ref, watch, onUnmounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

export function useBackgroundTask() {
  const auth = useAuthStore()
  const app = useAppStore()
  const isPolling = ref(false)
  const taskStatus = ref(null)
  let pollTimer = null
  let startTime = 0
  let epoch = 0
  let disposed = false

  async function pollStatus() {
    const requestEpoch = epoch
    const sessionId = auth.sessionUUID
    try {
      const data = await callRawAPI('/api/background_task/status', 'GET', null, { sessionContext: 'business' })
      if (disposed || requestEpoch !== epoch || sessionId !== auth.sessionUUID) return
      const status = data?.task_status
      if (!data?.success || !status) {
        stopPolling()
        return
      }
      taskStatus.value = status
      app.addRoutePlanningFailures(status.route_planning_failures)
      if (['completed', 'stopped', 'error'].includes(status.status)) {
        app.isRunning = false
        stopPolling()
      } else if (['running', 'paused'].includes(status.status)) {
        app.isRunning = true
      }
    } catch (_) {}
  }

  function startPolling() {
    if (disposed || isPolling.value) return
    stopPolling()
    isPolling.value = true
    startTime = Date.now()
    pollTimer = setInterval(pollStatus, 3000)
    pollStatus()
  }

  function stopPolling() {
    epoch++
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    isPolling.value = false
  }

  async function stopTask() {
    stopPolling()
    try {
      await callRawAPI('/api/background_task/stop', 'POST', null, { sessionContext: 'business' })
    } catch (_) {}
  }

  function getElapsedMs() {
    return startTime ? Date.now() - startTime : 0
  }

  watch(() => app.isRunning, running => {
    if (running) startPolling()
    else if (isPolling.value) pollStatus()
  })

  onUnmounted(() => {
    disposed = true
    stopPolling()
  })

  return { isPolling, taskStatus, pollStatus, startPolling, stopPolling, stopTask, getElapsedMs }
}
