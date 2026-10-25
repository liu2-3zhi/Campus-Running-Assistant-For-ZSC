import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../frontend/src/components/admin/AdminReminders.vue', import.meta.url),
  'utf8',
)
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)?.[1]

function createReminderEditor() {
  const requests = []
  const callRawAPI = async (url, method, body) => {
    requests.push({ url, method, body })
    return url === '/api/reminders/list'
      ? { success: true, reminders: [] }
      : { success: true }
  }
  const setup = script.replace(/^import .*$/gm, '')
  const editor = new Function(
    'ref', 'computed', 'onMounted', 'callAPI', 'callRawAPI',
    `${setup}\nreturn { form, openAddEditor, openEditEditor, saveReminder }`,
  )(
    (value) => ({ value }),
    (fn) => ({ get value() { return fn() } }),
    () => {},
    () => {},
    callRawAPI,
  )
  return { ...editor, requests }
}

test('Vue reminder form defaults guest visibility to false on each new reminder', () => {
  const editor = createReminderEditor()
  editor.openAddEditor()
  assert.equal(editor.form.value.allow_guest_view, false)
  editor.form.value.allow_guest_view = true
  editor.openAddEditor()
  assert.equal(editor.form.value.allow_guest_view, false)
})

test('Vue reminder editor treats missing legacy guest visibility as false', () => {
  const editor = createReminderEditor()
  editor.openEditEditor({ id: 'legacy', title: 'Old reminder' })
  assert.equal(editor.form.value.allow_guest_view, false)
  editor.openEditEditor({ id: 'new', title: 'New reminder', allow_guest_view: true })
  assert.equal(editor.form.value.allow_guest_view, true)
})

test('Vue reminder save sends guest visibility as a boolean on add and edit', async () => {
  const editor = createReminderEditor()
  editor.openAddEditor()
  Object.assign(editor.form.value, {
    title: 'Reminder', message: 'Message', start_time: '09:00', end_time: '10:00',
  })
  await editor.saveReminder()
  assert.deepEqual(editor.requests[0], {
    url: '/api/reminders/add', method: 'POST',
    body: {
      title: 'Reminder', message: 'Message', start_time: '09:00', end_time: '10:00',
      enabled: true, allow_guest_view: false,
    },
  })

  editor.openEditEditor({
    id: 'existing', title: 'Reminder', message: 'Message',
    start_time: '09:00', end_time: '10:00', allow_guest_view: true,
  })
  await editor.saveReminder()
  assert.equal(editor.requests[2].url, '/api/reminders/update')
  assert.equal(editor.requests[2].body.allow_guest_view, true)
})

test('Vue reminder UI exposes guest visibility and legacy list fallback', () => {
  assert.match(source, /v-model="form\.allow_guest_view"/)
  assert.match(source, /reminder\.allow_guest_view\s*===\s*true/)
  assert.match(source, /允许访客查看/)
})
