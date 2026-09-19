export function taskName(task, index = 0) {
  return task?.run_name || task?.name || task?.task_name || `任务 ${index + 1}`
}

export function taskStatus(task = {}) {
  if (task.info_text === '已过期') return { label: '已过期', icon: '⛔', className: 'text-red-600' }
  if (task.status === 1 || task.status === '1' || task.status === 'completed') {
    return { label: '已完成', icon: '✅', className: 'text-emerald-600' }
  }
  if (String(task.info_text || '').startsWith('开始于')) return { label: '未开始', icon: '⏳', className: 'text-slate-600' }
  if (task.status === 'running') return { label: '运行中', icon: '▶', className: 'text-green-600' }
  if (task.status === 'paused') return { label: '已暂停', icon: '⏸', className: 'text-amber-600' }
  return { label: '未完成', icon: '🕒', className: 'text-amber-600' }
}

export function taskPathStatus(task) {
  return task.run_coords?.length ? '已生成' : task.draft_coords?.length ? '草稿' : '无路径'
}

export function taskPoints(details = {}) {
  const names = String(details.target_point_names || '').split('|')
  return (details.target_points || details.checkpoints || details.points || []).map((point, index) => ({
    name: names[index] || point.name || point.label || `打卡点${index + 1}`,
    lng: Array.isArray(point) ? point[0] : (point.lng ?? point.lon),
    lat: Array.isArray(point) ? point[1] : point.lat,
    reached: Number(details.target_sequence || 1) > index + 1,
    current: Number(details.target_sequence || 1) === index + 1,
  }))
}

export async function loadSelectedTask(app, index, api, isDrawing = false) {
  if (index < 0 || index >= app.tasks.length) return false
  if (index === app.selectedTaskIndex && app.runData) return true
  if (app.isRunning && index !== app.selectedTaskIndex) throw new Error('任务执行中，无法切换任务！请先停止当前任务。')
  if (isDrawing) throw new Error('请先结束当前路径绘制！')

  const task = app.tasks[index]
  let details = task
  if (task.info_text !== '离线') {
    const status = await api.callRawAPI('/api/background_task/status', 'GET')
    if (['running', 'paused'].includes(status?.task_status?.status) && index !== app.selectedTaskIndex) {
      app.isRunning = true
      throw new Error('任务执行中，无法切换任务！请先停止当前任务。')
    }
    const result = await api.callAPI('get_task_details', index)
    if (!result?.success || !result.details) throw new Error(result?.message || '获取任务详情失败')
    details = result.details
  }
  app.selectedTaskIndex = index
  app.runData = { ...details, task_index: index }
  app.tasks[index] = { ...task, ...details }
  return true
}

export function applyPathResult(app, result) {
  if (result?.success === false) throw new Error(result.message || '路径操作失败')
  if (!app.runData) return
  app.runData = {
    ...app.runData,
    ...(result.run_coords ? { run_coords: result.run_coords } : {}),
    ...(result.total_dist != null ? { total_run_distance_m: result.total_dist } : {}),
    ...(result.total_time != null ? { total_run_time_s: result.total_time } : {}),
  }
  if (app.tasks[app.selectedTaskIndex]) app.tasks[app.selectedTaskIndex] = { ...app.tasks[app.selectedTaskIndex], ...app.runData }
}

export function clearTaskPath(app) {
  if (app.runData) app.runData = {
    ...app.runData, draft_coords: [], run_coords: [], total_run_distance_m: 0,
    total_run_time_s: 0, total_distance: 0, total_time: 0, progress: 0,
    target_sequence: 0, isInTargetZone: false,
  }
  if (app.tasks[app.selectedTaskIndex]) app.tasks[app.selectedTaskIndex] = { ...app.tasks[app.selectedTaskIndex], draft_coords: [], run_coords: [] }
}
