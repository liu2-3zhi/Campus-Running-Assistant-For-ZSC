import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function setup(invalid = false) {
  const navigated = []
  const auth = {
    adminOriginSession: 'origin-a', adminViewInvalid: invalid, sessionUUID: 'missing-target-c',
    isAuthenticated: true,
    clearAdminView() { this.adminOriginSession = ''; this.adminViewInvalid = false },
    activateSession(target) { this.sessionUUID = target },
    logout() { this.clearAdminView(); this.sessionUUID = null; this.isAuthenticated = false },
  }
  const source = readFileSync(new URL('../frontend/src/components/common/AdminReturnButton.vue', import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const context = vm.createContext({ useAuthStore: () => auth, useRouter: () => ({ push: route => navigated.push(route) }) })
  vm.runInContext(script, context)
  return { auth, navigated, click: () => vm.runInContext('returnToAdministrator()', context) }
}

test('return control can restore the original administrator when the viewed target is unavailable', () => {
  const ctx = setup()
  ctx.click()
  assert.equal(ctx.auth.sessionUUID, 'origin-a')
  assert.equal(ctx.auth.adminOriginSession, '')
  assert.equal(ctx.navigated[0].params.uuid, 'origin-a')
})

test('an explicitly invalid administrator origin returns to system login', () => {
  const ctx = setup(true)
  ctx.click()
  assert.equal(ctx.navigated[0].name, 'login')
  assert.equal(ctx.auth.adminOriginSession, '')
  assert.equal(ctx.auth.isAuthenticated, false)
})
