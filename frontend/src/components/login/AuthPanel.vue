<script setup>
import { ref, reactive, nextTick, onMounted, onUnmounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import TabPanel from '@/components/common/TabPanel.vue'
import Swal from 'sweetalert2'

const emit = defineEmits(['login-success'])
const auth = useAuthStore()

// --- State ---
const activeTab = ref('login')
const tabs = [
  { key: 'login', label: '登录' },
  { key: 'register', label: '注册' },
]

// Login form
const loginMode = ref('username') // 'username' | 'phone'
const passwordMode = ref('password') // 'password' | 'sms'
const loginForm = reactive({
  username: '',
  password: '',
  phone: '',
  smsCode: '',
  captchaId: '',
  captchaCode: '',
})

// Register form
const registerForm = reactive({
  username: '',
  phone: '',
  smsCode: '',
  nickname: '',
  password: '',
  confirmPassword: '',
  captchaId: '',
  captchaCode: '',
  avatarFile: null,
  avatarPreview: '',
})

// 2FA
const show2FA = ref(false)
const twoFACode = ref('')
const pending2FAData = ref(null)
const twoFAUsername = ref('')

// Captcha
const loginCaptchaIframeSrc = ref('')
const registerCaptchaIframeSrc = ref('')
const loginCaptchaDims = ref({ width: 0, height: 0 })
const registerCaptchaDims = ref({ width: 0, height: 0 })
const loginCaptchaContainerRef = ref(null)
const registerCaptchaContainerRef = ref(null)

// SMS cooldown
const loginSmsCooldown = ref(0)
const registerSmsCooldown = ref(0)
let loginSmsTimer = null
let registerSmsTimer = null

// Pre-auth anonymous session ID (for captcha rate limiting before login)
const anonSessionId = crypto.randomUUID()

// Guest login config
const guestLoginEnabled = ref(false)

// Available runs hint for registration
const availableRunsText = ref('')
const showAvailableRuns = ref(false)

// Messages
const errorMsg = ref('')
const successMsg = ref('')
const loading = ref(false)

// --- Captcha ---
function getCaptchaContainerWidth(target) {
  const containerEl = target === 'login'
    ? loginCaptchaContainerRef.value
    : registerCaptchaContainerRef.value
  if (!containerEl) return 300
  const style = window.getComputedStyle(containerEl)
  const paddingLeft = parseFloat(style.paddingLeft) || 0
  const paddingRight = parseFloat(style.paddingRight) || 0
  let w = containerEl.clientWidth - paddingLeft - paddingRight
  if (w > 600) w = 600
  if (w < 200) w = 200
  return Math.floor(w)
}

async function loadCaptcha(target) {
  try {
    await nextTick()
    const containerWidth = getCaptchaContainerWidth(target)
    const sessionId = auth.getAuthenticatedSessionHeaderValue() || anonSessionId

    const res = await fetch(`/api/captcha/get?width=${containerWidth}`, {
      method: 'GET',
      headers: { 'X-Session-ID': sessionId },
      credentials: 'include',
    })
    if (!res.ok) {
      console.warn('验证码加载失败:', res.status)
      return
    }
    const data = await res.json()
    const captchaId = data.captcha_id || data.id || ''
    if (!captchaId) return

    const captchaWidth = data.width || containerWidth
    const captchaHeight = data.height || 119
    const iframeSrc = `/api/captcha/html/${captchaId}?t=${Date.now()}&width=${captchaWidth}`

    if (target === 'login') {
      loginForm.captchaId = captchaId
      loginForm.captchaCode = ''
      loginCaptchaIframeSrc.value = iframeSrc
      loginCaptchaDims.value = { width: captchaWidth, height: captchaHeight }
    } else {
      registerForm.captchaId = captchaId
      registerForm.captchaCode = ''
      registerCaptchaIframeSrc.value = iframeSrc
      registerCaptchaDims.value = { width: captchaWidth, height: captchaHeight }
    }
  } catch (e) {
    console.warn('验证码加载失败:', e)
  }
}

// --- Check guest login config ---
async function checkGuestLoginEnabled() {
  try {
    const data = await callRawAPI('/auth/get_config', 'GET')
    if (data.success && data.allow_guest_login) {
      guestLoginEnabled.value = true
    } else {
      guestLoginEnabled.value = false
    }
    // Also check available_runs for registration hint
    if (data.available_runs_text) {
      availableRunsText.value = data.available_runs_text
      showAvailableRuns.value = true
    }
  } catch (e) {
    console.warn('获取配置失败:', e)
  }
}

// --- SMS Captcha Verification Modal ---
function showSmsCaptchaModal(phone, type) {
  let modalCaptchaId = ''

  async function loadModalCaptcha() {
    try {
      const sessionId = auth.getAuthenticatedSessionHeaderValue() || anonSessionId
      const containerEl = document.getElementById('swal-captcha-container')
      let modalWidth = 280
      if (containerEl) {
        const cs = window.getComputedStyle(containerEl)
        const pl = parseFloat(cs.paddingLeft) || 0
        const pr = parseFloat(cs.paddingRight) || 0
        const w = containerEl.clientWidth - pl - pr
        if (w >= 200 && w <= 600) modalWidth = Math.floor(w)
      }
      const res = await fetch(`/api/captcha/get?width=${modalWidth}`, {
        method: 'GET',
        headers: { 'X-Session-ID': sessionId },
        credentials: 'include',
      })
      if (!res.ok) throw new Error(res.status)
      const data = await res.json()
      modalCaptchaId = data.captcha_id || data.id || ''
      if (!modalCaptchaId) throw new Error('no captcha_id')
      const captchaW = data.width || modalWidth
      const captchaH = data.height || 119
      const displayEl = document.getElementById('swal-captcha-display')
      if (displayEl) {
        displayEl.innerHTML = `<iframe src="/api/captcha/html/${modalCaptchaId}?t=${Date.now()}&width=${captchaW}" style="max-width:${captchaW}px;max-height:${captchaH}px;width:${captchaW}px;height:${captchaH}px;border:none;overflow:hidden;display:block;margin:0 auto;" scrolling="no" frameborder="0"></iframe>`
      }
      const loadingEl = document.getElementById('swal-captcha-loading')
      if (loadingEl) loadingEl.style.display = 'none'
    } catch (e) {
      const loadingEl = document.getElementById('swal-captcha-loading')
      if (loadingEl) loadingEl.textContent = '加载失败，请点击刷新'
    }
  }

  Swal.fire({
    title: '安全验证',
    html: `
      <p style="color:#64748b;font-size:14px;margin-bottom:12px;">为保护您的账号安全，请完成以下验证</p>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:14px;font-weight:600;color:#334155;margin-bottom:6px;">图形验证码</label>
        <div style="display:flex;align-items:center;gap:8px;">
          <div id="swal-captcha-container" style="flex:1;min-height:50px;display:flex;align-items:center;justify-content:center;border:2px solid #cbd5e1;border-radius:8px;background:#fff;cursor:pointer;" title="点击刷新验证码">
            <span id="swal-captcha-loading" style="color:#94a3b8;font-size:12px;">加载中...</span>
            <div id="swal-captcha-display" style="width:100%;min-height:50px;"></div>
          </div>
          <button type="button" id="swal-captcha-refresh" style="background:none;border:1px solid #e2e8f0;border-radius:8px;padding:8px;cursor:pointer;color:#64748b;" title="刷新验证码">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          </button>
        </div>
      </div>
      <div>
        <label style="display:block;font-size:14px;font-weight:600;color:#334155;margin-bottom:6px;">请输入验证码</label>
        <input type="text" id="swal-captcha-input" maxlength="6" autocomplete="off" placeholder="请输入图形验证码" style="width:100%;padding:10px 14px;border:2px solid #cbd5e1;border-radius:8px;font-size:14px;outline:none;transition:border-color 0.2s;" onfocus="this.style.borderColor='#38bdf8'" onblur="this.style.borderColor='#cbd5e1'" />
      </div>
    `,
    showCancelButton: true,
    confirmButtonText: '确认发送',
    cancelButtonText: '取消',
    customClass: {
      confirmButton: 'btn btn-primary',
      cancelButton: 'btn btn-secondary',
    },
    didOpen: () => {
      loadModalCaptcha()
      const container = document.getElementById('swal-captcha-container')
      const refreshBtn = document.getElementById('swal-captcha-refresh')
      if (container) container.addEventListener('click', loadModalCaptcha)
      if (refreshBtn) refreshBtn.addEventListener('click', loadModalCaptcha)
      setTimeout(() => {
        const input = document.getElementById('swal-captcha-input')
        if (input) input.focus()
      }, 300)
    },
    preConfirm: () => {
      const captchaCode = document.getElementById('swal-captcha-input')?.value?.trim()
      if (!captchaCode) {
        Swal.showValidationMessage('请输入图形验证码')
        return false
      }
      if (!modalCaptchaId) {
        Swal.showValidationMessage('验证码未加载，请刷新后重试')
        return false
      }
      return { captchaCode, captchaId: modalCaptchaId }
    },
  }).then(async (result) => {
    if (result.isConfirmed && result.value) {
      const { captchaCode, captchaId } = result.value
      try {
        await callRawAPI('/api/sms/send_code', 'POST', {
          phone,
          scene: type,
          captcha_id: captchaId,
          captcha: captchaCode,
        })
        startSmsCooldown(type === 'login' ? 'login' : 'register')
        successMsg.value = '验证码已发送'
      } catch (e) {
        errorMsg.value = e.message || '发送验证码失败'
      }
    }
  })
}

// --- SMS ---
function startSmsCooldown(target) {
  const cooldownRef = target === 'login' ? loginSmsCooldown : registerSmsCooldown
  cooldownRef.value = 60
  const timer = setInterval(() => {
    cooldownRef.value--
    if (cooldownRef.value <= 0) {
      clearInterval(timer)
    }
  }, 1000)
  if (target === 'login') {
    loginSmsTimer = timer
  } else {
    registerSmsTimer = timer
  }
}

async function sendLoginSmsCode() {
  if (loginSmsCooldown.value > 0 || !loginForm.phone) return
  errorMsg.value = ''
  showSmsCaptchaModal(loginForm.phone, 'login')
}

async function sendRegisterSmsCode() {
  if (registerSmsCooldown.value > 0 || !registerForm.phone) return
  errorMsg.value = ''
  showSmsCaptchaModal(registerForm.phone, 'register')
}

// --- Login ---
async function handleLogin() {
  errorMsg.value = ''
  successMsg.value = ''
  loading.value = true
  try {
    const payload = {
      captcha_id: loginForm.captchaId,
      captcha: loginForm.captchaCode,
    }

    if (loginMode.value === 'phone') {
      payload.auth_phone = loginForm.phone
      if (passwordMode.value === 'sms') {
        payload.auth_sms_code = loginForm.smsCode
      } else {
        payload.auth_password = loginForm.password
      }
    } else {
      payload.auth_username = loginForm.username
      if (passwordMode.value === 'sms') {
        payload.auth_phone = loginForm.phone
        payload.auth_sms_code = loginForm.smsCode
      } else {
        payload.auth_password = loginForm.password
      }
    }

    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = { 'Content-Type': 'application/json' }
    if (sessionId) headers['X-Session-ID'] = sessionId

    const res = await fetch('/auth/login', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(payload),
    })
    const data = await res.json()

    if (!data.success) {
      // 手机号未注册 → 引导跳转注册并预填手机号/验证码
      if (loginMode.value === 'phone' && /未注册|不存在|未绑定/.test(data.message || '')) {
        const jump = await Swal.fire({
          icon: 'info',
          title: '手机号未注册',
          text: data.message || '该手机号尚未注册，是否立即前往注册？',
          showCancelButton: true,
          confirmButtonText: '前往注册',
          cancelButtonText: '取消',
        })
        if (jump.isConfirmed) {
          activeTab.value = 'register'
          registerForm.phone = loginForm.phone
          if (passwordMode.value === 'sms') registerForm.smsCode = loginForm.smsCode
          loadCaptcha('register')
          return
        }
      }
      errorMsg.value = data.message || '登录失败'
      loadCaptcha('login')
      return
    }

    if (data.requires_2fa) {
      pending2FAData.value = data
      twoFAUsername.value = data.auth_username
        || (loginMode.value === 'phone' ? loginForm.phone : loginForm.username)
      show2FA.value = true
      return
    }

    handleLoginSuccess(data)
  } catch (e) {
    errorMsg.value = e.message || '登录失败'
    loadCaptcha('login')
  } finally {
    loading.value = false
  }
}

