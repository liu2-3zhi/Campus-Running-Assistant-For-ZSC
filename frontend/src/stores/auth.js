import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function isUsableUUID(val) {
  if (typeof val !== 'string' || val.length === 0) return false
  const lower = val.trim().toLowerCase()
  return lower !== '' && lower !== 'none' && lower !== 'null' && lower !== 'undefined'
}

function normalizeAdminOrigin(value) {
  if (typeof value !== 'string') return ''
  const normalized = value.trim().toLowerCase()
  return /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(normalized)
    ? normalized : ''
}

function getUiEntryPath() {
  const base = typeof window !== 'undefined' ? window.__RUNNING_UI_BASE__ : '/'
  return typeof base === 'string' && base.startsWith('/') ? base : '/'
}

export const useAuthStore = defineStore('auth', () => {
  const adminOriginSession = ref(readAdminOrigin())
  const adminViewContext = ref(null)
  const adminViewInvalid = ref(false)
  const sessionUUID = ref(null)
  const authSessionUUID = ref(null)
  const loginInProgress = ref(false)
  const isAuthenticated = ref(false)
  const isBanned = ref(false)
  const bannedData = ref(null)
  const isGuest = ref(false)
  const isAdmin = ref(false)
  const group = ref('')

  const username = ref('')
  const displayName = ref('')
  const realName = ref('')
  const studentId = ref('')
  const avatarUrl = ref('')
  const theme = ref('light')
  const themeStyle = ref('default')
  const permissions = ref({})
  const sessionLimitInfo = ref(null)
  const token = ref('')

  const hasSession = computed(() => isUsableUUID(sessionUUID.value) || isUsableUUID(authSessionUUID.value))

  function readAdminOrigin() {
    try {
      const value = localStorage.getItem('admin_return_origin')
      const normalized = normalizeAdminOrigin(value)
      if (normalized) localStorage.setItem('admin_return_origin', normalized)
      else localStorage.removeItem('admin_return_origin')
      return normalized
    } catch (_) { return '' }
  }

  function clearAdminView() {
    adminOriginSession.value = ''
    adminViewContext.value = null
    adminViewInvalid.value = false
    try { localStorage.removeItem('admin_return_origin') } catch (_) {}
  }

  function syncViewedSession(target) {
    if (target === adminOriginSession.value) {
      authSessionUUID.value = target
      clearAdminView()
    }
    if (isUsableUUID(target)) sessionUUID.value = target
  }

  function getAdminOriginHeaderValue(target = sessionUUID.value) {
    return adminOriginSession.value && target !== adminOriginSession.value
      ? adminOriginSession.value : ''
  }

  function beginAdminView(target, targetUsername = '') {
    if (adminViewInvalid.value) throw new Error('管理员来源会话已失效，请重新登录')
    if (!isUsableUUID(target) || target === sessionUUID.value) return false
    if (!adminOriginSession.value) {
      if (!(permissions.value.view_all_sessions || isAdmin.value)) return false
      if (targetUsername && targetUsername === username.value) return false
      const origin = normalizeAdminOrigin(getAuthenticatedSessionHeaderValue())
      if (!origin) return false
      adminOriginSession.value = origin
      try { localStorage.setItem('admin_return_origin', origin) } catch (_) {}
    }
    sessionUUID.value = target
    sessionStorage.setItem('session_uuid', target)
    return true
  }

  function applyAdminViewContext(data, requestSession) {
    if (requestSession !== sessionUUID.value) return false
    const origin = adminOriginSession.value
    if (!origin || requestSession === origin) return false
    const context = data?.admin_view_context
    if (
      !context || normalizeAdminOrigin(context.session_id) !== origin || context.view_all_sessions !== true ||
      typeof context.auth_username !== 'string' || !context.auth_username.trim() ||
      typeof context.auth_group !== 'string' || !context.auth_group.trim()
    ) {
      adminViewContext.value = null
      adminViewInvalid.value = true
      try { localStorage.removeItem('admin_return_origin') } catch (_) {}
      return false
    }
    adminViewContext.value = { ...context, session_id: origin, auth_username: context.auth_username.trim(), auth_group: context.auth_group.trim() }
    authSessionUUID.value = origin
    adminViewInvalid.value = false
    permissions.value = { ...permissions.value, view_all_sessions: true }
    return true
  }

  function getAuthenticatedSessionHeaderValue() {
    if (adminViewContext.value && adminOriginSession.value) return adminOriginSession.value
    if (isUsableUUID(authSessionUUID.value)) return authSessionUUID.value
    if (isUsableUUID(sessionUUID.value)) return sessionUUID.value
    return ''
  }

  function getSessionHeaderValue(method) {
    if (adminOriginSession.value && isUsableUUID(sessionUUID.value)) return sessionUUID.value
    if (loginInProgress.value && isUsableUUID(authSessionUUID.value)) {
      return authSessionUUID.value
    }
    if (isUsableUUID(sessionUUID.value)) return sessionUUID.value

    const uuidFromUrl = getUUIDFromURL()
    if (isUsableUUID(uuidFromUrl) && !isUsableUUID(authSessionUUID.value)) {
      sessionUUID.value = uuidFromUrl
      return sessionUUID.value
    }

    sessionUUID.value = null
    if (isUsableUUID(authSessionUUID.value)) return authSessionUUID.value
    return ''
  }

  function getUUIDFromURL() {
    const match = window.location.pathname.match(/\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i)
    return match ? match[1] : null
  }

  function setLoginResult(data) {
    if (data.session_id) {
      sessionUUID.value = data.session_id
      sessionStorage.setItem('session_uuid', data.session_id)
    }
    if (data.auth_session_id) {
      authSessionUUID.value = data.auth_session_id
    } else if (data.session_id && !authSessionUUID.value) {
      authSessionUUID.value = data.session_id
    }
    isAuthenticated.value = true
    applyAuthInfo(data)
    loginInProgress.value = false
  }

  function activateSession(sessionId) {
    if (!isUsableUUID(sessionId)) return
    sessionUUID.value = sessionId
    if (!adminOriginSession.value) authSessionUUID.value = sessionId
    sessionStorage.setItem('session_uuid', sessionId)
  }

  function applyAuthInfo(data) {
    if (!data || data.success === false) return
    const actor = adminViewContext.value
    const identity = actor?.auth_username ?? data.auth_username ?? data.username
    if (identity !== undefined && identity !== username.value) {
      permissions.value = {}
      group.value = ''
      isAdmin.value = false
      displayName.value = ''
    }
    if (identity != null) username.value = identity
    if (actor?.auth_group != null || data.auth_group != null || data.group != null) {
      group.value = actor?.auth_group ?? data.auth_group ?? data.group
      isAdmin.value = ['admin', 'super_admin'].includes(group.value)
    } else if (data.is_admin !== undefined) isAdmin.value = !!data.is_admin
    if (data.is_authenticated !== undefined) isAuthenticated.value = !!data.is_authenticated
    if (data.is_guest !== undefined) isGuest.value = actor ? false : !!data.is_guest
    displayName.value = data.display_name ?? data.nickname ?? (displayName.value || username.value)
    const user = data.userInfo || data.user_info || data
    realName.value = user.real_name ?? user.realName ?? user.name ?? realName.value
    studentId.value = user.student_id ?? user.studentId ?? user.user_id ?? studentId.value
    if (data.avatar_url !== undefined) avatarUrl.value = data.avatar_url || ''
    if (data.theme) theme.value = data.theme
    if (data.theme_style) themeStyle.value = data.theme_style
    if (data.permissions && !actor) permissions.value = data.permissions
    if (actor) permissions.value = { ...permissions.value, view_all_sessions: true }
    if (data.session_limit_info !== undefined) sessionLimitInfo.value = data.session_limit_info
    if (data.token !== undefined) token.value = data.token || ''
  }

  async function loadPermissions(keys) {
    if (adminOriginSession.value && !adminViewContext.value) return
    const sessionId = getAuthenticatedSessionHeaderValue()
    if (!sessionId) return
    const entries = await Promise.all([...new Set(keys)].map(async permission => {
      try {
        const response = await fetch('/auth/check_permission', {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-Session-ID': sessionId },
          body: JSON.stringify({ permission }),
        })
        const result = await response.json()
        return [permission, !!(response.ok && result.success && result.has_permission)]
      } catch (_) { return [permission, false] }
    }))
    if (sessionId === getAuthenticatedSessionHeaderValue()) {
      permissions.value = { ...permissions.value, ...Object.fromEntries(entries) }
    }
  }

  function setBanned(banned, data = null) {
    isBanned.value = banned
    bannedData.value = data
  }

  function handleSessionExpired() {
    isAuthenticated.value = false
    sessionUUID.value = null

    if (window.Swal) {
      let seconds = 10
      window.Swal.fire({
        title: '会话已过期',
        html: `您的会话已过期，<b>${seconds}</b> 秒后将返回登录页面。`,
        icon: 'warning',
        timer: 10000,
        timerProgressBar: true,
        showConfirmButton: true,
        confirmButtonText: '立即返回',
        didOpen: () => {
          const b = window.Swal.getHtmlContainer()?.querySelector('b')
          if (b) {
            const interval = setInterval(() => {
              seconds--
              b.textContent = seconds
              if (seconds <= 0) clearInterval(interval)
            }, 1000)
          }
        },
      }).then(() => {
        window.location.href = getUiEntryPath()
      })
    } else {
      window.location.href = getUiEntryPath()
    }
  }

  function handleLoggedOutElsewhere(errorData) {
    isAuthenticated.value = false
    sessionUUID.value = null

    if (window.Swal) {
      let seconds = 120
      window.Swal.fire({
        title: '多设备登录检测',
        html: `您的账号已在其他设备登录，本设备已自动登出。<br><b>${seconds}</b> 秒后将跳转到登录页面。`,
        icon: 'warning',
        timer: 120000,
        timerProgressBar: true,
        showConfirmButton: true,
        confirmButtonText: '立即返回',
        allowOutsideClick: false,
        didOpen: () => {
          const b = window.Swal.getHtmlContainer()?.querySelector('b')
          if (b) {
            const interval = setInterval(() => {
              seconds--
              b.textContent = seconds
              if (seconds <= 0) clearInterval(interval)
            }, 1000)
          }
        },
      }).then(() => {
        window.location.href = getUiEntryPath()
      })
    } else {
      alert('您的账号已在其他设备登录，本设备已自动登出。')
      window.location.href = getUiEntryPath()
    }
  }

  function logout() {
    clearAdminView()
    sessionStorage.removeItem('session_uuid')
    sessionUUID.value = null
    authSessionUUID.value = null
    isAuthenticated.value = false
    isGuest.value = false
    isAdmin.value = false
    group.value = ''
    username.value = ''
    displayName.value = ''
    realName.value = ''
    studentId.value = ''
    avatarUrl.value = ''
    permissions.value = {}
    token.value = ''
    isBanned.value = false
    bannedData.value = null
    loginInProgress.value = false
  }

  return {
    sessionUUID, authSessionUUID, loginInProgress,
    isAuthenticated, isBanned, bannedData, isGuest, isAdmin, group,
    username, displayName, realName, studentId, avatarUrl, theme, themeStyle,
    permissions, sessionLimitInfo, token, hasSession,
    adminOriginSession, adminViewContext, adminViewInvalid,
    clearAdminView, syncViewedSession, beginAdminView, getAdminOriginHeaderValue, applyAdminViewContext,
    getAuthenticatedSessionHeaderValue, getSessionHeaderValue,
    setLoginResult, applyAuthInfo, activateSession, loadPermissions, setBanned, handleSessionExpired, handleLoggedOutElsewhere, logout,
  }
})
