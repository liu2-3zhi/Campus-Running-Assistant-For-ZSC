import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const isMobile = ref(false)
  const isLoading = ref(true)
  const currentView = ref('login') // 'login' | 'main' | 'multi'
  const isMultiMode = ref(false)

  // 任务相关
  const tasks = ref([])
  const selectedTaskIndex = ref(-1)
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

  function addLog(msg, level = 'INFO', source = 'System') {
    const entry = {
      msg,
      level,
      source,
      time: new Date().toLocaleTimeString(),
    }
    logs.value.push(entry)
    if (logs.value.length > maxLogs) {
      logs.value = logs.value.slice(-maxLogs)
    }
  }

  function clearLogs() {
    logs.value = []
  }

  function handleMultiStatusUpdate(data) {
    if (data?.username && data?.data) {
      multiStatus.value = { ...multiStatus.value, [data.username]: data.data }
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

  function handlePositionUpdate(data) {
    if (!data) return

    if (data.task_index !== undefined && data.task_index !== selectedTaskIndex.value) {
      selectedTaskIndex.value = data.task_index
      addLog(`任务切换: 正在执行任务 #${data.task_index}`, 'INFO', 'System')
    }

    const rd = runData.value || {}
    rd.current_distance = data.distance || rd.current_distance || 0
    rd.live_distance = rd.current_distance
    rd.duration = (rd.duration || 0) + (data.duration || 0)
    rd.live_time = rd.duration
    rd.elapsed_time = rd.duration
    rd.lat = data.lat
    rd.lng = data.lon
    rd.latitude = data.lat
    rd.longitude = data.lon
    rd.current_lon = data.lon
    rd.current_lat = data.lat
    rd.target_sequence = data.target_sequence != null ? data.target_sequence + 1 : rd.target_sequence
    if (rd.total_distance && rd.current_distance) {
      rd.progress = Math.min(100, (rd.current_distance / rd.total_distance) * 100)
    }
    runData.value = { ...rd }
  }

  function handleTaskCompleted(data) {
    if (data && typeof data.task_index !== 'undefined') {
      const idx = data.task_index
      if (tasks.value[idx]) {
        tasks.value[idx].status = 'completed'
      }
    }
    isRunning.value = false
    addLog('任务已完成', 'INFO', 'System')
  }

  function handleRunStopped() {
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
    tasks, selectedTaskIndex, selectedTask, isRunning, runData,
    users, multiAccounts, multiStatus, multiGlobalButtons, multiPositions,
    logs, notifications, unreadCount, verificationCodes,
    pythonParams, beianData,
    detectMobile, addLog, clearLogs,
    handleMultiStatusUpdate, handleAccountsUpdated,
    handleGlobalButtonsUpdate, handlePositionUpdate,
    handleTaskCompleted, handleRunStopped,
    handleNotificationsUpdated, handleVerificationCodesUpdated,
    handleMultiPositionUpdate, refreshVerificationCodes,
  }
})
