import { io } from 'socket.io-client'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

let socket = null
let socketSession = ''
let heartbeatState = null
const HEARTBEAT_INTERVAL_MS = 500
const HEARTBEAT_TIMEOUT_MS = 2000
const connectionListeners = new Set()
let socketConnected = false
let taskNoticeSession = ''
const taskNoticeIds = new Set()
let taskNoticeQueue = Promise.resolve()
let taskNoticePopup = null

export function getSocket() {
  return socket
}

export function isWebSocketConnected() {
  return socketConnected && !!socket?.connected
}

function notifyConnectionState(connected) {
  if (socketConnected === connected) return
  socketConnected = connected
  connectionListeners.forEach((listener) => {
    try {
      listener(connected)
    } catch (error) {
      console.warn('[WS] 连接状态监听器执行失败:', error)
    }
  })
}

export function onWebSocketStatus(listener) {
  if (typeof listener !== 'function') return () => {}
  connectionListeners.add(listener)
  listener(isWebSocketConnected())
  return () => connectionListeners.delete(listener)
}

function startHeartbeat() {
  stopHeartbeat()
  const connection = socket
  const auth = useAuthStore()
  const session = socketSession
  const state = { interval: null, timeout: null, acknowledge: null }
  heartbeatState = state
  const isCurrent = () => heartbeatState === state && connection === socket &&
    session === auth.sessionUUID && connection.connected

  // ACK deadline is independent of the send interval and belongs to this connection run.
  state.acknowledge = () => {
    if (!isCurrent()) return
    clearTimeout(state.timeout)
    state.timeout = setTimeout(() => {
      if (!isCurrent()) return
      console.warn('[WS] 心跳超时，切换到轮询并重连')
      stopHeartbeat()
      connection.disconnect()
      if (connection === socket && session === auth.sessionUUID && connection.io?.opts?.reconnection !== false) {
        connection.connect()
      }
    }, HEARTBEAT_TIMEOUT_MS)
  }
  state.acknowledge()
  state.interval = setInterval(() => {
    if (isCurrent()) connection.emit('heartbeat', { ts: Date.now() })
  }, HEARTBEAT_INTERVAL_MS)
  connection.emit('heartbeat', { ts: Date.now() })
}

function stopHeartbeat() {
  if (!heartbeatState) return
  clearInterval(heartbeatState.interval)
  clearTimeout(heartbeatState.timeout)
  heartbeatState = null
}

function queueTaskNotice(data, isCurrent) {
  const { notice_id: id, task_name: name, message, kind } = data ?? {}
  const swal = window.Swal
  if (typeof id !== 'string' || !id.trim() || taskNoticeIds.has(id)) return
  if (typeof name !== 'string' || !name.trim() || typeof message !== 'string' || !message.trim()) return
  if (!swal?.fire) return

  taskNoticeIds.add(id)
  taskNoticeQueue = taskNoticeQueue.then(async () => {
    if (!isCurrent()) return
    const compatibilityError = kind === 'compatibility_error'
    const dismissed = swal.fire({
      icon: 'warning',
      titleText: compatibilityError ? '检测到兼容性错误' : `任务暂不可执行：${name}`,
      text: compatibilityError ? `${name}\n${message}` : message,
      confirmButtonText: '确定',
    })
    taskNoticePopup = swal.getPopup?.() ?? null
    try {
      await dismissed
    } finally {
      taskNoticePopup = null
    }
  }).catch(error => console.warn('[WS] 显示任务提醒失败:', error))
}

