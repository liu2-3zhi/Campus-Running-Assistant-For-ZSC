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
  return source.slice(start, end)
}

test('desktop start-all checks overdue state for the visible multi-account list', () => {
  const startAllSource = extractFunction('multi_startAll', 'multi_stopAll')

  assert.match(startAllSource, /await _checkOverdueBeforeStartByCurrentMode\(/)
  assert.doesNotMatch(startAllSource, /loadInitialData\(\)/)
  assert.doesNotMatch(startAllSource, /initialData\.accounts/)
})

test('mobile start-all uses the same current-mode overdue gate as desktop', () => {
  const mobileStartAllSource = extractFunction(
    'mobileStartAllAccounts',
    'mobileStopAllAccounts',
  )

  assert.match(
    mobileStartAllSource,
    /await _checkOverdueBeforeStartByCurrentMode\(/,
  )
  assert.doesNotMatch(mobileStartAllSource, /loadInitialData\(\)/)
})

test('overdue gate can return skip so start-all proceeds without overdue accounts', async () => {
  const source = readFileSync(
    new URL('../scripts/main.js', import.meta.url),
    'utf8',
  )
  const start = source.indexOf('async function checkOverdueBeforeStart(')
  const end = source.indexOf('let _requirePaymentForOverdueCache', start)
  assert.notEqual(start, -1)
  assert.notEqual(end, -1)

  let skipAction = null
  const context = {
    sessionUUID: 'session-a',
    console: { log() {}, error() {}, warn() {} },
    showModalAlert() {},
    async showOverduePaymentModal(_accounts, options) {
      skipAction = options.allowSkip
      return 'skip'
    },
    fetch: async () => ({
      async json() {
        return {
          success: true,
          has_overdue: true,
          overdue_accounts: [{ username: 'student-overdue' }],
        }
      },
    }),
  }
  vm.createContext(context)
  vm.runInContext(source.slice(start, end), context)

  let skipped = null
  const canStart = await context.checkOverdueBeforeStart(
    ['student-ok', 'student-overdue'],
    {
      allowSkip: true,
      onSkip: (accounts) => {
        skipped = accounts
      },
    },
  )

  assert.equal(canStart, true)
  assert.equal(skipAction, true)
  assert.deepEqual(JSON.parse(JSON.stringify(skipped)), [
    { username: 'student-overdue' },
  ])
})

test('overdue modal offers skip only when some accounts can still start', () => {
  const modalSource = extractFunction(
    'showOverduePaymentModal',
    'clearOverduePlaceholder',
  )

  assert.match(modalSource, /showDenyButton:\s*allowSkip/)
  assert.match(modalSource, /跳过欠费账号并开始/)
  assert.match(modalSource, /if \(result\.isDenied\) return "skip"/)
})
