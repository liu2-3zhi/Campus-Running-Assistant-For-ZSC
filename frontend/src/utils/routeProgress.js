export function routePoint(point) {
  const lng = Number(Array.isArray(point) ? point[0] : point?.lng ?? point?.lon)
  const lat = Number(Array.isArray(point) ? point[1] : point?.lat)
  return Number.isFinite(lng) && Number.isFinite(lat) && (lng !== 0 || lat !== 0) ? [lng, lat] : null
}

export const ROUTE_COLORS = { completed: '#9ca3af', current: '#2563eb', remaining: '#ef4444' }

// All geometry stays in business GCJ-02. SDK adapters convert only when displaying it.
export function buildTaskRoutePresentation(data = {}) {
  const route = (data.run_coords || []).map(routePoint)
  let processed = Math.max(0, Math.min(route.length, Number(data.current_point_index ?? data.point_index ?? 0) || 0))
  const targets = (data.target_points || []).map(routePoint)
  let searchStart = 0
  const targetIndices = targets.map(target => {
    if (!target) return -1
    let best = -1
    let distance = Infinity
    for (let i = searchStart; i < route.length; i++) {
      if (!route[i]) continue
      const d = (route[i][0] - target[0]) ** 2 + (route[i][1] - target[1]) ** 2
      if (d < distance) { best = i; distance = d }
      if (d < 1e-14) break
    }
    if (best >= 0) searchStart = best + 1
    return best
  })
  const explicit = routePoint(data.current_position) || routePoint({ lng: data.current_lon ?? data.lng, lat: data.current_lat ?? data.lat })
  if (data.current_point_index == null && data.point_index == null && explicit) {
    const start = Math.max(0, targetIndices[Math.max(0, Number(data.target_sequence || 1) - 2)] || 0)
    let nearest = start
    let distance = Infinity
    for (let i = start; i < route.length; i++) {
      if (!route[i]) continue
      const d = (route[i][0] - explicit[0]) ** 2 + (route[i][1] - explicit[1]) ** 2
      if (d < distance) { nearest = i; distance = d }
    }
    processed = nearest + 1
  }
  const progress = processed - 1
  const nextTarget = targetIndices.find(index => index > progress) ?? route.length - 1
  const segments = []
  let current = null
  let gap = 0
  for (let i = 1; i < route.length; i++) {
    if (!route[i - 1] || !route[i]) { current = null; gap++; continue }
    const role = data.status === 1 || data.status === 'completed' || processed >= route.length || i <= progress ? 'completed' : i <= nextTarget && processed > 0 ? 'current' : 'remaining'
    if (!current || current.role !== role) {
      current = { id: `route-${gap}-${role}`, role, coords: [route[i - 1], route[i]] }
      segments.push(current)
    } else current.coords.push(route[i])
  }
  const names = String(data.target_point_names || '').split('|')
  const checkpoints = targets.flatMap((coords, index) => coords ? [{
    id: `target-${index}`, coords, title: names[index] || `点 ${index + 1}`,
    role: data.status === 1 || data.status === 'completed' || (targetIndices[index] >= 0 && targetIndices[index] <= progress) ? 'completed'
      : targetIndices[index] === nextTarget && processed > 0 ? 'current' : 'remaining',
  }] : [])
  return { segments, checkpoints, runner: explicit || (processed > 0 ? route[progress] : null) }
}