export function connectWebSocket() {
  const auth = useAuthStore()
  if (!auth.sessionUUID) return null
  if (socket?.connected && socketSession === auth.sessionUUID) return socket
  if (socket) disconnectWebSocket()
  const connectionSession = auth.sessionUUID
  socketSession = connectionSession
  if (taskNoticeSession !== connectionSession) {
    taskNoticeSession = connectionSession
    taskNoticeIds.clear()
  }

  socket = io({
    autoConnect: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 30000,
    reconnectionAttempts: Infinity,
    pingTimeout: 60000,
    pingInterval: 25000,
  })
  const connection = socket
  const isCurrent = () => connection === socket && connectionSession === auth.sessionUUID
  const on = (event, callback) => connection.on(event, (...args) => {
    if (!isCurrent()) return
    callback(...args)
  })

  on('connect', () => {
    notifyConnectionState(true)
    console.info('[WS] 连接成功, SID:', socket.id)
    socket.emit('join', { session_id: auth.sessionUUID, admin_origin_session_id: auth.getAdminOriginHeaderValue?.(auth.sessionUUID) || '' })
    startHeartbeat()
    import('@/services/api').then(({ callAPI }) => {
      callAPI('get_initial_data').then(data => {
        if (connection !== socket || connectionSession !== auth.sessionUUID) return
        if (data) {
          const app = useAppStore()
          if (data.users) app.users = data.users
          if (data.tasks) app.tasks = data.tasks
          if (data.is_running != null) app.isRunning = data.is_running
        }
      }).catch(() => {})
    })
  })

  on('disconnect', (reason) => {
    notifyConnectionState(false)
    console.info('[WS] 断开连接:', reason)
    stopHeartbeat()
  })

  on('connect_error', (err) => {
    stopHeartbeat()
    notifyConnectionState(false)
    console.warn('[WS] 连接错误:', err.message)
  })

  on('heartbeat_ack', () => heartbeatState?.acknowledge())

  on('log_message', (data) => {
    if (data?.msg) {
      const app = useAppStore()
      app.addLog(data.msg, data.level || 'INFO', 'Backend', data.diagnostic_id || '')
    }
  })

  on('multi_status_update', (data) => {
    const app = useAppStore()
    app.handleMultiStatusUpdate(data)
  })

  on('accounts_updated', (data) => {
    const app = useAppStore()
    app.handleAccountsUpdated(data)
  })

  on('multi_global_buttons_update', (data) => {
    const app = useAppStore()
    app.handleGlobalButtonsUpdate(data)
  })

  on('runner_execution_started', (data) => {
    const app = useAppStore()
    app.beginRunnerExecution?.(data)
  })

  on('runner_position_update_new', (data) => {
    const app = useAppStore()
    app.handlePositionUpdate(data)
  })

  on('multi_position_update', (data) => {
    if (data?.username && typeof data.lon === 'number' && typeof data.lat === 'number') {
      const app = useAppStore()
      app.handleMultiPositionUpdate(data)
    }
  })

  on('task_completed', (data) => {
    const app = useAppStore()
    app.handleTaskCompleted(data)
  })

  on('task_unavailable', (data) => queueTaskNotice(data, isCurrent))

  on('run_stopped', (data) => {
    const app = useAppStore()
    app.handleRunStopped(data)
  })

  on('onNotificationsUpdated', (data) => {
    const app = useAppStore()
    app.handleNotificationsUpdated(data)
    import('@/stores/notification').then(({ useNotificationStore }) => {
      const notifStore = useNotificationStore()
      notifStore.fetchNotifications()
    })
  })

  on('auto_attendance_updated', (data) => {
    if (data?.enabled !== false) return
    const app = useAppStore()
    app.pythonParams = {
      ...app.pythonParams,
      auto_attendance_enabled: false,
    }
    app.addLog('自动签到已完成设定次数，已自动关闭', 'INFO', 'Backend')
  })

  on('verification_codes_updated', () => {
    const app = useAppStore()
    app.handleVerificationCodesUpdated()
  })

  socket.connect()
  return socket
}

export function disconnectWebSocket() {
  stopHeartbeat()
  if (socket) {
    if (socket.io) socket.io.opts.reconnection = false
    socket.disconnect()
    socket = null
  }
  socketSession = ''
  const swal = globalThis.window?.Swal
  if (taskNoticePopup && swal?.getPopup?.() === taskNoticePopup) swal.close()
  notifyConnectionState(false)
}

export function disableReconnection() {
  stopHeartbeat()
  if (socket?.io) socket.io.opts.reconnection = false
  socket?.disconnect()
}

export function enableReconnection() {
  if (socket) {
    if (socket.io) socket.io.opts.reconnection = true
    socket.connect()
  }
}
