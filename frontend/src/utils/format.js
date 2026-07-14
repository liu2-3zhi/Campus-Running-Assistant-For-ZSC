export function formatDistance(meters) {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(2)} km`
  }
  return `${Math.round(meters)} m`
}

export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatSpeed(kmPerHour) {
  if (!kmPerHour) return '0.00 km/h'
  return `${kmPerHour.toFixed(2)} km/h`
}

export function formatPace(minPerKm) {
  if (!minPerKm || minPerKm === Infinity) return "--'--\""
  const m = Math.floor(minPerKm)
  const s = Math.round((minPerKm - m) * 60)
  return `${m}'${String(s).padStart(2, '0')}"`
}

export function formatDateTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`
  return formatDateTime(dateStr)
}

export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}
