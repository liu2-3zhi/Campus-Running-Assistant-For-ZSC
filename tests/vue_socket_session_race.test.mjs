import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function setup(Swal) {
  const auth = { sessionUUID: 'B' }
  const clients = []
  const positions = []
  const source = readFileSync(new URL('../frontend/src/services/socket.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace(/export (function|const) /g, '$1 ')
  const runtime = vm.runInNewContext(`${source}\n({ connectWebSocket, disconnectWebSocket })`, {
    useAuthStore: () => auth,
    useAppStore: () => ({ handlePositionUpdate: data => positions.push(data) }),
    window: { Swal },
    io: () => {
      const client = { events: {}, connected: false, io: { opts: {} },
        connect() { this.connected = true }, disconnect() { this.connected = false; this.closed = true },
        on(event, callback) { this.events[event] = callback }, emit() {},
      }
      clients.push(client)
      return client
    },
    setInterval: () => 1, clearInterval() {}, console,
  })
  return { auth, clients, positions, runtime }
}

test('switching a reused Vue route ignores the departed socket and rebinds the target session', () => {
  const { auth, clients, positions, runtime } = setup()
  runtime.connectWebSocket()
  auth.sessionUUID = 'C'
  runtime.connectWebSocket()
  clients[0].events.runner_position_update_new({ task_index: 2 })
  clients[1].events.runner_position_update_new({ task_index: 5 })
  assert.equal(clients[0].closed, true)
  assert.deepEqual(positions, [{ task_index: 5 }])
  runtime.disconnectWebSocket()
})

const settle = () => new Promise(resolve => setImmediate(resolve))
const notice = (id, taskName = '体育课 <b>跑步</b>') => ({
  notice_id: id,
  task_name: taskName,
  message: '请联系学校 <img> 核实任务。',
})

function createSwal() {
  const shown = []
  let popup = null
  let acknowledge
  return {
    shown,
    fire(options) {
      assert.equal(popup, null, 'a task reminder interrupted the active task reminder')
      popup = {}
      shown.push(options)
      return new Promise(resolve => { acknowledge = resolve })
    },
    getPopup: () => popup,
    close() {
      popup = null
      acknowledge?.()
    },
  }
}

test('Vue shows task notices as plain text and queues distinct notices once per session', async () => {
  const Swal = createSwal()
  const { clients, runtime } = setup(Swal)
  runtime.connectWebSocket()
  const notify = clients[0].events.task_unavailable
  notify(notice('first'))
  notify(notice('first'))
  notify(notice('second', '另一个任务'))
  await settle()

  assert.equal(Swal.shown.length, 1)
  assert.equal(Swal.shown[0].icon, 'warning')
  assert.match(Swal.shown[0].titleText, /体育课 <b>跑步<\/b>/)
  assert.equal(Swal.shown[0].text, '请联系学校 <img> 核实任务。')
  assert.equal(Swal.shown[0].html, undefined)

  Swal.close()
  await settle()
  assert.equal(Swal.shown.length, 2)
  assert.match(Swal.shown[1].titleText, /另一个任务/)
  Swal.close()
  notify(notice('first'))
  await settle()
  assert.equal(Swal.shown.length, 2)
  runtime.disconnectWebSocket()
})

test('Vue drops queued departed-session task notices and allows notice ids in a new session', async () => {
  const Swal = createSwal()
  const { auth, clients, runtime } = setup(Swal)
  runtime.connectWebSocket()
  clients[0].events.task_unavailable(notice('same'))
  clients[0].events.task_unavailable(notice('queued-old', '旧任务'))
  await settle()
  assert.equal(Swal.shown.length, 1)

  auth.sessionUUID = 'C'
  runtime.connectWebSocket()
  clients[0].events.task_unavailable(notice('late-old', '迟到的旧任务'))
  clients[1].events.task_unavailable(notice('same', '当前任务'))
  await settle()

  assert.equal(Swal.shown.length, 2)
  assert.match(Swal.shown[1].titleText, /当前任务/)
  runtime.disconnectWebSocket()
})
