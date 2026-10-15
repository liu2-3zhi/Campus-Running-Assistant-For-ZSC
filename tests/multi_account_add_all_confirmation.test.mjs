import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../', import.meta.url)

function read(path) {
  return readFileSync(new URL(path, root), 'utf8')
}

function extractFunction(source, name, nextName) {
  const start = source.indexOf(`async function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const end = source.indexOf(`function ${nextName}(`, start + 1)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end)
}

function assertTwoConfirmationsBeforeRequest(
  source,
  confirmationPattern,
  requestPattern,
  firstGuardPattern,
  secondGuardPattern,
) {
  const confirmations = [...source.matchAll(confirmationPattern)]
  assert.equal(confirmations.length, 2, '批量添加必须执行两次确认')
  const request = source.search(requestPattern)
  assert.notEqual(request, -1, 'missing batch-add request')
  assert.ok(
    confirmations.every(({ index }) => index < request),
    '两次确认都必须发生在批量添加请求之前',
  )
  assert.match(source, firstGuardPattern, '第一次取消必须终止批量添加')
  assert.match(source, secondGuardPattern, '第二次取消必须终止批量添加')
}

test('desktop add-all requires two confirmations before loading configured accounts', () => {
  const source = read('scripts/main.js')
  const fn = extractFunction(source, 'multi_loadAllFromConfig', 'openNewUserModal')
  assertTwoConfirmationsBeforeRequest(
    fn,
    /await jsShowConfirm\(/g,
    /callPythonAPI_raw\(/,
    /const confirmed = await jsShowConfirm\([\s\S]*?if \(!confirmed\) return/,
    /const confirmedAgain = await jsShowConfirm\([\s\S]*?if \(!confirmedAgain\) return/,
  )
})

test('mobile add-all requires two confirmations before loading configured accounts', () => {
  const source = read('scripts/legacy-mobile-multi.js')
  const fn = extractFunction(source, 'addMobileAllConfigs', 'openManualAccountModal')
  assertTwoConfirmationsBeforeRequest(
    fn,
    /await jsShowConfirm\(/g,
    /callPythonAPI\(/,
    /const confirmed = await jsShowConfirm\([\s\S]*?if \(!confirmed\) return/,
    /const confirmedAgain = await jsShowConfirm\([\s\S]*?if \(!confirmedAgain\) return/,
  )
})

test('Vue add-all requires two confirmations before loading configured accounts', () => {
  const source = read('frontend/src/views/MultiAccountView.vue')
  const fn = extractFunction(source, 'addAllFromConfig', 'addManual')
  assertTwoConfirmationsBeforeRequest(
    fn,
    /await window\.Swal\?\.fire\(/g,
    /callRawAPI\(/,
    /const confirmed = await window\.Swal\?\.fire\([\s\S]*?if \(!confirmed\?\.isConfirmed\) return/,
    /const confirmedAgain = await window\.Swal\?\.fire\([\s\S]*?if \(!confirmedAgain\?\.isConfirmed\) return/,
  )
})
