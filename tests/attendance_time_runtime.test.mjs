import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import * as formatters from '../frontend/src/utils/format.js'

process.env.TZ = 'Asia/Shanghai'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { createSSRApp } = require('vue')
const { renderToString } = require('@vue/server-renderer')
const legacySource = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const controlTabs = readFileSync(new URL('../frontend/src/components/main/ControlTabs.vue', import.meta.url), 'utf8')
const timeTemplate = controlTabs.match(/<div v-if="t\.(?:createtime|time)[\s\S]*?<\/div>/)?.[0]
assert.ok(timeTemplate, 'attendance time template must exist')

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char])
}

function legacyRuntime(notice, overrides = {}) {
  const element = () => ({
    get innerHTML() { return this.html || '' },
    set innerHTML(value) { this.html = value; this.children = [] },
    children: [], classList: { add() {}, remove() {} },
    appendChild(child) { this.children.push(child) }, addEventListener() {}, remove() {},
  })
  const elements = new Map()
  const getElement = id => {
    if (!elements.has(id)) elements.set(id, element())
    return elements.get(id)
  }
  const context = vm.createContext({
    window: { currentNotifications: [notice] },
    document: { createElement: element, getElementById: getElement },
    $: getElement, escapeHtml, escapeInlineJsArg: JSON.stringify, logMessage_Info() {},
    logMessage_Debug() {}, IS_OFFLINE: false, ...overrides,
  })
  vm.runInContext('let notificationAutoRefreshTimer = null; let isRefreshingNotifications = false', context)
  for (const name of [
    'formatNotificationTime', 'renderNotificationBatch', 'onNotificationsUpdated',
    'syncMobileAttendanceList', 'updateMobileNotificationUI', 'fetchNotifications',
    'refreshNotificationsUI',
  ]) {
    const source = legacySource.match(new RegExp(`(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`))?.[0]
    if (source) vm.runInContext(source, context)
  }
  return { context, getElement }
}

function legacyLists(notice) {
  const { context, getElement } = legacyRuntime(notice)
  context.onNotificationsUpdated({ success: true, notices: [notice], unreadCount: 0 })
  context.renderNotificationBatch([notice], getElement('notifications'))
  context.updateMobileNotificationUI()
  return Object.fromEntries([
    'attendance-list', 'mobile-attendance-list', 'notifications',
    'mobile-all-notifications-list', 'mobile-attendance-notifications-list',
  ].map(id => [id, getElement(id).children[0]?.innerHTML || '']))
}

test('legacy automatic refresh keeps full time when later responses contain timestamps', async () => {
  const timers = []
  const notice = {
    id: 'notice-1', title: 'Course', content: 'Attendance', image: 'attendance',
    attendance_code: -1, updateBy: '22.5,113.3', isRead: 1,
  }
  let refreshCount = 0
  const { context, getElement } = legacyRuntime(notice, {
    setTimeout(callback, delay) { timers.push({ callback, delay }); return timers.length },
    clearTimeout() {},
    callPythonAPI: async method => {
      if (method === 'get_cached_notifications') return { success: true, cached: false, notices: [] }
      assert.equal(method, 'get_notifications')
      refreshCount++
      return {
        success: true, unreadCount: 0, hasMore: false,
        notices: [{ ...notice, createtime: refreshCount === 1 ? '2026-10-13 17:32:20' : 1791883940000 }],
      }
    },
  })
  getElement('param-auto_attendance_refresh_s').value = '15'
  await context.refreshNotificationsUI(false, false, false)
  const expected = '>2026-10-13 17:32:20</'
  assert.ok(getElement('attendance-list').children[0].innerHTML.includes(expected))
  assert.equal(timers[0].delay, 15000)

  // Deliver the real refresh callback without waiting for a wall-clock timeout.
  timers.shift().callback()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(refreshCount, 2)
  assert.equal(context.window.currentNotifications[0].createtime, 1791883940000)
  for (const id of ['attendance-list', 'mobile-attendance-list', 'notifications-content']) {
    assert.equal(getElement(id).children.length, 1, `${id} must replace its previous content`)
    assert.ok(getElement(id).children[0].innerHTML.includes(expected), `${id} must retain full time after refresh`)
  }
})

const timestampCases = [
  [1791883940000, '2026-10-13 17:32:20'],
  ['1790673363000', '2026-09-29 17:16:03'],
  [1791883940, '2026-10-13 17:32:20'],
  ['1790673363', '2026-09-29 17:16:03'],
  ['2026-10-13 17:32:20', '2026-10-13 17:32:20'],
  ['2026-10-13T09:32:20Z', '2026-10-13 17:32:20'],
  [0, '1970-01-01 08:00:00'],
]

for (const [value, expected] of timestampCases) {
  test(`legacy attendance and notifications display full local time for ${JSON.stringify(value)}`, () => {
    const notice = {
      id: 'notice-1', title: 'Course', content: 'Attendance', image: 'attendance',
      attendance_code: -1, updateBy: '22.5,113.3', isRead: 1, createtime: value,
    }
    for (const [id, html] of Object.entries(legacyLists(notice))) {
      assert.ok(html.includes(`>${expected}</`), `${id} must show ${expected}; got ${html}`)
    }
    assert.equal(notice.createtime, value, 'rendering must preserve the API timestamp')
  })

  test(`Vue attendance reads createtime and displays full local time for ${JSON.stringify(value)}`, async () => {
    const app = createSSRApp({
      template: timeTemplate,
      setup: () => ({ t: { createtime: value }, ...formatters }),
    })
    const html = await renderToString(app)
    assert.ok(html.includes(expected), `Vue must show ${expected}; got ${html}`)
  })
}

for (const value of [null, undefined, '', 'invalid date', '<img src=x onerror=alert(1)>']) {
  test(`legacy lists handle missing or invalid time ${JSON.stringify(value)} safely`, () => {
    const notice = { id: 'notice-1', image: 'attendance', createtime: value }
    const expected = escapeHtml(value == null || value === '' ? '-' : value)
    for (const [id, html] of Object.entries(legacyLists(notice))) {
      assert.ok(html.includes(`>${expected}</`), `${id} must safely display ${expected}`)
      assert.ok(!html.includes('Invalid Date'), `${id} must not expose Invalid Date`)
    }
  })
}

for (const field of ['time', 'date', 'created_at']) {
  test(`Vue attendance preserves the ${field} fallback`, async () => {
    const app = createSSRApp({
      template: timeTemplate,
      setup: () => ({ t: { [field]: '1791883940000' }, ...formatters }),
    })
    assert.ok((await renderToString(app)).includes('2026-10-13 17:32:20'))
  })
}
