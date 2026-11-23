import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const main = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const accounts = readFileSync(new URL('../scripts/legacy-multi-accounts.js', import.meta.url), 'utf8')

function between(source, start, end) {
  return source.slice(source.indexOf(`async function ${start}(`), source.indexOf(end, source.indexOf(`async function ${start}(`)))
}

function setup(overrides = {}) {
  const calls = []
  const alerts = []
  const elements = {
    'multi-account-count': { textContent: '2' },
    'multi-use-delay-check': { checked: true },
    'multi-min-delay-input': { value: '1' },
    'multi-max-delay-input': { value: '1' },
    'multi-run-only-incomplete-check': { checked: true },
  }
  const context = {
    console: { error() {} },
    multiAccountStartGeneration: 0,
    multiAccountPendingStarts: new Set(),
    multiAccountStopPromise: null,
    stoppingMultiAccounts: false,
    $: id => elements[id],
    document: { getElementById: id => elements[id] },
    multi_getSelectedUsernames: () => ['student-a', 'student-b'],
    checkOverdueBeforeStart: async () => true,
    _checkOverdueBeforeStartByCurrentMode: async () => true,
    _consumeOverdueForceOverride: () => ({ bypass_overdue: false, waive_charge: false }),
    callPythonAPI: async (method, ...args) => { calls.push([method, ...args]); return { success: true } },
    showModalAlert: (message, title) => alerts.push([message, title]),
    swal: { fire() {} },
    logMessage_Error() {},
    ...overrides,
  }
  vm.createContext(context)
  vm.runInContext([
    between(main, 'callMultiAccountStart', 'async function multi_startAll('),
    between(main, 'multi_startAll', 'async function multi_stopAll('),
    between(main, 'multi_stopAll', 'function selectTaskFromBackend('),
    between(main, 'mobileStartAllAccounts', 'async function mobileStopAllAccounts('),
    between(main, 'mobileStopAllAccounts', 'async function mobileRefreshAllAccounts('),
    between(accounts, 'multi_startSelected', 'async function multi_stopSelected('),
  ].join('\n'), context)
  return { context, calls, alerts, elements }
}

test('legacy stop-all cancels the selected-account startup delay', async () => {
  let releaseDelay
  let delayStarted
  const delayed = new Promise(resolve => { delayStarted = resolve })
  const ctx = setup({ setTimeout(callback) {
    if (releaseDelay) queueMicrotask(callback)
    else { releaseDelay = callback; delayStarted() }
    return 1
  } })
  const pendingStart = ctx.context.multi_startSelected()
  await delayed
  await ctx.context.multi_stopAll()
  releaseDelay()
  await pendingStart
  assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts'])
})

test('legacy stop-all prevents another selected start after a pending request returns', async () => {
  const calls = []
  let releaseStart
  let firstStarted
  const started = new Promise(resolve => { firstStarted = resolve })
  const ctx = setup({
    callPythonAPI: async (method, ...args) => {
      calls.push([method, ...args])
      if (method === 'multi_start_single_account' && calls.length === 1) {
        firstStarted()
        return new Promise(resolve => { releaseStart = resolve })
      }
      return { success: true }
    },
  })
  ctx.elements['multi-use-delay-check'].checked = false
  const pendingStart = ctx.context.multi_startSelected()
  await started
  const pendingStop = ctx.context.multi_stopAll()
  releaseStart({ success: true })
  await Promise.all([pendingStart, pendingStop])
  assert.deepEqual(calls.map(call => call[0]), ['multi_start_single_account', 'multi_stop_all_accounts', 'multi_stop_all_accounts'])
})

