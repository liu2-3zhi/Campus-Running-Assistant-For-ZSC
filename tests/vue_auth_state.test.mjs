import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { ref, computed } = require('vue')
const { defineStore, createPinia, setActivePinia } = require('pinia')
const ORIGIN = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

function createAuth(fetch = async () => ({ ok: true, json: async () => ({ success: true, has_permission: true }) }), storedOrigin = '') {
  setActivePinia(createPinia())
  const values = new Map()
  if (storedOrigin) values.set('admin_return_origin', storedOrigin)
  const source = readFileSync(new URL('../frontend/src/stores/auth.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useAuthStore', 'const useAuthStore')
  const context = vm.createContext({ ref, computed, defineStore, fetch,
    window: { location: { pathname: '/' } },
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
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

test('view chains retain the earliest administrator and target business requests', () => {
  const { auth, values } = createAuth()
  auth.activateSession(ORIGIN)
  auth.applyAuthInfo({ auth_username: 'admin-a', auth_group: 'admin', permissions: { view_all_sessions: true } })
  assert.equal(auth.beginAdminView('target-b', 'user-b'), true)
  auth.applyAdminViewContext({ admin_view_context: { session_id: ORIGIN, auth_username: 'admin-a', auth_group: 'admin', view_all_sessions: true } }, 'target-b')
  auth.applyAuthInfo({ auth_username: 'user-b', auth_group: 'user', userInfo: { name: 'B' } })
  assert.equal(auth.username, 'admin-a')
  assert.equal(auth.group, 'admin')
  assert.equal(auth.realName, 'B')
  assert.equal(auth.beginAdminView('own-other-c', 'admin-a'), true)
  auth.loginInProgress = true
  assert.equal(auth.getSessionHeaderValue('get_initial_data'), 'own-other-c')
  assert.equal(auth.getAuthenticatedSessionHeaderValue(), ORIGIN)
  assert.equal(values.get('admin_return_origin'), ORIGIN)
  assert.equal(auth.getAdminOriginHeaderValue('own-other-c'), ORIGIN)
})

test('a late response cannot replace the current administrator view context', () => {
  const { auth } = createAuth()
  auth.activateSession(ORIGIN)
  auth.applyAuthInfo({ auth_username: 'admin-a', auth_group: 'admin', permissions: { view_all_sessions: true } })
  auth.beginAdminView('target-b', 'user-b')
  auth.beginAdminView('target-c', 'user-c')
  assert.equal(auth.applyAdminViewContext({ admin_view_context: { session_id: 'wrong', auth_username: 'other', view_all_sessions: true } }, 'target-b'), false)
  assert.equal(auth.adminOriginSession, ORIGIN)
  assert.equal(auth.adminViewInvalid, false)
})

test('an invalid origin clears persisted hints and prevents a token-switch fallback', () => {
  const { auth, values } = createAuth()
  auth.activateSession(ORIGIN)
  auth.applyAuthInfo({ auth_username: 'admin-a', auth_group: 'admin', permissions: { view_all_sessions: true } })
  auth.beginAdminView('target-b', 'user-b')
  auth.applyAdminViewContext({ success: true }, 'target-b')
  assert.equal(values.has('admin_return_origin'), false)
  assert.equal(auth.adminViewInvalid, true)
  assert.throws(() => auth.beginAdminView('target-c', 'user-c'), /来源.*失效/)
})

test('returning to the original administrator ends the view chain', () => {
  const { auth, values } = createAuth()
  auth.activateSession(ORIGIN)
  auth.applyAuthInfo({ auth_username: 'admin-a', auth_group: 'admin', permissions: { view_all_sessions: true } })
  auth.beginAdminView('target-b', 'user-b')
  auth.syncViewedSession(ORIGIN)
  assert.equal(auth.adminOriginSession, '')
  assert.equal(auth.getAuthenticatedSessionHeaderValue(), ORIGIN)
  assert.equal(values.has('admin_return_origin'), false)
})

test('an origin hint cannot load permissions before the server verifies the view', async () => {
  const calls = []
  const { auth } = createAuth(async url => { calls.push(url); return { ok: true, json: async () => ({ success: true, has_permission: true }) } })
  auth.activateSession(ORIGIN)
  auth.applyAuthInfo({ auth_username: 'admin-a', auth_group: 'admin', permissions: { view_all_sessions: true } })
  auth.beginAdminView('target-b', 'user-b')
  await auth.loadPermissions(['manage_users'])
  assert.deepEqual(calls, [])
  auth.applyAdminViewContext({ admin_view_context: { session_id: ORIGIN, auth_username: 'admin-a', auth_group: 'admin', view_all_sessions: true } }, 'target-b')
  await auth.loadPermissions(['manage_users'])
  assert.deepEqual(calls, ['/auth/check_permission'])
})

test('stored administrator origins use normalized UUIDv4 values only', () => {
  const valid = createAuth(undefined, ` ${ORIGIN.toUpperCase()} `)
  assert.equal(valid.auth.adminOriginSession, ORIGIN)
  assert.equal(valid.values.get('admin_return_origin'), ORIGIN)
  for (const value of ['junk', 'aaaaaaaa-aaaa-3aaa-8aaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-4aaa-7aaa-aaaaaaaaaaaa']) {
    const invalid = createAuth(undefined, value)
    assert.equal(invalid.auth.adminOriginSession, '')
    assert.equal(invalid.values.has('admin_return_origin'), false)
  }
})

test('administrator contexts require complete string identity fields', () => {
  for (const fields of [{ auth_username: '' }, { auth_username: [] }, { auth_group: '' }, { auth_group: null }]) {
    const { auth } = createAuth(undefined, ORIGIN)
    auth.activateSession('target-b')
    const context = { session_id: ORIGIN, auth_username: 'admin-a', auth_group: 'admin', view_all_sessions: true, ...fields }
    assert.equal(auth.applyAdminViewContext({ admin_view_context: context }, 'target-b'), false)
    assert.equal(auth.adminViewContext, null)
    assert.equal(auth.adminViewInvalid, true)
  }
})
