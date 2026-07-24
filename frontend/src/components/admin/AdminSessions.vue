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
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-[var(--ink)]">会话管理</h2>
      <div class="flex items-center gap-3">
        <span class="text-sm text-[var(--ink-secondary)]">
          {{ godMode ? '系统会话数' : '当前会话数' }}: <strong class="text-[var(--ink)]">{{ validSessions.length }}</strong>
        </span>
        <label class="flex items-center gap-2 text-sm text-[var(--ink-secondary)] cursor-pointer">
          <input type="checkbox" v-model="godMode" class="rounded" @change="toggleGodMode" />
          上帝模式
        </label>
        <button class="btn btn-secondary text-sm" :disabled="loading" @click="loadSessions">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Search -->
    <input
      v-model="searchQuery"
      type="text"
      class="input-field w-full"
      placeholder="搜索用户名、会话 ID 或权限组..."
    />

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&times;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&times;</button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <div v-else class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">用户</th>
            <th v-if="godMode" class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">权限组</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">会话标识</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">创建时间</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">状态</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredSessions.length === 0">
            <td :colspan="godMode ? 6 : 5" class="px-3 py-6 text-center text-[var(--ink-secondary)]">
              {{ searchQuery ? '未找到匹配的会话' : '暂无活跃会话' }}
            </td>
          </tr>
          <tr
            v-for="session in filteredSessions"
            :key="session.session_id"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
            :class="session.is_current ? 'bg-[var(--accent)]/5' : ''"
          >
            <td class="px-3 py-2 font-mono whitespace-nowrap">{{ sessionUser(session) }}</td>
            <td v-if="godMode" class="px-3 py-2 whitespace-nowrap">{{ session.auth_group || '--' }}</td>
            <td class="px-3 py-2 font-mono text-xs">{{ session.session_hash || String(session.session_id).slice(0, 16) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(session.created_at) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <span v-if="session.is_current" class="px-2 py-0.5 rounded-full text-xs bg-[var(--accent)]/15 text-[var(--accent)] mr-1">当前</span>
              <span v-if="session.login_success" class="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">已登录</span>
              <span v-else class="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">未登录</span>
              <span v-if="session.is_multi_account_mode" class="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700 ml-1">多账号</span>
            </td>
            <td class="px-3 py-2">
              <button
                class="btn btn-danger text-xs px-2 py-1"
                :disabled="session.is_current"
                @click="kickSession(session)"
              >{{ godMode ? '销毁' : '删除' }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