async function handleGuestLogin() {
  errorMsg.value = ''
  successMsg.value = ''
  loading.value = true
  try {
    const data = await callRawAPI('/auth/guest_login', 'POST')
    if (data.success === false) {
      errorMsg.value = data.message || '游客登录失败'
      return
    }
    handleLoginSuccess(data)
  } catch (e) {
    errorMsg.value = e.message || '游客登录失败'
  } finally {
    loading.value = false
  }
}

function handleLoginSuccess(data) {
  auth.setLoginResult(data)
  successMsg.value = '登录成功'
  emit('login-success', data)
}

// --- Register ---
async function handleRegister() {
  errorMsg.value = ''
  successMsg.value = ''

  if (registerForm.password !== registerForm.confirmPassword) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }

  if (!registerForm.username || !registerForm.password) {
    errorMsg.value = '请填写用户名和密码'
    return
  }

  if (/[一-龥]/.test(registerForm.username)) {
    errorMsg.value = '用户名不能包含中文'
    return
  }

  if (registerForm.password.length < 6) {
    errorMsg.value = '密码长度至少为6个字符'
    return
  }

  loading.value = true
  try {
    const payload = {
      auth_username: registerForm.username,
      phone: registerForm.phone,
      sms_code: registerForm.smsCode,
      nickname: registerForm.nickname || registerForm.username,
      auth_password: registerForm.password,
      captcha_id: registerForm.captchaId,
      captcha: registerForm.captchaCode,
    }

    if (registerForm.avatarFile) {
      const reader = new FileReader()
      const avatarBase64 = await new Promise((resolve, reject) => {
        reader.onload = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(registerForm.avatarFile)
      })
      payload.avatar = avatarBase64
    }

    const data = await callRawAPI('/auth/register', 'POST', payload)
    if (data.success === false) {
      errorMsg.value = data.message || '注册失败'
      loadCaptcha('register')
      return
    }
    successMsg.value = data.message || '注册成功，请登录'
    activeTab.value = 'login'
    loginForm.username = registerForm.username
    loadCaptcha('login')
  } catch (e) {
    errorMsg.value = e.message || '注册失败'
    loadCaptcha('register')
  } finally {
    loading.value = false
  }
}

