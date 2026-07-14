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

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return sessions.value
  const q = searchQuery.value.trim().toLowerCase()
  return sessions.value.filter(s =>
    (s.username || '').toLowerCase().includes(q) ||
    (s.user_id || '').toLowerCase().includes(q) ||
    (s.ip || '').toLowerCase().includes(q) ||
    (s.session_id || '').toLowerCase().includes(q)
  )
})

async function loadSessions() {
  loading.value = true
  clearMessages()
  try {
    const params = godMode.value ? '?god_mode=true' : ''
    const res = await callRawAPI(`/auth/admin/all_sessions${params}`, 'GET')
    sessions.value = res.sessions || []
  } catch (e) {
    error.value = e.message || '加载会话列表失败'
  } finally {
    loading.value = false
  }
}

async function toggleGodMode() {
  await loadSessions()
}

async function kickSession(sessionId) {
  if (!confirm('确定要踢出该会话吗？')) return
  clearMessages()
  try {
    await callRawAPI('/auth/admin/destroy_session', 'POST', { session_id: sessionId })
    success.value = '已踢出该会话'
    await loadSessions()
  } catch (e) {
    error.value = e.message || '踢出会话失败'
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
          当前会话数: <strong class="text-[var(--ink)]">{{ sessions.length }}</strong>
        </span>
        <label class="flex items-center gap-2 text-sm text-[var(--ink-secondary)] cursor-pointer">
          <input type="checkbox" v-model="godMode" class="rounded" @change="toggleGodMode" />
          God Mode
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
      placeholder="搜索用户名、IP 或会话 ID..."
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
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">IP 地址</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">登录时间</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">最后活跃</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredSessions.length === 0">
            <td colspan="5" class="px-3 py-6 text-center text-[var(--ink-secondary)]">
              {{ searchQuery ? '未找到匹配的会话' : '暂无活跃会话' }}
            </td>
          </tr>
          <tr
            v-for="session in filteredSessions"
            :key="session.session_id"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <td class="px-3 py-2 font-mono">{{ session.username || session.user_id || '--' }}</td>
            <td class="px-3 py-2 font-mono">{{ session.ip || '--' }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(session.login_time) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(session.last_active) }}</td>
            <td class="px-3 py-2">
              <button class="btn btn-danger text-xs px-2 py-1" @click="kickSession(session.session_id)">踢出</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
