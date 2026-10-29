export const MAP_PROVIDER_OPTIONS = [
  { value: 'amap', label: '高德地图' },
  { value: 'tencent', label: '腾讯地图' },
  { value: 'tianditu', label: '天地图' },
  { value: 'baidu', label: '百度地图' },
]

export const MAP_PROFILE_FIELDS = {
  amap: [{ key: 'js_key', label: 'JS Key' }, { key: 'security_js_code', label: '安全密钥（选填）' }],
  tencent: [{ key: 'map_key', label: '地图 Key' }],
  tianditu: [{ key: 'token', label: 'Token' }],
  baidu: [{ key: 'ak', label: 'AK' }],
}

const providerName = provider => MAP_PROVIDER_OPTIONS.find(option => option.value === provider)?.label || provider

export function createMapConfigProfile(provider = 'amap', configs = []) {
  if (!MAP_PROFILE_FIELDS[provider]) throw new Error('不支持的地图供应商')
  const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  const count = configs.filter(config => config.provider === provider).length + 1
  return {
    id: `config-${suffix}`, name: `${providerName(provider)} ${count}`, provider,
    ...Object.fromEntries(MAP_PROFILE_FIELDS[provider].map(field => [field.key, ''])),
    backend_page_origin: '',
  }
}

export function normalizeMapConfigProfiles(map = {}) {
  let configs
  if (Array.isArray(map.configs)) {
    configs = map.configs.map(config => ({ ...config }))
  } else {
    const aliases = { amap: 'amap_js_key', tencent: 'tencent_map_key', tianditu: 'tianditu_token', baidu: 'baidu_map_ak' }
    configs = MAP_PROVIDER_OPTIONS.map(({ value: provider, label }) => {
      const source = map.providers?.[provider] || {}
      return {
        id: `legacy-${provider}`, name: `${label} 1`, provider,
        ...Object.fromEntries(MAP_PROFILE_FIELDS[provider].map((field, index) => [field.key, String(source[field.key] || (index === 0 ? map[aliases[provider]] : '') || '')])),
        backend_page_origin: String(source.backend_page_origin || ''),
      }
    })
  }
  if (!configs.length) configs.push(createMapConfigProfile())
  const fallback = configs.find(config => config.provider === map.provider)?.id || configs[0].id
  const selected = id => configs.some(config => config.id === id) ? id : fallback
  return { configs, frontend_config_id: selected(map.frontend_config_id), backend_config_id: selected(map.backend_config_id) }
}

export function moveMapConfigProfile(configs, id, targetIndex) {
  const sourceIndex = configs.findIndex(config => config.id === id)
  if (sourceIndex < 0) return configs
  const result = configs.slice()
  const [profile] = result.splice(sourceIndex, 1)
  result.splice(Math.max(0, Math.min(result.length, targetIndex)), 0, profile)
  return result
}

export function removeMapConfigProfile(map, id) {
  if (map.configs.length <= 1) throw new Error('请至少保留一份地图配置')
  const configs = map.configs.filter(config => config.id !== id)
  const replacement = configs[0].id
  return {
    configs,
    frontend_config_id: map.frontend_config_id === id ? replacement : map.frontend_config_id,
    backend_config_id: map.backend_config_id === id ? replacement : map.backend_config_id,
  }
}

export function serializeMapConfigProfiles(map, normalizeOrigin = value => String(value || '').trim()) {
  if (!Array.isArray(map.configs) || !map.configs.length) throw new Error('请至少保留一份地图配置')
  const ids = new Set()
  const configs = map.configs.map(config => {
    const id = String(config.id || '')
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(id) || ids.has(id)) throw new Error('地图配置标识无效或重复，请重新加载配置')
    ids.add(id)
    if (!MAP_PROFILE_FIELDS[config.provider]) throw new Error('不支持的地图供应商')
    const rawName = String(config.name || '')
    const name = rawName.trim()
    if (!name || Array.from(name).length > 100 || /[\x00-\x1f]/.test(rawName)) throw new Error('地图配置名称须为 1 至 100 个字符，且不能包含控制字符')
    return {
      id, name, provider: config.provider,
      ...Object.fromEntries(MAP_PROFILE_FIELDS[config.provider].map(field => [field.key, String(config[field.key] || '').trim()])),
      backend_page_origin: normalizeOrigin(config.backend_page_origin),
    }
  })
  for (const field of ['frontend_config_id', 'backend_config_id']) {
    if (!ids.has(map[field])) throw new Error(`请选择有效的${field === 'frontend_config_id' ? '前端' : '后端'}地图配置`)
  }
  return { configs, frontend_config_id: map.frontend_config_id, backend_config_id: map.backend_config_id }
}
