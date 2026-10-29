import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const begin = source.indexOf('async function onConfirmAutoGenerate(')
const end = source.indexOf('async function loadHistory(', begin)
assert.ok(begin >= 0 && end > begin)

function fixture(response) {
  const requests = []
  const alerts = []
  const controls = new Map([
    ['min-time-input', { value: '10' }], ['max-time-input', { value: '15' }],
    ['min-dist-input', { value: '1200' }],
    ['auto-gen-modal', { classList: { add() {}, remove() {} } }],
  ])
  const run = { target_points: [{ lng: 113.4, lat: 22.5 }, { lng: 113.41, lat: 22.51 }] }
  const context = vm.createContext({
    currentRunData: run, selectedTaskIndex: 0,
    singleProcessedPoints: 1, singleTotalPoints: 1,
    document: { body: { classList: { remove() {} } } },
    $: id => controls.get(id), logMessage_Info() {},
    drawOnMap() {}, updateDashboard() {}, renderTaskList() {}, updateSingleProgress() {},
    showModalAlert: text => alerts.push(text),
    callPythonAPI: async (...args) => { requests.push(args); return response },
    getMapProviderDisplayName() { throw new Error('Frontend display provider cannot choose the planner') },
  })
  vm.runInContext(source.slice(begin, end), context)
  return { context, requests, alerts, run }
}

test('legacy auto generation requests the backend planner without loading a browser map SDK', async () => {
  const path = [[113.4, 22.5, 0], [113.401, 22.501, 1000]]
  const state = fixture({ success: true, run_coords: path, total_dist: 1200, total_time: 600, notices: [] })
  await state.context.onConfirmAutoGenerate()
  assert.equal(state.requests.length, 1)
  assert.equal(state.requests[0][0], 'auto_generate_path_with_provider')
  assert.deepEqual(JSON.parse(JSON.stringify(state.requests[0][1])), { min_t_m: 10, max_t_m: 15, min_d_m: 1200 })
  assert.equal(state.run.run_coords, path)
  assert.equal(state.run.total_run_distance_m, 1200)
  assert.equal(state.context.singleTotalPoints, 2)
  assert.equal(state.alerts.length, 0)
})

test('backend planning failure does not fall back to browser-side planning', async () => {
  const state = fixture({ success: false, message: '测试规划失败' })
  await state.context.onConfirmAutoGenerate()
  assert.equal(state.requests.length, 1)
  assert.match(state.alerts[0], /测试规划失败/)
  assert.equal(state.run.run_coords, undefined)
})
