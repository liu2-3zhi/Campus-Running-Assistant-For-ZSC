import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const start = source.indexOf('async function onUserChange()')
const end = source.indexOf('async function onLogin()', start)

for (const credentials of [
  { password: 'selected-password', ua: 'selected-UA' },
  { password: '', ua: '' },
]) {
  test(`selecting a saved account uses only its filtered credential response (${credentials.ua || 'hidden credentials'})`, async () => {
    const elements = new Map()
    const element = id => {
      if (!elements.has(id)) elements.set(id, { value: '', textContent: '', disabled: false })
      return elements.get(id)
    }
    element('user-combo').value = '10001'
    element('password-entry').value = 'previous-password'
    const calls = []
    const allAccountReads = []
    const mobileUAs = []
    const context = vm.createContext({
      sessionUUID: '11111111-1111-4111-8111-111111111111', currentAuthUsername: 'owner',
      $: element, pythonParams: {},
      callPythonAPI: async (method, ...args) => {
        calls.push({ method, args })
        assert.equal(element('login-button').disabled, true)
        return { ...credentials, params: { theme_style: 'default' } }
      },
      fetch: async (...args) => {
        allAccountReads.push(args)
        return { ok: true, json: async () => ({ success: true, accounts: {
          '10001': { password: 'unfiltered-password', ua: 'unfiltered-UA' },
        } }) }
      },
      syncUAToMobile: ua => mobileUAs.push(ua),
      updateParamInputs() {}, setBaseColor() {}, setThemeStyle() {},
      logMessage_Info() {}, logMessage_Warning() {},
    })
    const sessionCheck = source.slice(
      source.indexOf('function isUsableClientSessionUUID('),
      source.indexOf('const ADMIN_RETURN_ORIGIN_STORAGE_KEY'),
    )
    vm.runInContext(sessionCheck + '\n' + source.slice(start, end), context)
    await context.onUserChange()

    assert.deepEqual(calls, [{ method: 'on_user_selected', args: ['10001'] }])
    assert.deepEqual(allAccountReads, [], 'selection must not request all account statistics and credentials')
    assert.equal(element('password-entry').value, credentials.password)
    assert.equal(element('ua-label').textContent, credentials.ua || '(新用户将在登录时自动生成)')
    assert.deepEqual(mobileUAs, [credentials.ua || '(新用户将在登录时自动生成)'])
    assert.equal(element('login-button').disabled, false)
  })
}
