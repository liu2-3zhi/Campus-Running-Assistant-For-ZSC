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

test('admin users use the legacy card list instead of the table', () => {
  const adminUsers = read('frontend/src/components/admin/AdminUsers.vue')
  assert.match(adminUsers, /id="admin-users-list_modal"/)
  assert.match(adminUsers, /搜索昵称 \/ 用户名 \/ 手机号 \/ 学校账号/)
  assert.match(adminUsers, /grid w-full grid-cols-3/)
  assert.doesNotMatch(adminUsers, /<table class="w-full text-sm">/)
})

test('admin sessions and health retain legacy headers', () => {
  const sessions = read('frontend/src/components/admin/AdminSessions.vue')
  const health = read('frontend/src/components/admin/AdminHealth.vue')
  assert.match(sessions, /id="admin-sessions-list_modal"/)
  assert.match(sessions, /查看所有会话/)
  assert.doesNotMatch(sessions, /<table class="w-full text-sm">/)
  assert.match(health, /系统健康状态/)
  assert.match(health, /自动刷新\(5秒\)/)
})

test('admin ip ban uses the legacy card sections', () => {
  const ipBan = read('frontend/src/components/admin/AdminIPBan.vue')
  assert.match(ipBan, /IP封禁管理/)
  assert.match(ipBan, /id="ip-ban-list"/)
  assert.match(ipBan, /添加封禁规则/)
  assert.doesNotMatch(ipBan, /<table class="w-full text-sm">/)
})

test('sms billing and restore use legacy page headers', () => {
  const sms = read('frontend/src/components/admin/AdminSMS.vue')
  const billing = read('frontend/src/components/admin/AdminBilling.vue')
  const restore = read('frontend/src/components/admin/AdminRestoreAccount.vue')
  assert.match(sms, /短信服务配置/)
  assert.match(sms, /from-purple-50 to-pink-50/)
  assert.match(billing, /from-green-50 to-emerald-50/)
  assert.match(billing, /admin-billing-school-input/)
  assert.doesNotMatch(billing, /<table class="w-full text-sm">/)
  assert.match(restore, /from-amber-50 to-orange-50/)
  assert.match(restore, /id="removed-accounts-list-container"/)
  assert.doesNotMatch(restore, /<table class="w-full text-sm">/)
})

test('additional admin pages retain legacy titles', () => {
  const groups = read('frontend/src/components/admin/AdminGroups.vue')
  const logs = read('frontend/src/components/admin/AdminLogs.vue')
  const cdn = read('frontend/src/components/admin/AdminCDN.vue')
  assert.match(groups, /权限组列表/)
  assert.match(groups, /新增权限组/)
  assert.match(logs, /系统日志/)
  assert.match(cdn, /CDN缓存设置/)
})

test('security admin pages retain legacy top-level titles', () => {
  const ssl = read('frontend/src/components/admin/AdminSSL.vue')
  const brute = read('frontend/src/components/admin/AdminBruteforce.vue')
  const captcha = read('frontend/src/components/admin/AdminCaptcha.vue')
  assert.match(ssl, /SSL \/ HTTPS 配置/)
  assert.match(brute, /密码恢复/)
  assert.match(captcha, /验证码配置/)
})

test('system config retains the legacy header', () => {
  const config = read('frontend/src/components/admin/AdminConfig.vue')
  assert.match(config, /系统配置/)
  assert.match(config, /@click="loadConfig"/)
})

test('multi account view uses the legacy 530px desktop grid', () => {
  const multi = read('frontend/src/views/MultiAccountView.vue')
  assert.match(multi, /lg:grid-cols-\[530px_1fr\]/)
  assert.match(multi, /md:h-screen md:overflow-hidden/)
})
