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

test('expanded multi-account filters classify status gender and executability', () => {
  const context = {}
  vm.createContext(context)
  vm.runInContext(
    `
      ${extractFunction('formatMultiAccountStatusText', 'getMultiAccountStatusClass')}
      ${extractFunction('getMultiAccountStatusCategory', 'normalizeMultiAccountGender')}
      ${extractFunction('normalizeMultiAccountGender', 'filterMultiAccountExpandedAccounts')}
      ${extractFunction('filterMultiAccountExpandedAccounts', 'buildExpandedMultiAccountCard')}
    `,
    context,
  )

  assert.equal(context.getMultiAccountStatusCategory('全部完成'), '已完成')
  assert.equal(context.getMultiAccountStatusCategory('全部失败'), '全部失败')
  assert.equal(
    context.getMultiAccountStatusCategory('部分成功，2个任务失败'),
    '部分成功',
  )
  assert.equal(context.getMultiAccountStatusCategory('运行 1/2: 测试 · 30%'), '运行中')
  assert.equal(context.normalizeMultiAccountGender('男'), '男')
  assert.equal(context.normalizeMultiAccountGender('female'), '女')
  assert.equal(context.normalizeMultiAccountGender(''), '未知')

  const filtered = context.filterMultiAccountExpandedAccounts(
    [
      {
        username: 'a',
        gender: '男',
        status_text: '全部完成',
        summary: { executable: 0 },
      },
      {
        username: 'b',
        gender: '女',
        status_text: '运行 1/2: 测试 · 30%',
        summary: { executable: 1 },
      },
    ],
    {
      status: '运行中',
      gender: '女',
      executable: '有可执行任务',
    },
  )

  assert.deepEqual(
    JSON.parse(JSON.stringify(filtered.map((account) => account.username))),
    ['b'],
  )
})

test('expanded view button is next to import and opens a Swal card dialog', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  const importIndex = html.indexOf('id="multi-import-excel-btn"')
  const expandIndex = html.indexOf('id="multi-expand-btn"')

  assert.notEqual(importIndex, -1)
  assert.notEqual(expandIndex, -1)
  assert.ok(expandIndex < importIndex, 'expand button should be left of import button')
  assert.match(source, /multi-expand-btn".*addEventListener\("click", openMultiAccountExpandedView/)
  assert.match(source, /async function openMultiAccountExpandedView\(/)
  assert.match(source, /Swal\.fire\(\{/)
  assert.match(source, /data-expanded-filter="status"/)
  assert.match(source, /data-expanded-filter="gender"/)
  assert.match(source, /data-expanded-filter="executable"/)
})

test('expanded account cards include attendance summary counts', () => {
  const start = source.indexOf('function buildExpandedMultiAccountCard(')
  const end = source.indexOf('async function openMultiAccountExpandedView(', start)
  const cardSource = source.slice(start, end)

  assert.match(cardSource, /待签/)
  assert.match(cardSource, /summary\.att_pending/)
  assert.match(cardSource, /已签/)
  assert.match(cardSource, /summary\.att_completed/)
  assert.match(cardSource, /过期/)
  assert.match(cardSource, /summary\.att_expired/)
})

test('live account updates refresh an open expanded view and cached snapshot', async () => {
  const context = {
    cachedMultiAccounts: [
      {
        username: 'student-a',
        status_text: '正在登录...',
        summary: { executable: 0 },
      },
    ],
    requestMultiAccountStatusRefresh() {},
    lastMultiAccountStatusRefreshRequest: new Map(),
    document: {
      getElementById() {
        return null;
      },
    },
  }
  let refreshCount = 0
  context.activeExpandedMultiAccountRefresh = () => {
    refreshCount += 1
  }
  vm.createContext(context)
  vm.runInContext(
    `
      ${extractFunction('formatMultiAccountStatusText', 'getMultiAccountStatusClass')}
      ${extractFunction('getMultiAccountStatusClass', 'updateAllAccountsStatusText')}
      ${extractFunction('multi_updateAccountStatus', 'multi_updateRunnerPosition')}
    `,
    context,
  )

  await context.multi_updateAccountStatus('student-a', {
    status_text: '无任务可执行',
    summary: { executable: 0 },
  })

  assert.equal(context.cachedMultiAccounts[0].status_text, '无任务可执行')
  assert.equal(refreshCount, 1)
})
