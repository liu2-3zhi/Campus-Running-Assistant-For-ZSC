import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function isUsableUUID(val) {
  if (typeof val !== 'string' || val.length === 0) return false
  const lower = val.trim().toLowerCase()
  return lower !== '' && lower !== 'none' && lower !== 'null' && lower !== 'undefined'
}

export const useAuthStore = defineStore('auth', () => {
  const sessionUUID = ref(null)
  const authSessionUUID = ref(null)
  const loginInProgress = ref(false)
  const isAuthenticated = ref(false)
  const isBanned = ref(false)
  const bannedData = ref(null)
  const isGuest = ref(false)
  const isAdmin = ref(false)

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

  function getAuthenticatedSessionHeaderValue() {
    if (isUsableUUID(authSessionUUID.value)) return authSessionUUID.value
    if (isUsableUUID(sessionUUID.value)) return sessionUUID.value
    return ''
  }

  function getSessionHeaderValue(method) {
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
    username.value = data.username || ''
    displayName.value = data.display_name || data.username || ''
    realName.value = data.real_name || data.name || ''
    studentId.value = data.student_id || data.user_id || ''
    avatarUrl.value = data.avatar_url || ''
    theme.value = data.theme || 'light'
    themeStyle.value = data.theme_style || 'default'
    isGuest.value = data.is_guest || false
    isAdmin.value = data.is_admin || false
    permissions.value = data.permissions || {}
    sessionLimitInfo.value = data.session_limit_info || null
    token.value = data.token || ''
    loginInProgress.value = false
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
        window.location.href = '/'
      })
    } else {
      window.location.href = '/'
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
        window.location.href = '/'
      })
    } else {
      alert('您的账号已在其他设备登录，本设备已自动登出。')
      window.location.href = '/'
    }
  }

  function logout() {
    sessionStorage.removeItem('session_uuid')
    sessionUUID.value = null
    authSessionUUID.value = null
    isAuthenticated.value = false
    isGuest.value = false
    isAdmin.value = false
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
    isAuthenticated, isBanned, bannedData, isGuest, isAdmin,
    username, displayName, realName, studentId, avatarUrl, theme, themeStyle,
    permissions, sessionLimitInfo, token, hasSession,
    getAuthenticatedSessionHeaderValue, getSessionHeaderValue,
    setLoginResult, setBanned, handleSessionExpired, handleLoggedOutElsewhere, logout,
  }
})
