import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { normalizeBackendPageOrigin } from '../frontend/src/services/mapBackendOrigin.js'

const legacy = await readFile(new URL('../scripts/legacy-admin-config.js', import.meta.url), 'utf8')
const source = legacy.slice(legacy.indexOf('function normalizeBackendPageOrigin('), legacy.indexOf('async function saveSystemConfig('))
const context = vm.createContext({ URL, window: { location: { origin: 'https://app.test:8443' } } })
vm.runInContext(source, context)
for (const normalize of [normalizeBackendPageOrigin, context.normalizeBackendPageOrigin]) {
  assert.equal(normalize('https://EXAMPLE.com:443/path?session_id=private#fragment'), 'https://example.com')
  assert.equal(normalize('http://example.com:80/a'), 'http://example.com')
  assert.equal(normalize('https://example.com:8443/a'), 'https://example.com:8443')
  assert.equal(normalize(''), '')
  for (const value of ['example.com', 'https://user:secret@example.com', 'file:///tmp/a', 'https://x.test\\evil', 'https://x.test\n/path', 'https://x.test:70000', 'https://x.test:']) {
    assert.throws(() => normalize(value))
  }
}
const clonedInput = { value: '' }
context.useCurrentMapPageOrigin({ parentElement: { querySelector: () => clonedInput } })
assert.equal(clonedInput.value, 'https://app.test:8443')
assert.match(legacy, /const panel = sourceButton\?\.closest/)
assert.match(legacy, /map_config_id: configData\.Map\.frontend_config_id/)
assert.match(legacy, /id, name, provider, backend_page_origin, \.\.\.frontendKeys/)
assert.match(legacy, /directUpdate\.map_providers\[provider\] = \{ \.\.\.frontendKeys/)
console.log('map backend origin: normalization, cloned mobile controls, and frontend boundary passed')
