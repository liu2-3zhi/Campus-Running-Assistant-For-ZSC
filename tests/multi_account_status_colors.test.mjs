import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')

function extractFunction(name, nextName) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const end = source.indexOf(`function ${nextName}(`, start + 1)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end).trim()
}

test('multi-account terminal status colors distinguish outcomes', () => {
  const context = {}
  vm.createContext(context)
  vm.runInContext(
    extractFunction(
      'getMultiAccountStatusClass',
      'updateAllAccountsStatusText',
    ),
    context,
  )

  assert.match(context.getMultiAccountStatusClass('全部完成'), /text-emerald-700/)
  assert.match(context.getMultiAccountStatusClass('全部完成'), /bg-emerald-100/)
  assert.match(context.getMultiAccountStatusClass('全部失败'), /text-red-700/)
  assert.match(context.getMultiAccountStatusClass('全部失败'), /bg-red-100/)
  assert.match(
    context.getMultiAccountStatusClass('部分成功，2个任务失败'),
    /text-amber-700/,
  )
  assert.match(
    context.getMultiAccountStatusClass('部分成功，2个任务失败'),
    /bg-amber-100/,
  )
})

test('initial render and live status updates share the status color helper', () => {
  const renderStart = source.indexOf('function renderMultiAccountList(')
  const renderEnd = source.indexOf('function multi_toggleSelectAll(', renderStart)
  const renderSource = source.slice(renderStart, renderEnd)
  const updateStart = source.indexOf('function multi_updateAccountStatus(')
  const updateEnd = source.indexOf('function multi_updateRunnerPosition(', updateStart)
  const updateSource = source.slice(updateStart, updateEnd)

  assert.match(
    renderSource,
    /getMultiAccountStatusClass\(\s*displayStatusText,?\s*\)/,
  )
  assert.match(updateSource, /getMultiAccountStatusClass\(/)
})