// --- 2FA ---
async function handle2FAVerify() {
  if (!twoFACode.value || twoFACode.value.length < 6) {
    errorMsg.value = '请输入6位验证码'
    return
  }
  errorMsg.value = ''
  loading.value = true
  try {
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = { 'Content-Type': 'application/json' }
    if (sessionId) headers['X-Session-ID'] = sessionId

    const res = await fetch('/auth/2fa/verify_login', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({
        auth_username: twoFAUsername.value || pending2FAData.value?.auth_username || '',
        code: twoFACode.value,
      }),
    })
    const data = await res.json()
    if (!data.success) {
      errorMsg.value = data.message || '验证失败'
      return
    }
    handleLoginSuccess(data)
  } catch (e) {
    errorMsg.value = e.message || '验证失败'
  } finally {
    loading.value = false
  }
}

function back2FA() {
  show2FA.value = false
  twoFACode.value = ''
  pending2FAData.value = null
  errorMsg.value = ''
}

// --- Avatar ---
function handleAvatarChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  registerForm.avatarFile = file
  const reader = new FileReader()
  reader.onload = () => {
    registerForm.avatarPreview = reader.result
  }
  reader.readAsDataURL(file)
}

// --- Lifecycle ---
onMounted(() => {
  loadCaptcha('login')
  loadCaptcha('register')
  checkGuestLoginEnabled()
})

