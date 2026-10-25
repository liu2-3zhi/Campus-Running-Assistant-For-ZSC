import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(resolve(import.meta.dirname, '..', 'scripts/legacy-reminders.js'), 'utf8')
const start = source.indexOf('async function openReminderEditModal(')
const end = source.indexOf('async function toggleReminderEnabled(', start)
assert.ok(start >= 0 && end > start)

function createHarness(reminder = null) {
  const elements = new Map()
  let markdown = ''
  for (const id of [
    'reminder-edit-modal', 'reminder-modal-title', 'reminder-id-field',
    'reminder-title-field', 'reminder-message-field', 'reminder-start-time-field',
    'reminder-end-time-field', 'reminder-enabled-field', 'reminder-allow-guest-view-field',
  ]) {
    elements.set(id, {
      value: '', checked: false,
      classList: { add() {}, remove() {} },
      focus() {},
    })
  }
  const requests = []
  const context = vm.createContext({
    $: (id) => elements.get(id),
    document: { getElementById: (id) => elements.get(id) || null },
    window: {
      _reminderEditorInitialized: true,
      reminderEditor: {
        setMarkdown(value) { markdown = value },
        getMarkdown() { return markdown },
        clear() { markdown = '' },
      },
    },
    fetch: async (url, options) => {
      requests.push({ url, options })
      return { json: async () => url.endsWith('/list')
        ? { success: true, reminders: reminder ? [reminder] : [] }
        : { success: true } }
    },
    sessionUUID: '11111111-1111-4111-8111-111111111111',
    setTimeout() {},
    showModalAlert() {},
    loadReminders() {},
    console: { log() {}, warn() {}, error() {} },
  })
  vm.runInContext(source.slice(start, end), context)
  return { context, elements, requests }
}

test('legacy PC new and old reminders default to no guest visibility', async () => {
  const oldReminder = {
    id: 'old', title: '旧提醒', message: '内容', start_time: '09:00',
    end_time: '10:00', enabled: true,
  }
  const { context, elements } = createHarness(oldReminder)
  elements.get('reminder-allow-guest-view-field').checked = true
  await context.openReminderEditModal()
  assert.equal(elements.get('reminder-allow-guest-view-field').checked, false)

  await context.openReminderEditModal('old')
  assert.equal(elements.get('reminder-allow-guest-view-field').checked, false)
})

test('legacy PC editor restores and submits the guest visibility boolean', async () => {
  const reminder = {
    id: 'guest-visible', title: '访客提醒', message: '内容', start_time: '09:00',
    end_time: '10:00', enabled: true, allow_guest_view: true,
  }
  const { context, elements, requests } = createHarness(reminder)
  await context.openReminderEditModal('guest-visible')
  assert.equal(elements.get('reminder-allow-guest-view-field').checked, true)
  await context.saveReminder()
  const save = requests.find(({ url }) => url.endsWith('/update'))
  assert.ok(save)
  assert.equal(JSON.parse(save.options.body).allow_guest_view, true)

  await context.openReminderEditModal()
  assert.equal(elements.get('reminder-allow-guest-view-field').checked, false)
  elements.get('reminder-title-field').value = '新提醒'
  context.window.reminderEditor.setMarkdown('内容')
  elements.get('reminder-start-time-field').value = '09:00'
  elements.get('reminder-end-time-field').value = '10:00'
  await context.saveReminder()
  const add = requests.find(({ url }) => url.endsWith('/add'))
  assert.ok(add)
  assert.equal(JSON.parse(add.options.body).allow_guest_view, false)
})
