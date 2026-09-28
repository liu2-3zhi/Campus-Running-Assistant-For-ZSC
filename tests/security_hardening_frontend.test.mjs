import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('Vue 2FA verification forwards the server challenge', () => {
  const source = readFileSync(
    new URL('../frontend/src/components/login/AuthPanel.vue', import.meta.url),
    'utf8',
  )
  assert.match(source, /two_fa_challenge/)
  assert.match(source, /challenge:\s*pending2FAData\.value\?\.two_fa_challenge/)
})

test('legacy 2FA verification forwards the server challenge', () => {
  const source = readFileSync(
    new URL('../scripts/main.js', import.meta.url),
    'utf8',
  )
  assert.match(source, /temp2FAChallenge/)
  assert.match(source, /challenge:\s*window\.temp2FAChallenge/)
})
