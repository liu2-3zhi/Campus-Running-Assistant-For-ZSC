<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const sessions = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
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
    const url = godMode.value ? '/auth/admin/all_sessions' : '/auth/user/sessions'
    const res = await callRawAPI(url, 'GET')
    sessions.value = res.sessions || []
  } catch (e) {
    error.value = e.message || '加载会话列表失败'
  } finally {
    loading.value = false
  }
}

function toggleGodMode() {
  loadSessions()
}

async function kickSession(session) {
  if (session.is_current) {
    error.value = '不能操作当前会话'
    return
  }
  if (!confirm(godMode.value ? '确定要强制销毁该会话吗？' : '确定要删除该会话吗？')) return
  clearMessages()
  try {
    // 上帝模式使用管理员销毁接口，否则删除自己的会话
    if (godMode.value) {
      await callRawAPI('/auth/admin/destroy_session', 'POST', { session_id: session.session_id })
    } else {
      await callRawAPI('/auth/user/delete_session', 'POST', { session_id: session.session_id })
    }
    success.value = godMode.value ? '已销毁该会话' : '已删除该会话'
    await loadSessions()
  } catch (e) {
    error.value = e.message || '操作失败'
  }
}

onMounted(loadSessions)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-3">
      <h4 class="font-semibold">会话列表</h4>
      <div class="flex items-center gap-3">
        <label class="flex cursor-pointer items-center gap-2">
          <input v-model="godMode" type="checkbox" class="h-4 w-4 rounded accent-red-600" @change="toggleGodMode" />
          <span class="text-sm font-semibold text-red-600">查看所有会话</span>
        </label>
        <span class="text-sm text-slate-600">{{ validSessions.length }}</span>
        <button class="btn btn-ghost !px-2 !py-1" :disabled="loading" @click="loadSessions">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&times;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&times;</button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <div v-else id="admin-sessions-list_modal" class="max-h-[50vh] space-y-2 overflow-y-auto">
      <p v-if="validSessions.length === 0" class="py-10 text-center text-slate-400">
        暂无活跃会话
      </p>
      <div
        v-for="session in validSessions"
        :key="session.session_id"
        class="rounded-lg border p-3"
        :class="session.is_current ? 'border-sky-300 bg-sky-50/60' : 'border-slate-200 bg-white'"
      >
        <div class="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div class="min-w-0 flex-1">
            <p class="flex flex-wrap items-center gap-2 font-semibold text-slate-800">
              {{ sessionUser(session) }}
              <span v-if="session.is_current" class="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">当前</span>
              <span v-if="session.is_multi_account_mode" class="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">多账号</span>
            </p>
            <p class="mt-1 break-all font-mono text-xs text-slate-500">
              {{ session.session_hash || session.session_id }}
            </p>
            <p class="mt-1 text-xs text-slate-500">创建时间: {{ formatDate(session.created_at) }}</p>
            <p v-if="godMode" class="mt-1 text-xs text-slate-500">权限组: {{ session.auth_group || '--' }}</p>
            <p class="mt-1 text-xs" :class="session.login_success ? 'text-green-600' : 'text-slate-400'">
              状态: {{ session.login_success ? '已登录' : '未登录' }}
            </p>
          </div>
          <button
            class="btn btn-danger !px-3 !py-1 text-xs"
            :disabled="session.is_current"
            @click="kickSession(session)"
          >
            {{ godMode ? '销毁会话' : '删除会话' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
