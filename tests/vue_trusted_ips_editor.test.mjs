import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const vue = require('vue')
const source = readFileSync(new URL('../frontend/src/components/admin/AdminConfig.vue', import.meta.url), 'utf8')

function setup(callRawAPI) {
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const context = vm.createContext({ ...vue, onMounted() {}, onUnmounted() {}, callRawAPI })
  vm.runInContext(script, context)
  return expression => vm.runInContext(expression, context)
}

test('trusted IP editor loads exact text and revision without modifying the main configuration', async () => {
  const calls = []
  const text = '# 注释\r\n 203.0.113.10  # edge\r\n\r\n'
  const run = setup(async (...args) => {
    calls.push(args)
    return { success: true, content: text, revision: 3 }
  })
  await run('openTrustedIpsEditor()')
  assert.equal(run('trustedIpsVisible.value'), true)
  assert.equal(run('trustedIpsContent.value'), text)
  assert.equal(run('trustedIpsRevision.value'), 3)
  assert.equal(run('trustedIpsLoaded.value'), true)
  assert.equal(run('trustedIpsDirty.value'), false)
  assert.equal(run('isDirty.value'), false)
  assert.deepEqual(calls, [['/api/admin/trusted-ips', 'GET']])
})

test('trusted IP save sends untrimmed text with its loaded revision and uses the returned revision', async () => {
  const calls = []
  const run = setup(async (...args) => {
    calls.push(args)
    return args[1] === 'GET'
      ? { success: true, content: '# baseline\n', revision: 4 }
      : { success: true, revision: 5, message: '可信代理已更新，立即生效' }
  })
  await run('openTrustedIpsEditor()')
  const edited = ' 203.0.113.12 # gateway\n\n'
  run(`trustedIpsContent.value = ${JSON.stringify(edited)}`)
  assert.equal(run('trustedIpsDirty.value'), true)
  await run('saveTrustedIps()')
  assert.equal(calls[1][0], '/api/admin/trusted-ips')
  assert.equal(calls[1][1], 'POST')
  assert.equal(calls[1][2].content, edited)
  assert.equal(calls[1][2].revision, 4)
  assert.equal(run('trustedIpsRevision.value'), 5)
  assert.equal(run('trustedIpsDirty.value'), false)
  assert.match(run('trustedIpsSuccess.value'), /立即生效/)
  assert.equal(run('isDirty.value'), false)
})

test('loading failures cannot expose a save operation and leave an actionable error', async () => {
  let count = 0
  const run = setup(async () => { count++; throw new Error('权限不足') })
  await run('openTrustedIpsEditor()')
  run("trustedIpsContent.value = '203.0.113.12'")
  await run('saveTrustedIps()')
  assert.equal(count, 1)
  assert.equal(run('trustedIpsLoaded.value'), false)
  assert.match(run('trustedIpsError.value'), /权限不足/)
})

test('revision conflicts keep the draft and never retry with a newer revision automatically', async () => {
  const calls = []
  const run = setup(async (...args) => {
    calls.push(args)
    if (args[1] === 'GET') return { success: true, content: '# baseline', revision: 7 }
    const error = new Error('配置已被其他管理员修改，请重新加载后再保存')
    error.status = 409
    throw error
  })
  await run('openTrustedIpsEditor()')
  run(`trustedIpsContent.value = ${JSON.stringify('198.51.100.1\n')}`)
  await run('saveTrustedIps()')
  assert.equal(calls.length, 2)
  assert.equal(run('trustedIpsContent.value'), '198.51.100.1\n')
  assert.equal(run('trustedIpsRevision.value'), 7)
  assert.equal(run('trustedIpsDirty.value'), true)
  assert.match(run('trustedIpsError.value'), /重新加载/)
  assert.equal(run('trustedIpsSaving.value'), false)
})

test('explicit reload replaces a draft with current server content and revision', async () => {
  let reads = 0
  const run = setup(async () => ({ success: true, content: ++reads === 1 ? '# old' : '# current', revision: reads }))
  await run('openTrustedIpsEditor()')
  run("trustedIpsContent.value = '203.0.113.20'")
  await run('loadTrustedIps()')
  assert.equal(run('trustedIpsContent.value'), '# current')
  assert.equal(run('trustedIpsRevision.value'), 2)
  assert.equal(run('trustedIpsDirty.value'), false)
})

test('late loads from a closed editor cannot overwrite the newly opened editor', async () => {
  const pending = []
  const run = setup(() => new Promise(resolve => pending.push(resolve)))
  const first = run('openTrustedIpsEditor()')
  run('closeTrustedIpsEditor()')
  const second = run('openTrustedIpsEditor()')
  pending[1]({ success: true, content: '# newest', revision: 8 })
  await second
  pending[0]({ success: true, content: '# stale', revision: 2 })
  await first
  assert.equal(run('trustedIpsContent.value'), '# newest')
  assert.equal(run('trustedIpsRevision.value'), 8)
})

test('save is guarded against repeat clicks and closing until its response completes', async () => {
  let finish
  let posts = 0
  const run = setup(async (_url, method) => {
    if (method === 'GET') return { success: true, content: '# old', revision: 1 }
    posts++
    return new Promise(resolve => { finish = resolve })
  })
  await run('openTrustedIpsEditor()')
  run("trustedIpsContent.value = '203.0.113.20'")
  const pending = run('saveTrustedIps()')
  await run('saveTrustedIps()')
  run('closeTrustedIpsEditor()')
  assert.equal(posts, 1)
  assert.equal(run('trustedIpsVisible.value'), true)
  finish({ success: true, revision: 2 })
  await pending
  run('closeTrustedIpsEditor()')
  assert.equal(run('trustedIpsVisible.value'), false)
})

test('trust-all warning follows empty and full-wildcard rules but excludes comment-only or partial wildcards', () => {
  const run = setup(async () => ({}))
  for (const text of ['', '  \n', '*', '* # all', '*.*.*.*', '*.*', '203.0.113.10\n*']) {
    run(`trustedIpsContent.value = ${JSON.stringify(text)}`)
    assert.equal(run('trustedIpsTrustAll.value'), true, JSON.stringify(text))
  }
  for (const text of ['# empty external proxy list\n', '203.0.113.10', '198.51.*', '# *\n203.0.113.20']) {
    run(`trustedIpsContent.value = ${JSON.stringify(text)}`)
    assert.equal(run('trustedIpsTrustAll.value'), false, JSON.stringify(text))
  }
})

test('entry and plain-text modal provide clear labels, a trust scope warning and explicit reload', () => {
  assert.match(source, /@click="openTrustedIpsEditor"/)
  assert.match(source, /<AppModal[\s\S]*?title="可信代理 IP/)
  assert.match(source, /<textarea[\s\S]*?v-model="trustedIpsContent"/)
  assert.doesNotMatch(source, /v-model\.trim="trustedIpsContent"/)
  assert.match(source, /for="trusted-ips-editor"/)
  assert.match(source, /id="trusted-ips-editor"/)
  assert.match(source, /信任全部代理/)
  assert.match(source, /@click="loadTrustedIps"/)
  assert.match(source, /@click="saveTrustedIps"/)
})
