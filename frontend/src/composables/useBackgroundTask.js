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
  let inFlight = null
  let latestStatusTimestamp = 0
  let disposed = false
  let updatingRunningFromStatus = false
  const mapRestorer = createTaskMapRestorer({ app, loadSnapshot: index => callAPI('get_task_map_snapshot', index), getSession: () => auth.sessionUUID })

  function isObsoleteExecution(status) {
    if (!app.activeExecutionId) return false
    if (!status.execution_id) return true
    return status.execution_id !== app.activeExecutionId && Number(status.execution_started_at || 0) <= Number(app.activeExecutionStartedAt || 0)
  }

  function applyStatus(status) {
    if (disposed || !status) return false
    if (isObsoleteExecution(status)) return false
    const timestamp = Number(status.last_update ?? status.start_time ?? 0)
    if (timestamp && timestamp < latestStatusTimestamp) return false
    if (timestamp) latestStatusTimestamp = timestamp
    taskStatus.value = status
    app.addRoutePlanningFailures(status.route_planning_failures)
    updatingRunningFromStatus = true
    try {
      if (['running', 'paused'].includes(status.status)) app.isRunning = true
      else if (['completed', 'stopped', 'error'].includes(status.status)) app.isRunning = false
    } finally {
      updatingRunningFromStatus = false
    }
    // Geometry has its own generation guards and must not hold up status polling.
    try { Promise.resolve(mapRestorer.apply(status)).catch(() => {}) } catch (_) {}
    return !disposed && !isObsoleteExecution(status)
  }

  function isCurrentRequest(request) {
    return !disposed && request.epoch === epoch && request.sessionId === auth.sessionUUID
  }

  function pollStatus() {
    if (disposed) return Promise.resolve()
    if (inFlight && isCurrentRequest(inFlight)) return inFlight.promise
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
    const request = { epoch, sessionId: auth.sessionUUID, controller: new AbortController(), timeout: null, promise: null }
    inFlight = request
    let onAbort
    const aborted = new Promise((_, reject) => {
      onAbort = () => reject(new Error('后台状态请求已取消'))
      request.controller.signal.addEventListener('abort', onAbort, { once: true })
    })
    request.timeout = setTimeout(() => request.controller.abort(), 30000)
    request.promise = (async () => {
      try {
        const data = await Promise.race([
          callRawAPI('/api/background_task/status', 'GET', null, { sessionContext: 'business', signal: request.controller.signal }),
          aborted,
        ])
        if (!isCurrentRequest(request)) return
        const status = data?.task_status
        if (!data?.success || !status) {
          stopPolling()
          return
        }
        if (!applyStatus(status) || !isCurrentRequest(request)) return
        if (['completed', 'stopped', 'error'].includes(status.status)) {
          stopPolling()
        }
      } catch (_) {
      } finally {
        clearTimeout(request.timeout)
        request.controller.signal.removeEventListener('abort', onAbort)
        if (inFlight === request) inFlight = null
        if (isCurrentRequest(request) && isPolling.value) {
          pollTimer = setTimeout(() => { pollTimer = null; pollStatus() }, 3000)
        }
      }
    })()
    return request.promise
  }

  function startPolling() {
    if (disposed || isPolling.value) return
    stopPolling()
    isPolling.value = true
    startTime = Date.now()
    pollStatus()
  }

  function stopPolling() {
    epoch++
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    const request = inFlight
    inFlight = null
    if (request) {
      clearTimeout(request.timeout)
      request.controller.abort()
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

  // Sync watching preserves the status-backfill guard until this callback runs.
  watch(() => app.isRunning, running => {
    if (updatingRunningFromStatus) return
    if (running) startPolling()
    else if (isPolling.value) pollStatus()
  }, { flush: 'sync' })
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
