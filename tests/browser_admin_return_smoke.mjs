import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { readAdminFixtureAsset } from './browser_admin_fixture.mjs'
import { randomBytes } from 'node:crypto'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const dist = join(root, 'dist')
const A = '11111111-1111-4111-8111-111111111111'
const B = '22222222-2222-4222-8222-222222222222'
const C = '33333333-3333-4333-8333-333333333333'
const requests = []
const failures = new Map()
const actor = { session_id: A, auth_username: 'smoke-admin', auth_group: 'admin', view_all_sessions: true }
const authToken = randomBytes(24).toString('hex')
const targetTasks = { [B]: { running: true, executions: 2 }, [C]: { running: true, executions: 3 } }
let thirdOwner = 'smoke-third'
let originValid = true
let delayedTarget = ''

function mockAPI(path, headers, body) {
  const target = headers['x-session-id'] || ''
  if (path === '/auth/check_uuid_type') {
    const state = failures.get(body.uuid)
    if (state === 'missing') return { success: true, uuid_type: 'unknown' }
    if (state === 'error') return { success: false, message: '模拟会话初始化失败' }
    return { success: true, uuid_type: 'system_account' }
  }
  if (path === '/api/get_initial_data') return {
    success: failures.get(target) !== 'initialization',
    ...(failures.get(target) === 'initialization' ? { __status: 500, message: '模拟初始化接口失败' } : {}),
    is_authenticated: true, is_guest: false,
    auth_username: target === A ? 'smoke-admin' : target === C ? thirdOwner : 'smoke-user',
    auth_group: target === A || (target === C && thirdOwner === 'smoke-admin') ? 'admin' : 'user', users: [],
    ...(originValid && target !== A && headers['x-admin-origin-session-id'] === A ? { admin_view_context: actor } : {}),
  }
  if (path === '/auth/user/sessions' || path === '/auth/admin/all_sessions') return {
    success: true, god_mode_available: target === A,
    sessions: [{ session_id: C, auth_username: thirdOwner, created_at: 1 }], max_sessions: -1,
  }
  if (path === '/api/get_theme_styles') return { success: true, theme_styles: [] }
  if (path === '/auth/check_permission') return { success: true, has_permission: target === A }
  return { success: true }
}

const server = createServer(async (req, res) => {
  try {
    const path = new URL(req.url, 'http://127.0.0.1').pathname
    if (path.startsWith('/api/cdn/')) {
      res.writeHead(200, { 'Content-Type': 'text/css' }).end('')
      return
    }
    if (path.startsWith('/api/') || path.startsWith('/auth/')) {
      let raw = ''
      for await (const chunk of req) raw += chunk
      const body = raw ? JSON.parse(raw) : {}
      requests.push({ path, headers: req.headers, body })
      if (path === '/api/get_initial_data' && req.headers['x-session-id'] === delayedTarget) {
        await new Promise(resolve => setTimeout(resolve, 200))
      }
      const data = mockAPI(path, req.headers, body)
      const status = data.__status || 200
      delete data.__status
      res.writeHead(status, { 'Content-Type': 'application/json' }).end(JSON.stringify(data))
      return
    }
    if (path === '/favicon.ico' || path === '/manifest.json') {
      res.writeHead(204).end()
      return
    }
    const asset = await readAdminFixtureAsset(path, { root, dist })
    res.writeHead(asset.status, { 'Content-Type': asset.contentType, 'X-Content-Type-Options': 'nosniff' }).end(asset.body)
  } catch (error) {
    res.writeHead(500).end(String(error))
  }
})

