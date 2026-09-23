import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { ref, computed } = require('vue')
const { defineStore, createPinia, setActivePinia } = require('pinia')

function createAppStore() {
  setActivePinia(createPinia())
  const source = readFileSync(new URL('../frontend/src/stores/app.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '')
    .replace('export const useAppStore', 'const useAppStore')
  const context = vm.createContext({ ref, computed, defineStore })
  return vm.runInContext(source + '\nuseAppStore()', context)
}

test('Vue live status updates are merged into the matching account card', () => {
  const app = createAppStore()
  app.multiAccounts = [{ username: 'student-a', status_text: '待命' }]
  app.handleMultiStatusUpdate({
    username: 'student-a',
    data: {
      status_text: 'Have_Tasks',
      summary: { not_started: 0, unexpired_incomplete_count: 2 },
    },
  })

  assert.equal(app.multiAccounts[0].status_text, 'Have_Tasks')
  assert.deepEqual(app.multiAccounts[0].summary, {
    not_started: 0,
    unexpired_incomplete_count: 2,
  })
})
