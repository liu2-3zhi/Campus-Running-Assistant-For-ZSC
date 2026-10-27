const PROGRESS_FIELDS = ['current_point_index', 'point_index', 'current_position', 'current_lon', 'current_lat', 'lat', 'lng', 'target_sequence', 'checked_targets_count', 'current_distance', 'live_distance', 'duration', 'elapsed_time', 'live_time', 'progress']

export function mergeMapSnapshot(snapshot, latest) {
  const result = { ...snapshot }
  if (latest?.task_index === snapshot.task_index && Number(latest.current_point_index ?? -1) >= Number(snapshot.current_point_index ?? -1)) {
    for (const field of PROGRESS_FIELDS) if (latest[field] != null) result[field] = latest[field]
  }
  return result
}

export function createTaskMapRestorer({ app, loadSnapshot, getSession }) {
  let generation = 0
  let identity = ''
  let routeRestored = false
  let pending = null
  return {
    reset() { generation++; identity = ''; routeRestored = false; pending = null; app.activeTaskIndex = null; app.activeExecutionId = ''; app.activeExecutionStartedAt = 0 },
    async apply(status) {
      const index = status?.active_task_index
      if (!Number.isInteger(index) || index < 0) return
      if (status.execution_id && app.beginRunnerExecution?.({
        execution_id: status.execution_id,
        execution_started_at: status.execution_started_at ?? status.start_time,
        task_index: index,
      }) === false) return
      const session = getSession()
      app.activeTaskIndex = index
      const key = `${session}:${status.execution_id || status.start_time || ''}:${index}`
      if (key !== identity) {
        generation++
        identity = key
        routeRestored = false
        pending = null
        app.selectedTaskIndex = index
        app.runData = { task_index: index }
      }
      app.runData = { ...app.runData, status: status.status }
      const requestGeneration = generation
      const requestExecutionId = app.activeExecutionId || ''
      const position = status.current_position
      if (position) {
        const previous = app.runData || {}
        const processed = position.point_index ?? status.singleProcessedPoints
        if (processed == null || Number(processed) >= Number(previous.current_point_index ?? -1)) {
          app.runData = {
            ...previous, task_index: index,
            current_position: { lon: position.lon, lat: position.lat }, current_lon: position.lon, current_lat: position.lat,
            ...(processed != null ? { current_point_index: processed, point_index: processed } : {}),
            ...(position.target_sequence != null ? { target_sequence: position.target_sequence + 1 } : {}),
            ...(status.current_distance_m != null ? { current_distance: status.current_distance_m, live_distance: status.current_distance_m } : {}),
            ...(status.elapsed_time_s != null ? { duration: status.elapsed_time_s, elapsed_time: status.elapsed_time_s, live_time: status.elapsed_time_s } : {}),
          }
        }
      }
      if (routeRestored || status.route_ready === false) return
      if (pending) return pending
      pending = (async () => {
        const snapshot = await loadSnapshot(index)
        if (requestGeneration !== generation || session !== getSession() || app.selectedTaskIndex !== index || requestExecutionId !== (app.activeExecutionId || '')) return
        if (snapshot?.success && snapshot.details) {
          const details = { ...snapshot.details, task_index: index, status: app.runData?.status ?? status.status }
          if (details.target_sequence != null) details.target_sequence = Number(details.target_sequence) + 1
          app.runData = mergeMapSnapshot(details, app.runData)
          routeRestored = snapshot.route_ready === true
        }
      })().finally(() => { if (requestGeneration === generation) pending = null })
      return pending
    },
  }
}
