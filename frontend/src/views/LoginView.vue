<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import AuthPanel from '@/components/login/AuthPanel.vue'
import SessionPicker from '@/components/login/SessionPicker.vue'
import SessionLogin from '@/components/login/SessionLogin.vue'
import BeianFooter from '@/components/common/BeianFooter.vue'
import AppModal from '@/components/common/AppModal.vue'
import Swal from 'sweetalert2'

const props = defineProps({
  uuid: { type: String, default: '' },
})

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const importFileInput = ref(null)

// 'loading' | 'auth' | 'session-picker' | 'school-login' | 'error'
const viewMode = ref('loading')
const errorMsg = ref('')
const sessionData = ref({})

// --- Inline session management (school-login right column) ---
const inlineSessions = ref([])
const inlineSessionsLoading = ref(false)
const godModeEnabled = ref(false)
const hasGodModePermission = ref(false)

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

// --- UUID validation ---
async function checkUUID(uuid) {
  viewMode.value = 'loading'
  errorMsg.value = ''
  try {
    const data = await callRawAPI('/auth/check_uuid_type', 'POST', { uuid })
    if (data.type === 'session' || data.valid) {
      auth.sessionUUID = uuid
      auth.loginInProgress = true
      sessionData.value = data
      viewMode.value = 'school-login'
    } else {
      viewMode.value = 'auth'
    }
  } catch (e) {
    console.warn('UUID验证失败:', e)
    viewMode.value = 'auth'
  }
}

// --- System login success → show session picker ---
function onAuthSuccess(data) {
  if (data.is_guest) {
    viewMode.value = 'school-login'
    setTimeout(loadInlineSessions, 300)
  } else {
    viewMode.value = 'session-picker'
  }
}

// --- Session selected from picker → navigate to school login ---
function onSessionSelected(sessionId) {
  auth.sessionUUID = sessionId
  auth.loginInProgress = true
  sessionData.value = {}
  viewMode.value = 'school-login'
  setTimeout(loadInlineSessions, 300)
}

// --- School login success → go to main app ---
function onSchoolLoginSuccess(data) {
  app.isLoading = false
  router.push('/app')
}

// --- Multi-account entry ---
function onEnterMulti() {
  router.push('/multi')
}

