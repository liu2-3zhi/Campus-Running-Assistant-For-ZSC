import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const nextFunction = {
    calculateStatusText: 'function updateAllAccountsStatusText(',
    formatMultiAccountStatusText: 'function updateAllAccountsStatusText(',
    updateAllAccountsStatusText: 'function renderMultiAccountList(',
    multi_updateAccountStatus: 'function multi_updateRunnerPosition(',
  }[name]
  assert.ok(nextFunction, `missing boundary for ${name}`)
  const end = source.indexOf(nextFunction, start)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end).trim()
}

function localDateTime(date) {
  const pad = value => String(value).padStart(2, '0')
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join(' ')
}

function mixedExecutableAccount() {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrowStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  const tomorrowEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 2)
  return {
    username: 'student-a',
    status_text: 'Have_Tasks',
    tasks: [
      { status: 0, start_time: localDateTime(tomorrowStart), end_time: localDateTime(tomorrowEnd) },
      { status: 0, start_time: localDateTime(tomorrowStart), end_time: localDateTime(tomorrowEnd) },
      { status: 0, start_time: localDateTime(tomorrowStart), end_time: localDateTime(tomorrowEnd) },
      { status: 0, start_time: localDateTime(todayStart), end_time: localDateTime(tomorrowEnd) },
    ],
    summary: {
      total: 4,
      completed: 0,
      not_started: 3,
      executable: 1,
      expired: 0,
      unexpired_count: 4,
      unexpired_incomplete_count: 4,
    },
  }
}

function createItem() {
  const status = { textContent: '', className: '' }
  const value = { textContent: '' }
  return {
    status,
    querySelector(selector) {
      return selector === '.status-text' ? status : value
    },
  }
}

test('cached Have_Tasks status respects only-incomplete and excludes not-started tasks', () => {
  const pcItem = createItem()
  const mobileItem = createItem()
  const checkboxes = {
    'mobile-multi-only-incomplete-check': { checked: true },
    'multi-run-only-incomplete-check': { checked: true },
    'multi-param-ignore_task_time': { checked: true },
  }
  const context = {
    cachedMultiAccounts: [mixedExecutableAccount()],
    console: { log() {} },
    document: {
      getElementById(id) {
        if (id === 'multi-acc-student-a') return pcItem
        if (id === 'mobile-multi-acc-student-a') return mobileItem
        return checkboxes[id] || null
      },
    },
  }
  vm.createContext(context)
  vm.runInContext(`${extractFunction('calculateStatusText')}\n${extractFunction('formatMultiAccountStatusText')}\n${extractFunction('updateAllAccountsStatusText')}`, context)
  context.updateAllAccountsStatusText()

  assert.equal(pcItem.status.textContent, '有 1 个任务可执行')
  assert.equal(mobileItem.status.textContent, '有 1 个任务可执行')
})

test('websocket Have_Tasks update excludes not-started tasks from the summary count', () => {
  const pcItem = createItem()
  const mobileItem = createItem()
  const account = mixedExecutableAccount()
  const context = {
    requestMultiAccountStatusRefresh() {},
    lastMultiAccountStatusRefreshRequest: new Map(),
    document: {
      getElementById(id) {
        if (id === 'multi-acc-student-a') return pcItem
        if (id === 'mobile-multi-acc-student-a') return mobileItem
        if (id.endsWith('only-incomplete-check')) return { checked: true }
        return null
      },
    },
  }
  vm.createContext(context)
  vm.runInContext(`${extractFunction('formatMultiAccountStatusText')}\n${extractFunction('multi_updateAccountStatus')}`, context)
  context.multi_updateAccountStatus('student-a', {
    status_text: account.status_text,
    summary: account.summary,
  })

  assert.equal(pcItem.status.textContent, '有 1 个任务可执行')
  assert.equal(mobileItem.status.textContent, '有 1 个任务可执行')
})

test('websocket status count follows each only-incomplete checkbox independently', () => {
  const pcItem = createItem()
  const mobileItem = createItem()
  const context = {
    requestMultiAccountStatusRefresh() {},
    lastMultiAccountStatusRefreshRequest: new Map(),
    document: {
      getElementById(id) {
        if (id === 'multi-acc-student-a') return pcItem
        if (id === 'mobile-multi-acc-student-a') return mobileItem
        if (id === 'multi-run-only-incomplete-check') return { checked: true }
        if (id === 'mobile-multi-only-incomplete-check') return { checked: false }
        return null
      },
    },
  }
  vm.createContext(context)
  vm.runInContext(`${extractFunction('formatMultiAccountStatusText')}\n${extractFunction('multi_updateAccountStatus')}`, context)
  context.multi_updateAccountStatus('student-a', {
    status_text: 'Have_Tasks',
    summary: {
      not_started: 3,
      unexpired_count: 7,
      unexpired_incomplete_count: 5,
    },
  })

  assert.equal(pcItem.status.textContent, '有 2 个任务可执行')
  assert.equal(mobileItem.status.textContent, '有 4 个任务可执行')
})

test('raw Have_Tasks is never shown when summary is unavailable', () => {
  const pcItem = createItem()
  const mobileItem = createItem()
  const context = {
    requestMultiAccountStatusRefresh() {},
    lastMultiAccountStatusRefreshRequest: new Map(),
    document: {
      getElementById(id) {
        if (id === 'multi-acc-student-a') return pcItem
        if (id === 'mobile-multi-acc-student-a') return mobileItem
        return null
      },
    },
  }
  vm.createContext(context)
  vm.runInContext(`${extractFunction('formatMultiAccountStatusText')}\n${extractFunction('multi_updateAccountStatus')}`, context)
  context.multi_updateAccountStatus('student-a', { status_text: 'Have_Tasks' })

  assert.equal(pcItem.status.textContent, '有任务可执行')
  assert.equal(mobileItem.status.textContent, '有任务可执行')
})

test('legacy rendering automatically requests a backend refresh for Have_Tasks', () => {
  assert.match(source, /function requestMultiAccountStatusRefresh\(username\)/)
  assert.match(source, /if \(acc\.status_text === "Have_Tasks"\) \{\s*void requestMultiAccountStatusRefresh\(acc\.username\)/)
  assert.match(source, /MULTI_ACCOUNT_STATUS_REFRESH_COOLDOWN_MS = 10000/)
})
