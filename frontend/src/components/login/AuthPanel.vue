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

// 验证码提供方（本地图片 / 验证码服务器）
const captchaProvider = ref('image')
const behaviorCaptchaType = ref('SLIDER')
let tacLoaderPromise = null
const tacInstances = {}

async function fetchCaptchaProvider() {
  try {
    const res = await fetch('/api/captcha/provider', { method: 'GET', credentials: 'include' })
    if (res.ok) {
      const d = await res.json()
      if (d && d.success) {
        captchaProvider.value = d.provider === 'behavior' ? 'behavior' : 'image'
        behaviorCaptchaType.value = d.behavior_type || 'SLIDER'
      }
    }
  } catch (_) { /* 回退本地图片 */ }
}

// 通过后端代理加载 behavior TAC SDK（浏览器只访问本站）
function ensureTacLoader() {
  if (window.initTAC) return Promise.resolve()
  if (tacLoaderPromise) return tacLoaderPromise
  tacLoaderPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = '/api/captcha/behavior/loader.js'
    s.async = true
    s.onload = () => (window.initTAC ? resolve() : reject(new Error('TAC loader 未暴露 initTAC')))
    s.onerror = () => reject(new Error('加载验证码 SDK 失败'))
    document.head.appendChild(s)
  })
  return tacLoaderPromise
}

function createTacTriggerStyle() {
  return {
    triggerMode: 'click',
    popupMode: true,
    logoUrl: null,
    i18n: {
      trigger_text: '点击进行人机验证码',
    },
  }
}

function destroyTac(target) {
  try { tacInstances[target]?.destroyWindow?.() } catch (_) {}
  tacInstances[target] = null
}

function resetBehaviorCaptcha(target) {
  const form = target === 'login' ? loginForm : registerForm
  form.captchaId = ''
  form.captchaCode = ''
}

// 在指定容器渲染验证码服务器入口；校验通过后把验证过的 id 写入表单 captchaId
async function mountTacWidget(target) {
  const form = target === 'login' ? loginForm : registerForm
  const hasVerifiedBehaviorCaptcha = !!form.captchaId
  if (!hasVerifiedBehaviorCaptcha) {
    form.captchaId = ''
    form.captchaCode = ''
  } else {
    form.captchaCode = 'behavior-verified'
  }
  try {
    await ensureTacLoader()
    await nextTick()
    destroyTac(target)
    const bindEl = target === 'login' ? '#tac-login' : '#tac-register'
    if (!document.querySelector(bindEl)) return
    const preserveSuccessOnClose = () => !!form.captchaId
    const tac = await window.initTAC('/api/captcha/behavior/tac/', {
      requestCaptchaDataUrl: '/api/captcha/behavior/gen?type=' + encodeURIComponent(behaviorCaptchaType.value),
      validCaptchaUrl: '/api/captcha/behavior/check',
      bindEl,
      btnCloseFun: (event, t) => {
        if (t && t.isClickTriggerMode?.() && t.renderTrigger) {
          t.renderTrigger(preserveSuccessOnClose())
        } else if (t && t.destroyWindow) {
          t.destroyWindow()
        }
      },
      validSuccess: (res, c, t) => {
        form.captchaId = res && res.data ? res.data.id : ''
        form.captchaCode = 'behavior-verified'
        if (t && t.showTriggerSuccess) t.showTriggerSuccess()
      },
      validFail: (res, c, t) => {
        if (form.captchaId) {
          if (t && t.showTriggerSuccess) t.showTriggerSuccess()
        } else if (t && t.reloadCaptcha) {
          t.reloadCaptcha()
        }
      },
    }, createTacTriggerStyle())
    tacInstances[target] = tac
    tac.init()
    if (hasVerifiedBehaviorCaptcha && tac && tac.showTriggerSuccess) tac.showTriggerSuccess()
  } catch (e) {
    console.warn('验证码服务器加载失败:', e)
  }
}

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
  // 验证码服务器提供方：渲染行为验证码组件
  if (captchaProvider.value === 'behavior') {
    return mountTacWidget(target)
  }
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
  if (captchaProvider.value === 'behavior') {
    return showSmsTacModal(phone, type)
  }
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

