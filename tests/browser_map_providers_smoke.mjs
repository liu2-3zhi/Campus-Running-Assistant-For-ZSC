// Opt-in online verification. Credentials are passed in memory or environment only.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

export async function runMapProviderSmoke({ chromium, credentials, launchOptions = {}, providers = ['amap', 'tencent', 'tianditu', 'baidu'] }) {
  const source = await readFile(new URL('../main.py', import.meta.url), 'utf8')
  const browser = await chromium.launch({ headless: true, ...launchOptions })
  const results = []
  try {
    for (const provider of providers) {
      const credential = credentials[provider]
      assert.ok(credential?.key, `${provider}: a credential must be supplied explicitly`)
      const origin = new URL(credential.origin).origin
      const context = await browser.newContext({ serviceWorkers: 'block' })
      try {
        assert.equal((await context.cookies()).length, 0, `${provider}: the isolated context starts without application cookies`)
        const page = await context.newPage()
        const externalDocuments = []
        const errors = []
        page.on('pageerror', error => errors.push(String(error.message).replace(/https?:\/\/[^\s]+/g, '<url>')))
        page.on('dialog', dialog => dialog.dismiss())
        page.on('request', request => {
          if (request.isNavigationRequest() && request.frame() === page.mainFrame() && request.url() !== origin + '/map-runtime') externalDocuments.push(true)
        })
        let fulfilled = 0
        await page.route(origin + '/map-runtime', route => {
          fulfilled++
          return route.fulfill({ status: 200, contentType: 'text/html', headers: {
            'Cache-Control': 'no-store', 'Referrer-Policy': 'strict-origin',
          }, body: '<!doctype html><meta name="zx-map-runtime" content="online-smoke"><body></body>' })
        })
        await page.goto(origin + '/map-runtime', { waitUntil: 'domcontentloaded' })
        const fnSource = source.split(`def _plan_route_path_with_${provider}_runtime(`)[1]?.match(/"""\s*([\s\S]*?)\s*"""/)[1]
        assert.ok(fnSource, `${provider}: the production planner must be used`)
        const points = [[116.397128, 39.916527], [116.398128, 39.916527]]
        const params = { api_retries: 0, api_fallback_line: false, api_retry_delay_s: 0, api_queue_interval_s: 0 }
        const args = provider === 'amap'
          ? [points, credential.key, params, ['AMap.Walking'], 'walking', credential.securityJsCode || '']
          : [points, credential.key, params, 'walking']
        const started = Date.now()
        const result = await page.evaluate(async ({ source, args }) => {
          let timer
          try {
            return await Promise.race([(0, eval)('(' + source + ')')(args),
              new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('online planner timeout')), 45000) })])
          } finally { clearTimeout(timer) }
        }, { source: fnSource, args })
        // Assertions avoid printing raw vendor payloads, URLs, credentials, or complete routes.
        const error = String(result?.error || '').replaceAll(credential.key, '<redacted>').replaceAll(credential.securityJsCode || '\u0000', '<redacted>')
        assert.ok(!error, `${provider}: ${error}`)
        assert.ok(Array.isArray(result.path) && result.path.length >= 2, `${provider}: route geometry`)
        assert.equal(await page.evaluate(() => location.origin), origin)
        assert.equal(fulfilled, 1)
        assert.equal(externalDocuments.length, 0, `${provider}: external top-level navigation`)
        if (provider === 'baidu') {
          const setter = await page.evaluate(() => {
            const p = new BMap.Point(116.4035, 39.9225)
            const q = new BMap.Point(116.4045, 39.9235)
            const line = new BMap.Polyline([p, q])
            const marker = new BMap.Marker(p)
            const map = window.__backendBaiduRouteMap
            map.addOverlay(line); map.addOverlay(marker)
            line.setPath([q, p]); line.setStrokeColor('#0ea5e9'); marker.setPosition(q)
            const error = Math.max(Math.abs(line.getPath()[0].lng - q.lng), Math.abs(marker.getPosition().lat - q.lat))
            map.removeOverlay(line); map.removeOverlay(marker)
            return { error, bmap: !!window.BMap, gl: !!window.BMapGL }
          })
          assert.ok(setter.bmap && setter.error < 1e-6, 'BMap v4 default BD09 setters')
        }
        results.push({ provider, origin, points: result.path.length, elapsed_ms: Date.now() - started,
          attempts: result.diagnostic?.segments?.map(row => row.attempts), script_errors: errors.length })
      } finally { await context.close() }
    }
    return results
  } finally { await browser.close() }
}

if (typeof process !== 'undefined' && process.argv[1] === fileURLToPath(import.meta.url)) {
  const require = createRequire(import.meta.url)
  const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright')
  const credentials = JSON.parse(process.env.MAP_SMOKE_CREDENTIALS || '{}')
  const launchOptions = process.env.MAP_SMOKE_BROWSER_PATH ? { executablePath: process.env.MAP_SMOKE_BROWSER_PATH } : {}
  console.log(JSON.stringify(await runMapProviderSmoke({ chromium, credentials, launchOptions }), null, 2))
}