for (const action of ['multi_startSelected', 'multi_startAll', 'mobileStartAllAccounts']) {
  test(`legacy stop-all catches a sent ${action} request handled after its first stop`, async () => {
    const methods = []
    let running = false
    let deliverStart
    let notifyStart
    const dispatched = new Promise(resolve => { notifyStart = resolve })
    const ctx = setup({
      multi_getSelectedUsernames: () => ['student-a'],
      callPythonAPI: async method => {
        methods.push(method)
        if (method.startsWith('multi_start_')) {
          notifyStart()
          return new Promise(resolve => { deliverStart = () => { running = true; resolve({ success: true }) } })
        }
        if (method === 'multi_stop_all_accounts') running = false
        return { success: true }
      },
    })
    ctx.elements['multi-use-delay-check'].checked = false
    const pendingStart = ctx.context[action]()
    await dispatched
    const pendingStop = ctx.context.multi_stopAll()
    assert.equal(methods.at(-1), 'multi_stop_all_accounts')
    deliverStart()
    await Promise.all([pendingStart, pendingStop])
    assert.equal(running, false)
    assert.equal(methods.filter(method => method === 'multi_stop_all_accounts').length, 2)
  })
}

test('legacy blocks all startup actions while stop-all is pending', async () => {
  const methods = []
  let finishStop
  const ctx = setup({
    callPythonAPI: async method => {
      methods.push(method)
      if (method === 'multi_stop_all_accounts') return new Promise(resolve => { finishStop = resolve })
      return { success: true }
    },
  })
  ctx.elements['multi-use-delay-check'].checked = false
  const pendingStop = ctx.context.multi_stopAll()
  await ctx.context.multi_startSelected()
  await ctx.context.multi_startAll()
  await ctx.context.mobileStartAllAccounts()
  assert.deepEqual(methods, ['multi_stop_all_accounts'])
  finishStop({ success: true })
  await pendingStop
})

for (const action of ['multi_startAll', 'mobileStartAllAccounts']) {
  test(`legacy stop-all invalidates pending ${action} preflight`, async () => {
    let releaseCheck
    let checkStarted
    const checking = new Promise(resolve => { checkStarted = resolve })
    const ctx = setup({
      _checkOverdueBeforeStartByCurrentMode: () => new Promise(resolve => { releaseCheck = resolve; checkStarted() }),
    })
    const pendingStart = ctx.context[action]()
    await checking
    await ctx.context.multi_stopAll()
    releaseCheck(true)
    await pendingStart
    assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts'])
  })

  test(`a new legacy ${action} request can start after stop-all`, async () => {
    const ctx = setup()
    await ctx.context.multi_stopAll()
    await ctx.context[action]()
    assert.deepEqual(ctx.calls.map(call => call[0]), ['multi_stop_all_accounts', 'multi_start_all_accounts'])
  })
}

test('legacy mobile stop-all does not report success when the backend rejects stopping', async () => {
  const ctx = setup({ callPythonAPI: async () => ({ success: false, message: '停止请求未接受' }) })
  await ctx.context.mobileStopAllAccounts()
  assert.equal(ctx.alerts.some(([, title]) => title === '成功'), false)
  assert.equal(ctx.alerts.some(([, title]) => title === '错误'), true)
})

test('legacy mobile reports an error if its final stop after a pending start fails', async () => {
  let deliverStart
  let notifyStart
  const dispatched = new Promise(resolve => { notifyStart = resolve })
  let stopCount = 0
  const ctx = setup({
    callPythonAPI: async method => {
      if (method.startsWith('multi_start_')) {
        notifyStart()
        return new Promise(resolve => { deliverStart = resolve })
      }
      stopCount += 1
      return stopCount === 1 ? { success: true } : { success: false, message: '停止请求未接受' }
    },
  })
  const pendingStart = ctx.context.multi_startAll()
  await dispatched
  const pendingStop = ctx.context.mobileStopAllAccounts()
  deliverStart({ success: true })
  await Promise.all([pendingStart, pendingStop])
  assert.equal(stopCount, 2)
  assert.equal(ctx.alerts.some(([, title]) => title === '成功'), false)
  assert.ok(ctx.alerts.some(([message, title]) => message === '停止请求未接受' && title === '错误'))
})