// --- Back to system login ---
function onBackToAuth() {
  viewMode.value = 'auth'
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

  const formData = new FormData()
  formData.append('file', file)

  try {
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = {}
    if (sessionId) headers['X-Session-ID'] = sessionId

    const response = await fetch('/auth/import_users', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
    })

    const data = await response.json()

    if (response.ok && data.success !== false) {
      await Swal.fire({
        icon: 'success',
        title: '导入成功',
        text: data.message || '用户数据已成功导入',
      })
      window.location.reload()
    } else {
      await Swal.fire({
        icon: 'error',
        title: '导入失败',
        text: data.message || '导入用户数据失败',
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
  if (auth.isAuthenticated) {
    router.push('/app')
    return
  }

  if (props.uuid) {
    await checkUUID(props.uuid)
  } else {
    viewMode.value = 'auth'
  }

  app.isLoading = false
})
</script>

<template>
  <div class="flex min-h-screen flex-col" style="background: var(--base-color)">

    <!-- ============ Loading ============ -->
    <div v-if="viewMode === 'loading'" class="flex flex-1 items-center justify-center">
      <div class="text-center">
        <div class="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-sky-200 border-t-sky-500"></div>
        <p class="text-sm" style="color: var(--ink-muted)">正在验证会话...</p>
      </div>
    </div>

    <!-- ============ Phase 1: System Login ============ -->
    <div v-else-if="viewMode === 'auth'" class="flex flex-1 items-center justify-center p-4 md:p-8">
      <div class="w-full max-w-[600px]">
        <div class="panel rounded-2xl p-6 space-y-6">
          <div class="text-center space-y-1">
            <h1 class="text-2xl font-bold" style="color: var(--ink)">
              <svg class="mb-1 mr-2 inline-block h-7 w-7" style="color: var(--accent)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              跑步助手
            </h1>
            <p class="text-sm" style="color: var(--ink-secondary)">请登录或注册以继续使用</p>
          </div>
          <AuthPanel @login-success="onAuthSuccess" />
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
      <div class="h-screen w-full grid grid-cols-1 lg:grid-cols-3">

        <!-- Column 1: Multi-account entry (purple gradient) -->
        <div class="relative flex items-center justify-center overflow-hidden p-4 lg:p-8"
             style="background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 50%, #c4b5fd 100%)">
          <div class="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-white/10 blur-2xl"></div>
          <div class="absolute -bottom-16 -right-16 h-48 w-48 rounded-full bg-white/10 blur-xl"></div>

          <div class="relative z-10 w-full max-w-sm">
            <div class="rounded-3xl bg-white/60 backdrop-blur-xl shadow-2xl p-6 lg:p-8 space-y-5">
              <div class="flex justify-center">
                <svg class="h-16 w-16 drop-shadow-lg" fill="none" viewBox="0 0 64 64">
                  <circle cx="22" cy="22" r="8" fill="#7c3aed" opacity="0.8"/>
                  <circle cx="42" cy="22" r="8" fill="#a78bfa" opacity="0.8"/>
                  <circle cx="32" cy="42" r="8" fill="#c4b5fd" opacity="0.8"/>
                  <path d="M14 38c0-5 4-8 8-8s8 3 8 8" stroke="#7c3aed" stroke-width="2" fill="none" stroke-linecap="round"/>
                  <path d="M34 38c0-5 4-8 8-8s8 3 8 8" stroke="#a78bfa" stroke-width="2" fill="none" stroke-linecap="round"/>
                  <path d="M24 54c0-5 4-8 8-8s8 3 8 8" stroke="#c4b5fd" stroke-width="2" fill="none" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="text-center space-y-1.5">
                <h2 class="text-xl font-bold text-violet-900 tracking-tight">掌上莲峰</h2>
                <p class="text-sm text-violet-700 font-medium">多账号模式</p>
              </div>

              <div class="space-y-3">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-violet-50/80">
                  <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600 text-white shadow-lg shadow-violet-200">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-violet-900">支持批量导入账号</p>
                    <p class="text-xs text-violet-600">支持 Excel / CSV 格式文件</p>
                  </div>
                </div>
                <div class="flex items-center gap-3 p-3 rounded-xl bg-violet-50/80">
                  <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600 text-white shadow-lg shadow-violet-200">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-violet-900">统一管理所有任务</p>
                    <p class="text-xs text-violet-600">为每个账号独立配置</p>
                  </div>
                </div>
                <div class="flex items-center gap-3 p-3 rounded-xl bg-violet-50/80">
                  <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-600 text-white shadow-lg shadow-violet-200">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-violet-900">一键执行全部流程</p>
                    <p class="text-xs text-violet-600">实时状态看板监控</p>
                  </div>
                </div>
              </div>

              <button
                class="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-violet-600 text-white font-semibold shadow-lg shadow-violet-300/50 hover:bg-violet-700 hover:shadow-violet-400/50 transition-all duration-300 active:scale-[0.98]"
                @click="onEnterMulti"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
                进入多账号控制台
              </button>
            </div>
          </div>
        </div>

        <!-- Column 2: Single account login (sky gradient) -->
        <div class="relative flex items-center justify-center overflow-hidden p-4 lg:p-8"
             style="background: linear-gradient(135deg, #0ea5e9 0%, #38bdf8 50%, #7dd3fc 100%)">
          <div class="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-white/15 blur-2xl"></div>
          <div class="absolute -bottom-12 -left-12 h-40 w-40 rounded-full bg-white/15 blur-xl"></div>

          <div class="relative z-10 w-full max-w-md">
            <div class="rounded-3xl bg-white/80 backdrop-blur-xl shadow-2xl p-6 lg:p-8 space-y-5">
              <div class="text-center space-y-3">
                <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-lg shadow-sky-200/60">
                  <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <div>
                  <h2 class="text-xl font-bold text-slate-800 tracking-tight">单账号登录</h2>
                  <p class="text-sm text-sky-600 font-medium">掌上莲峰跑步助手</p>
                </div>
              </div>

              <SessionLogin
                :initial-data="sessionData"
                @login-success="onSchoolLoginSuccess"
                @import-users="onImportUsers"
              />
            </div>
          </div>
        </div>

        <!-- Column 3: Session management -->
        <div class="flex items-start justify-center overflow-y-auto p-4 lg:p-8" style="background: var(--base-color)">
          <div class="w-full max-w-sm">
            <div class="panel rounded-3xl p-5 lg:p-6 space-y-4 shadow-xl">
              <div class="flex items-center gap-3 pb-3 border-b" style="border-color: var(--border-color)">
                <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600">
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-base font-bold" style="color: var(--ink)">会话管理</h3>
                  <p class="text-xs" style="color: var(--ink-muted)">管理您的登录会话</p>
                </div>
              </div>

              <div class="flex items-center justify-between">
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
                  class="flex h-8 w-8 items-center justify-center rounded-lg border transition-colors hover:bg-gray-50"
                  style="border-color: var(--border-color)"
                  :disabled="inlineSessionsLoading"
                  @click="loadInlineSessions"
                  title="刷新会话列表"
                >
                  <svg class="h-4 w-4" :class="{ 'animate-spin': inlineSessionsLoading }" style="color: var(--ink-secondary)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
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
                        {{ session.username || session.user || '未知用户' }}
                        <span v-if="session.is_current" class="ml-1 text-xs text-sky-600 font-semibold">(当前)</span>
                      </div>
                      <div class="text-xs mt-0.5" style="color: var(--ink-muted)">
                        {{ formatSessionDate(session.created_at || session.login_time) }}
                        <span v-if="session.ip"> | {{ session.ip }}</span>
                      </div>
                    </div>
                    <div class="h-2 w-2 shrink-0 rounded-full" :class="session.active !== false ? 'bg-green-500' : 'bg-gray-400'"></div>
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
      accept=".json,.csv,.xlsx,.xls"
      class="hidden"
      @change="handleImportFile"
    />

    <BeianFooter v-if="viewMode !== 'school-login'" />
  </div>
</template>
