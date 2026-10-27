import { useAuthStore } from '@/stores/auth'

const RUNTIME_NAMESPACE = '__MAP_KEY_RUNTIME__'

let runtimeLoadPromise = null
let runtimeLoadContext = ''
let runtimeLoadGeneration = 0

function getRuntimeScriptUrl(scriptUrl, runtimeVersion, sessionId) {
  const baseUrl = scriptUrl || '/api/map_key_runtime.js'
  const version = String(runtimeVersion || '').trim()
  const params = []
  if (version && !/[?&]v=/.test(baseUrl)) {
    params.push(`v=${encodeURIComponent(version)}`)
  }
  if (sessionId && !/[?&]session_id=/.test(baseUrl)) {
    params.push(`session_id=${encodeURIComponent(sessionId)}`)
  }
  if (!params.length) return baseUrl
  return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}${params.join('&')}`
}

function loadRuntimeScript(scriptUrl, runtimeVersion, sessionId, originSessionId, assertCurrentContext) {
  const expectedVersion = String(runtimeVersion || '').trim()
  const contextKey = JSON.stringify([expectedVersion, sessionId, originSessionId])
  if (runtimeLoadPromise && runtimeLoadContext === contextKey) {
    return runtimeLoadPromise
  }

  const runtime = window[RUNTIME_NAMESPACE]
  if (expectedVersion && runtime && runtime.version === expectedVersion) {
    return Promise.resolve()
  }

  runtimeLoadContext = contextKey
  const generation = ++runtimeLoadGeneration
  runtimeLoadPromise = (async () => {
    const headers = { 'X-Session-ID': sessionId }
    if (originSessionId) headers['X-Admin-Origin-Session-ID'] = originSessionId
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    let scriptText
    try {
      const response = await fetch(getRuntimeScriptUrl(scriptUrl, expectedVersion, sessionId), {
        credentials: 'include', cache: 'no-store', headers, signal: controller.signal,
      })
      if (!response.ok) throw new Error('地图密钥运行时脚本加载失败')
      scriptText = await response.text()
    } finally {
      clearTimeout(timeout)
    }
    assertCurrentContext()
    if (generation !== runtimeLoadGeneration) throw new Error('地图密钥运行时会话已切换')
    const scripts = Array.from(document.querySelectorAll('script[data-map-key-runtime="1"]'))
    scripts.forEach((script) => script.remove())
    const script = document.createElement('script')
    script.textContent = scriptText
    script.dataset.mapKeyRuntime = '1'
    script.dataset.mapKeyRuntimeVersion = expectedVersion
    document.head.appendChild(script)
    if (expectedVersion && window[RUNTIME_NAMESPACE]?.version !== expectedVersion) {
      script.remove()
      throw new Error('地图密钥运行时版本不匹配')
    }
  })().catch((error) => {
    if (generation === runtimeLoadGeneration) {
      runtimeLoadPromise = null
      runtimeLoadContext = ''
    }
    throw error
  })
  return runtimeLoadPromise
}

export async function hydrateMapProviderSecrets(initialData) {
  if (!initialData || typeof initialData !== 'object') return initialData
  const keyBundle = initialData.map_provider_key_bundle
  if (!keyBundle || typeof keyBundle !== 'object') return initialData
  if (keyBundle.available === false) return initialData

  const auth = useAuthStore()
  const getBusinessSession = () => auth.getSessionHeaderValue?.('get_initial_data') || auth.getAuthenticatedSessionHeaderValue()
  const sessionId = getBusinessSession()
  const originSessionId = auth.getAdminOriginHeaderValue?.(sessionId) || ''
  const assertCurrentContext = () => {
    if (getBusinessSession() !== sessionId || (auth.getAdminOriginHeaderValue?.(sessionId) || '') !== originSessionId) {
      throw new Error('地图密钥运行时会话已切换')
    }
  }
  await loadRuntimeScript(
    keyBundle.runtime_script,
    keyBundle.runtime_version,
    sessionId,
    originSessionId,
    assertCurrentContext,
  )
  assertCurrentContext()
  const runtime = window[RUNTIME_NAMESPACE]
  if (!runtime || typeof runtime.decryptMapProviderKeys !== 'function') {
    throw new Error('地图密钥运行时不可用')
  }

  const decryptedProviders = await runtime.decryptMapProviderKeys(keyBundle, sessionId, originSessionId)
  assertCurrentContext()
  const nextProviders = { ...(initialData.map_providers || {}) }
  Object.entries(decryptedProviders || {}).forEach(([provider, secrets]) => {
    const current = nextProviders[provider]
    nextProviders[provider] = {
      ...(current && typeof current === 'object' ? current : {}),
      ...(secrets && typeof secrets === 'object' ? secrets : {}),
    }
  })

  return {
    ...initialData,
    map_providers: nextProviders,
  }
}
