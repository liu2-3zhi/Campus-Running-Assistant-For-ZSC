import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { ref, computed } = require('vue')
const { defineStore, createPinia, setActivePinia } = require('pinia')

function createAuth(fetch = async () => ({ ok: true, json: async () => ({ success: true, has_permission: true }) })) {
  setActivePinia(createPinia())
  const values = new Map()
  const source = readFileSync(new URL('../frontend/src/stores/auth.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useAuthStore', 'const useAuthStore')
  const context = vm.createContext({ ref, computed, defineStore, fetch,
    window: { location: { pathname: '/' } },
    sessionStorage: { setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
  })
  return { auth: vm.runInContext(source + '\nuseAuthStore()', context), values }
}

test('system login reads the actual backend identity and retains it through school login', () => {
  const { auth } = createAuth()
  auth.setLoginResult({ auth_session_id: 'system-session', auth_username: 'reviewer', group: 'super_admin' })
  assert.equal(auth.username, 'reviewer')
  assert.equal(auth.group, 'super_admin')
  assert.equal(auth.isAdmin, true)
  auth.setLoginResult({ success: true, userInfo: { name: '示例学生', studentId: 'student-001' } })
  assert.equal(auth.username, 'reviewer')
  assert.equal(auth.isAdmin, true)
  assert.equal(auth.realName, '示例学生')
  assert.equal(auth.studentId, 'student-001')
})

test('restored initial data updates group and clears a previous admin identity', () => {
  const { auth } = createAuth()
  auth.setLoginResult({ auth_username: 'admin-fixture', group: 'admin' })
  auth.applyAuthInfo({ is_authenticated: true, auth_username: 'guest', auth_group: 'guest', is_guest: true })
  assert.equal(auth.username, 'guest')
  assert.equal(auth.group, 'guest')
  assert.equal(auth.isAdmin, false)
  assert.equal(auth.isGuest, true)
})

test('selected session is persisted and used for both business and authenticated requests', () => {
  const { auth, values } = createAuth()
  auth.activateSession('selected-session')
  assert.equal(auth.getSessionHeaderValue('get_initial_data'), 'selected-session')
  assert.equal(auth.getAuthenticatedSessionHeaderValue(), 'selected-session')
  assert.equal(values.get('session_uuid'), 'selected-session')
})

test('permission state follows the backend per-key response', async () => {
  const { auth } = createAuth(async (url, options) => ({ ok: true, json: async () => ({ success: true, has_permission: JSON.parse(options.body).permission === 'modify_config' }) }))
  auth.activateSession('selected-session')
  await auth.loadPermissions(['modify_config', 'manage_users'])
  assert.equal(auth.permissions.modify_config, true)
  assert.equal(auth.permissions.manage_users, false)
})
