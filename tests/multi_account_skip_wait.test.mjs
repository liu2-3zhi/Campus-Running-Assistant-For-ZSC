import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/legacy-multi-accounts.js', import.meta.url), 'utf8')

function extract(start, end) {
  const first = source.indexOf(start)
  const last = source.indexOf(end, first)
  assert.ok(first >= 0 && last > first)
  return source.slice(first, last)
}

function setup(canSkipWait, stopping = false) {
  const calls = []
  let paymentChecks = 0
  let forceOverrides = 0
  let expandedClick
  const account = {
    username: 'student-a', name: 'Student', can_skip_wait: canSkipWait,
    status_text: '任务间等待 925s', summary: {},
  }
  const desktopButton = { dataset: { username: account.username } }
  const mobileButton = { dataset: { username: account.username } }
  const list = button => ({
    innerHTML: '', appendChild() {},
    querySelectorAll: selector => selector === '.btn-account-start' ? [button] : [],
  })
  const containers = {
    'multi-account-list': list(desktopButton),
    'mobile-multi-account-list': list(mobileButton),
  }
  const cards = { innerHTML: '', addEventListener: (_name, callback) => { expandedClick = callback } }
  const root = { querySelector: selector => selector === '#expanded-multi-account-count' ? {} : selector === '#expanded-multi-account-cards' ? cards : null }
  const context = {
    cachedMultiAccounts: [account], activeExpandedMultiAccountRefresh: null,
    stoppingMultiAccounts: stopping, multiAccountStartGeneration: 0,
    document: {
      getElementById: id => containers[id] || null,
      querySelector: () => root,
      createElement: () => ({ dataset: {} }),
      body: { contains: () => true },
    },
    formatMultiAccountStatusText: text => text,
    getMultiAccountStatusClass: () => '',
    getMultiAccountProgressState: () => ({ progressPct: 0, progressText: '', progressExtra: '' }),
    lastMultiAccountStatusRefreshRequest: new Map(),
    filterMultiAccountExpandedAccounts: accounts => accounts,
    buildExpandedMultiAccountCard: () => 'card',
    escapeHtml: value => value,
    checkOverdueBeforeStart: async () => { paymentChecks += 1; return false },
    _consumeOverdueForceOverride: () => { forceOverrides += 1; return { bypass_overdue: true, waive_charge: true } },
    callMultiAccountStart: async (method, ...args) => { calls.push([method, ...args]); return { success: true, wait_skipped: true } },
    showModalAlert() {},
    logMessage_Error() {},
    Swal: { fire: async options => { options.didOpen?.(); return {} } },
  }
  vm.createContext(context)
  vm.runInContext([
    extract('async function openMultiAccountExpandedView(', 'function renderMultiAccountList('),
    extract('function renderMultiAccountList(', 'function multi_toggleSelectAll('),
    extract('function multi_updateAccountStatus(', 'function multi_updateRunnerPosition('),
  ].join('\n'), context)
  context.renderMultiAccountList([account])
  return {
    calls, context, desktopButton, mobileButton,
    checks: () => ({ paymentChecks, forceOverrides }),
    pushWait(canSkipWait) {
      context.multi_updateAccountStatus(account.username, { can_skip_wait: canSkipWait })
    },
    async click(surface) {
      if (surface === 'expanded') {
        await context.openMultiAccountExpandedView()
        const button = { dataset: { username: account.username, expandedAction: 'start' } }
        await expandedClick({ target: { closest: () => button } })
      } else {
        const button = surface === 'mobile' ? mobileButton : desktopButton
        await button.onclick({ target: button, currentTarget: button })
      }
    },
  }
}

for (const surface of ['desktop', 'mobile', 'expanded']) {
  test(`legacy ${surface} starts a waiting account without a new payment preflight`, async () => {
    const ctx = setup(true)
    await ctx.click(surface)

    assert.deepEqual(ctx.checks(), { paymentChecks: 0, forceOverrides: 0 })
    assert.deepEqual(ctx.calls, [['multi_start_single_account', 'student-a', true, false, false]])
  })

  test(`legacy ${surface} keeps payment checks for accounts not eligible to skip waiting`, async () => {
    const ctx = setup(false)
    await ctx.click(surface)

    assert.deepEqual(ctx.checks(), { paymentChecks: 1, forceOverrides: 0 })
    assert.deepEqual(ctx.calls, [])
  })

  test(`legacy ${surface} cannot skip a wait while all accounts are stopping`, async () => {
    const ctx = setup(true, true)
    await ctx.click(surface)

    assert.deepEqual(ctx.checks(), { paymentChecks: 0, forceOverrides: 0 })
    assert.deepEqual(ctx.calls, [])
  })

  test(`legacy ${surface} uses the latest pushed eligibility when the current wait begins and ends`, async () => {
    const ctx = setup(false)
    ctx.pushWait(true)
    await ctx.click(surface)
    ctx.pushWait(false)
    await ctx.click(surface)

    assert.deepEqual(ctx.checks(), { paymentChecks: 1, forceOverrides: 0 })
    assert.deepEqual(ctx.calls, [['multi_start_single_account', 'student-a', true, false, false]])
  })
}
