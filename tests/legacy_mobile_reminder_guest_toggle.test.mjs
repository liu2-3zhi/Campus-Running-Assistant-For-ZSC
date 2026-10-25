import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const source = readFileSync(resolve('scripts/legacy-mobile-multi.js'), 'utf8')
const listStart = source.indexOf('async function mobileRefreshReminders(')
const editorStart = source.indexOf('async function ensureMobileReminderEditorInitialized(', listStart)
const openStart = source.indexOf('async function openMobileReminderEditModal(')
const closeStart = source.indexOf('function closeMobileReminderEditModal(', openStart)
const saveStart = source.indexOf('async function saveMobileReminder(', closeStart)
const toggleStart = source.indexOf('async function mobileToggleReminderEnabled(', saveStart)

assert.ok(listStart >= 0 && editorStart > listStart)
assert.ok(openStart >= 0 && closeStart > openStart && saveStart > closeStart && toggleStart > saveStart)

const listSource = source.slice(listStart, source.lastIndexOf('/**', editorStart))
const openSource = source.slice(openStart, source.lastIndexOf('/**', closeStart))
const closeSource = source.slice(closeStart, source.lastIndexOf('/**', saveStart))
const saveSource = source.slice(saveStart, source.lastIndexOf('/**', toggleStart))

function createHarness(reminders = []) {
  const elements = new Map()
  const requests = []
  const classList = () => ({ add() {}, remove() {} })
  const document = {
    getElementById(id) {
      return elements.get(id) || null
    },
    createElement() {
      const element = {
        id: '',
        classList: classList(),
        set innerHTML(html) {
          this.html = html
          for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
            elements.set(match[1], {
              id: match[1],
              value: '',
              checked: /\bchecked(?:\s|>)/.test(match[0]),
              focus() {},
            })
          }
        },
        get innerHTML() {
          return this.html
        },
      }
      return element
    },
    body: {
      appendChild(element) {
        elements.set(element.id, element)
      },
    },
  }
  async function fetch(url, options) {
    requests.push({ url, options })
    return {
      async json() {
        return url.endsWith('/list')
          ? { success: true, reminders }
          : { success: true }
      },
    }
  }
  const load = new Function(
    'document', 'fetch', 'setTimeout', 'sessionUUID',
    'showModalAlert', 'ensureMobileReminderEditorInitialized',
    'mobileRefreshReminders', 'loadReminders',
    `let mobileReminderEditor = null;\n${openSource}\n${closeSource}\n${saveSource}\nreturn { openMobileReminderEditModal, saveMobileReminder }`,
  )
  const functions = load(
    document, fetch, () => {}, 'session-id', () => {},
    async () => {}, () => {}, () => {},
  )
  return { document, elements, requests, ...functions }
}

test('mobile reminder editor defaults guest visibility to off for old and new records', async () => {
  const harness = createHarness([
    { id: 'visible', title: 'Visible', message: 'Message', start_time: '09:00', end_time: '10:00', enabled: true, allow_guest_view: true },
    { id: 'old', title: 'Old', message: 'Message', start_time: '09:00', end_time: '10:00', enabled: true },
  ])

  await harness.openMobileReminderEditModal('visible')
  const toggle = harness.document.getElementById('mobile-reminder-allow-guest-view-field')
  assert.ok(toggle, 'the editor should expose a guest visibility checkbox')
  assert.equal(toggle.checked, true)

  await harness.openMobileReminderEditModal('old')
  assert.equal(toggle.checked, false, 'old data without the field must be private to accounts')

  toggle.checked = true
  await harness.openMobileReminderEditModal()
  assert.equal(toggle.checked, false, 'new reminders must not inherit the previous edit')
})

test('mobile reminder save sends an explicit guest visibility boolean', async () => {
  const harness = createHarness()
  await harness.openMobileReminderEditModal()
  harness.document.getElementById('mobile-reminder-title-field').value = 'Title'
  harness.document.getElementById('mobile-reminder-message-field').value = 'Message'
  harness.document.getElementById('mobile-reminder-start-time-field').value = '09:00'
  harness.document.getElementById('mobile-reminder-end-time-field').value = '10:00'
  const toggle = harness.document.getElementById('mobile-reminder-allow-guest-view-field')
  assert.ok(toggle)

  toggle.checked = false
  await harness.saveMobileReminder()
  const first = harness.requests.find((request) => request.url.endsWith('/add'))
  assert.equal(JSON.parse(first.options.body).allow_guest_view, false)

  harness.document.getElementById('mobile-reminder-id-field').value = 'existing'
  toggle.checked = true
  await harness.saveMobileReminder()
  const second = harness.requests.find((request) => request.url.endsWith('/update'))
  assert.equal(JSON.parse(second.options.body).allow_guest_view, true)
})

test('mobile reminder list marks only explicitly guest-visible reminders', async () => {
  const rows = []
  const listContainer = {
    innerHTML: '',
    appendChild(row) {
      rows.push(row)
    },
  }
  const document = {
    getElementById(id) {
      return id === 'mobile-multi-admin-reminders-content' ? listContainer : null
    },
    createElement() {
      return { className: '', innerHTML: '' }
    },
  }
  const reminders = [
    { id: 'guest', title: 'Guest', message: 'Message', start_time: '09:00', end_time: '10:00', enabled: true, allow_guest_view: true },
    { id: 'old', title: 'Old', message: 'Message', start_time: '09:00', end_time: '10:00', enabled: true },
    { id: 'string', title: 'String', message: 'Message', start_time: '09:00', end_time: '10:00', enabled: true, allow_guest_view: 'true' },
  ]
  const fetch = async () => ({ json: async () => ({ success: true, reminders }) })
  const refresh = new Function(
    'document', 'fetch', 'sessionUUID', 'escapeHtml',
    `${listSource}\nreturn mobileRefreshReminders;`,
  )(document, fetch, 'session-id', (value) => value)

  await refresh()

  assert.equal(rows.length, 3)
  assert.match(rows[0].innerHTML, /访客可见/)
  assert.doesNotMatch(rows[1].innerHTML, /访客可见/)
  assert.doesNotMatch(rows[2].innerHTML, /访客可见/)
})