onUnmounted(() => {
  if (loginSmsTimer) clearInterval(loginSmsTimer)
  if (registerSmsTimer) clearInterval(registerSmsTimer)
})
</script>

<template>
  <div class="w-full">
    <!-- 2FA form -->
    <div v-if="show2FA" class="space-y-4">
      <h3 class="text-lg font-semibold">双因素认证</h3>
      <p class="text-sm" style="color: var(--ink-secondary)">
        请输入您的验证器应用中的6位验证码
      </p>
      <input
        v-model="twoFACode"
        type="text"
        maxlength="6"
        class="input-field text-center text-2xl tracking-[0.5em]"
        placeholder="000000"
        @keyup.enter="handle2FAVerify"
      />
      <div class="flex gap-2">
        <button class="btn btn-secondary flex-1" @click="back2FA" :disabled="loading">
          返回
        </button>
        <button class="btn btn-primary flex-1" @click="handle2FAVerify" :disabled="loading || twoFACode.length < 6">
          {{ loading ? '验证中...' : '验证' }}
        </button>
      </div>
    </div>

    <!-- Login / Register tabs -->
    <div v-else>
      <TabPanel :tabs="tabs" v-model="activeTab">
        <!-- ====== LOGIN TAB ====== -->
        <template #login>
          <div class="space-y-4">
            <!-- Login mode toggle -->
            <div class="flex gap-2 text-sm">
              <button
                class="tab-button"
                :class="{ active: loginMode === 'username' }"
                @click="loginMode = 'username'; passwordMode = 'password'"
              >
                用户名登录
              </button>
              <button
                class="tab-button"
                :class="{ active: loginMode === 'phone' }"
                @click="loginMode = 'phone'"
              >
                手机号登录
              </button>
            </div>

            <!-- Username input (username mode) -->
            <div v-if="loginMode === 'username'">
              <label class="mb-1 block text-sm font-medium">用户名</label>
              <input
                v-model="loginForm.username"
                type="text"
                class="input-field"
                placeholder="请输入用户名"
                autocomplete="username"
              />
            </div>

            <!-- Phone input (phone mode or SMS mode) -->
            <div v-if="loginMode === 'phone' || passwordMode === 'sms'">
              <label class="mb-1 block text-sm font-medium">手机号</label>
              <input
                v-model="loginForm.phone"
                type="tel"
                class="input-field"
                placeholder="请输入手机号"
                autocomplete="tel"
              />
            </div>

            <!-- Password/SMS toggle (only show SMS option in phone mode) -->
            <div v-if="loginMode === 'phone'" class="flex gap-2 text-sm">
              <button
                class="tab-button"
                :class="{ active: passwordMode === 'password' }"
                @click="passwordMode = 'password'"
              >
                密码登录
              </button>
              <button
                class="tab-button"
                :class="{ active: passwordMode === 'sms' }"
                @click="passwordMode = 'sms'"
              >
                验证码登录
              </button>
            </div>

            <!-- Password input -->
            <div v-if="passwordMode === 'password'">
              <label class="mb-1 block text-sm font-medium">密码</label>
              <input
                v-model="loginForm.password"
                type="password"
                class="input-field"
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="handleLogin"
              />
            </div>

            <!-- SMS code input -->
            <div v-if="passwordMode === 'sms'">
              <label class="mb-1 block text-sm font-medium">短信验证码</label>
              <div class="flex gap-2">
                <input
                  v-model="loginForm.smsCode"
                  type="text"
                  maxlength="6"
                  class="input-field flex-1"
                  placeholder="请输入验证码"
                  @keyup.enter="handleLogin"
                />
                <button
                  class="btn btn-secondary shrink-0"
                  :disabled="loginSmsCooldown > 0 || !loginForm.phone"
                  @click="sendLoginSmsCode"
                >
                  {{ loginSmsCooldown > 0 ? `${loginSmsCooldown}s` : '发送验证码' }}
                </button>
              </div>
            </div>

            <!-- Captcha -->
            <div>
              <label class="mb-1 block text-sm font-medium">验证码</label>
              <div class="flex items-center gap-2">
                <input
                  v-model="loginForm.captchaCode"
                  type="text"
                  maxlength="6"
                  class="input-field flex-1"
                  placeholder="请输入图形验证码"
                  @keyup.enter="handleLogin"
                />
                <div
                  ref="loginCaptchaContainerRef"
                  class="flex min-w-[120px] shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg border"
                  :style="{
                    borderColor: 'var(--border-color)',
                    width: loginCaptchaDims.width ? loginCaptchaDims.width + 'px' : undefined,
                    height: loginCaptchaDims.height ? loginCaptchaDims.height + 'px' : '80px',
                  }"
                  @click="loadCaptcha('login')"
                  title="点击刷新验证码"
                >
                  <iframe
                    v-if="loginCaptchaIframeSrc"
                    :src="loginCaptchaIframeSrc"
                    scrolling="no"
                    frameborder="0"
                    :style="{
                      width: loginCaptchaDims.width ? loginCaptchaDims.width + 'px' : '100%',
                      height: loginCaptchaDims.height ? loginCaptchaDims.height + 'px' : '80px',
                      border: 'none',
                      overflow: 'hidden',
                      display: 'block',
                      margin: '0 auto',
                      pointerEvents: 'none',
                    }"
                  ></iframe>
                  <span v-else class="px-3 text-xs" style="color: var(--ink-muted)">加载中</span>
                </div>
                <button
                  class="btn btn-ghost shrink-0 p-2"
                  @click="loadCaptcha('login')"
                  title="刷新验证码"
                >
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Login button -->
            <div class="pt-2">
              <button
                class="btn btn-primary w-full"
                :disabled="loading"
                @click="handleLogin"
              >
                {{ loading ? '登录中...' : '登录' }}
              </button>
            </div>

            <!-- Guest login section (conditional based on backend config) -->
            <div v-if="guestLoginEnabled" class="text-center">
              <div class="relative flex py-2 items-center">
                <div class="flex-grow border-t" style="border-color: var(--border-color)"></div>
                <span class="mx-4 shrink-0 text-xs" style="color: var(--ink-muted)">或</span>
                <div class="flex-grow border-t" style="border-color: var(--border-color)"></div>
              </div>
              <button
                class="btn btn-ghost w-full"
                :disabled="loading"
                @click="handleGuestLogin"
              >
                以游客身份继续
              </button>
              <div class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-left dark:border-amber-700 dark:bg-amber-900/20">
                <div class="flex items-start gap-2">
                  <svg class="mt-0.5 h-5 w-5 shrink-0 text-amber-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" />
                  </svg>
                  <div class="text-xs text-amber-800 dark:text-amber-300">
                    <p class="mb-1 font-semibold">游客模式提示</p>
                    <ul class="space-y-1">
                      <li>&#8226; 游客使用UUID恢复状态，请务必保存地址</li>
                      <li>&#8226; 丢失URL将无法恢复您的数据和进度</li>
                      <li>&#8226; 5分钟不活跃会话将被自动清理</li>
                      <li>&#8226; 建议注册账号以获得更好的体验</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ====== REGISTER TAB ====== -->
        <template #register>
          <div class="space-y-4">
            <!-- Username -->
            <div>
              <label class="mb-1 block text-sm font-medium">用户名 <span class="text-red-500">*</span></label>
              <input
                v-model="registerForm.username"
                type="text"
                class="input-field"
                placeholder="请输入用户名（3-20字符，不含中文）"
                autocomplete="username"
              />
            </div>

            <!-- Phone + SMS -->
            <div>
              <label class="mb-1 block text-sm font-medium">手机号</label>
              <div class="flex gap-2">
                <div class="relative flex-1">
                  <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm font-medium" style="color: var(--ink-secondary)">+86</span>
                  <input
                    v-model="registerForm.phone"
                    type="tel"
                    class="input-field w-full"
                    style="padding-left: 2.8rem"
                    placeholder="请输入手机号"
                    autocomplete="tel"
                    inputmode="numeric"
                    pattern="[0-9]*"
                    maxlength="11"
                  />
                </div>
                <button
                  class="btn btn-secondary shrink-0"
                  :disabled="registerSmsCooldown > 0 || !registerForm.phone"
                  @click="sendRegisterSmsCode"
                >
                  {{ registerSmsCooldown > 0 ? `${registerSmsCooldown}s` : '发送验证码' }}
                </button>
              </div>
            </div>

            <div>
              <label class="mb-1 block text-sm font-medium">短信验证码</label>
              <input
                v-model="registerForm.smsCode"
                type="text"
                maxlength="6"
                class="input-field"
                placeholder="请输入短信验证码"
              />
            </div>

            <!-- Nickname -->
            <div>
              <label class="mb-1 block text-sm font-medium">昵称</label>
              <input
                v-model="registerForm.nickname"
                type="text"
                class="input-field"
                placeholder="请输入昵称（可含中文）"
              />
            </div>

            <!-- Avatar -->
            <div>
              <label class="mb-1 block text-sm font-medium">头像</label>
              <div class="flex items-center gap-3">
                <div
                  class="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border"
                  style="border-color: var(--border-color); background: var(--glass)"
                >
                  <img
                    v-if="registerForm.avatarPreview"
                    :src="registerForm.avatarPreview"
                    alt="头像预览"
                    class="h-full w-full object-cover"
                  />
                  <svg v-else class="h-6 w-6" style="color: var(--ink-muted)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <label class="btn btn-secondary cursor-pointer text-sm">
                  选择头像
                  <input
                    type="file"
                    accept="image/*"
                    class="hidden"
                    @change="handleAvatarChange"
                  />
                </label>
              </div>
            </div>

            <!-- Password -->
            <div>
              <label class="mb-1 block text-sm font-medium">密码 <span class="text-red-500">*</span></label>
              <input
                v-model="registerForm.password"
                type="password"
                class="input-field"
                placeholder="请输入密码（至少6字符）"
                autocomplete="new-password"
              />
            </div>

            <!-- Confirm password -->
            <div>
              <label class="mb-1 block text-sm font-medium">确认密码 <span class="text-red-500">*</span></label>
              <input
                v-model="registerForm.confirmPassword"
                type="password"
                class="input-field"
                placeholder="请再次输入密码"
                autocomplete="new-password"
                @keyup.enter="handleRegister"
              />
            </div>

            <!-- Captcha -->
            <div>
              <label class="mb-1 block text-sm font-medium">验证码</label>
              <div class="flex items-center gap-2">
                <input
                  v-model="registerForm.captchaCode"
                  type="text"
                  maxlength="6"
                  class="input-field flex-1"
                  placeholder="请输入图形验证码"
                  @keyup.enter="handleRegister"
                />
                <div
                  ref="registerCaptchaContainerRef"
                  class="flex min-w-[120px] shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg border"
                  :style="{
                    borderColor: 'var(--border-color)',
                    width: registerCaptchaDims.width ? registerCaptchaDims.width + 'px' : undefined,
                    height: registerCaptchaDims.height ? registerCaptchaDims.height + 'px' : '80px',
                  }"
                  @click="loadCaptcha('register')"
                  title="点击刷新验证码"
                >
                  <iframe
                    v-if="registerCaptchaIframeSrc"
                    :src="registerCaptchaIframeSrc"
                    scrolling="no"
                    frameborder="0"
                    :style="{
                      width: registerCaptchaDims.width ? registerCaptchaDims.width + 'px' : '100%',
                      height: registerCaptchaDims.height ? registerCaptchaDims.height + 'px' : '80px',
                      border: 'none',
                      overflow: 'hidden',
                      display: 'block',
                      margin: '0 auto',
                      pointerEvents: 'none',
                    }"
                  ></iframe>
                  <span v-else class="px-3 text-xs" style="color: var(--ink-muted)">加载中</span>
                </div>
                <button
                  class="btn btn-ghost shrink-0 p-2"
                  @click="loadCaptcha('register')"
                  title="刷新验证码"
                >
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Available runs hint (conditional) -->
            <div v-if="showAvailableRuns && availableRunsText" class="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-700 dark:bg-green-900/20">
              <p class="text-center text-sm font-medium text-green-700 dark:text-green-400">
                🎁 {{ availableRunsText }}
              </p>
            </div>

            <!-- Register button -->
            <button
              class="btn btn-primary w-full"
              :disabled="loading"
              @click="handleRegister"
            >
              {{ loading ? '注册中...' : '注册' }}
            </button>
          </div>
        </template>
      </TabPanel>
    </div>

    <!-- Messages -->
    <div v-if="errorMsg" class="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="mt-3 rounded-lg bg-green-50 p-3 text-sm text-green-600 dark:bg-green-900/20 dark:text-green-400">
      {{ successMsg }}
    </div>
  </div>
</template>
