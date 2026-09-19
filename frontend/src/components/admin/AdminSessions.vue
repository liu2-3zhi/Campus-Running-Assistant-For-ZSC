<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canViewAllSessions = computed(() => !!auth.permissions?.view_all_sessions)
const canDestroySessions = computed(() => !!auth.permissions?.manage_user_sessions)

const sessions = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const creating = ref(false)
const switching = ref(false)
const maxSessions = ref(-1)
const godMode = ref(false)
const searchQuery = ref('')

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(val) {
  if (val === null || val === undefined || val === '' || val === 0) return '--'
  let ms = val
  if (typeof val === 'number') ms = val < 1e12 ? val * 1000 : val
  const d = new Date(ms)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

function sessionUser(s) {
  return s.auth_username || s.username || s.user_data?.username || s.user_info?.username || '--'
}

function isCurrentSession(session) {
  return session.is_current || session.session_id === auth.sessionUUID
}

const sessionCountClass = computed(() => {
  if (godMode.value) return 'text-purple-600'
  if (auth.isGuest) return 'text-blue-600'
  if (maxSessions.value === -1) return 'text-green-600'
  if (validSessions.value.length >= maxSessions.value) return 'text-red-600'
  return validSessions.value.length >= maxSessions.value * 0.8 ? 'text-amber-600' : 'text-slate-600'
})

const validSessions = computed(() =>
  sessions.value.filter(s => s.session_id && String(s.session_id).trim() !== '' && String(s.session_id) !== 'null')
)

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return validSessions.value
  const q = searchQuery.value.trim().toLowerCase()
  return validSessions.value.filter(s =>
    sessionUser(s).toLowerCase().includes(q) ||
    (s.session_id || '').toLowerCase().includes(q) ||
    (s.session_hash || '').toLowerCase().includes(q) ||
    (s.auth_group || '').toLowerCase().includes(q)
  )
})

async function loadSessions() {
  loading.value = true
  clearMessages()
  try {
    // 上帝模式：查看系统全部会话；否则仅查看当前用户会话
    const url = godMode.value && canViewAllSessions.value ? '/auth/admin/all_sessions' : '/auth/user/sessions'
    const res = await callRawAPI(url, 'GET')
    if (res.success === false) throw new Error(res.message || '加载会话列表失败')
    sessions.value = res.sessions || []
    maxSessions.value = res.max_sessions ?? -1
  } catch (e) {
    error.value = e.message || '加载会话列表失败'
  } finally {
    loading.value = false
  }
}

async function selectSession(sessionId) {
  if (switching.value) return
  switching.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/auth/switch_session', 'POST', { target_session_id: sessionId })
    if (res.success === false) throw new Error(res.message || '切换会话失败')
    window.location.assign(`/uuid=${encodeURIComponent(sessionId)}`)
  } catch (e) {
    error.value = e.message || '切换会话失败'
  } finally {
    switching.value = false
  }
}

async function createSession() {
  if (creating.value || auth.isGuest) return
  clearMessages()
  const atLimit = maxSessions.value !== -1 && validSessions.value.length >= maxSessions.value
  let oldestSession = null
  if (atLimit) {
    oldestSession = [...validSessions.value].filter(session => !isCurrentSession(session))
      .sort((a, b) => (a.created_at || 0) - (b.created_at || 0))[0]
    if (!oldestSession) {
      error.value = '会话数量已达上限，请先删除其他会话或联系管理员调整限制'
      return
    }
    if (!confirm(`会话数量已达上限（${maxSessions.value}个），是否删除最早的会话并创建新会话？`)) return
  } else if (!confirm('您确定要创建一个新的会话吗？')) return
  creating.value = true
  try {
    if (oldestSession) {
      const deleted = await callRawAPI('/auth/user/delete_session', 'POST', { session_id: oldestSession.session_id })
      if (deleted.success === false) throw new Error(deleted.message || '删除旧会话失败')
    }
    const sessionId = crypto.randomUUID()
    const res = await callRawAPI('/auth/user/create_session_persistence', 'POST', { session_id: sessionId })
    if (res.success === false) throw new Error(res.message || '创建会话失败')
    window.location.assign(`/uuid=${encodeURIComponent(res.session_id || sessionId)}`)
  } catch (e) {
    error.value = e.message || '创建会话失败'
  } finally {
    creating.value = false
  }
}

