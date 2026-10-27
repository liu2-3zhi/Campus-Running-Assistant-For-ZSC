import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const isMobile = ref(false)
  const isLoading = ref(true)
  const currentView = ref('login') // 'login' | 'main' | 'multi'
  const isMultiMode = ref(false)
  const businessSession = ref('')

  // 任务相关
  const tasks = ref([])
  const selectedTaskIndex = ref(-1)
  const activeTaskIndex = ref(null)
  const activeExecutionId = ref('')
  const activeExecutionStartedAt = ref(0)
  const isRunning = ref(false)
  const runData = ref(null)

  // 用户列表
  const users = ref([])

  // 多账号
  const multiAccounts = ref([])
  const multiStatus = ref({})
  const multiGlobalButtons = ref({ startDisabled: false, stopDisabled: false, exitDisabled: false })
  const multiPositions = ref({})

  // 日志
  const logs = ref([])
  const maxLogs = 500

  // 通知
  const notifications = ref([])
  const unreadCount = ref(0)

  // 验证码
  const verificationCodes = ref([])

  // 参数
  const pythonParams = ref({})

  // 备案信息
  const beianData = ref(null)

  const selectedTask = computed(() =>
    selectedTaskIndex.value >= 0 ? tasks.value[selectedTaskIndex.value] : null
  )

  function detectMobile() {
    isMobile.value = window.innerWidth < 768
  }

  function addLog(msg, level = 'INFO', source = 'System', diagnosticId = '') {
    if (diagnosticId && logs.value.some(entry => entry.diagnostic_id === diagnosticId)) return
    const entry = {
      msg,
      level,
      source,
      time: new Date().toLocaleTimeString(),
      ...(diagnosticId ? { diagnostic_id: diagnosticId } : {}),
    }
    logs.value.push(entry)
    if (logs.value.length > maxLogs) {
      logs.value = logs.value.slice(-maxLogs)
    }
  }

  function addRoutePlanningFailures(failures) {
    if (!Array.isArray(failures)) return
    for (const failure of failures) {
      if (!failure?.diagnostic_id || typeof failure.message !== 'string') continue
      const existing = logs.value.find(entry => entry.diagnostic_id === failure.diagnostic_id)
      if (existing?.route_detail) continue
      const context = [failure.segment != null ? `路段：${failure.segment}` : '', failure.error_code != null && failure.error_code !== '' ? `错误码：${failure.error_code}` : ''].filter(Boolean).join('；')
      const readable = [failure.error_explanation, failure.error_hint].filter(value => typeof value === 'string' && value && !failure.message.includes(value))
      const msg = `[${failure.provider || '地图服务'}] ${context ? context + '；' : ''}${failure.message}${readable.length ? '；' + readable.join('；') : ''}（诊断编号：${failure.diagnostic_id}）`
      if (existing) {
        Object.assign(existing, { msg, level: 'ERROR', source: 'Backend', route_detail: true })
      } else {
        addLog(msg, 'ERROR', 'Backend', failure.diagnostic_id)
        logs.value[logs.value.length - 1].route_detail = true
      }
    }
  }

  function clearLogs() {
    logs.value = []
  }

  function bindBusinessSession(session) {
    if (businessSession.value && businessSession.value !== session) {
      tasks.value = []
      users.value = []
      selectedTaskIndex.value = -1
      activeTaskIndex.value = null
      activeExecutionId.value = ''
      activeExecutionStartedAt.value = 0
      runData.value = null
      isRunning.value = false
      multiAccounts.value = []
      multiPositions.value = {}
      multiStatus.value = {}
      clearLogs()
    }
    businessSession.value = session
  }

  function handleMultiStatusUpdate(data) {
    if (data?.username && data?.data) {
      multiStatus.value = { ...multiStatus.value, [data.username]: data.data }
      multiAccounts.value = multiAccounts.value.map((account) => {
        const username = account.username || account.name || account.id
        return username === data.username
          ? { ...account, ...data.data }
          : account
      })
    }
  }

  function handleAccountsUpdated(data) {
    if (data?.accounts) {
      multiAccounts.value = data.accounts
    }
  }

  function handleGlobalButtonsUpdate(data) {
    if (data) {
      multiGlobalButtons.value = {
        startDisabled: !!data.start_disabled,
        stopDisabled: !!data.stop_disabled,
        exitDisabled: !!data.exit_disabled,
      }
    }
  }

  function beginRunnerExecution(data) {
    if (!data?.execution_id) return true
    const id = String(data.execution_id)
    const startedAt = Number(data.execution_started_at || 0)
    if (id !== activeExecutionId.value && activeExecutionId.value && startedAt <= activeExecutionStartedAt.value) return false
    if (id === activeExecutionId.value && (data.task_index == null || data.task_index === activeTaskIndex.value)) return true
    activeExecutionId.value = id
    activeExecutionStartedAt.value = Math.max(startedAt, activeExecutionStartedAt.value)
    if (Number.isInteger(data.task_index)) {
      activeTaskIndex.value = data.task_index
      selectedTaskIndex.value = data.task_index
      const previous = runData.value?.task_index === data.task_index ? runData.value : {}
      runData.value = {
        ...previous, task_index: data.task_index, status: 'running', execution_id: id,
        current_point_index: 0, point_index: 0, current_distance: 0, live_distance: 0,
        duration: 0, elapsed_time: 0, live_time: 0, target_sequence: 1,
      }
      for (const field of ['current_position', 'current_lon', 'current_lat', 'lat', 'lng', 'latitude', 'longitude']) delete runData.value[field]
    }
    return true
  }

  function handlePositionUpdate(data) {
    if (!data) return
    if (data.execution_id) {
      if (!activeExecutionId.value) beginRunnerExecution(data)
      if (String(data.execution_id) !== activeExecutionId.value) return
    } else if (activeExecutionId.value) return
    if (isRunning.value && activeTaskIndex.value != null && data.task_index != null && data.task_index !== activeTaskIndex.value) return

    if (data.task_index !== undefined && data.task_index !== selectedTaskIndex.value) {
      selectedTaskIndex.value = data.task_index
      runData.value = { task_index: data.task_index }
      addLog(`任务切换: 正在执行任务 #${data.task_index}`, 'INFO', 'System')
    }

    const rd = runData.value || {}
    const pointIndex = data.point_index ?? data.current_point_index
    if (pointIndex != null && Number(pointIndex) < Number(rd.current_point_index ?? -1)) return
    if (pointIndex != null) { rd.current_point_index = Number(pointIndex); rd.point_index = Number(pointIndex) }
    rd.task_index = data.task_index ?? selectedTaskIndex.value
    rd.current_distance = data.distance ?? rd.current_distance ?? 0
    rd.live_distance = rd.current_distance
    rd.duration = data.elapsed_time != null ? Number(data.elapsed_time) : (rd.duration || 0) + (data.duration || 0)
    rd.live_time = rd.duration
    rd.elapsed_time = rd.duration
    rd.lat = data.lat
    rd.lng = data.lon
    rd.latitude = data.lat
    rd.longitude = data.lon
    rd.current_lon = data.lon
    rd.current_lat = data.lat
    rd.current_position = { lon: data.lon, lat: data.lat }
    rd.target_sequence = data.target_sequence != null ? data.target_sequence + 1 : rd.target_sequence
    if (rd.total_distance && rd.current_distance) {
      rd.progress = Math.min(100, (rd.current_distance / rd.total_distance) * 100)
    }
    runData.value = { ...rd }
  }

  function handleTaskCompleted(data) {
    if (data?.execution_id && data.execution_id !== activeExecutionId.value) return
    if (data && typeof data.task_index !== 'undefined') {
      const idx = data.task_index
      if (tasks.value[idx]) {
        tasks.value[idx].status = 'completed'
      }
    }
    isRunning.value = false
    addLog('任务已完成', 'INFO', 'System')
  }

  function handleRunStopped(data) {
    if (data?.execution_id && data.execution_id !== activeExecutionId.value) return
    isRunning.value = false
    addLog('运行已停止', 'INFO', 'System')
  }

  function handleNotificationsUpdated(data) {
    if (data?.success && data.notices) {
      notifications.value = data.notices
      unreadCount.value = data.unreadCount || 0
    }
  }

  function handleVerificationCodesUpdated() {
    // 原始协议：此事件不带数据，仅作为刷新信号
    refreshVerificationCodes()
  }

  async function refreshVerificationCodes() {
    // verification_codes_updated 是 socket 信号，具体验证码通过 get_initial_data 获取
    try {
      const { callAPI } = await import('@/services/api')
      const result = await callAPI('get_initial_data')
      if (result?.verification_codes) {
        verificationCodes.value = result.verification_codes
      }
    } catch (_) {}
  }

  function handleMultiPositionUpdate(data) {
    if (data?.username) {
      multiPositions.value = {
        ...multiPositions.value,
        [data.username]: { lon: data.lon, lat: data.lat, name: data.name || data.username }
      }
    }
  }

  return {
    isMobile, isLoading, currentView, isMultiMode,
    businessSession, bindBusinessSession,
    tasks, selectedTaskIndex, activeTaskIndex, activeExecutionId, activeExecutionStartedAt, selectedTask, isRunning, runData,
    users, multiAccounts, multiStatus, multiGlobalButtons, multiPositions,
    logs, notifications, unreadCount, verificationCodes,
    pythonParams, beianData,
    detectMobile, addLog, clearLogs, addRoutePlanningFailures,
    handleMultiStatusUpdate, handleAccountsUpdated,
    handleGlobalButtonsUpdate, handlePositionUpdate, beginRunnerExecution,
    handleTaskCompleted, handleRunStopped,
    handleNotificationsUpdated, handleVerificationCodesUpdated,
    handleMultiPositionUpdate, refreshVerificationCodes,
  }
})
