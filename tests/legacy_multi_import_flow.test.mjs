import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')

function extractImportFunction() {
  const start = source.indexOf('async function multi_importFromExcel(')
  const end = source.indexOf('async function multi_exportToExcel(', start + 1)
  assert.notEqual(start, -1)
  assert.notEqual(end, -1)
  return source.slice(start, end)
}

test('legacy import previews, confirms, then runs the single-account flow', () => {
  const fn = extractImportFunction()
  assert.match(fn, /multi_preview_import_accounts/)
  assert.match(fn, /swal\.fire\(/)
  assert.match(fn, /当前检测到/)
  assert.match(fn, /runMultiImportProgress\(/)
  assert.match(source, /waitForLegacyImportVerification/)
  assert.match(source, /pending_verification/)
  assert.match(source, /login_verified/)
  assert.match(fn, /missingFlowDoneCallback = \(\) =>/)
  assert.match(fn, /startMissingPasswordFlow\(/)
  assert.match(fn, /flushMissingFlowDone\(\)/)
  assert.doesNotMatch(fn, /multi_import_accounts['"]/)
})

test('legacy import exposes a draggable upper-left progress panel with stop action', () => {
  assert.match(source, /id = "multi-import-progress-panel"/)
  assert.match(source, /startLegacyImportDrag/)
  assert.match(source, /pointermove/)
  assert.match(source, /停止导入/)
  assert.match(source, /等待登录验证/)
  assert.match(source, /position = "fixed"/)
})
