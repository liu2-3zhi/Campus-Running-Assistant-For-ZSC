import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { createMapConfigBrowserFixture } from './browser_map_cache_config_smoke.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const fixture = await createMapConfigBrowserFixture({ Map: {} })
const screenshots = resolve('output/trusted-ips-ui')
await mkdir(screenshots, { recursive: true })
let browser
try {
  try { browser = await chromium.launch({ headless: true }) }
  catch { browser = await chromium.launch({ channel: 'chrome', headless: true }) }
  for (const mobile of [false, true]) {
    const viewport = mobile ? { width: 390, height: 844 } : { width: 1440, height: 980 }
    const context = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile })
    const page = await context.newPage()
    const errors = []
    const unexpected = []
    const saved = []
    let current = { content: '# 原有规则\n203.0.113.10  # edge\n\n', revision: 1 }
    page.on('pageerror', error => errors.push(String(error)))
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin === fixture.base) return route.continue()
      unexpected.push(route.request().url())
      return route.abort()
    })
    await context.route('**/api/admin/trusted-ips', async route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ json: { success: true, ...current } })
      }
      const data = route.request().postDataJSON()
      saved.push(data)
      if (data.revision !== current.revision) {
        return route.fulfill({ status: 409, json: { success: false, message: '配置已更改，请重新加载' } })
      }
      current = { content: data.content, revision: current.revision + 1 }
      return route.fulfill({ json: { success: true, revision: current.revision, message: '可信代理配置已保存，立即生效' } })
    })
    await page.goto(`${fixture.base}/vue`)
    await page.waitForFunction(() => window.fixtureReady === true)
    const entry = page.getByRole('button', { name: '可信代理 IP', exact: true })
    await entry.click()
    const modal = page.getByRole('dialog', { name: '可信代理 IP · trusted_ips.txt' })
    const editor = modal.getByLabel('trusted_ips.txt 内容', { exact: true })
    await editor.waitFor()
    await page.waitForFunction(() => document.querySelector('#trusted-ips-editor')?.disabled === false)
    assert.equal(await editor.inputValue(), current.content)
    assert.equal(await editor.evaluate(element => element === document.activeElement), true)
    const edited = '# editable comment\n198.51.100.10 # proxy\n\n'
    await editor.fill(edited)
    await modal.getByRole('button', { name: '保存并生效', exact: true }).click()
    await modal.getByRole('status').filter({ hasText: '立即生效' }).waitFor()
    assert.equal(current.content, edited)
    assert.equal(saved[0].content, edited)
    assert.equal(saved[0].revision, 1)
    assert.equal(await modal.getByRole('button', { name: '保存并生效', exact: true }).isDisabled(), true)
    const bounds = await modal.boundingBox()
    assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= viewport.width, 'modal must fit mobile and desktop width')
    await page.screenshot({ path: resolve(screenshots, `vue-${mobile ? 'mobile' : 'desktop'}.png`) })

    const draft = '203.0.113.22\n'
    await editor.fill(draft)
    current = { content: '# another administrator\n198.51.100.4\n', revision: 3 }
    await modal.getByRole('button', { name: '保存并生效', exact: true }).click()
    await modal.getByRole('alert').waitFor()
    assert.equal(await editor.inputValue(), draft, 'conflict must keep the editable draft')
    assert.equal(current.content, '# another administrator\n198.51.100.4\n')
    await modal.getByRole('button', { name: '重新加载', exact: true }).click()
    await page.waitForFunction(() => document.querySelector('#trusted-ips-editor')?.value.startsWith('# another administrator'))
    await editor.fill('*\n')
    await modal.getByText('留空或填写 * 会信任全部代理来源。配置规则会自动合并内置 IPv4、IPv6 局域网和本机网段。仅保留注释时，使用内置规则。', { exact: true }).waitFor()
    await editor.press('Escape')
    await modal.waitFor({ state: 'hidden' })
    assert.equal(await entry.evaluate(element => element === document.activeElement), true)
    assert.deepEqual(errors, [])
    assert.deepEqual(unexpected, [])
    await context.close()
    console.log(`PASS Vue ${viewport.width}x${viewport.height}: exact text, revision save/conflict, explicit reload, scope warning, keyboard close`)
  }
} finally {
  await browser?.close()
  await fixture.close()
}
