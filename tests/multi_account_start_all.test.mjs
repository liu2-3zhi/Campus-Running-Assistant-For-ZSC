import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

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

  assert.match(startAllSource, /await _checkOverdueBeforeStartByCurrentMode\(\)/)
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
    /await _checkOverdueBeforeStartByCurrentMode\(\)/,
  )
  assert.doesNotMatch(mobileStartAllSource, /loadInitialData\(\)/)
})
