import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'

const root = resolve(import.meta.dirname, '..')
const runtimeSource = readFileSync(resolve(root, 'scripts/legacy-app-runtime.js'), 'utf8')
const mainSource = readFileSync(resolve(root, 'scripts/main.js'), 'utf8')

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `${name} must exist`)
  const end = source.indexOf('\n}', start)
  assert.notEqual(end, -1)
  return source.slice(start, end + 2)
}

function createOverlayHarness(pathname = '/') {
  const roots = []
  const intervals = new Map()
  const navigations = []
  let intervalId = 0
  const document = {
    getElementById(id) {
      const visit = (node) => node.id === id ? node : node.children.map(visit).find(Boolean)
      return roots.map(visit).find(Boolean) || null
    },
    createElement(tagName) {
      return {
        tagName,
        children: [],
        style: {},
        classList: { contains() { return false } },
        appendChild(child) { this.children.push(child); child.parentNode = this },
        removeChild(child) { this.children.splice(this.children.indexOf(child), 1) },
      }
    },
    body: { appendChild(node) { roots.push(node); node.parentNode = this }, removeChild(node) { roots.splice(roots.indexOf(node), 1) } },
  }
  const context = vm.createContext({
    document,
    window: { location: { pathname, replace(path) { navigations.push(path) } } },
    setInterval(callback) { const id = ++intervalId; intervals.set(id, callback); return id },
    clearInterval(id) { intervals.delete(id) },
    buildLegacyUiPath: () => pathname.startsWith('/old/') ? '/old/' : '/', 
    stopReminderChecker() {},
    logMessage_Info() {},
  })
  const source = `let sessionMissingCountdownTimer = null;\n${extractFunction(runtimeSource, 'showSessionMissingOverlay')}`
  vm.runInContext(source, context)
  return { context, document, intervals, navigations }
}

test('session-missing prompt on root uses the existing copy and reloads root after ten seconds', () => {
  const { context, document, intervals, navigations } = createOverlayHarness('/')
  context.showSessionMissingOverlay()
  const overlay = document.getElementById('logout-elsewhere-overlay')
  assert.ok(overlay)
  const content = overlay.children[0].children
  assert.ok(content.some((node) => node.textContent === '会话不存在'))
  assert.ok(content.some((node) => node.textContent === '该会话已过期或不存在，请重新登录'))
  assert.ok(content.some((node) => node.textContent === '10秒后自动跳转'))
  for (let i = 0; i < 10; i++) [...intervals.values()][0]()
  assert.deepEqual(navigations, ['/'])
  assert.equal(intervals.size, 0)
})

test('session-missing prompt button preserves the old UI entry path', () => {
  const { context, document, intervals, navigations } = createOverlayHarness('/old/uuid=11111111-1111-4111-8111-111111111111')
  context.showSessionMissingOverlay()
  const button = document.getElementById('logout-elsewhere-overlay').children[0].children.find((node) => node.tagName === 'button')
  button.onclick()
  assert.deepEqual(navigations, ['/old/'])
  assert.equal(intervals.size, 0)
})

function createExitHarness(shutdownResult, isGuest = false) {
  let exitHandler
  const notices = []
  let promptCount = 0
  let stopCount = 0
  const exitButton = { addEventListener(_name, handler) { exitHandler = handler } }
  const executionStart = mainSource.indexOf('const legacyRunnerExecutionState =')
  const executionEnd = mainSource.indexOf('function acceptLegacyRunnerExecution(', executionStart)
  assert.ok(executionStart >= 0 && executionEnd > executionStart)
  const start = mainSource.indexOf('    const exitAppBtn = $("exit-app-btn");')
  const end = mainSource.indexOf('    const modalAdminPanel =', start)
  assert.ok(start >= 0 && end > start)
  const context = vm.createContext({
    $: () => exitButton,
    currentUserIsGuest: isGuest,
    sessionUUID: '11111111-1111-4111-8111-111111111111',
    jsShowConfirm: async () => true,
    callPythonAPI_raw: async () => shutdownResult,
    fetch: async () => ({ ok: shutdownResult.success, json: async () => shutdownResult }),
    stopReminderChecker() { stopCount++ },
    startReminderChecker() {},
    showSessionMissingOverlay() { promptCount++ },
    Swal: { fire(options) { notices.push(options); return Promise.resolve() } },
    console: { error() {} },
    window: { location: { href: '' } },
  })
  vm.runInContext(`${mainSource.slice(executionStart, executionEnd)}\n${mainSource.slice(start, end)}`, context)
  return { click: () => exitHandler({ preventDefault() {}, stopPropagation() {} }), notices, get promptCount() { return promptCount }, get stopCount() { return stopCount } }
}

test('successful multi-account exit shows the session-missing prompt', async () => {
  const harness = createExitHarness({ success: true, redirect_url: '/' })
  await harness.click()
  assert.equal(harness.promptCount, 1)
  assert.equal(harness.notices.length, 0)
  assert.equal(harness.stopCount, 1)
})

test('failed multi-account exit keeps the page and reports the API error', async () => {
  const harness = createExitHarness({ success: false, message: '未能登出' })
  await harness.click()
  assert.equal(harness.promptCount, 0)
  assert.match(harness.notices[0].text, /未能登出/)
})

test('successful guest exit uses the same session-missing prompt', async () => {
  const harness = createExitHarness({ success: true }, true)
  await harness.click()
  assert.equal(harness.promptCount, 1)
  assert.equal(harness.notices.length, 0)
  assert.equal(harness.stopCount, 1)
})