// --- SMS Captcha Modal（验证码服务器版）---
function showSmsTacModal(phone, type) {
  let validatedId = ''
  Swal.fire({
    title: '安全验证',
    html: `
      <p style="color:#64748b;font-size:14px;margin-bottom:12px;">为保护您的账号安全，请完成人机验证</p>
      <div id="swal-tac" style="min-height:60px;"></div>
      <p id="swal-tac-status" style="color:#94a3b8;font-size:12px;margin-top:8px;">请完成上方行为验证</p>
    `,
    showCancelButton: true,
    confirmButtonText: '确认发送',
    cancelButtonText: '取消',
    customClass: {
      confirmButton: 'btn btn-primary',
      cancelButton: 'btn btn-secondary',
    },
    didOpen: async () => {
      try {
        await ensureTacLoader()
        const preserveSuccessOnClose = () => !!validatedId
        const tac = await window.initTAC('/api/captcha/behavior/tac/', {
          requestCaptchaDataUrl: '/api/captcha/behavior/gen?type=' + encodeURIComponent(behaviorCaptchaType.value),
          validCaptchaUrl: '/api/captcha/behavior/check',
          bindEl: '#swal-tac',
          btnCloseFun: (event, t) => {
            if (t && t.isClickTriggerMode?.() && t.renderTrigger) {
              t.renderTrigger(preserveSuccessOnClose())
            } else if (t && t.destroyWindow) {
              t.destroyWindow()
            }
          },
          validSuccess: (res, c, t) => {
            validatedId = res && res.data ? res.data.id : ''
            const st = document.getElementById('swal-tac-status')
            if (st) { st.textContent = '✓ 验证通过，请点击确认发送'; st.style.color = '#16a34a' }
            if (t && t.showTriggerSuccess) t.showTriggerSuccess()
          },
          validFail: (r, c, t) => {
            if (validatedId) {
              if (t && t.showTriggerSuccess) t.showTriggerSuccess()
            } else if (t && t.reloadCaptcha) {
              t.reloadCaptcha()
            }
          },
        }, createTacTriggerStyle())
        tac.init()
      } catch (e) {
        const st = document.getElementById('swal-tac-status')
        if (st) { st.textContent = '验证码加载失败，请稍后重试'; st.style.color = '#dc2626' }
      }
    },
    preConfirm: () => {
      if (!validatedId) {
        Swal.showValidationMessage('请先完成人机验证')
        return false
      }
      return { captchaId: validatedId, captchaCode: 'behavior-verified' }
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

  if (captchaProvider.value === 'behavior' && !loginForm.captchaId) {
    errorMsg.value = '请先完成人机验证'
    return
  }
  if (captchaProvider.value !== 'behavior' && !loginForm.captchaCode.trim()) {
    errorMsg.value = '请输入图形验证码'
    return
  }

  loading.value = true
  try {
    const payload = {
      captcha_id: loginForm.captchaId,
      captcha: captchaProvider.value === 'behavior' ? 'behavior-verified' : loginForm.captchaCode,
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
      if (captchaProvider.value === 'behavior') resetBehaviorCaptcha('login')
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
    if (captchaProvider.value === 'behavior') resetBehaviorCaptcha('login')
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

  if (captchaProvider.value === 'behavior' && !registerForm.captchaId) {
    errorMsg.value = '请先完成人机验证'
    return
  }
  if (captchaProvider.value !== 'behavior' && !registerForm.captchaCode.trim()) {
    errorMsg.value = '请输入图形验证码'
    return
  }

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
      captcha: captchaProvider.value === 'behavior' ? 'behavior-verified' : registerForm.captchaCode,
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
      if (captchaProvider.value === 'behavior') resetBehaviorCaptcha('register')
      loadCaptcha('register')
      return
    }
    successMsg.value = data.message || '注册成功，请登录'
    activeTab.value = 'login'
    loginForm.username = registerForm.username
    loadCaptcha('login')
  } catch (e) {
    errorMsg.value = e.message || '注册失败'
    if (captchaProvider.value === 'behavior') resetBehaviorCaptcha('register')
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
onMounted(async () => {
  await fetchCaptchaProvider()
  loadCaptcha('login')
  loadCaptcha('register')
  checkGuestLoginEnabled()
})

onUnmounted(() => {
  if (loginSmsTimer) clearInterval(loginSmsTimer)
  if (registerSmsTimer) clearInterval(registerSmsTimer)
  destroyTac('login')
  destroyTac('register')
})
</script>

<template>
  <div class="w-full">
    <!-- 2FA form -->
    <div v-if="show2FA" id="auth-2fa-form" class="space-y-4">
      <div class="mb-4 text-center">
        <h3 class="mb-2 text-xl font-bold text-sky-700">双因素认证</h3>
        <p class="text-sm text-slate-500">
          请输入您的验证器应用中的6位验证码
        </p>
      </div>
      <div id="auth-2fa-code-wrapper">
        <label class="block text-sm font-semibold leading-6 text-slate-700">验证码</label>
      <input
        id="auth-2fa-code"
        v-model="twoFACode"
        type="text"
        maxlength="6"
        class="input-field mt-1"
        placeholder="输入6位验证码"
        inputmode="numeric"
        pattern="[0-9]{6}"
        autocomplete="one-time-code"
        @keyup.enter="handle2FAVerify"
      />
      </div>
      <button
        id="auth-2fa-verify-btn"
        class="btn btn-primary w-full py-3"
        :disabled="loading || twoFACode.length < 6"
        @click="handle2FAVerify"
      >
        {{ loading ? '验证中...' : '验证' }}
      </button>
      <button
        id="auth-2fa-back-btn"
        class="btn btn-ghost w-full"
        :disabled="loading"
        @click="back2FA"
      >
        返回登录
      </button>
    </div>

    <!-- Login / Register tabs -->
    <div v-else>
      <TabPanel class="auth-tabs" :tabs="tabs" v-model="activeTab">
        <!-- ====== LOGIN TAB ====== -->
        <template #login>
          <form
            id="auth-login-form"
            class="max-h-[60vh] space-y-4 overflow-y-auto p-1"
            autocomplete="on"
            @submit.prevent="handleLogin"
          >
            <!-- Login mode toggle -->
            <div id="auth-login-type-toggle" class="flex justify-center gap-2 pb-2">
              <button
                id="auth-login-username-btn"
                type="button"
                class="rounded-lg px-4 py-2 text-sm font-semibold"
                :class="loginMode === 'username' ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-600'"
                @click="loginMode = 'username'; passwordMode = 'password'"
              >
                用户名登录
              </button>
              <button
                id="auth-login-phone-btn"
                type="button"
                class="rounded-lg px-4 py-2 text-sm font-semibold"
                :class="loginMode === 'phone' ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-600'"
                @click="loginMode = 'phone'"
              >
                手机号登录
              </button>
            </div>

            <!-- Username input (username mode) -->
            <div v-if="loginMode === 'username'">
              <label class="block text-sm font-semibold leading-6 text-slate-700">用户名</label>
              <input
                id="auth-username"
                v-model="loginForm.username"
                type="text"
                name="username"
                class="input-field mt-1"
                placeholder="请输入用户名"
                autocomplete="username"
              />
            </div>

            <!-- Phone input (phone mode or SMS mode) -->
            <div v-if="loginMode === 'phone' || passwordMode === 'sms'">
              <label class="block text-sm font-semibold leading-6 text-slate-700">手机号</label>
              <input
                v-model="loginForm.phone"
                type="tel"
                class="input-field mt-1"
                placeholder="请输入手机号"
                autocomplete="tel"
              />
            </div>

            <!-- Password/SMS toggle (only show SMS option in phone mode) -->
            <div v-if="loginMode === 'phone'" class="flex justify-end">
              <button
                type="button"
                class="text-xs text-sky-600 hover:text-sky-700"
                @click="passwordMode = passwordMode === 'password' ? 'sms' : 'password'"
              >
                {{ passwordMode === 'password' ? '使用验证码登录' : '使用密码登录' }}
              </button>
            </div>

            <!-- Password input -->
            <div v-if="passwordMode === 'password'">
              <label class="block text-sm font-semibold leading-6 text-slate-700">密码</label>
              <input
                id="auth-password"
                v-model="loginForm.password"
                type="password"
                name="password"
                class="input-field mt-1"
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="handleLogin"
              />
            </div>

            <!-- SMS code input -->
            <div v-if="passwordMode === 'sms'">
              <label class="block text-sm font-semibold leading-6 text-slate-700">验证码</label>
              <div class="mt-1 flex gap-2">
                <input
                  id="auth-sms-code"
                  v-model="loginForm.smsCode"
                  type="text"
                  maxlength="6"
                  class="input-field flex-1"
                  placeholder="请输入验证码"
                  inputmode="numeric"
                  pattern="[0-9]{6}"
                  @keyup.enter="handleLogin"
                />
                <button
                  id="auth-send-login-code"
                  type="button"
                  class="btn btn-primary shrink-0 whitespace-nowrap"
                  style="min-height: 44px"
                  :disabled="loginSmsCooldown > 0 || !loginForm.phone"
                  @click="sendLoginSmsCode"
                >
                  {{ loginSmsCooldown > 0 ? `${loginSmsCooldown}s` : '发送验证码' }}
                </button>
              </div>
            </div>

            <!-- Captcha -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">
                {{ captchaProvider === 'behavior' ? '人机验证' : '验证码' }}
              </label>
              <!-- 本地图片验证码 -->
              <div v-if="captchaProvider !== 'behavior'">
                <div
                  id="auth-login-captcha-container_display"
                  ref="loginCaptchaContainerRef"
                  class="flex justify-center"
                >
                  <div class="mt-1 flex items-center gap-2">
                    <div
                      id="auth-login-captcha-display"
                      class="flex h-auto w-auto flex-shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded border border-slate-300 bg-white transition-colors hover:border-sky-400"
                      style="min-height: 64px"
                      title="点击刷新验证码"
                      @click="loadCaptcha('login')"
                    >
                      <iframe
                        v-if="loginCaptchaIframeSrc"
                        :src="loginCaptchaIframeSrc"
                        scrolling="no"
                        frameborder="0"
                        :style="{
                          width: loginCaptchaDims.width ? loginCaptchaDims.width + 'px' : '100%',
                          height: loginCaptchaDims.height ? loginCaptchaDims.height + 'px' : '64px',
                          border: 'none',
                          overflow: 'hidden',
                          display: 'block',
                          margin: '0 auto',
                          pointerEvents: 'none',
                        }"
                      ></iframe>
                      <span v-else class="px-3 text-xs text-slate-400">加载中...</span>
                    </div>
                    <button
                      id="auth-login-captcha-refresh"
                      type="button"
                      class="btn btn-ghost !p-2"
                      title="刷新验证码"
                      @click="loadCaptcha('login')"
                    >
                      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      <span class="auth-captcha-refresh-text">刷新验证码</span>
                    </button>
                  </div>
                </div>
                <div class="mt-2">
                  <input
                    id="auth-login-captcha"
                    v-model="loginForm.captchaCode"
                    type="text"
                    maxlength="6"
                    class="input-field w-full"
                    placeholder="请输入验证码"
                    autocomplete="off"
                    @keyup.enter="handleLogin"
                  />
                </div>
              </div>
              <!-- 验证码服务器 -->
              <div v-else>
                <div id="tac-login" class="min-h-[60px] w-full"></div>
                <p class="mt-1 text-xs" :style="{ color: loginForm.captchaId ? '#16a34a' : 'var(--ink-muted)' }">
                  {{ loginForm.captchaId ? '验证通过' : '请完成上方行为验证' }}
                </p>
              </div>
            </div>

            <!-- Login button -->
            <button
              id="auth-login-btn"
              class="btn btn-primary w-full py-3"
              style="min-height: 44px"
              type="submit"
              :disabled="loading"
            >
              {{ loading ? '登录中...' : '登录' }}
            </button>

            <!-- Guest login section (conditional based on backend config) -->
            <div v-if="guestLoginEnabled" id="guest-login-section" class="text-center">
              <div class="relative flex items-center py-2">
                <div class="flex-grow border-t border-slate-200"></div>
                <span class="mx-4 shrink-0 text-xs text-slate-400">或</span>
                <div class="flex-grow border-t border-slate-200"></div>
              </div>
              <button
                id="auth-guest-btn"
                type="button"
                class="btn btn-ghost w-full"
                :disabled="loading"
                @click="handleGuestLogin"
              >
                以游客身份继续
              </button>
              <div class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-left">
                <div class="flex items-start gap-2">
                  <svg class="mt-0.5 h-5 w-5 shrink-0 text-amber-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" />
                  </svg>
                  <div class="text-xs text-amber-800">
                    <p class="mb-1 font-semibold">⚠️ 游客模式提示</p>
                    <ul class="space-y-1">
                      <li>• 游客使用UUID恢复状态，请务必保存地址</li>
                      <li>• 丢失URL将无法恢复您的数据和进度</li>
                      <li>• 5分钟不活跃会话将被自动清理</li>
                      <li>• 建议注册账号以获得更好的体验</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </template>

        <!-- ====== REGISTER TAB ====== -->
        <template #register>
          <form
            id="auth-register-form"
            class="max-h-[60vh] space-y-4 overflow-y-auto p-1"
            autocomplete="on"
            @submit.prevent="handleRegister"
          >
            <!-- Username -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">用户名</label>
              <input
                id="auth-reg-username"
                v-model="registerForm.username"
                type="text"
                name="username"
                class="input-field mt-1"
                placeholder="请输入用户名（3-20字符，不含中文）"
                autocomplete="username"
              />
            </div>

            <!-- Phone + SMS -->
            <div id="auth-reg-phone-wrapper">
              <label class="block text-sm font-semibold leading-6 text-slate-700">手机号</label>
              <div class="phone-input-wrapper mt-1">
                <span class="phone-prefix">+86 </span>
                <input
                  id="auth-reg-phone"
                  v-model="registerForm.phone"
                  type="tel"
                  class="input-field"
                  placeholder="请输入手机号"
                  autocomplete="tel"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  maxlength="11"
                />
              </div>
            </div>

            <div id="auth-reg-sms-wrapper">
              <label class="block text-sm font-semibold leading-6 text-slate-700">验证码</label>
              <div class="flex gap-2">
                <input
                  id="auth-reg-sms-code"
                  v-model="registerForm.smsCode"
                  type="text"
                  class="input-field mt-1 flex-1"
                  placeholder="请输入验证码"
                  maxlength="6"
                  inputmode="numeric"
                  pattern="[0-9]{6}"
                />
                <button
                  id="auth-reg-send-code-btn"
                  type="button"
                  class="btn btn-primary mt-1 shrink-0 whitespace-nowrap"
                  style="min-height: 44px"
                  :disabled="registerSmsCooldown > 0 || !registerForm.phone"
                  @click="sendRegisterSmsCode"
                >
                  {{ registerSmsCooldown > 0 ? `${registerSmsCooldown}s` : '发送验证码' }}
                </button>
              </div>
            </div>

            <!-- Nickname -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">昵称</label>
              <input
                id="auth-reg-nickname"
                v-model="registerForm.nickname"
                type="text"
                class="input-field mt-1"
                placeholder="请输入昵称（可含中文）"
              />
            </div>

            <!-- Avatar -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">头像</label>
              <div class="mt-1 flex items-center gap-3">
                <img
                  id="auth-reg-avatar-preview"
                  :src="registerForm.avatarPreview || '/static/default_avatar.png'"
                  alt="头像预览"
                  class="h-16 w-16 rounded-full border-2 border-slate-200 object-cover"
                />
                <input
                  id="auth-reg-avatar"
                  type="file"
                  accept="image/*"
                  class="hidden"
                  @change="handleAvatarChange"
                />
                <label
                  for="auth-reg-avatar"
                  class="btn btn-ghost cursor-pointer !px-3 !py-1.5 text-sm"
                >
                  <svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  上传头像
                </label>
              </div>
            </div>

            <!-- Password -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">密码</label>
              <input
                id="auth-reg-password"
                v-model="registerForm.password"
                type="password"
                name="new-password"
                class="input-field mt-1"
                placeholder="请输入密码（至少6字符）"
                autocomplete="new-password"
              />
            </div>

            <!-- Confirm password -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">确认密码</label>
              <input
                id="auth-reg-password-confirm"
                v-model="registerForm.confirmPassword"
                type="password"
                name="new-password-confirm"
                class="input-field mt-1"
                placeholder="请再次输入密码"
                autocomplete="new-password"
                @keyup.enter="handleRegister"
              />
            </div>

            <!-- Captcha -->
            <div>
              <label class="block text-sm font-semibold leading-6 text-slate-700">
                {{ captchaProvider === 'behavior' ? '人机验证' : '验证码' }}
              </label>
              <!-- 本地图片验证码 -->
              <div v-if="captchaProvider !== 'behavior'">
                <div
                  id="auth-register-captcha-display_wrapper"
                  ref="registerCaptchaContainerRef"
                  class="mt-1 flex items-center justify-center gap-2"
                >
                  <div
                    id="auth-register-captcha-display"
                    class="flex h-auto w-auto flex-shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded border border-slate-300 bg-white transition-colors hover:border-sky-400"
                    style="min-height: 64px"
                    title="点击刷新验证码"
                    @click="loadCaptcha('register')"
                  >
                    <iframe
                      v-if="registerCaptchaIframeSrc"
                      :src="registerCaptchaIframeSrc"
                      scrolling="no"
                      frameborder="0"
                      :style="{
                        width: registerCaptchaDims.width ? registerCaptchaDims.width + 'px' : '100%',
                        height: registerCaptchaDims.height ? registerCaptchaDims.height + 'px' : '64px',
                        border: 'none',
                        overflow: 'hidden',
                        display: 'block',
                        margin: '0 auto',
                        pointerEvents: 'none',
                      }"
                    ></iframe>
                    <span v-else class="px-3 text-xs text-slate-400">加载中...</span>
                  </div>
                  <button
                    id="auth-register-captcha-refresh"
                    type="button"
                    class="btn btn-ghost !p-2"
                    title="刷新验证码"
                    @click="loadCaptcha('register')"
                  >
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span class="auth-captcha-refresh-text">刷新验证码</span>
                  </button>
                </div>
                <div class="mt-2">
                  <input
                    id="auth-register-captcha"
                    v-model="registerForm.captchaCode"
                    type="text"
                    maxlength="6"
                    class="input-field w-full"
                    placeholder="请输入验证码"
                    autocomplete="off"
                    @keyup.enter="handleRegister"
                  />
                </div>
              </div>
              <!-- 验证码服务器 -->
              <div v-else>
                <div id="tac-register" class="min-h-[60px] w-full"></div>
                <p class="mt-1 text-xs" :style="{ color: registerForm.captchaId ? '#16a34a' : 'var(--ink-muted)' }">
                  {{ registerForm.captchaId ? '验证通过' : '请完成上方行为验证' }}
                </p>
              </div>
            </div>

            <!-- Available runs hint (conditional) -->
            <div
              v-if="showAvailableRuns && availableRunsText"
              id="auth-register-available-runs-hint"
              class="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-700 dark:bg-green-900/20"
            >
              <p class="text-center text-sm font-medium text-green-700 dark:text-green-400">
                🎁 {{ availableRunsText }}
              </p>
            </div>

            <!-- Register button -->
            <button
              id="auth-register-btn"
              class="btn btn-success w-full py-3"
              style="min-height: 44px"
              type="submit"
              :disabled="loading"
            >
              {{ loading ? '注册中...' : '注册' }}
            </button>
          </form>
        </template>
      </TabPanel>
    </div>

    <!-- Messages -->
    <div
      v-if="errorMsg"
      id="auth-error-msg"
      class="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-center text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400"
    >
      {{ errorMsg }}
    </div>
    <div
      v-if="successMsg"
      id="auth-success-msg"
      class="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-center text-sm text-green-600 dark:bg-green-900/20 dark:text-green-400"
    >
      {{ successMsg }}
    </div>
  </div>
</template>
