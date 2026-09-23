import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const legacy = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const socketService = readFileSync(new URL('../frontend/src/services/socket.js', import.meta.url), 'utf8')
const mainView = readFileSync(new URL('../frontend/src/views/MainView.vue', import.meta.url), 'utf8')
const multiView = readFileSync(new URL('../frontend/src/views/MultiAccountView.vue', import.meta.url), 'utf8')

test('Vue views expose websocket state and gate polling behind it', () => {
  assert.match(socketService, /export function isWebSocketConnected\(\)/)
  assert.match(socketService, /export function onWebSocketStatus\(listener\)/)
  assert.match(mainView, /onWebSocketStatus\(syncUserRefreshWithSocket\)/)
  assert.match(mainView, /if \(!viewMounted \|\| isWebSocketConnected\(\)\) return/)
  assert.match(multiView, /onWebSocketStatus\(syncAutoRefreshWithSocket\)/)
  assert.match(multiView, /isWebSocketConnected\(\)[\s\S]*requestId !== autoRefreshRequestId/)
})

test('legacy polling is a websocket fallback and rejects stale responses', () => {
  assert.doesNotMatch(legacy, /^setInterval\(refreshUserList, 30000\);$/m)
  assert.match(legacy, /function startUserListPollingFallback\(\)/)
  assert.match(legacy, /socket\.on\("connect", \(\) => \{[\s\S]*syncUserListPollingBySocketState\(\)/)
  assert.match(legacy, /socket\.on\("disconnect", \(reason\) => \{[\s\S]*syncMultiAccountAutoRefreshBySocketState\(\)/)
  assert.match(legacy, /refreshGeneration !== multiAccountAutoRefreshGeneration/)
  assert.match(legacy, /markMultiAccountRealtimeUpdate\(\)/)
})
