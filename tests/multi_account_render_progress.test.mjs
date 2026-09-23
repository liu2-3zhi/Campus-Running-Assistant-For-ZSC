import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const nextFunction = {
    getMultiAccountProgressState: 'function renderMultiAccountList(',
    renderMultiAccountList: 'function multi_toggleSelectAll(',
  }[name]
  assert.ok(nextFunction, `missing boundary for ${name}`)
  const end = source.indexOf(nextFunction, start + 1)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end).trim()
}

test('account snapshots preserve live progress when the list is redrawn', () => {
  const context = {}
  vm.createContext(context)
  vm.runInContext(extractFunction('getMultiAccountProgressState'), context)

  const progress = context.getMultiAccountProgressState({
    progress_pct: 3,
    progress_text: '运行 1/1: 第三次2公里跑步30... · 3%',
    progress_extra: '14/445 点',
  })

  assert.deepEqual(
    JSON.parse(JSON.stringify(progress)),
    {
      progressPct: 3,
      progressText: '运行 1/1: 第三次2公里跑步30... · 3%',
      progressExtra: '14/445 点',
    },
  )
})

test('multi-account card template renders progress values instead of hardcoded defaults', () => {
  const renderSource = extractFunction('renderMultiAccountList')

  assert.match(
    renderSource,
    /const\s+\{\s*progressPct,\s*progressText,\s*progressExtra,?\s*\}\s*=\s*getMultiAccountProgressState\(acc\)/,
  )
  assert.match(renderSource, /style="width:\$\{progressPct\}%"/)
  assert.match(renderSource, />\$\{progressText\}<\/span>/)
  assert.match(renderSource, />\$\{progressExtra\}<\/span>/)
  assert.doesNotMatch(renderSource, /<span class="progress-text text-slate-600">未开始<\/span>/)
})