let browser
const screenshots = process.env.ADMIN_RETURN_SCREENSHOTS === '1' ? await mkdtemp(join(tmpdir(), 'admin-return-smoke-')) : null
try {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${server.address().port}`
  const proxyScript = await fetch(base + '/scripts/map-request-proxy.js')
  assert.equal(proxyScript.status, 200)
  assert.match(proxyScript.headers.get('content-type'), /javascript/)
  assert.match(await proxyScript.text(), /ZXMapRequestProxy/)
  for (const path of ['/scripts/missing.js', '/frontend/assets/missing.js', '/frontend/unknown.js']) {
    const response = await fetch(base + path)
    assert.equal(response.status, 404, path)
    assert.doesNotMatch(response.headers.get('content-type'), /html/)
  }
  try { browser = await chromium.launch({ headless: true }) }
  catch (_) { browser = await chromium.launch({ channel: 'chrome', headless: true }) }
  for (const viewport of [{ width: 1440, height: 980 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport })
    await context.addCookies([{ name: 'auth_token', value: authToken, url: base }])
    const initialCookies = await context.cookies()
    const taskBaseline = JSON.stringify(targetTasks)
    await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort())
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(String(error)))
    const visitB = async () => {
      await page.goto(base + '/frontend/')
      await page.evaluate(origin => localStorage.setItem('admin_return_origin', origin), A)
      await page.goto(`${base}/frontend/uuid=${B}`)
    }
    const checkReturnButton = async () => {
      const button = page.getByRole('button', { name: '返回管理员会话', exact: true })
      await button.waitFor({ state: 'visible' })
      const box = await button.boundingBox()
      assert.ok(box && box.x < 80 && box.y < 80, 'return button must remain at the upper left')
      const top = await button.evaluate(element => {
        const box = element.getBoundingClientRect()
        return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === element
      })
      assert.equal(top, true, 'return button must remain above blocking overlays')
      return button
    }
    requests.length = 0
    failures.clear()
    await visitB()
    await (await checkReturnButton()).waitFor({ state: 'visible' })
    await page.getByText('上帝模式', { exact: false }).first().waitFor({ state: 'visible' })
    const sessionRequests = requests.filter(r => r.path === '/auth/user/sessions')
    assert.ok(sessionRequests.length)
    assert.equal(sessionRequests.every(r => r.headers['x-session-id'] === A), true, 'refresh must recover the verified actor before loading admin session data')
    await page.getByRole('button', { name: '进入', exact: true }).click()
    await page.waitForURL(`**/uuid=${C}`)
    await checkReturnButton()
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), A)
    await page.reload()
    await checkReturnButton()
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), A)
    if (screenshots) await page.screenshot({ path: join(screenshots, `${viewport.width}-chain.png`), fullPage: false })
    await (await checkReturnButton()).click()
    await page.waitForURL(`**/uuid=${A}`)
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), null)
    assert.equal(requests.some(r => r.path === '/auth/switch_session'), false)

    thirdOwner = 'smoke-admin'
    await visitB()
    await page.getByRole('button', { name: '进入', exact: true }).click()
    await page.waitForURL(`**/uuid=${C}`)
    await checkReturnButton()
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), A, 'an owned C must preserve the earliest A')
    await (await checkReturnButton()).click()
    await page.waitForURL(`**/uuid=${A}`)
    thirdOwner = 'smoke-third'

    await visitB()
    delayedTarget = C
    const delayedRequest = page.waitForRequest(request => request.url().endsWith('/api/get_initial_data') && request.headers()['x-session-id'] === C)
    const delayedResponse = page.waitForResponse(response => response.url().endsWith('/api/get_initial_data') && response.request().headers()['x-session-id'] === C)
    await page.getByRole('button', { name: '进入', exact: true }).click()
    await page.waitForURL(`**/uuid=${C}`)
    await delayedRequest
    await page.evaluate(uuid => document.querySelector('#app').__vue_app__.config.globalProperties.$router.push({ name: 'session', params: { uuid } }), B)
    await page.waitForURL(`**/uuid=${B}`)
    await delayedResponse
    delayedTarget = ''
    await checkReturnButton()
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), A)
    await (await checkReturnButton()).click()
    await page.waitForURL(`**/uuid=${A}`)

    for (const failure of ['missing', 'error', 'initialization']) {
      failures.set(B, failure)
      await visitB()
      await page.getByText('验证失败', { exact: true }).waitFor({ state: 'visible' })
      if (screenshots) await page.screenshot({ path: join(screenshots, `${viewport.width}-${failure}.png`), fullPage: false })
      await (await checkReturnButton()).click()
      await page.waitForURL(`**/uuid=${A}`)
      assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), null)
      failures.delete(B)
    }
    await visitB()
    originValid = false
    await page.reload()
    const invalidOrigin = page.getByRole('button', { name: '管理员会话失效，返回登录', exact: true })
    await invalidOrigin.waitFor({ state: 'visible' })
    assert.equal(await page.evaluate(() => localStorage.getItem('admin_return_origin')), null)
    await invalidOrigin.click()
    await page.waitForURL(base + '/frontend/')
    originValid = true
    assert.equal(requests.some(r => ['/auth/switch_session', '/auth/logout', '/api/shutdown', '/api/background_task/start', '/api/background_task/stop'].includes(r.path)), false)
    assert.equal(JSON.stringify(targetTasks), taskBaseline, 'viewing must not mutate the target task fixtures')
    assert.deepEqual(await context.cookies(), initialCookies, 'viewing must not rotate authentication cookies')
    assert.deepEqual(errors, [], 'built UI should not produce runtime errors')
    await context.close()
    console.log(`PASS ${viewport.width}x${viewport.height}: refreshed actor, B->C->A, owned C, rapid navigation, invalid origin, failed targets, unchanged cookie/target tasks`)
  }
  if (screenshots) console.log(`Screenshots: ${screenshots}`)
} finally {
  await browser?.close()
  await new Promise(resolve => server.close(resolve))
  assert.equal(server.listening, false)
  if (browser) assert.equal(browser.isConnected(), false)
}
