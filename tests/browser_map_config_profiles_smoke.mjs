import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { createMapConfigBrowserFixture } from './browser_map_cache_config_smoke.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const screenshots = resolve('output/map-config-profiles-smoke')
await mkdir(screenshots, { recursive: true })

const initialConfig = () => ({ Map: {
  configs: [{ id: 'front', name: '高德1', provider: 'amap', js_key: 'frontend-placeholder', security_js_code: 'frontend-code', backend_page_origin: 'https://front.test' }],
  frontend_config_id: 'front', backend_config_id: 'front', backend_page_origin: 'https://global.test',
  frontend_proxy_enabled: true, tile_cache_ttl_days: 7, tile_cache_max_size_gb: 1.25,
} })

async function dragBefore(page, handle, target, mobile) {
  await target.evaluate(element => element.scrollIntoView({ block: 'start' }))
  const sourceBounds = await handle.boundingBox()
  const targetBounds = await target.boundingBox()
  assert.ok(sourceBounds && targetBounds)
  const start = { x: sourceBounds.x + sourceBounds.width / 2, y: sourceBounds.y + sourceBounds.height / 2 }
  const end = { x: targetBounds.x + targetBounds.width / 2, y: Math.max(8, targetBounds.y + 24) }
  assert.ok(start.y > 0 && start.y < page.viewportSize().height, 'drag handle must be visible')
  if (!mobile) {
    await page.mouse.move(start.x, start.y)
    await page.mouse.down()
    await page.mouse.move(start.x + 4, start.y - 4, { steps: 3 })
    await page.mouse.move(end.x, end.y, { steps: 24 })
    await page.mouse.up()
    return
  }
  const session = await page.context().newCDPSession(page)
  const dispatch = (type, point) => session.send('Input.dispatchTouchEvent', {
    type, touchPoints: point ? [{ ...point, id: 1 }] : [],
  })
  try {
    await dispatch('touchStart', start)
    await page.waitForTimeout(180)
    for (let step = 1; step <= 24; step++) {
      await dispatch('touchMove', { x: start.x + (end.x - start.x) * step / 24, y: start.y + (end.y - start.y) * step / 24 })
      await page.waitForTimeout(16)
    }
    await dispatch('touchEnd')
  } finally { await session.detach() }
}

