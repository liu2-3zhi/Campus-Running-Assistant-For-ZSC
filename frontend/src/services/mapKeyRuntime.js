const RUNTIME_NAMESPACE = '__MAP_KEY_RUNTIME__'

let runtimeLoadPromise = null
let runtimeLoadVersion = ''

function getRuntimeScriptUrl(scriptUrl, runtimeVersion) {
  const baseUrl = scriptUrl || '/api/map_key_runtime.js'
  const version = String(runtimeVersion || '').trim()
  if (!version || /[?&]v=/.test(baseUrl)) return baseUrl
  return `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}v=${encodeURIComponent(version)}`
}

function loadRuntimeScript(scriptUrl, runtimeVersion) {
  const expectedVersion = String(runtimeVersion || '').trim()
  if (runtimeLoadPromise && runtimeLoadVersion === expectedVersion) {
    return runtimeLoadPromise
  }

  const runtime = window[RUNTIME_NAMESPACE]
  if (expectedVersion && runtime && runtime.version === expectedVersion) {
    return Promise.resolve()
  }

  runtimeLoadVersion = expectedVersion
  runtimeLoadPromise = new Promise((resolve, reject) => {
    const scripts = Array.from(document.querySelectorAll('script[data-map-key-runtime="1"]'))
    const existing = scripts.find((script) => (
      String(script.dataset.mapKeyRuntimeVersion || '') === expectedVersion
    ))
    if (existing) {
      if (!expectedVersion || window[RUNTIME_NAMESPACE]?.version === expectedVersion) {
        resolve()
      } else {
        reject(new Error('地图密钥运行时版本不匹配'))
      }
      return
    }
    const script = document.createElement('script')
    script.src = getRuntimeScriptUrl(scriptUrl, expectedVersion)
    script.async = true
    script.dataset.mapKeyRuntime = '1'
    script.dataset.mapKeyRuntimeVersion = expectedVersion
    script.onload = () => {
      if (expectedVersion && window[RUNTIME_NAMESPACE]?.version !== expectedVersion) {
        reject(new Error('地图密钥运行时版本不匹配'))
        return
      }
      resolve()
    }
    script.onerror = () => reject(new Error('地图密钥运行时脚本加载失败'))
    document.head.appendChild(script)
  }).catch((error) => {
    runtimeLoadPromise = null
    runtimeLoadVersion = ''
    throw error
  })
  return runtimeLoadPromise
}

export async function hydrateMapProviderSecrets(initialData) {
  if (!initialData || typeof initialData !== 'object') return initialData
  const keyBundle = initialData.map_provider_key_bundle
  if (!keyBundle || typeof keyBundle !== 'object') return initialData
  if (keyBundle.available === false) return initialData

  await loadRuntimeScript(keyBundle.runtime_script, keyBundle.runtime_version)
  const runtime = window[RUNTIME_NAMESPACE]
  if (!runtime || typeof runtime.decryptMapProviderKeys !== 'function') {
    throw new Error('地图密钥运行时不可用')
  }

  const decryptedProviders = await runtime.decryptMapProviderKeys(keyBundle)
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
