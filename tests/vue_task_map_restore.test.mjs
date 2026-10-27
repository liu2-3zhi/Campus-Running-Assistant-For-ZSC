import test from 'node:test'
import assert from 'node:assert/strict'
import { createTaskMapRestorer } from '../frontend/src/utils/taskMapRestore.js'
import { buildTaskRoutePresentation } from '../frontend/src/utils/routeProgress.js'

test('read-only route restore waits for generated geometry and retains in-flight newer progress', async () => {
  const app = { selectedTaskIndex: 0, runData: { run_coords: [[1, 1]] } }
  let finish
  let calls = 0
  const restorer = createTaskMapRestorer({ app, getSession: () => 'C', loadSnapshot: () => { calls++; return new Promise(resolve => { finish = resolve }) } })
  await restorer.apply({ start_time: 1, active_task_index: 5, route_ready: false })
  assert.equal(calls, 0)
  assert.equal(app.selectedTaskIndex, 5)
  assert.equal(app.runData.run_coords, undefined)
  const pending = restorer.apply({ start_time: 1, active_task_index: 5, route_ready: true })
  app.runData = { ...app.runData, current_point_index: 4, current_position: { lon: 114, lat: 22 } }
  finish({ success: true, route_ready: true, details: { run_coords: [[113, 22], [114, 22]], current_point_index: 1 } })
  await pending
  assert.equal(app.runData.current_point_index, 4)
  assert.equal(app.runData.run_coords.length, 2)
  await restorer.apply({ start_time: 1, active_task_index: 5, route_ready: true })
  assert.equal(calls, 1, 'position polling must not reload geometry')
})

test('old task and old session snapshots cannot overwrite the current task', async () => {
  const app = { selectedTaskIndex: 0, runData: null }
  let session = 'B'
  const requests = []
  const restorer = createTaskMapRestorer({ app, getSession: () => session, loadSnapshot: index => new Promise(resolve => requests.push({ index, resolve })) })
  const old = restorer.apply({ start_time: 1, active_task_index: 2, route_ready: true })
  session = 'C'
  const current = restorer.apply({ start_time: 1, active_task_index: 5, route_ready: true })
  requests[1].resolve({ success: true, route_ready: true, details: { run_name: 'new', run_coords: [[1, 2]] } })
  await current
  requests[0].resolve({ success: true, route_ready: true, details: { run_name: 'old', run_coords: [[3, 4]] } })
  await old
  assert.equal(app.runData.run_name, 'new')
  assert.equal(app.selectedTaskIndex, 5)
})

test('a snapshot awaiting the previous execution cannot overwrite a same-task websocket restart', async () => {
  const app = { selectedTaskIndex: 2, activeExecutionId: 'old', runData: null }
  const requests = []
  const restorer = createTaskMapRestorer({ app, getSession: () => 'C', loadSnapshot: () => new Promise(resolve => requests.push(resolve)) })
  const old = restorer.apply({ execution_id: 'old', status: 'running', active_task_index: 2, route_ready: true })
  app.activeExecutionId = 'new'
  app.runData = { task_index: 2, execution_id: 'new', status: 'running', current_point_index: 0 }
  requests[0]({ success: true, route_ready: true, details: { current_point_index: 90, run_coords: [[113, 22], [114, 22]] } })
  await old
  assert.equal(app.runData.execution_id, 'new')
  assert.equal(app.runData.current_point_index, 0)
  assert.equal(app.runData.run_coords, undefined)

  const current = restorer.apply({ execution_id: 'new', status: 'running', active_task_index: 2, route_ready: true })
  requests[1]({ success: true, route_ready: true, details: { current_point_index: 0, run_coords: [[115, 23], [116, 23]] } })
  await current
  assert.equal(app.runData.current_point_index, 0)
  assert.deepEqual(app.runData.run_coords, [[115, 23], [116, 23]])
})

test('rerunning a completed task starts fresh and does not inherit completed coloring', async () => {
  const app = { selectedTaskIndex: 0, runData: { task_index: 0, current_point_index: 4, status: 1 } }
  const restorer = createTaskMapRestorer({ app, getSession: () => 'C', loadSnapshot: async () => ({ success: true, route_ready: true,
    details: { status: 1, current_point_index: 0, run_coords: [[113, 22], [114, 22], [115, 22], [116, 22]], target_points: [[113, 22], [116, 22]] },
  }) })
  await restorer.apply({ start_time: 2, status: 'running', active_task_index: 0, route_ready: true })
  await restorer.apply({ start_time: 2, status: 'running', active_task_index: 0, route_ready: true, current_position: { lon: 114, lat: 22, point_index: 2 } })
  assert.equal(app.runData.current_point_index, 2)
  assert.equal(app.runData.status, 'running')
  assert.ok(buildTaskRoutePresentation(app.runData).segments.some(segment => segment.role === 'current'))
})

test('route progress retains discontinuities, loops and business coordinates', () => {
  const coords = [[113, 22], [114, 22], [113, 22], [114, 22], [0, 0], [115, 22], [116, 22]]
  const task = { run_coords: coords, target_points: [[113, 22], [114, 22], [113, 22], [116, 22]], current_point_index: 3 }
  const before = JSON.stringify(task)
  const result = buildTaskRoutePresentation(task)
  assert.equal(result.runner[0], 113)
  assert.ok(result.segments.some(segment => segment.role === 'completed'))
  assert.ok(result.segments.some(segment => segment.role === 'current'))
  assert.ok(result.segments.every(segment => !segment.coords.some(point => point[0] === 0)))
  assert.ok(result.segments.every(segment => !(segment.coords.some(point => point[0] === 114) && segment.coords.some(point => point[0] === 115))))
  assert.equal(JSON.stringify(task), before)
})
