import { io } from 'socket.io-client'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

let socket = null
let heartbeatTimer = null

export function getSocket() {
  return socket
}

function startHeartbeat() {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    if (socket?.connected) {
      socket.emit('heartbeat', { ts: Date.now() })
    }
  }, 20000)
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

export function connectWebSocket() {
  if (socket?.connected) return socket

  const auth = useAuthStore()
  if (!auth.sessionUUID) return null

  socket = io({
    autoConnect: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 30000,
    reconnectionAttempts: Infinity,
    pingTimeout: 60000,
    pingInterval: 25000,
  })

  socket.connect()

  socket.on('connect', () => {
    console.info('[WS] 连接成功, SID:', socket.id)
    socket.emit('join', { session_id: auth.sessionUUID })
    startHeartbeat()
    import('@/services/api').then(({ callAPI }) => {
      callAPI('get_initial_data').then(data => {
        if (data) {
          const app = useAppStore()
          if (data.users) app.users = data.users
          if (data.tasks) app.tasks = data.tasks
          if (data.run_data) app.runData = data.run_data
          if (data.is_running != null) app.isRunning = data.is_running
        }
      }).catch(() => {})
    })
  })

  socket.on('disconnect', (reason) => {
    console.info('[WS] 断开连接:', reason)
    stopHeartbeat()
  })

  socket.on('connect_error', (err) => {
    console.warn('[WS] 连接错误:', err.message)
  })

  socket.on('heartbeat_ack', () => {})

  socket.on('log_message', (data) => {
    if (data?.msg) {
      const app = useAppStore()
      app.addLog(data.msg, data.level || 'INFO', 'Backend')
    }
  })

  socket.on('multi_status_update', (data) => {
    const app = useAppStore()
    app.handleMultiStatusUpdate(data)
  })

  socket.on('accounts_updated', (data) => {
    const app = useAppStore()
    app.handleAccountsUpdated(data)
  })

  socket.on('multi_global_buttons_update', (data) => {
    const app = useAppStore()
    app.handleGlobalButtonsUpdate(data)
  })

  socket.on('runner_position_update_new', (data) => {
    const app = useAppStore()
    app.handlePositionUpdate(data)
  })

  socket.on('multi_position_update', (data) => {
    if (data?.username && typeof data.lon === 'number' && typeof data.lat === 'number') {
      const app = useAppStore()
      app.handleMultiPositionUpdate(data)
    }
  })

  socket.on('task_completed', (data) => {
    const app = useAppStore()
    app.handleTaskCompleted(data)
  })

  socket.on('run_stopped', () => {
    const app = useAppStore()
    app.handleRunStopped()
  })

  socket.on('onNotificationsUpdated', (data) => {
    const app = useAppStore()
    app.handleNotificationsUpdated(data)
    import('@/stores/notification').then(({ useNotificationStore }) => {
      const notifStore = useNotificationStore()
      notifStore.fetchNotifications()
    })
  })

  socket.on('verification_codes_updated', () => {
    const app = useAppStore()
    app.handleVerificationCodesUpdated()
  })

  return socket
}

export function disconnectWebSocket() {
  stopHeartbeat()
  if (socket) {
    if (socket.io) socket.io.opts.reconnection = false
    if (socket.connected) socket.disconnect()
    socket = null
  }
}

export function disableReconnection() {
  if (socket?.io) socket.io.opts.reconnection = false
  if (socket?.connected) socket.disconnect()
}

export function enableReconnection() {
  if (socket) {
    if (socket.io) socket.io.opts.reconnection = true
    socket.connect()
  }
}
