import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function editor(respond) {
  const elements = new Map()
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', disabled: false, open: false,
      focus() {}, setAttribute() {},
      showModal() { this.open = true }, close() { this.open = false },
    })
    return elements.get(id)
  }
  const calls = []
  const context = vm.createContext({
    document: { addEventListener() {}, getElementById: get },
    sessionUUID: 'fixture-session',
    addAdminViewOriginSessionHeader(headers) { headers['X-Admin-Origin-Session-ID'] = 'fixture-origin' },
    fetch: async (path, options) => {
      calls.push({ path, options })
      return respond(path, options, calls.length)
    },
  })
  vm.runInContext(readFileSync(new URL('../scripts/legacy-admin-config.js', import.meta.url), 'utf8'), context)
  return { context, get, calls }
}

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data })

test('legacy editor loads and saves plain text with revision and caller authentication', async () => {
  const content = '# comment\r\n 203.0.113.8 # gateway\r\n\r\n2001:db8::/32\r\n'
  const ui = editor((_path, _options, count) => response({ success: true, content, revision: count === 1 ? 7 : 8 }))
  assert.equal(typeof ui.context.openTrustedIpsEditor, 'function')
  await ui.context.openTrustedIpsEditor({ focus() {} })
  assert.equal(ui.get('trusted-ips-editor-text').value, content)
  assert.equal(ui.get('trusted-ips-editor-save').disabled, false)
  await ui.context.saveTrustedIpsEditor()
  assert.equal(ui.calls.length, 2)
  assert.equal(ui.calls[0].options.cache, 'no-store')
  assert.equal(ui.calls[1].path, '/api/admin/trusted-ips')
  assert.equal(ui.calls[1].options.credentials, 'include')
  assert.equal(ui.calls[1].options.headers['X-Session-ID'], 'fixture-session')
  assert.equal(ui.calls[1].options.headers['X-Admin-Origin-Session-ID'], 'fixture-origin')
  assert.deepEqual(JSON.parse(ui.calls[1].options.body), { content, revision: 7 })
  assert.match(ui.get('trusted-ips-editor-status').textContent, /生效/)
})

test('failed loading cannot submit blank defaults over the stored rules', async () => {
  const ui = editor(() => response({ success: false, message: '需要配置修改权限' }, 403))
  await ui.context.openTrustedIpsEditor()
  assert.equal(ui.get('trusted-ips-editor-save').disabled, true)
  assert.match(ui.get('trusted-ips-editor-status').textContent, /配置修改权限/)
  await ui.context.saveTrustedIpsEditor()
  assert.equal(ui.calls.length, 1)
})

test('conflicts retain the draft and explicit reload obtains a fresh revision', async () => {
  const ui = editor((_path, _options, count) => {
    if (count === 2) return response({ success: false, message: '规则已更新，请重新加载' }, 409)
    return response({ success: true, content: count === 1 ? '# original\n' : '# updated\n', revision: count === 1 ? 1 : 2 })
  })
  await ui.context.openTrustedIpsEditor()
  ui.get('trusted-ips-editor-text').value = '# my draft\n'
  await ui.context.saveTrustedIpsEditor()
  assert.equal(ui.get('trusted-ips-editor-text').value, '# my draft\n')
  assert.match(ui.get('trusted-ips-editor-status').textContent, /重新加载/)
  await ui.context.loadTrustedIpsEditor()
  assert.equal(ui.get('trusted-ips-editor-text').value, '# updated\n')
  await ui.context.saveTrustedIpsEditor()
  assert.equal(JSON.parse(ui.calls.at(-1).options.body).revision, 2)
})

test('a late load from a closed editor cannot replace a newer editor draft', async () => {
  let first
  const ui = editor((_path, _options, count) => count === 1
    ? new Promise(resolve => { first = resolve })
    : response({ success: true, content: '# current\n', revision: 2 }))
  const oldLoad = ui.context.openTrustedIpsEditor()
  ui.context.closeTrustedIpsEditor()
  await ui.context.openTrustedIpsEditor()
  ui.get('trusted-ips-editor-text').value = '# current draft\n'
  first(response({ success: true, content: '# obsolete\n', revision: 1 }))
  await oldLoad
  assert.equal(ui.get('trusted-ips-editor-text').value, '# current draft\n')
})
