import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { ref, computed, reactive, watch, nextTick } = require('vue')

function setup(name, overrides = {}) {
  const source = fs.readFileSync(new URL(`../frontend/src/components/admin/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const context = vm.createContext({
    ref, computed, reactive, watch, URLSearchParams, onMounted() {},
    defineProps: () => ({ visible: false }), defineEmits: () => () => {},
    useAuthStore: () => ({ isAdmin: false, isGuest: false, permissions: {}, loadPermissions: async () => {} }),
    useAppStore: () => ({ isMobile: false }),
    callRawAPI: async () => ({ success: true, users: [], groups: {} }),
    confirm: () => true, prompt: () => null,
    ...overrides,
  })
  vm.runInContext(script, context)
  return expression => vm.runInContext(expression, context)
}

test('user search matches school accounts in either backend representation', async () => {
  const run = setup('AdminUsers', {
    callRawAPI: async url => url.includes('list_users') ? {
      users: [
        { auth_username: 'first', school_accounts: ['school-123'] },
        { auth_username: 'second', school_accounts: { 'school-456': {} } },
      ],
    } : { groups: {} },
  })
  await run('loadUsers()')
  run("searchQuery.value = 'SCHOOL-123'")
  assert.equal(run('filteredUsers.value[0]?.auth_username'), 'first')
  run("searchQuery.value = 'school-456'")
  assert.equal(run('filteredUsers.value[0]?.auth_username'), 'second')
})

test('declining a phone reassignment does not update either account', async () => {
  const requests = []
  const answers = ['13800000000', '']
  let confirmed = false
  const run = setup('AdminUsers', {
    prompt: () => answers.shift(),
    confirm: () => { confirmed = true; return false },
    callRawAPI: async url => {
      requests.push(url)
      return { success: true, is_bound: true, bound_to_user: 'other-user' }
    },
  })
  await run("modifyPhone({ auth_username: 'target-user' })")
  assert.ok(confirmed, 'existing phone owner must be shown before reassignment')
  assert.deepEqual(requests, ['/api/auth/check_phone'])
})

test('a failed phone ownership lookup cannot fall through to an update', async () => {
  const requests = []
  const answers = ['13800000000', '']
  const run = setup('AdminUsers', {
    prompt: () => answers.shift(),
    callRawAPI: async url => {
      requests.push(url)
      if (url === '/api/auth/check_phone') throw new Error('lookup unavailable')
      return { success: true }
    },
  })
  await run("modifyPhone({ auth_username: 'target-user' })")
  assert.deepEqual(requests, ['/api/auth/check_phone'])
  assert.match(run('error.value'), /lookup unavailable/)
})

test('successful user operations retain feedback after list refresh', async () => {
  const run = setup('AdminUsers')
  await run("runOp(async () => ({ success: true }), '已更新最大会话数')")
  assert.equal(run('success.value'), '已更新最大会话数')
})

test('backend permissions expose their matching admin pages', () => {
  const run = setup('AdminPanel', {
    useAuthStore: () => ({ isAdmin: false, isGuest: false, permissions: {
      manage_permissions: true, modify_config: true, manage_system: true,
      view_logs: true, view_audit_logs: true,
    } }),
  })
  const visible = Array.from(run('visibleTabs.value.map(tab => tab.key)'))
  for (const key of ['groups', 'config', 'sms', 'cdn', 'ipban', 'reminders', 'payment-logs']) {
    assert.ok(visible.includes(key), `${key} must use a backend permission key`)
  }
  assert.ok(!visible.includes('restore-account'), 'role-only pages stay restricted')
})

test('guests can open their sessions and permissions changes leave a visible active page', async () => {
  const auth = reactive({ isAdmin: false, isGuest: true, permissions: {} })
  const run = setup('AdminPanel', { useAuthStore: () => auth })
  assert.ok(run("visibleTabs.value.some(tab => tab.key === 'sessions')"))
  assert.ok(!run("visibleTabs.value.some(tab => tab.key === 'profile')"))
  assert.equal(run('activeTab.value'), 'sessions')
  auth.isGuest = false
  auth.permissions.manage_users = true
  await nextTick()
  run("activeTab.value = 'users'")
  auth.permissions = {}
  await nextTick()
  assert.equal(run('activeTab.value'), 'sessions')
})

test('paid mode exposes personal payment history to ordinary users', async () => {
  let paid = true
  const requests = []
  const run = setup('AdminPanel', {
    callRawAPI: async url => {
      requests.push(url)
      return { success: true, config: { require_payment: paid } }
    },
  })
  await run('loadPricingVisibility()')
  assert.ok(run("visibleTabs.value.some(tab => tab.key === 'payment-logs')"))
  paid = false
  await run('loadPricingVisibility()')
  assert.ok(!run("visibleTabs.value.some(tab => tab.key === 'payment-logs')"))
  assert.deepEqual(requests, ['/api/config/pricing', '/api/config/pricing'])
})

test('personal payment history uses the user endpoint and displays supplied details', async () => {
  const requests = []
  const run = setup('AdminPaymentLogs', {
    callRawAPI: async url => {
      requests.push(url)
      return { success: true, logs: [{ log_id: 'my-log', order_id: 'my-order', amount: 2 }], total: 1 }
    },
  })
  run("filterUserId.value = 'other-user'")
  await run('fetchLogs(1)')
  assert.match(requests[0], /^\/api\/payment_logs\?/)
  assert.ok(!requests[0].includes('user_id'))
  await run('openDetail(logs.value[0])')
  assert.equal(run('detailData.value.order_id'), 'my-order')
  assert.equal(requests.length, 1, 'personal details must not request an admin-only endpoint')
})

test('audit-authorized payment history can explicitly request all users', async () => {
  const requests = []
  const run = setup('AdminPaymentLogs', {
    useAuthStore: () => ({ isAdmin: false, permissions: { view_audit_logs: true } }),
    callRawAPI: async url => { requests.push(url); return { success: true, logs: [] } },
  })
  run("showAllUsers.value = true; filterUserId.value = 'selected-user'")
  await run('fetchLogs(1)')
  assert.match(requests[0], /^\/api\/admin\/payment_logs\?/)
  assert.ok(requests[0].includes('user_id=selected-user'))
})

test('switching sessions navigates only after a successful server response', async () => {
  const navigated = []
  const requests = []
  let accepted = false
  const run = setup('AdminSessions', {
    window: { location: { assign: url => navigated.push(url) } },
    callRawAPI: async (url, method, body) => {
      requests.push({ url, method, body })
      return { success: accepted, message: '切换被拒绝' }
    },
  })
  await run("selectSession('target-session')")
  assert.equal(navigated.length, 0)
  accepted = true
  await run("selectSession('target-session')")
  assert.equal(navigated[0], '/uuid=target-session')
  assert.equal(requests[0].url, '/auth/switch_session')
  assert.equal(requests[0].body.target_session_id, 'target-session')
})

test('session creation preserves existing sessions when limit replacement is declined', async () => {
  const requests = []
  const run = setup('AdminSessions', {
    confirm: () => false,
    callRawAPI: async url => { requests.push(url); return { success: true } },
  })
  run("maxSessions.value = 1; sessions.value = [{ session_id: 'existing-session', created_at: 1 }]")
  await run('createSession()')
  assert.equal(requests.length, 0)
})

test('session creation uses persistence endpoint and returned session identity', async () => {
  const navigated = []
  const requests = []
  const run = setup('AdminSessions', {
    crypto: { randomUUID: () => 'requested-session' },
    window: { location: { assign: url => navigated.push(url) } },
    callRawAPI: async (url, method, body) => {
      requests.push({ url, method, body })
      return { success: true, session_id: 'created-session' }
    },
  })
  await run('createSession()')
  assert.equal(requests[0].url, '/auth/user/create_session_persistence')
  assert.equal(requests[0].body.session_id, 'requested-session')
  assert.equal(navigated[0], '/uuid=created-session')
})

test('school account tools normalize legacy and current credential records', async () => {
  const run = setup('AdminUserTools', {
    defineProps: () => ({ username: 'demo-user', mode: 'accounts' }),
    callRawAPI: async () => ({ success: true, accounts: { legacy: 'example-password', current: { password: 'example-password', ua: 'example-agent' } } }),
  })
  await run('loadData()')
  assert.equal(run('schoolAccounts.value[0].school_username'), 'legacy')
  assert.equal(run('schoolAccounts.value[1].ua'), 'example-agent')
})

test('custom permission editor sends only changes from the base group', async () => {
  const requests = []
  const run = setup('AdminUserTools', {
    defineProps: () => ({ username: 'demo-user', mode: 'permissions' }),
    callRawAPI: async (url, method, body) => {
      requests.push({ url, body })
      return { success: true, group: 'user', group_permissions: { view_logs: true, manage_users: false, use_attendance: true }, all_permissions: { view_logs: false, manage_users: false, use_attendance: true } }
    },
  })
  await run('loadData()')
  run('permissionValues.value.manage_users = true; permissionValues.value.use_attendance = false; permissionValues.value.view_logs = true')
  await run('savePermissions()')
  const saved = requests.find(r => r.url === '/auth/admin/set_user_permission').body
  assert.deepEqual(JSON.parse(JSON.stringify(saved)), { username: 'demo-user', added_permissions: { manage_users: true }, removed_permissions: { use_attendance: true } })
})

test('user logs use encoded target usernames for both tabs', async () => {
  const requests = []
  const run = setup('AdminUserTools', {
    defineProps: () => ({ username: 'demo+user', mode: 'logs' }),
    callRawAPI: async url => { requests.push(url); return { success: true, logs: [] } },
  })
  await run('loadData()')
  run("logTab.value = 'audit'")
  await run('loadData()')
  assert.deepEqual(requests, ['/api/admin/logs/login_history?username=demo%2Buser', '/api/admin/logs/audit?username=demo%2Buser'])
})
