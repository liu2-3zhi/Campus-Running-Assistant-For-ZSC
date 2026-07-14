import { useAuthStore } from '@/stores/auth'
import { useNetworkStore } from '@/stores/network'

const NETWORK_RETRY_MAX = 3
const NETWORK_RETRY_DELAY_MS = 2000

export async function checkServerHealth() {
  try {
    const ctrl = new AbortController()
    const tid = setTimeout(() => ctrl.abort(), 5000)
    const res = await fetch('/health', { method: 'GET', cache: 'no-cache', signal: ctrl.signal })
    clearTimeout(tid)
    return res.ok
  } catch (_) {
    return false
  }
}

function getSessionHeaders(method) {
  const auth = useAuthStore()
  const sessionId = auth.getSessionHeaderValue(method)
  const headers = { 'Content-Type': 'application/json' }
  if (sessionId) headers['X-Session-ID'] = sessionId
  return headers
}

export async function callAPI(method, ...args) {
  const network = useNetworkStore()
  const auth = useAuthStore()

  if (network.isInErrorState) {
    throw new Error('网络错误状态中，请等待恢复')
  }

  const headers = getSessionHeaders(method)
  const body = JSON.stringify(
    args.length === 1 && typeof args[0] === 'object' && args[0] !== null && !Array.isArray(args[0])
      ? args[0]
      : args
  )

  let response
  try {
    response = await fetch(`/api/${method}`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body,
    })
  } catch (networkError) {
    console.error(`[API] 网络请求失败 (${method}):`, networkError)

    if (!network.retryInProgress) {
      network.retryInProgress = true

      const alive = await checkServerHealth()
      if (alive) {
        for (let attempt = 1; attempt <= NETWORK_RETRY_MAX; attempt++) {
          await new Promise(r => setTimeout(r, NETWORK_RETRY_DELAY_MS))
          try {
            response = await fetch(`/api/${method}`, {
              method: 'POST',
              headers,
              credentials: 'include',
              body,
            })
            console.info(`[API] 重试第 ${attempt} 次成功 (${method})`)
            network.retryInProgress = false
            break
          } catch (retryErr) {
            console.warn(`[API] 重试 ${attempt}/${NETWORK_RETRY_MAX} 失败 (${method})`)
            if (attempt === NETWORK_RETRY_MAX) {
              network.retryInProgress = false
              network.enterErrorState()
              network.showErrorDialog()
              throw retryErr
            }
          }
        }
      } else {
        network.retryInProgress = false
        network.enterErrorState()
        network.showErrorDialog()
        throw networkError
      }
    } else {
      throw networkError
    }
  }

  if (!response.ok) {
    let errorData = {}
    try {
      errorData = await response.json()
    } catch (_) {}

    if (response.status === 403 && errorData.message?.includes('账号已被封禁')) {
      network.enterErrorState()
      auth.setBanned(true, errorData)
      throw new Error('账号已被封禁')
    }

    if (
      response.status === 401 &&
      errorData.message?.includes('会话已过期或无效')
    ) {
      if ((method === 'get_theme_styles' && !auth.sessionUUID) || auth.loginInProgress) {
        throw new Error('会话已过期或无效')
      }
      auth.handleSessionExpired()
      throw new Error('会话已过期或无效')
    }

    if (errorData.need_login) {
      const errorMsg = errorData.message || '需要重新登录'
      if (errorData.logged_out_elsewhere && !auth.loginInProgress) {
        auth.handleLoggedOutElsewhere(errorData)
      } else if (!auth.loginInProgress) {
        if (window.Swal) {
          window.Swal.fire({ title: '需要重新登录', text: errorMsg, icon: 'warning', confirmButtonText: '返回登录' }).then(() => {
            window.location.href = '/'
          })
        }
        auth.isAuthenticated = false
        auth.sessionUUID = null
      }
      throw new Error(errorMsg)
    }

    throw new Error(errorData.message || `API错误: ${response.status}`)
  }

  return response.json()
}

export async function callRawAPI(url, method = 'POST', body = null) {
  const auth = useAuthStore()
  const headers = { 'Content-Type': 'application/json' }
  const sessionId = auth.getAuthenticatedSessionHeaderValue()
  if (sessionId) headers['X-Session-ID'] = sessionId

  const opts = { method, headers, credentials: 'include' }
  if (body !== null) opts.body = JSON.stringify(body)

  const response = await fetch(url, opts)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.message || `请求失败: ${response.status}`)
  }
  return response.json()
}
