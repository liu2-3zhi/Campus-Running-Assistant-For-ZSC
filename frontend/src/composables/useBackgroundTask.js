import { ref, watch, onUnmounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'
import { createTaskMapRestorer } from '@/utils/taskMapRestore'
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
  let statusRequest = 0
  let latestStatusTimestamp = 0
  let disposed = false
  const mapRestorer = createTaskMapRestorer({ app, loadSnapshot: index => callAPI('get_task_map_snapshot', index), getSession: () => auth.sessionUUID })

  async function applyStatus(status) {
    if (disposed || !status) return
    if (status.execution_id && app.activeExecutionId && status.execution_id !== app.activeExecutionId && Number(status.execution_started_at || 0) <= Number(app.activeExecutionStartedAt || 0)) return
    const timestamp = Number(status.last_update ?? status.start_time ?? 0)
    if (timestamp && timestamp < latestStatusTimestamp) return
    if (timestamp) latestStatusTimestamp = timestamp
    taskStatus.value = status
    app.addRoutePlanningFailures(status.route_planning_failures)
    if (['running', 'paused'].includes(status.status)) app.isRunning = true
    else if (['completed', 'stopped', 'error'].includes(status.status)) app.isRunning = false
    try { await mapRestorer.apply(status) } catch (_) {}
  }

  async function pollStatus() {
    const requestEpoch = epoch
    const requestNumber = ++statusRequest
    const sessionId = auth.sessionUUID
    try {
      const data = await callRawAPI('/api/background_task/status', 'GET', null, { sessionContext: 'business' })
      if (disposed || requestEpoch !== epoch || requestNumber !== statusRequest || sessionId !== auth.sessionUUID) return
      const status = data?.task_status
      if (!data?.success || !status) {
        stopPolling()
        return
      }
      await applyStatus(status)
      if (disposed || requestEpoch !== epoch || sessionId !== auth.sessionUUID) return
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
  watch(() => auth.sessionUUID, () => {
    mapRestorer.reset()
    latestStatusTimestamp = 0
    stopPolling()
    app.runData = null
    app.selectedTaskIndex = -1
    startPolling()
  })

  onUnmounted(() => {
    disposed = true
    mapRestorer.reset()
    stopPolling()
  })

  return { isPolling, taskStatus, applyStatus, pollStatus, startPolling, stopPolling, stopTask, getElapsedMs }
}
