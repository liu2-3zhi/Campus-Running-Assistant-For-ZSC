import { ref, onUnmounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

export function useBackgroundTask() {
  const isPolling = ref(false)
  const taskStatus = ref(null)
  let pollTimer = null
  let startTime = 0

  async function pollStatus() {
    try {
      const data = await callRawAPI('/api/background_task/status', 'GET')
      taskStatus.value = data
      if (data?.status === 'completed' || data?.status === 'stopped') {
        stopPolling()
      }
    } catch (_) {}
  }

  function startPolling() {
    stopPolling()
    isPolling.value = true
    startTime = Date.now()
    pollTimer = setInterval(pollStatus, 3000)
    pollStatus()
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    isPolling.value = false
  }

  async function stopTask() {
    stopPolling()
    try {
      await callRawAPI('/api/background_task/stop', 'POST', null)
    } catch (_) {}
  }

  function getElapsedMs() {
    return startTime ? Date.now() - startTime : 0
  }

  onUnmounted(stopPolling)

  return { isPolling, taskStatus, startPolling, stopPolling, stopTask, getElapsedMs }
}
