import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../scripts/main.js', import.meta.url), 'utf8')
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
const start = source.indexOf('function normalizeRuntimeCaptchaProviderConfig(')
const end = source.indexOf('\nfunction openCaptchaModal(', start)
assert.ok(start >= 0 && end > start)

const forms = [
  ['login', 'auth-login-captcha-display', 'auth-login-captcha-refresh'],
  ['register', 'auth-register-captcha-display', 'auth-register-captcha-refresh'],
  ['mobile-login', 'mobile-login-captcha-display', 'mobile-login-captcha-refresh'],
  ['mobile-register', 'mobile-register-captcha-display', 'mobile-register-captcha-refresh'],
  ['modal', 'captcha-modal-display', 'modal-login-captcha-refresh'],
]

function createElement(id) {
  const attributes = new Map()
  const classes = new Set()
  return {
    id,
    dataset: {},
    style: { display: '' },
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
    },
    hasAttribute: (name) => attributes.has(name),
    getAttribute: (name) => attributes.get(name) ?? null,
    setAttribute: (name, value) => attributes.set(name, value),
    removeAttribute: (name) => attributes.delete(name),
    closest: () => null,
  }
}

function createRuntime({ failSdk = false } = {}) {
  const elements = new Map()
  for (const [, displayId, refreshId] of forms) {
    elements.set(displayId, createElement(displayId))
    elements.set(refreshId, createElement(refreshId))
  }
  const requests = []
  const context = vm.createContext({
    document: { getElementById: (id) => elements.get(id) ?? null },
    window: {
      initTAC: async () => {
        if (failSdk) throw new Error('SDK unavailable')
        return { init() {}, destroyWindow() {} }
      },
    },
    console: { log() {}, warn() {}, error() {} },
    fetch: async (url) => {
      requests.push(url)
      return {
        json: async () => ({
          success: true,
          captcha_id: '11111111-1111-4111-8111-111111111111',
          width: 200,
          height: 64,
        }),
      }
    },
    RUNTIME_CAPTCHA_PROVIDER_DEFAULT: { provider: 'image', behavior_type: 'SLIDER' },
    runtimeCaptchaProviderConfig: null,
    runtimeCaptchaProviderConfigPromise: null,
    behaviorCaptchaLoaderPromise: null,
    behaviorCaptchaInstances: {},
    captchaIds_login: '',
    captchaIds_register: '',
    captchaIds_mobile_login: '',
    captchaIds_mobile_register: '',
    captchaIds_modal: '',
    captchaDimensions: {},
    captchaModalRequestedWidth: null,
    containerWidth: 200,
    sessionUUID: 'test-session',
  })
  vm.runInContext(source.slice(start, end), context)
  return { context, elements, requests }
}

async function load(context, formType, provider) {
  context.setRuntimeCaptchaProviderConfig({ provider })
  if (formType === 'modal') await context.loadCaptchaModal(200)
  else await context.loadCaptcha(formType)
}

for (const [formType, displayId, refreshId] of forms) {
  test(`${formType}: local refresh is visible, server refresh is hidden, switching back restores it`, async () => {
    assert.ok(html.includes(`id="${displayId}"`))
    assert.ok(html.includes(`id="${refreshId}"`))
    const { context, elements, requests } = createRuntime()
    const button = elements.get(refreshId)

    await load(context, formType, 'image')
    assert.equal(button.style.display, '')
    assert.equal(requests.length, 1)

    await load(context, formType, 'behavior')
    assert.equal(button.style.display, 'none')
    assert.equal(requests.length, 1, 'server mode must not request a local captcha')

    await load(context, formType, 'image')
    assert.equal(button.style.display, '')
    assert.equal(requests.length, 2)
    assert.match(elements.get(displayId).innerHTML, /<iframe/)
  })

  test(`${formType}: a server SDK failure does not expose the local refresh button`, async () => {
    const { context, elements } = createRuntime({ failSdk: true })
    await load(context, formType, 'behavior')
    assert.equal(elements.get(refreshId).style.display, 'none')
    assert.match(elements.get(displayId).innerHTML, /text-red-500/)
  })
}

test('missing display or refresh controls do not break mode switching', () => {
  const { context, elements } = createRuntime()
  assert.doesNotThrow(() => context.setCaptchaDisplayBehaviorMode(null, true))
  for (const [, displayId, refreshId] of forms) {
    elements.delete(refreshId)
    assert.doesNotThrow(() => context.setCaptchaDisplayBehaviorMode(elements.get(displayId), true))
    assert.doesNotThrow(() => context.setCaptchaDisplayBehaviorMode(elements.get(displayId), false))
  }
})

test('changing captcha mode leaves admin configuration and history refresh buttons alone', () => {
  const { context, elements } = createRuntime()
  const adminIds = [
    'admin-refresh-captcha-btn',
    'mobile-multi-admin-refresh-captcha',
    'admin-refresh-captcha_modal',
  ]
  for (const id of adminIds) elements.set(id, createElement(id))
  for (const [, displayId] of forms) context.setCaptchaDisplayBehaviorMode(elements.get(displayId), true)
  for (const id of adminIds) assert.equal(elements.get(id).style.display, '')
})
