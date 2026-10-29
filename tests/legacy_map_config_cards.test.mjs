import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/legacy-admin-config.js', import.meta.url), 'utf8')
const context = vm.createContext({
  URL, crypto: { randomUUID: () => 'new-config' },
  document: { addEventListener() {} },
})
vm.runInContext(source, context)
const plain = value => JSON.parse(JSON.stringify(value))

// Model only the DOM operations used by the editor; browser smoke tests cover rendering.
function editorFixture(configs, frontend, backend) {
  const selects = { frontend: { value: frontend }, backend: { value: backend } }
  const list = {
    cards: [],
    get lastElementChild() { return this.cards.at(-1) },
    insertBefore(card, before) {
      this.cards.splice(this.cards.indexOf(card), 1)
      this.cards.splice(this.cards.indexOf(before), 0, card)
    },
    insertAdjacentHTML(_position, html) {
      const config = {
        id: html.match(/data-config-id="([^"]*)"/)[1],
        provider: html.match(/data-provider="([^"]*)"/)[1],
      }
      for (const match of html.matchAll(/data-map-config-field="([^"]*)"[^>]*value="([^"]*)"/g)) config[match[1]] = match[2]
      this.cards.push(cardFixture(config))
    },
  }
  const editor = {
    querySelectorAll(selector) {
      return selector === '[data-map-config-card]' ? list.cards : Object.values(selects)
    },
    querySelector(selector) {
      if (selector === '[data-map-config-list]') return list
      if (selector === '[data-map-add-provider]') return { value: 'amap' }
      return selects[selector.includes('frontend') ? 'frontend' : 'backend']
    },
  }
  function cardFixture(config) {
    const fields = Object.fromEntries(Object.entries(config).filter(([key]) => !['id', 'provider'].includes(key))
      .map(([key, value]) => [key, { value, dataset: { mapConfigField: key }, focus() {} }]))
    const controls = {}
    return {
      dataset: { configId: config.id, provider: config.provider }, fields,
      parentElement: list,
      get previousElementSibling() { return list.cards[list.cards.indexOf(this) - 1] },
      get nextElementSibling() { return list.cards[list.cards.indexOf(this) + 1] },
      closest: () => editor,
      querySelectorAll: () => Object.values(fields),
      querySelector(selector) {
        const field = selector.match(/data-map-config-field="([^"]+)"/)?.[1]
        return field ? fields[field] : (controls[selector] ??= {})
      },
      remove() { list.cards.splice(list.cards.indexOf(this), 1) },
    }
  }
  list.cards = configs.map(cardFixture)
  const panel = { querySelector: () => editor }
  const button = card => ({ closest: selector => selector.includes('editor') ? editor : card })
  return { editor, list, selects, panel, button }
}

test('legacy migration keeps all provider credentials and deterministic selection IDs', () => {
  const settings = plain(context.normalizeLegacyMapConfigSettings({
    provider: 'tencent', providers: { amap: { js_key: 'front-placeholder', security_js_code: 'security-placeholder' } },
    tencent_map_key: 'legacy-placeholder',
  }))
  assert.equal(settings.configs.length, 4)
  assert.equal(settings.configs[0].id, 'legacy-amap')
  assert.equal(settings.configs[0].js_key, 'front-placeholder')
  assert.equal(settings.configs[1].map_key, 'legacy-placeholder')
  assert.equal(settings.frontend_config_id, 'legacy-tencent')
  assert.equal(settings.backend_config_id, 'legacy-tencent')
})

test('rendering escapes names, IDs and credentials and uses password fields', () => {
  const html = context.renderMapConfigCards({ configs: [{
    id: 'map-1', name: '<img src=x onerror="bad">', provider: 'amap',
    js_key: '" autofocus onfocus="bad', security_js_code: '', backend_page_origin: '',
  }], frontend_config_id: 'map-1', backend_config_id: 'map-1' })
  assert.ok(!html.includes('<img'))
  assert.ok(html.includes('&lt;img'))
  assert.ok(html.includes('type="password" data-map-config-field="js_key"'))
  assert.ok(html.includes('&quot; autofocus onfocus=&quot;bad'))
})

