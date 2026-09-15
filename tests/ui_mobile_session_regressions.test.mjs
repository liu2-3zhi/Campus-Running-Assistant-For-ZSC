import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readProjectFile(relativePath) {
  return readFileSync(resolve(PROJECT_ROOT, relativePath), 'utf8')
}

test('original mobile layout keeps generate, clear, and export path tools', () => {
  const html = readProjectFile('index.html')

  assert.match(html, /id="mobile-auto-gen-button"/)
  assert.match(html, /id="mobile-clear-button"/)
  assert.match(html, /id="mobile-export-button"/)
  assert.doesNotMatch(html, /id="mobile-record-button"/)
  assert.doesNotMatch(html, /id="mobile-process-button"/)
  assert.match(html, /id="record-button"/)
})

test('Vue mobile keeps path tools except recording and processing', () => {
  const source = readProjectFile('frontend/src/components/main/ControlTabs.vue')

  assert.match(source, /:tabs="tabs"/)
  assert.match(
    source,
    /v-if="!app\.isMobile"[\s\S]{0,300}@click="recordPath"/,
  )
  assert.match(
    source,
    /v-if="!app\.isMobile"[\s\S]{0,300}@click="processPath"/,
  )
  assert.match(source, /@click="showAutoGenModal = true"/)
  assert.match(source, /@click="clearPath"/)
  assert.match(source, /@click="exportPath"/)
})

test('Vue UUID validation recognizes backend uuid_type responses', async () => {
  const validation = await import('../frontend/src/utils/validation.js')
  const isRestorableSessionUUIDResponse =
    validation.isRestorableSessionUUIDResponse

  assert.equal(typeof isRestorableSessionUUIDResponse, 'function')
  assert.equal(
    isRestorableSessionUUIDResponse({ success: true, uuid_type: 'guest' }),
    true,
  )
  assert.equal(
    isRestorableSessionUUIDResponse({
      success: true,
      uuid_type: 'system_account',
    }),
    true,
  )
  assert.equal(
    isRestorableSessionUUIDResponse({ success: true, uuid_type: 'unknown' }),
    false,
  )
  assert.equal(
    isRestorableSessionUUIDResponse({ success: false, uuid_type: 'guest' }),
    false,
  )
  assert.equal(isRestorableSessionUUIDResponse({ type: 'session' }), true)
  assert.equal(isRestorableSessionUUIDResponse({ valid: true }), true)
})

test('Vue invalid or expired UUID returns to the root route', () => {
  const source = readProjectFile('frontend/src/views/LoginView.vue')
  const redirectCalls = source.match(/router\.replace\(['"]\/['"]\)/g) || []

  assert.ok(
    redirectCalls.length >= 2,
    'checkUUID must replace /uuid=... with / for invalid responses and errors',
  )
})

test('original expired-session helper replaces uuid routes with root', () => {
  const source = readProjectFile('scripts/main.new.js')
  const helperStart = source.indexOf(
    'function redirectToLoginAfterSessionExpiry()',
  )

  assert.notEqual(helperStart, -1)

  const helperEnd = source.indexOf('\n}', helperStart)
  assert.notEqual(helperEnd, -1)

  const helperSource = source.slice(helperStart, helperEnd + 2)
  const replaceCalls = []

  globalThis.window = {
    location: {
      pathname: '/uuid=11111111-1111-4111-8111-111111111111',
      replace(url) {
        replaceCalls.push(url)
        this.pathname = url
      },
    },
  }
  globalThis.logMessage_Info = () => {}

  const redirectToLoginAfterSessionExpiry = new Function(
    `${helperSource}; return redirectToLoginAfterSessionExpiry;`,
  )()
  redirectToLoginAfterSessionExpiry()
  redirectToLoginAfterSessionExpiry()

  assert.deepEqual(replaceCalls, ['/'])
})

test('original initialization and mobile 401 paths use the expiry redirect', () => {
  const source = readProjectFile('scripts/main.new.js')

  assert.match(
    source,
    /if \(!isAuthenticated\) \{[\s\S]{0,600}if \(sessionUUID\) \{[\s\S]{0,200}redirectToLoginAfterSessionExpiry\(\)/,
  )
  assert.match(
    source,
    /if \(isMobileMode\) \{[\s\S]{0,400}showMobileMessage\([\s\S]{0,400}redirectToLoginAfterSessionExpiry\(\)/,
  )
})
