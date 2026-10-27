import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function createStore() {
  const source = readFileSync(new URL('../frontend/src/stores/app.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useAppStore', 'const useAppStore')
  return vm.runInNewContext(`${source}\nuseAppStore()`, {
    defineStore: (_name, factory) => factory,
    ref: value => ({ value }), computed: getter => ({ get value() { return getter() } }),
  })
}

const account = (username, lon, lat) => ({ username, name: `${username}-name`, current_position: lon == null ? null : { lon, lat } })

test('multi-account HTTP snapshots restore positions without a websocket event', () => {
  const store = createStore()
  store.bindBusinessSession('A')
  store.handleAccountsUpdated({ accounts: [account('first', 113, 22), account('idle', null)] })
  assert.equal(store.multiPositions.value.first.lon, 113)
  assert.equal(store.multiPositions.value.first.name, 'first-name')
  assert.equal(store.multiPositions.value.idle, undefined)
})

test('a refresh cannot replace a newer websocket position or clear it with an old null', () => {
  const store = createStore()
  store.bindBusinessSession('A')
  store.applyMultiAccountsSnapshot([account('first', 113, 22)])
  const request = store.captureMultiAccountsSnapshot()
  store.handleMultiPositionUpdate({ username: 'first', lon: 114, lat: 23 })
  store.applyMultiAccountsSnapshot([account('first', 110, 20)], request)
  assert.equal(store.multiPositions.value.first.lon, 114)
  const nextRequest = store.captureMultiAccountsSnapshot()
  store.handleMultiPositionUpdate({ username: 'first', lon: 115, lat: 24 })
  store.applyMultiAccountsSnapshot([account('first', null)], nextRequest)
  assert.equal(store.multiPositions.value.first.lon, 115)
})

test('removing accounts prunes markers and an older HTTP snapshot or late position cannot resurrect them', () => {
  const store = createStore()
  store.bindBusinessSession('A')
  store.applyMultiAccountsSnapshot([account('first', 113, 22), account('second', 114, 23)])
  const oldRequest = store.captureMultiAccountsSnapshot()
  store.handleAccountsUpdated({ accounts: [account('second', 114, 23)] })
  assert.equal(store.multiPositions.value.first, undefined)
  assert.equal(store.applyMultiAccountsSnapshot([account('first', 113, 22), account('second', 114, 23)], oldRequest), false)
  store.handleMultiPositionUpdate({ username: 'first', lon: 115, lat: 24 })
  assert.equal(store.multiPositions.value.first, undefined)
  store.handleAccountsUpdated({ accounts: [] })
  assert.equal(Object.keys(store.multiPositions.value).length, 0)
})

test('newer HTTP results and a changed business session reject superseded snapshots', () => {
  const store = createStore()
  store.bindBusinessSession('A')
  const oldRequest = store.captureMultiAccountsSnapshot()
  const currentRequest = store.captureMultiAccountsSnapshot()
  store.applyMultiAccountsSnapshot([account('first', 114, 23)], currentRequest)
  assert.equal(store.applyMultiAccountsSnapshot([account('first', 113, 22)], oldRequest), false)
  assert.equal(store.multiPositions.value.first.lon, 114)
  const previousSession = store.captureMultiAccountsSnapshot()
  store.bindBusinessSession('B')
  assert.equal(store.applyMultiAccountsSnapshot([account('first', 113, 22)], previousSession), false)
  assert.equal(Object.keys(store.multiPositions.value).length, 0)
})

test('an explicit idle position clears a marker while a metadata-only account update retains it', () => {
  const store = createStore()
  store.applyMultiAccountsSnapshot([account('first', 113, 22)])
  store.handleAccountsUpdated({ accounts: [{ username: 'first', name: 'new-name' }] })
  assert.equal(store.multiPositions.value.first.lon, 113)
  store.handleAccountsUpdated({ accounts: [account('first', null)] })
  assert.equal(store.multiPositions.value.first, undefined)
})
