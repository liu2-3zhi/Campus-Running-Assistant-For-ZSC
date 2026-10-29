import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createMapConfigProfile, normalizeMapConfigProfiles, moveMapConfigProfile,
  removeMapConfigProfile, serializeMapConfigProfiles,
} from '../frontend/src/utils/mapConfigProfiles.js'

test('legacy credentials migrate into stable profiles with both selections preserved', () => {
  const result = normalizeMapConfigProfiles({
    provider: 'tencent', providers: { amap: { js_key: 'frontend-key', security_js_code: 'code' }, tencent: { map_key: 'backend-key' } },
  })
  assert.deepEqual(result.configs.map(profile => profile.id), ['legacy-amap', 'legacy-tencent', 'legacy-tianditu', 'legacy-baidu'])
  assert.equal(result.frontend_config_id, 'legacy-tencent')
  assert.equal(result.backend_config_id, 'legacy-tencent')
  assert.equal(result.configs[0].security_js_code, 'code')
  assert.equal(result.configs[1].map_key, 'backend-key')
  assert.equal(normalizeMapConfigProfiles({ baidu_map_ak: 'old-ak' }).configs[3].ak, 'old-ak')
})

test('same-provider profiles keep independent credentials and selected IDs after sorting', () => {
  const first = { ...createMapConfigProfile('amap'), js_key: 'first-key' }
  const second = { ...createMapConfigProfile('amap', [first]), js_key: 'second-key' }
  const map = { configs: [first, second], frontend_config_id: first.id, backend_config_id: second.id }
  map.configs = moveMapConfigProfile(map.configs, second.id, 0)
  const saved = serializeMapConfigProfiles(map)
  assert.deepEqual(saved.configs.map(profile => profile.js_key), ['second-key', 'first-key'])
  assert.equal(saved.frontend_config_id, first.id)
  assert.equal(saved.backend_config_id, second.id)
  assert.notEqual(first.id, second.id)
  assert.equal(second.name, '高德地图 2')
})

test('removing the selected profile redirects only affected selections to the first remaining card', () => {
  const map = normalizeMapConfigProfiles({ provider: 'amap' })
  map.backend_config_id = 'legacy-tencent'
  const result = removeMapConfigProfile(map, 'legacy-amap')
  assert.equal(result.frontend_config_id, 'legacy-tencent')
  assert.equal(result.backend_config_id, 'legacy-tencent')
  assert.throws(() => removeMapConfigProfile({ ...map, configs: [map.configs[0]] }, 'legacy-amap'), /至少保留/)
})

test('load clones profiles, repairs stale references, and keeps ordering', () => {
  const original = { configs: [{ id: 'two', provider: 'amap', name: 'Two' }, { id: 'one', provider: 'amap', name: 'One' }], frontend_config_id: 'missing', backend_config_id: 'one' }
  const loaded = normalizeMapConfigProfiles(original)
  assert.equal(loaded.frontend_config_id, 'two')
  assert.equal(loaded.backend_config_id, 'one')
  loaded.configs[0].name = 'Changed'
  assert.equal(original.configs[0].name, 'Two')
})

test('serialization rejects stale references and invalid profiles instead of saving partial credentials', () => {
  const base = normalizeMapConfigProfiles({})
  assert.throws(() => serializeMapConfigProfiles({ ...base, frontend_config_id: 'missing' }), /前端地图配置/)
  assert.throws(() => serializeMapConfigProfiles({ ...base, configs: [] }), /至少保留/)
  const duplicate = { ...base, configs: [base.configs[0], base.configs[0]] }
  assert.throws(() => serializeMapConfigProfiles(duplicate), /重复/)
  const unnamed = { ...base, configs: [{ ...base.configs[0], name: ' ' }] }
  assert.throws(() => serializeMapConfigProfiles(unnamed), /名称/)
  for (const name of ['前端\u0000配置', '前端\t配置', '\n前端配置', '前端配置\r']) {
    assert.throws(() => serializeMapConfigProfiles({ ...base, configs: [{ ...base.configs[0], name }] }), /控制字符/)
  }
  const unicodeName = { ...base, configs: [{ ...base.configs[0], name: '\u{1f5fa}'.repeat(100) }] }
  assert.equal(serializeMapConfigProfiles(unicodeName).configs[0].name, unicodeName.configs[0].name)
})

test('serialization normalizes each origin and includes only provider-specific fields', () => {
  const map = normalizeMapConfigProfiles({})
  map.configs[0].backend_page_origin = 'https://maps.example/path'
  map.configs[0].ak = 'unrelated-secret'
  const saved = serializeMapConfigProfiles(map, value => value ? new URL(value).origin : '')
  assert.equal(saved.configs[0].backend_page_origin, 'https://maps.example')
  assert.equal('ak' in saved.configs[0], false)
})