test('adding, moving, renaming and deleting cards preserve independent frontend/backend choices', () => {
  const first = { id: 'front', name: '高德1', provider: 'amap', js_key: 'front-placeholder', security_js_code: '', backend_page_origin: '' }
  const second = { ...first, id: 'back', name: '高德2', js_key: 'back-placeholder', backend_page_origin: 'https://backend.test/path' }
  const fixture = editorFixture([first, second], 'front', 'back')
  context.addMapConfigCard(fixture.button())
  assert.equal(fixture.list.cards.length, 3)
  const added = fixture.list.cards[2]
  assert.equal(added.dataset.configId, 'map-new-config')
  context.moveMapConfigCard(fixture.button(added), -1)
  assert.deepEqual(fixture.list.cards.map(card => card.dataset.configId), ['front', 'map-new-config', 'back'])
  assert.equal(fixture.selects.frontend.value, 'front')
  assert.equal(fixture.selects.backend.value, 'back')
  fixture.list.cards.at(-1).fields.name.value = '后端专用'
  context.syncMapConfigCardOptions(fixture.editor)
  const payload = plain(context.readMapConfigCards(fixture.panel))
  assert.equal(payload.configs.at(-1).name, '后端专用')
  assert.equal(payload.configs.at(-1).js_key, 'back-placeholder')
  assert.equal(payload.configs.at(-1).backend_page_origin, 'https://backend.test')
  assert.equal(payload.frontend_config_id, 'front')
  assert.equal(payload.backend_config_id, 'back')
  context.removeMapConfigCard(fixture.button(fixture.list.cards[0]))
  assert.equal(fixture.selects.frontend.value, 'map-new-config')
  assert.equal(fixture.selects.backend.value, 'back')
  context.removeMapConfigCard(fixture.button(fixture.list.cards[1]))
  context.removeMapConfigCard(fixture.button(fixture.list.cards[0]))
  assert.equal(fixture.list.cards.length, 1)
})

test('saving is scoped to its editor and rejects blank names or invalid origins', () => {
  const fixture = editorFixture([{ id: 'one', name: '', provider: 'baidu', ak: '', backend_page_origin: '' }], 'one', 'one')
  assert.throws(() => context.readMapConfigCards(fixture.panel), /名称/)
  fixture.list.cards[0].fields.name.value = '百度'
  fixture.list.cards[0].fields.backend_page_origin.value = 'file:///map'
  assert.throws(() => context.readMapConfigCards(fixture.panel), /HTTP/)
  fixture.list.cards[0].fields.backend_page_origin.value = ''
  assert.equal(context.readMapConfigCards(fixture.panel).configs[0].ak, '')
})

test('cloned mobile editors restore live values and initialize a distinct drag instance', () => {
  const config = { id: 'one', name: '高德1', provider: 'amap', js_key: '', security_js_code: '', backend_page_origin: '' }
  const fixture = editorFixture([config], 'one', 'one')
  const live = [{ value: '已编辑名称' }, { value: 'placeholder-new-key' }, { value: 'one' }]
  const cloned = live.map(() => ({ value: '' }))
  const instances = []
  context.Sortable = function (list, options) { instances.push({ list, options }) }
  const target = {
    querySelectorAll: selector => selector === '[data-map-config-editor]' ? [fixture.editor] : cloned,
  }
  context.copyMapConfigEditorState({ querySelectorAll: () => live }, target)
  assert.deepEqual(cloned.map(input => input.value), live.map(input => input.value))
  assert.equal(instances.length, 1)
  assert.equal(instances[0].list, fixture.list)
  assert.equal(instances[0].options.handle, '[data-map-drag-handle]')
  context.initMapConfigCardsSort(target)
  assert.equal(instances.length, 1)
  delete context.Sortable
})
