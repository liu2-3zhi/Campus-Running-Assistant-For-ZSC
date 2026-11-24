import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))
const SESSION = '11111111-1111-4111-8111-111111111111'

function createHarness(sessionUUID) {
  const elements = new Map()
  const calls = []
  const mobileUAs = []
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', disabled: false, options: [], listeners: {},
      addEventListener(name, callback) { this.listeners[name] = callback },
    })
    return elements.get(id)
  }
  element('user-combo').value = '10001'
  element('user-combo').options = [{ value: '10001' }]
  element('username-entry').value = '10001'
  element('password-entry').value = 'previous-password'
  element('ua-label').textContent = 'previous-UA'
  const context = vm.createContext({
    sessionUUID, authSessionUUID: SESSION, pythonParams: {}, $: element,
    callPythonAPI: async (method, ...args) => {
      calls.push({ method, args })
      return { password: 'selected-password', ua: 'selected-UA', params: {} }
    },
    syncUAToMobile: value => mobileUAs.push(value),
    updateParamInputs() {}, setBaseColor() {}, setThemeStyle() {}, logMessage_Info() {},
  })
  vm.runInContext([
    section('function isUsableClientSessionUUID(', 'const ADMIN_RETURN_ORIGIN_STORAGE_KEY'),
    section('async function onUserChange()', 'async function onLogin()'),
    section('$("user-combo").addEventListener("change", onUserChange);', '$("random-ua-btn").addEventListener('),
  ].join('\n'), context)
  return { context, element, calls, mobileUAs }
}

for (const event of ['selection', 'typing']) {
  test(`${event} before choosing a business session clears old credentials without requesting account data`, async () => {
    for (const session of [null, undefined, '', '  ', 'null', 'undefined', 'none', 'invalid-session']) {
      const h = createHarness(session)
      if (event === 'selection') await h.context.onUserChange()
      else await h.element('username-entry').listeners.input({ target: { value: '10001' } })

      assert.deepEqual(h.calls, [], `business session ${String(session)} must not trigger an account request`)
      assert.equal(h.element('password-entry').value, '')
      assert.equal(h.element('ua-label').textContent, '(新用户将在登录时自动生成)')
      assert.equal(h.element('username-entry').value, '10001')
      assert.equal(h.element('login-button').disabled, false)
      assert.deepEqual(h.mobileUAs, ['(新用户将在登录时自动生成)'])
    }
  })

  test(`${event} in a valid business session retains selected account credentials`, async () => {
    const h = createHarness(SESSION)
    if (event === 'selection') await h.context.onUserChange()
    else await h.element('username-entry').listeners.input({ target: { value: '10001' } })

    assert.deepEqual(h.calls, [{ method: 'on_user_selected', args: ['10001'] }])
    assert.equal(h.element('password-entry').value, 'selected-password')
    assert.equal(h.element('ua-label').textContent, 'selected-UA')
    assert.equal(h.element('login-button').disabled, false)
  })
}

test('an authenticated user can load the session picker before choosing a business session', async () => {
  const list = { innerHTML: '' }
  const requests = []
  const context = vm.createContext({
    sessionUUID: null, authSessionUUID: SESSION, legacyAdminViewContext: null,
    window: {}, currentSessionInfo: {},
    $: id => id === 'session-picker-list' ? list : null,
    fetch: async (url, options) => {
      requests.push({ url, session: options.headers['X-Session-ID'] })
      return { ok: true, json: async () => ({ success: true, sessions: [], max_sessions: 5 }) }
    },
    updateSessionCountDisplay() {}, logMessage_Error() {},
  })
  vm.runInContext([
    section('function isUsableClientSessionUUID(', 'const ADMIN_RETURN_ORIGIN_STORAGE_KEY'),
    section('function getAuthenticatedSessionHeaderValue()', 'function setActiveLegacySession('),
    section('async function loadSessionPickerList()', 'function refreshSessionPicker()'),
  ].join('\n'), context)

  await context.loadSessionPickerList()

  assert.deepEqual(requests, [{ url: '/auth/user/sessions', session: SESSION }])
  assert.match(list.innerHTML, /暂无会话/)
  assert.equal(context.currentSessionInfo.currentCount, 0)
  assert.equal(context.currentSessionInfo.maxSessions, 5)
})
