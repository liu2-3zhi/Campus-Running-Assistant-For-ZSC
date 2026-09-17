import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('global styles retain legacy page and surface tokens', () => {
  const css = read('frontend/src/assets/style.css')
  assert.match(css, /linear-gradient\(\s*180deg,\s*rgba\(245,\s*250,\s*255,\s*1\)/)
  assert.match(css, /box-shadow:\s*0 10px 24px rgba\(16,\s*24,\s*40,\s*0\.12\)/)
  assert.match(css, /body\.dark-mode \.panel/)
})

test('auth screens expose legacy semantic anchors', () => {
  const loginView = read('frontend/src/views/LoginView.vue')
  const authPanel = read('frontend/src/components/login/AuthPanel.vue')
  assert.match(loginView, /id="auth-login-container"/)
  assert.match(loginView, /id="auth-login-container_panel"/)
  assert.match(authPanel, /id="auth-login-form"/)
  assert.match(authPanel, /id="auth-login-captcha-display"/)
  assert.match(authPanel, /id="guest-login-section"/)
  assert.match(loginView, /id="auth-beian-footer"/)
})

test('main and mobile shells retain legacy layout anchors', () => {
  const mainView = read('frontend/src/views/MainView.vue')
  const mobileControl = read('frontend/src/components/main/MobileControlPanel.vue')
  const mobileTask = read('frontend/src/components/main/MobileTaskPanel.vue')

  assert.match(mainView, /xl:grid-cols-4/)
  assert.match(mainView, /mobile-bottom-nav/)
  assert.match(mobileControl, /id="mobile-control-panel"/)
  assert.match(mobileControl, /id="mobile-run-stats-block"/)
  assert.match(mobileControl, /id="mobile-single-progress-fill"/)
  assert.match(mobileTask, /id="mobile-task-panel"/)
})

test('admin panel uses the legacy centered modal shell', () => {
  const adminPanel = read('frontend/src/components/admin/AdminPanel.vue')
  assert.match(adminPanel, /id="admin-panel-modal"/)
  assert.match(adminPanel, /w-\[65rem\]/)
  assert.match(adminPanel, /overflow-x-auto border-b-2 border-slate-200/)
})
