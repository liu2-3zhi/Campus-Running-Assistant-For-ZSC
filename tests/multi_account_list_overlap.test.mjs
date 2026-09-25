import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const legacy = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../styles/style.css', import.meta.url), 'utf8')
const vue = readFileSync(new URL('../frontend/src/views/MultiAccountView.vue', import.meta.url), 'utf8')

test('legacy account rows wrap long statuses on desktop and mobile', () => {
  assert.match(legacy, /isMobile \? "flex flex-col gap-2 min-w-0"/)
  assert.match(legacy, /getMultiAccountStatusClass\(\s*displayStatusText,?\s*\)/)
  assert.match(legacy, /text-sky-600 bg-sky-100/)
  assert.match(styles, /#multi-account-list \.status-text \{[\s\S]*max-width: 58%[\s\S]*white-space: normal/)
  assert.match(styles, /#mobile-multi-account-list \.status-text \{[\s\S]*width: 100%[\s\S]*white-space: normal/)
})

test('Vue account rows move long statuses below identity on mobile', () => {
  assert.match(vue, /status-text max-w-\[58%\][^"]*text-right[^"]*break-words/)
  assert.match(vue, /flex min-w-0 flex-col gap-2/)
  assert.match(vue, /status-text w-full[^"]*text-left[^"]*break-words/)
})
