import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('switching a reused Vue route ignores the departed socket and rebinds the target session', () => {
  const auth = { sessionUUID: 'B' }
  const clients = []
  const positions = []
  const source = readFileSync(new URL('../frontend/src/services/socket.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace(/export (function|const) /g, '$1 ')
  const runtime = vm.runInNewContext(`${source}\n({ connectWebSocket, disconnectWebSocket })`, {
    useAuthStore: () => auth,
    useAppStore: () => ({ handlePositionUpdate: data => positions.push(data) }),
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
  runtime.connectWebSocket()
  auth.sessionUUID = 'C'
  runtime.connectWebSocket()
  clients[0].events.runner_position_update_new({ task_index: 2 })
  clients[1].events.runner_position_update_new({ task_index: 5 })
  assert.equal(clients[0].closed, true)
  assert.deepEqual(positions, [{ task_index: 5 }])
  runtime.disconnectWebSocket()
})
