import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../frontend/src/views/MultiAccountView.vue', import.meta.url),
  'utf8',
)

function extractFunction(name, nextName) {
  const start = source.indexOf(`async function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const end = source.indexOf(`async function ${nextName}(`, start + 1)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end)
}

test('Vue import first previews accounts and confirms with a SweetAlert list', () => {
  const fn = extractFunction('importExcel', 'exportExcel')

  assert.match(fn, /multi_preview_import_accounts/)
  assert.match(fn, /window\.Swal\?\.fire\(/)
  assert.match(fn, /检测到/)
  assert.match(fn, /isConfirmed/)
  assert.doesNotMatch(fn, /multi_import_accounts['"]/) 
  assert.match(source, /function buildImportPreviewHtml\(records\)[\s\S]*records\.map\(/)
})

test('Vue confirmed import processes one account at a time and exposes stop state', () => {
  assert.match(source, /multi_import_account/)
  assert.match(source, /async function runImportTask\(/)
  assert.match(source, /stopRequested/)
  assert.match(source, /function stopImport\(/)
  assert.match(source, /importTask\.stopRequested/)
  assert.match(source, /importTask\.processed/)
})

test('Vue import progress panel is draggable and mounted at the upper left', () => {
  assert.match(source, /id="multi-import-progress-panel"/)
  assert.match(source, /startImportDrag/)
  assert.match(source, /pointermove/)
  assert.match(source, /position: 'fixed'/)
  assert.match(source, /importTask\.left/)
  assert.match(source, /导入进度/)
  assert.match(source, /停止导入/)
})