function toggleGodMode() {
  loadSessions()
}

async function kickSession(session) {
  if (isCurrentSession(session)) {
    error.value = '不能操作当前会话'
    return
  }
  if (!confirm(godMode.value ? '确定要强制销毁该会话吗？' : '确定要删除该会话吗？')) return
  clearMessages()
  try {
    // 上帝模式使用管理员销毁接口，否则删除自己的会话
    if (godMode.value && canViewAllSessions.value) {
      await callRawAPI('/auth/admin/destroy_session', 'POST', { session_id: session.session_id })
    } else {
      await callRawAPI('/auth/user/delete_session', 'POST', { session_id: session.session_id })
    }
    await loadSessions()
    success.value = godMode.value ? '已销毁该会话' : '已删除该会话'
  } catch (e) {
    error.value = e.message || '操作失败'
  }
}

onMounted(loadSessions)
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h4 class="font-semibold">会话列表</h4>
      <div class="flex items-center gap-3">
        <label v-if="canViewAllSessions" class="flex cursor-pointer items-center gap-2">
          <input v-model="godMode" type="checkbox" class="h-4 w-4 rounded accent-red-600" @change="toggleGodMode" />
          <span class="text-sm font-semibold text-red-600">查看所有会话</span>
        </label>
        <span v-if="!loading && !error" class="text-sm" :class="sessionCountClass">
          <template v-if="godMode">系统总会话数: {{ validSessions.length }}</template>
          <template v-else-if="auth.isGuest">会话数: 1 / 游客仅限单会话</template>
          <template v-else>会话数: {{ validSessions.length }} / {{ maxSessions === -1 ? '无限制' : maxSessions }}</template>
        </span>
        <button class="btn btn-ghost !px-2 !py-1" :disabled="loading" @click="loadSessions">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&times;</button>
    </div>
    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>
    <p v-else-if="error" class="py-10 text-center text-red-500">{{ error }}</p>

    <div v-else id="admin-sessions-list_modal" class="space-y-2 md:max-h-[50vh] md:overflow-y-auto">
      <div v-if="!godMode && !auth.isGuest" class="mb-4 rounded-lg border border-sky-200 bg-sky-50 p-3">
        <p class="mb-2 text-sm text-slate-700">选择现有会话或创建新会话</p>
        <button class="btn btn-primary w-full" :disabled="creating" @click="createSession">{{ creating ? '创建中...' : '创建新会话' }}</button>
      </div>
      <div v-else-if="!godMode" class="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3">
        <p class="text-sm text-blue-700">游客模式：当前会话如下。如需使用多个会话，请注册账号。</p>
      </div>
      <p v-if="validSessions.length === 0" class="py-10 text-center text-slate-400">
        暂无会话
      </p>
      <div
        v-for="session in validSessions"
        :key="session.session_id"
        class="mb-2 rounded-lg border p-3"
        :class="isCurrentSession(session) ? 'border-sky-500 bg-sky-50' : 'border-slate-200'"
      >
        <div class="flex flex-col items-start justify-between gap-2 sm:flex-row">
          <div class="min-w-0 flex-1">
            <p class="break-all font-semibold text-slate-800">会话 {{ session.session_id }}</p>
            <p v-if="isCurrentSession(session)" class="text-right"><span class="ml-2 text-xs text-sky-600">(当前会话)</span></p>
            <p class="text-xs text-slate-500">创建时间: {{ formatDate(session.created_at) }}</p>
            <p class="text-xs text-slate-500">
              状态: <span :class="session.login_success ? 'font-semibold text-green-600' : ''">{{ session.login_success ? '已登录' : '未登录' }}</span>
            </p>
            <p v-if="godMode" class="text-xs text-slate-500">创建者: {{ sessionUser(session) === '--' ? '游客模式' : sessionUser(session) }}</p>
          </div>
          <div v-if="!isCurrentSession(session)" class="flex shrink-0 gap-2">
            <button class="btn btn-ghost !px-2 !py-1 text-xs" :disabled="switching" @click="selectSession(session.session_id)">选择</button>
            <button v-if="!godMode" class="btn btn-ghost !px-2 !py-1 !text-red-600 text-xs" @click="kickSession(session)">删除</button>
            <button v-else-if="canDestroySessions" class="btn btn-danger !px-2 !py-1 text-xs" @click="kickSession(session)">销毁</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