const fixture = await createMapConfigBrowserFixture(initialConfig())
let browser
try {
  try { browser = await chromium.launch({ headless: true }) }
  catch { browser = await chromium.launch({ channel: 'chrome', headless: true }) }
  for (const ui of ['vue', 'legacy']) {
    for (const mobile of [false, true]) {
      fixture.setConfig(initialConfig())
      const viewport = mobile ? { width: 390, height: 844 } : { width: 1440, height: 980 }
      const context = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile })
      const page = await context.newPage()
      const errors = []
      const unexpected = []
      page.on('pageerror', error => errors.push(String(error)))
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === fixture.base) return route.continue()
        unexpected.push(route.request().url())
        return route.abort()
      })
      const visit = async () => {
        await page.goto(`${fixture.base}/${ui}?mobile=${mobile ? 1 : 0}`)
        await page.waitForFunction(() => window.fixtureReady === true)
        await page.locator(ui === 'vue' ? '#app' : mobile ? '#mobile-admin-config-content-panel' : '#admin-config-panel_modal').locator('[data-map-config-card]').first().waitFor()
      }
      await visit()
      const panel = ui === 'vue' ? page.locator('#app') : page.locator(mobile ? '#mobile-admin-config-content-panel' : '#admin-config-panel_modal')
      const editor = panel.locator('[data-map-config-editor]')
      const cards = editor.locator('[data-map-config-card]')
      const selection = side => ui === 'vue'
        ? editor.getByRole('combobox', { name: side === 'frontend' ? '前端地图配置' : '后端路径规划配置', exact: true })
        : editor.locator(`[data-map-config-select="${side}"]`)
      const nameInput = card => ui === 'vue' ? card.locator('input[id$="-name"]') : card.locator('[data-map-config-field="name"]')
      const keyInput = card => ui === 'vue' ? card.locator('input[id$="-js_key"]') : card.locator('[data-map-config-field="js_key"]')
      const originInput = card => ui === 'vue' ? card.locator('input[id$="-origin"]') : card.locator('[data-map-config-field="backend_page_origin"]')
      const cardId = async card => await card.getAttribute(ui === 'vue' ? 'data-map-config-card' : 'data-config-id')
      const idOrder = () => cards.evaluateAll((elements, attr) => elements.map(element => element.getAttribute(attr)), ui === 'vue' ? 'data-map-config-card' : 'data-config-id')
      const save = async () => {
        const response = page.waitForResponse(response => response.url().endsWith('/api/admin/config/save') && response.status() === 200)
        await panel.getByRole('button', { name: '保存配置', exact: true }).click()
        await response
        return fixture.saved.at(-1).Map
      }

      assert.equal(await cards.count(), 1)
      await editor.getByRole('button', { name: ui === 'vue' ? '添加地图配置' : '添加配置', exact: true }).click()
      assert.equal(await cards.count(), 2)
      const secondId = await cardId(cards.nth(1))
      assert.notEqual(secondId, 'front')
      await nameInput(cards.nth(1)).fill('高德2')
      await keyInput(cards.nth(1)).fill('backend-placeholder')
      await originInput(cards.nth(1)).fill('https://back.test/path?x=1')
      await originInput(cards.nth(1)).blur()
      await selection('frontend').selectOption('front')
      await selection('backend').selectOption(secondId)
      assert.equal(await keyInput(cards.nth(0)).getAttribute('type'), 'password')
      const handle = ui === 'vue'
        ? cards.nth(1).getByRole('button', { name: '拖动高德2排序', exact: true })
        : cards.nth(1).locator('[data-map-drag-handle]')
      await dragBefore(page, handle, cards.nth(0), mobile)
      await page.waitForFunction(({ selector, attr, id }) => {
        const visiblePanel = document.querySelector(selector)
        return visiblePanel.querySelector('[data-map-config-card]')?.getAttribute(attr) === id
      }, { selector: ui === 'vue' ? '#app' : mobile ? '#mobile-admin-config-content-panel' : '#admin-config-panel_modal', attr: ui === 'vue' ? 'data-map-config-card' : 'data-config-id', id: secondId })
      assert.deepEqual(await idOrder(), [secondId, 'front'])
      assert.equal(await selection('frontend').inputValue(), 'front')
      assert.equal(await selection('backend').inputValue(), secondId)

      const proxy = ui === 'vue' ? panel.getByRole('switch', { name: '启用地图请求后端代理', exact: true }) : panel.locator('[id="config-Map-frontend_proxy_enabled"]')
      if (ui === 'vue') await proxy.click()
      else await proxy.selectOption('false')
      const saved = await save()
      assert.equal(saved.frontend_config_id, 'front')
      assert.equal(saved.backend_config_id, secondId)
      assert.deepEqual(saved.configs.map(profile => profile.id), [secondId, 'front'])
      assert.equal(saved.configs[0].js_key, 'backend-placeholder')
      assert.equal(saved.configs[0].backend_page_origin, 'https://back.test')
      assert.equal(saved.configs[1].js_key, 'frontend-placeholder')
      assert.equal(saved.frontend_proxy_enabled, false)
      assert.equal(saved.tile_cache_ttl_days, 7)
      assert.equal(saved.tile_cache_max_size_gb, 1.25)
      assert.equal(saved.backend_page_origin, 'https://global.test')

      await visit()
      assert.deepEqual(await idOrder(), [secondId, 'front'])
      assert.equal(await selection('frontend').inputValue(), 'front')
      assert.equal(await selection('backend').inputValue(), secondId)
      assert.equal(await keyInput(cards.nth(0)).inputValue(), 'backend-placeholder')
      await editor.scrollIntoViewIfNeeded()
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true)
      await page.screenshot({ path: resolve(screenshots, `${ui}-${mobile ? 'mobile' : 'desktop'}.png`), fullPage: true })
      await editor.screenshot({ path: resolve(screenshots, `${ui}-${mobile ? 'mobile' : 'desktop'}-cards.png`) })
      await cards.nth(0).getByRole('button', { name: ui === 'vue' ? '删除高德2' : '删除', exact: true }).click()
      assert.equal(await cards.count(), 1)
      assert.equal(await selection('frontend').inputValue(), 'front')
      assert.equal(await selection('backend').inputValue(), 'front')
      assert.equal(await cards.nth(0).getByRole('button', { name: ui === 'vue' ? '删除高德1' : '删除', exact: true }).isDisabled(), true)
      const afterDelete = await save()
      assert.equal(afterDelete.configs.length, 1)
      assert.equal(afterDelete.backend_config_id, 'front')
      await visit()
      assert.equal(await cards.count(), 1)
      assert.equal(await selection('backend').inputValue(), 'front')
      assert.deepEqual(errors, [])
      assert.deepEqual(unexpected, [])
      await context.close()
      console.log(`PASS ${ui} ${mobile ? 'touch 390x844' : 'mouse 1440x980'}: add same-provider profiles, independent selections, drag, save/reload, delete fallback, cache retention`)
    }
  }
} finally {
  await browser?.close()
  await fixture.close()
  if (browser) assert.equal(browser.isConnected(), false)
}
