<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { callAPI, callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import AuthPanel from '@/components/login/AuthPanel.vue'
import SessionPicker from '@/components/login/SessionPicker.vue'
import SessionLogin from '@/components/login/SessionLogin.vue'
import BeianFooter from '@/components/common/BeianFooter.vue'
import AppModal from '@/components/common/AppModal.vue'
import Swal from 'sweetalert2'
import { isRestorableSessionUUIDResponse } from '@/utils/validation'

const props = defineProps({
  uuid: { type: String, default: '' },
})

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const app = useAppStore()

const importFileInput = ref(null)

// 'loading' | 'auth' | 'session-picker' | 'school-login' | 'error'
const viewMode = ref('loading')
const errorMsg = ref('')
const sessionData = ref({})
const frontendConfig = ref({})

// --- Inline session management (school-login right column) ---
const inlineSessions = ref([])
const inlineSessionsLoading = ref(false)
const godModeEnabled = ref(false)
const hasGodModePermission = ref(false)

function getActiveSessionId() {
  const sessionId = auth.sessionUUID || auth.authSessionUUID || ''
  return typeof sessionId === 'string' ? sessionId.trim() : ''
}

async function replaceSessionUrl(value) {
  const sessionId = String(value || '').trim()
  if (!sessionId || sessionId.toLowerCase() === 'null') return
  auth.sessionUUID = sessionId
  sessionStorage.setItem('session_uuid', sessionId)
  if (route.params.uuid !== sessionId) {
    await router.replace({ name: 'session', params: { uuid: sessionId } })
  }
}

async function loadInlineSessions() {
  inlineSessionsLoading.value = true
  try {
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = {}
    if (sessionId) headers['X-Session-ID'] = sessionId

    const endpoint = godModeEnabled.value ? '/auth/admin/all_sessions' : '/auth/user/sessions'
    const res = await fetch(endpoint, { headers, credentials: 'include' })
    const data = await res.json()
    if (data.success !== false && data.sessions) {
      inlineSessions.value = data.sessions
    }
    if (data.permissions?.god_mode || data.god_mode_available) {
      hasGodModePermission.value = true
    }
  } catch (_) {}
  inlineSessionsLoading.value = false
}

function toggleGodMode() {
  godModeEnabled.value = !godModeEnabled.value
  loadInlineSessions()
}

function sessionDisplayName(session) {
  return (
    session?.username ||
    session?.auth_username ||
    session?.user_data?.username ||
    session?.user_info?.username ||
    session?.user ||
    '未知用户'
  )
}

function isCurrentInlineSession(session) {
  return !!session?.is_current || session?.session_id === auth.sessionUUID
}

async function selectInlineSession(session) {
  const sessionId = session?.session_id
  if (!sessionId || isCurrentInlineSession(session)) return
  try {
    const result = await callRawAPI('/auth/switch_session', 'POST', {
      target_session_id: sessionId,
    })
    if (result.success === false) throw new Error(result.message || '切换会话失败')
    auth.sessionUUID = sessionId
    auth.authSessionUUID = sessionId
    auth.loginInProgress = true
    await replaceSessionUrl(sessionId)
    sessionData.value = await callRawAPI('/auth/check_uuid_type', 'POST', {
      uuid: sessionId,
    })
    viewMode.value = 'school-login'
    await loadInlineSessions()
  } catch (error) {
    errorMsg.value = error.message || '切换会话失败'
  }
}

async function deleteInlineSession(session) {
  const sessionId = session?.session_id
  if (!sessionId || isCurrentInlineSession(session)) return
  const confirmed = await Swal.fire({
    title: '确认删除',
    text: '确定要删除该会话吗？',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
  })
  if (!confirmed.isConfirmed) return
  try {
    const result = await callRawAPI('/auth/user/delete_session', 'POST', {
      session_id: sessionId,
    })
    if (result.success === false) throw new Error(result.message || '删除会话失败')
    await loadInlineSessions()
  } catch (error) {
    errorMsg.value = error.message || '删除会话失败'
  }
}

// --- UUID validation ---
async function checkUUID(uuid) {
  viewMode.value = 'loading'
  errorMsg.value = ''
  try {
    const data = await callRawAPI('/auth/check_uuid_type', 'POST', { uuid })
    if (isRestorableSessionUUIDResponse(data)) {
      auth.sessionUUID = uuid
      auth.isAuthenticated = true
      auth.loginInProgress = true
      sessionStorage.setItem('session_uuid', uuid)
      sessionData.value = data
      viewMode.value = 'school-login'
      await loadInlineSessions()
    } else {
      auth.sessionUUID = null
      auth.loginInProgress = false
      viewMode.value = 'auth'
      await router.replace('/')
    }
  } catch (e) {
    console.warn('UUID验证失败:', e)
    auth.sessionUUID = null
    auth.loginInProgress = false
    viewMode.value = 'auth'
    await router.replace('/')
  }
}

// --- System login success → show session picker ---
async function onAuthSuccess(data) {
  if (data.session_id) await replaceSessionUrl(data.session_id)
  if (data.is_guest) {
    viewMode.value = 'school-login'
    setTimeout(loadInlineSessions, 300)
  } else {
    viewMode.value = 'session-picker'
  }
}

// --- Session selected from picker → navigate to school login ---
async function onSessionSelected(sessionId) {
  auth.sessionUUID = sessionId
  // The selected ID is now the active business session; stop using the
  // temporary system-auth context for subsequent API calls.
  auth.authSessionUUID = sessionId
  auth.loginInProgress = true
  sessionData.value = {}
  viewMode.value = 'school-login'
  await replaceSessionUrl(sessionId)
  setTimeout(loadInlineSessions, 300)
}

// --- School login success → go to main app ---
async function onSchoolLoginSuccess(data) {
  app.isLoading = false
  const sessionId = getActiveSessionId()
  if (!sessionId) return
  await router.push({ name: 'main', params: { uuid: sessionId } })
}

// --- Multi-account entry ---
async function onEnterMulti() {
  const sessionId = getActiveSessionId()
  if (!sessionId) return
  await router.push({ name: 'multi', params: { uuid: sessionId } })
}

// --- Back to system login ---
function onBackToAuth() {
  viewMode.value = 'auth'
}

async function openHelp() {
  await Swal.fire({
    title: '新手帮助',
    html: `
      <div class="text-left text-sm leading-6 text-slate-600">
        <p>登录或注册后，您可以选择会话并进入跑步控制台。</p>
        <p class="mt-2">游客模式需要保存页面地址，才能恢复当前状态。</p>
      </div>
    `,
    confirmButtonText: '我知道了',
    customClass: {
      confirmButton: 'btn btn-primary',
    },
  })
}

// --- Import users from offline file ---
function onImportUsers() {
  if (importFileInput.value) {
    importFileInput.value.click()
  }
}

async function handleImportFile(event) {
  const file = event.target.files?.[0]
  if (!file) return

  try {
    const data = await callAPI('import_task_data', await file.text())
    if (data.success) {
      app.tasks = data.tasks || []
      app.selectedTaskIndex = app.tasks.length ? 0 : -1
      auth.setLoginResult({ ...data, ...(data.userInfo || {}), session_id: auth.sessionUUID })
      onSchoolLoginSuccess(data)
    } else {
      await Swal.fire({
        icon: 'error',
        title: '导入失败',
        text: data.message || '导入离线任务失败',
      })
    }
  } catch (e) {
    await Swal.fire({
      icon: 'error',
      title: '导入失败',
      text: e.message || '导入过程中出现错误',
    })
  }

  if (importFileInput.value) {
    importFileInput.value.value = ''
  }
}

function formatSessionDate(timestamp) {
  if (!timestamp) return '未知'
  const d = new Date(typeof timestamp === 'number' && timestamp < 1e12 ? timestamp * 1000 : timestamp)
  if (isNaN(d.getTime())) return '未知'
  const Y = d.getFullYear()
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${Y}-${M}-${D} ${h}:${m}`
}

// --- Lifecycle ---
onMounted(async () => {
  callRawAPI('/api/frontend-config', 'GET').then(data => { frontendConfig.value = data }).catch(() => {})

  if (props.uuid) {
    await checkUUID(props.uuid)
    app.isLoading = false
    return
  }

  if (auth.isAuthenticated && auth.sessionUUID) {
    await router.replace({ name: 'main', params: { uuid: auth.sessionUUID } })
    return
  }

  viewMode.value = 'auth'
  app.isLoading = false
})
</script>

<template>
  <div class="flex min-h-screen flex-col">

    <!-- ============ Loading ============ -->
    <div v-if="viewMode === 'loading'" class="flex flex-1 items-center justify-center">
      <div class="text-center">
        <div class="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-sky-200 border-t-sky-500"></div>
        <p class="text-sm" style="color: var(--ink-muted)">正在验证会话...</p>
      </div>
    </div>

    <!-- ============ Phase 1: System Login ============ -->
    <div
      v-else-if="viewMode === 'auth'"
      id="auth-login-container"
      class="flex h-screen w-screen items-center justify-center p-0 md:p-4"
    >
      <button
        v-if="frontendConfig.show_newbie_help || app.isMobile"
        id="newbie-help-btn"
        type="button"
        class="btn btn-ghost fixed z-10 !px-4 !py-2"
        style="
          top: 100px;
          right: 1rem;
          min-height: 48px;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          background: rgba(255, 255, 255, 0.8);
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
        "
        @click="openHelp"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        帮助
      </button>
      <div
        id="auth-login-container_panel"
        class="panel w-full max-w-[600px] space-y-6 rounded-2xl p-6"
        style="
          background: rgba(255, 255, 255, 0.52);
          border: 1px solid rgba(255, 255, 255, 0.24);
          box-shadow: 0 20px 60px rgba(15, 23, 42, 0.12);
        "
      >
        <div class="text-center">
          <h2 class="card-title mb-2 text-3xl font-bold text-sky-700">
            {{ app.isMobile ? '欢迎使用跑步助手' : '跑步助手' }}
          </h2>
          <p class="text-sm text-slate-500">请登录或注册以继续使用</p>
        </div>
        <AuthPanel :frontend-config="frontendConfig" @login-success="onAuthSuccess" />
        <div
          id="auth-beian-footer"
          class="mt-6 flex flex-col items-center justify-center gap-2 border-t border-slate-200 pt-4 text-xs text-slate-400"
        >
          <BeianFooter />
        </div>
      </div>
    </div>

    <!-- ============ Phase 2: Session Picker (modal-style overlay) ============ -->
    <div v-else-if="viewMode === 'session-picker'" class="flex flex-1 items-center justify-center p-4 md:p-8">
      <div class="w-full max-w-2xl">
        <div class="panel rounded-2xl p-6 md:p-8">
          <div class="mb-6 text-center space-y-1">
            <h1 class="text-2xl font-bold" style="color: var(--ink)">
              <svg class="mb-1 mr-2 inline-block h-7 w-7" style="color: var(--accent)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              会话管理
            </h1>
            <p class="text-sm" style="color: var(--ink-secondary)">选择或创建会话以继续</p>
          </div>
          <SessionPicker
            @session-selected="onSessionSelected"
            @back="onBackToAuth"
          />
        </div>
      </div>
    </div>

    <!-- ============ Phase 3: School Login (3-column grid matching original) ============ -->
    <div v-else-if="viewMode === 'school-login'" class="flex-1">
      <div class="min-h-screen w-full grid grid-cols-1 gap-4 p-4 lg:h-screen lg:grid-cols-3 lg:gap-0 lg:p-0">

<div
          class="school-multi-column order-2 lg:order-1 flex flex-col items-center justify-center p-8 lg:p-12 bg-gradient-to-br from-purple-50 via-violet-50 to-purple-100 relative overflow-hidden"
        >
          <div
            class="absolute top-0 right-0 w-64 h-64 bg-violet-200 rounded-full opacity-20 blur-3xl -translate-y-1/2 translate-x-1/2"
          ></div>
          <div
            class="absolute bottom-0 left-0 w-48 h-48 bg-purple-300 rounded-full opacity-20 blur-2xl translate-y-1/2 -translate-x-1/2"
          ></div>

          <div
            class="relative text-center w-full max-w-sm space-y-7 panel rounded-3xl p-10 bg-white/60 backdrop-blur-xl shadow-2xl border border-white/50 hover:shadow-violet-200/50 transition-all duration-500 hover:scale-[1.02] overflow-auto"
          >
            <div class="relative inline-block">
              <div
                class="absolute inset-0 bg-violet-400 rounded-full blur-2xl opacity-30 animate-pulse"
              ></div>

              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="relative w-20 h-20 mx-auto text-violet-600 drop-shadow-lg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path
                  d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05c1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"
                ></path>
              </svg>
            </div>

            <h2
              class="text-3xl lg:text-4xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent card-title leading-tight"
            >
              掌上莲峰<br />多账号模式
            </h2>

            <div class="space-y-3">
              <p class="text-slate-600 text-base leading-relaxed">
                ✨ 支持批量导入账号<br />
                🎯 统一管理所有任务<br />
                ⚡ 一键执行全部流程
              </p>
            </div>

            <button
              id="multi-account-btn" @click="onEnterMulti"
              class="btn btn-secondary w-full py-3.5 text-lg font-bold shadow-xl shadow-violet-300/40 hover:shadow-2xl hover:shadow-violet-400/50 transition-all duration-300"
              title="多账号"
              aria-label="多账号"
            >
              <span>进入多账号控制台</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="w-5 h-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                ></path>
              </svg>
            </button>
          </div>
        </div>

        <div
          class="school-single-column order-1 lg:order-2 flex items-center justify-center p-6 lg:p-8 bg-gradient-to-br from-white via-sky-50/30 to-cyan-50/40 relative overflow-hidden"
        >
          <div
            class="absolute top-0 right-0 w-64 h-64 bg-sky-300 rounded-full opacity-10 blur-3xl translate-x-1/3 -translate-y-1/3"
          ></div>
          <div
            class="absolute bottom-0 left-0 w-48 h-48 bg-cyan-200 rounded-full opacity-15 blur-2xl -translate-x-1/4 translate-y-1/4"
          ></div>

          <div
            class="relative panel rounded-3xl w-full max-w-md p-10 space-y-4 shadow-2xl border border-white/60 hover:shadow-sky-200/40 transition-all duration-300 overflow-y-auto max-h-full"
            id="desktop-container-single-login-panel-wrapper"
          >
            <div class="flex items-center justify-center gap-3 pb-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="w-8 h-8 text-sky-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                ></path>
              </svg>
              <h2
                class="text-3xl font-bold text-sky-700 lg:text-4xl card-title"
              >
                单账号登录
              </h2>
            </div>

            <div class="text-center">
              <p class="text-slate-500 text-sm">掌上莲峰跑步助手</p>
            </div>

            <SessionLogin :initial-data="sessionData" @login-success="onSchoolLoginSuccess" @import-users="onImportUsers" />
</div>
</div>
        <!-- Column 3: Session management -->
        <div class="relative order-3 flex flex-col items-center justify-center overflow-hidden rounded-2xl bg-gradient-to-br from-sky-50 via-white to-cyan-50 p-6 md:p-10 lg:rounded-none lg:p-12">
          <div class="relative w-full max-w-2xl">
            <div class="panel flex max-h-[calc(100vh-12rem)] flex-col space-y-5 overflow-x-hidden rounded-3xl p-8 border border-white/60 bg-white/80 shadow-2xl">
              <div class="flex items-center justify-center gap-2 border-b border-sky-100 pb-2">
                <svg class="h-6 w-6 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                <h3 class="text-2xl font-bold text-sky-700">会话管理</h3>
              </div>

              <div class="flex items-center justify-between gap-4 rounded-xl bg-gradient-to-r from-sky-50 to-transparent p-4">
                <h4 class="text-lg font-bold text-slate-700">会话列表</h4>
                <div class="flex items-center gap-4">
                <label
                  v-if="hasGodModePermission"
                  class="flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-colors"
                  :class="godModeEnabled ? 'bg-red-100' : 'bg-red-50 hover:bg-red-100'"
                >
                  <input
                    type="checkbox"
                    :checked="godModeEnabled"
                    class="h-4 w-4 cursor-pointer rounded accent-red-600"
                    @change="toggleGodMode"
                  />
                  <span class="font-bold text-red-600">⚠️ 上帝模式</span>
                </label>

                <span class="rounded-full border px-3 py-1.5 text-sm font-medium" style="border-color: var(--border-color); color: var(--ink-secondary)">
                  会话数: {{ inlineSessions.length }}
                </span>

                <button
                  class="btn btn-ghost !px-3 !py-1.5"
                  :disabled="inlineSessionsLoading"
                  @click="loadInlineSessions"
                  title="刷新会话列表"
                >
                  <svg class="h-4 w-4" :class="{ 'animate-spin': inlineSessionsLoading }" style="color: var(--ink-secondary)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  刷新
                </button>
                </div>
              </div>

              <div class="max-h-[50vh] overflow-y-auto space-y-2 pr-1">
                <div v-if="inlineSessionsLoading" class="py-8 text-center">
                  <div class="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-3 border-sky-200 border-t-sky-500"></div>
                  <p class="text-xs" style="color: var(--ink-muted)">正在加载会话数据...</p>
                </div>
                <div v-else-if="inlineSessions.length === 0" class="py-8 text-center text-sm" style="color: var(--ink-muted)">
                  暂无会话
                </div>
                <div
                  v-else
                  v-for="session in inlineSessions"
                  :key="session.session_id || session.id"
                  class="rounded-xl p-3 border transition-colors"
                  :class="session.is_current ? 'border-sky-300 bg-sky-50/50' : ''"
                  :style="session.is_current ? '' : 'border-color: var(--border-color)'"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="min-w-0 flex-1">
                      <div class="text-sm font-medium truncate" style="color: var(--ink)">
                        {{ sessionDisplayName(session) }}
                        <span v-if="isCurrentInlineSession(session)" class="ml-1 text-xs text-sky-600 font-semibold">(当前)</span>
                      </div>
                      <div class="text-xs mt-0.5" style="color: var(--ink-muted)">
                        {{ formatSessionDate(session.created_at || session.login_time) }}
                        <span v-if="session.ip"> | {{ session.ip }}</span>
                      </div>
                    </div>
                    <div class="flex shrink-0 items-center gap-2">
                      <template v-if="!isCurrentInlineSession(session)">
                        <button
                          class="btn btn-ghost !px-2 !py-1 text-xs"
                          @click="selectInlineSession(session)"
                        >
                          进入
                        </button>
                        <button
                          class="btn btn-ghost !px-2 !py-1 text-xs !text-red-600"
                          @click="deleteInlineSession(session)"
                        >
                          删除
                        </button>
                      </template>
                      <span
                        class="h-2 w-2 rounded-full"
                        :class="session.active !== false ? 'bg-green-500' : 'bg-gray-400'"
                      ></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- ============ Error ============ -->
    <div v-else-if="viewMode === 'error'" class="flex flex-1 items-center justify-center p-4">
      <div class="panel mx-auto max-w-md rounded-2xl p-8 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
          <svg class="h-7 w-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 class="mb-2 text-lg font-semibold text-red-600">验证失败</h2>
        <p class="mb-4 text-sm" style="color: var(--ink-secondary)">{{ errorMsg || '会话验证失败，请重试' }}</p>
        <button class="btn btn-primary" @click="viewMode = 'auth'">返回登录</button>
      </div>
    </div>

    <input
      ref="importFileInput"
      type="file"
      accept=".json"
      class="hidden"
      @change="handleImportFile"
    />

  </div>
</template>

<style scoped>
@media (max-width: 767px) {
  :global(body.mobile-mode #auth-login-container) { padding-top: 56px; }
  :global(body.mobile-mode #auth-login-container_panel) { border-radius: 16px; }
  :global(body.mobile-mode #auth-login-container_panel h2) {
    color: #0f172a;
    font-family: "Noto Sans SC", sans-serif;
    line-height: 36px;
  }
}
</style>
