import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const surfaces = [
  { label: 'desktop', file: 'scripts/main.js', functionName: 'multi_loadAllFromConfig', nextName: 'openNewUserModal' },
  { label: 'mobile', file: 'scripts/legacy-mobile-multi.js', functionName: 'addMobileAllConfigs', nextName: 'openManualAccountModal' },
]

async function loadConfiguredAccounts(surface, accounts, savedAccounts) {
  const source = readFileSync(new URL(`../${surface.file}`, import.meta.url), 'utf8')
  const start = source.indexOf(`async function ${surface.functionName}(`)
  const end = source.indexOf(`function ${surface.nextName}(`, start)
  assert.ok(start >= 0 && end > start, `missing ${surface.functionName}`)
  let rendered
  const response = { success: true, accounts }
  const context = vm.createContext({
    sessionUUID: 'test-session', currentAuthUsername: 'test-owner',
    SECURITY_CONSTRAINTS: { MAX_PASSWORD_LENGTH: 256, MAX_UA_LENGTH: 4096 },
    jsShowConfirm: async () => true,
    callPythonAPI_raw: async (path, method) => {
      assert.equal(path, '/api/multi_load_accounts_from_config')
      assert.equal(method, 'POST')
      return response
    },
    callPythonAPI: async method => {
      assert.equal(method, 'multi_load_accounts_from_config')
      return response
    },
    fetch: async path => {
      assert.equal(path, '/auth/get_user_school_accounts')
      return { ok: true, json: async () => ({ success: true, accounts: savedAccounts }) }
    },
    renderMultiAccountList: value => { rendered = structuredClone(value) },
    showModalAlert() {}, logMessage_Info() {}, logMessage_Warning() {},
    console: { log() {}, warn() {}, error() {} },
  })
  vm.runInContext(source.slice(start, end), context)
  await context[surface.functionName]()
  assert.ok(rendered, 'the account list must be rendered after merging')
  return rendered
}

for (const surface of surfaces) {
  test(`${surface.label}: live account UAs take priority over stale saved UAs`, async () => {
    const rendered = await loadConfiguredAccounts(surface, [
      { username: '1001', device_ua: 'live-device-A' },
      { username: '1002', device_ua: 'live-device-B' },
    ], {
      '1001': { password: 'password-A', ua: 'stale-shared-device' },
      '1002': { password: 'password-B', ua: 'stale-shared-device' },
    })
    assert.deepEqual(rendered.map(account => account.device_ua), ['live-device-A', 'live-device-B'])
    assert.deepEqual(rendered.map(account => account.password), ['password-A', 'password-B'])
  })

  test(`${surface.label}: missing account UA falls back to that account's saved UA`, async () => {
    const rendered = await loadConfiguredAccounts(surface, [
      { username: '1001' },
      { username: '1002', device_ua: '' },
      { username: '1003', device_ua: null },
      { username: '1004', device_ua: '   ' },
      { username: '1005', device_ua: 123 },
    ], {
      '1001': { ua: 'saved-device-A' },
      '1002': { ua: 'saved-device-B' },
      '1003': { ua: 'saved-device-C' },
      '1004': { ua: 'saved-device-D' },
      '1005': { ua: 'saved-device-E' },
    })
    assert.deepEqual(rendered.map(account => account.device_ua), [
      'saved-device-A', 'saved-device-B', 'saved-device-C', 'saved-device-D', 'saved-device-E',
    ])
  })

  test(`${surface.label}: absent saved UA never copies another account's device`, async () => {
    const rendered = await loadConfiguredAccounts(surface, [
      { username: '1001', device_ua: 'live-device-A' },
      { username: '1002' },
      { username: '1003', device_ua: 'live-device-C' },
    ], {
      '1001': { ua: 'stale-device-A' },
      '1002': { password: 'password-B' },
      '1003': 'legacy-password-C',
    })
    assert.equal(rendered[0].device_ua, 'live-device-A')
    assert.equal(rendered[1].device_ua, undefined)
    assert.equal(rendered[2].device_ua, 'live-device-C')
    assert.equal(rendered[2].password, 'legacy-password-C')
  })
}
