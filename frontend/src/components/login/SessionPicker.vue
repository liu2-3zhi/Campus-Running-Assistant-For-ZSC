<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import Swal from 'sweetalert2'

const emit = defineEmits(['session-selected', 'back'])
const auth = useAuthStore()

const sessions = ref([])
const loading = ref(false)
const creating = ref(false)
const errorMsg = ref('')
const maxSessions = ref(-1)

function formatDate(timestamp) {
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

async function loadSessions() {
  loading.value = true
  errorMsg.value = ''
  try {
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = {}
    if (sessionId) headers['X-Session-ID'] = sessionId
    const res = await fetch('/auth/user/sessions', {
      headers,
      credentials: 'include',
    })
    const data = await res.json()
    if (!data.success) {
      errorMsg.value = data.message || '加载会话列表失败'
      return
    }
    maxSessions.value = data.max_sessions ?? -1
    const valid = (data.sessions || []).filter(
      s => s.session_id && s.session_id !== 'null' && s.session_id.trim() !== ''
    )
    sessions.value = valid
  } catch (e) {
    errorMsg.value = e.message || '加载会话列表失败'
  } finally {
    loading.value = false
  }
}

async function selectSession(sessionId) {
  errorMsg.value = ''
  try {
    const headerVal = auth.getAuthenticatedSessionHeaderValue()
    const res = await fetch('/auth/switch_session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': headerVal,
      },
      credentials: 'include',
      body: JSON.stringify({ target_session_id: sessionId }),
    })
    const data = await res.json()
    if (res.ok && data.success) {
      auth.sessionUUID = sessionId
      emit('session-selected', sessionId)
    } else {
      if (data.need_login) {
        await Swal.fire({
          icon: 'warning',
          title: '需要重新登录',
          text: data.message || '认证已失效，请重新登录',
          confirmButtonText: '返回登录',
          allowOutsideClick: false,
        })
        emit('back')
      } else {
        errorMsg.value = data.message || '切换会话失败'
      }
    }
  } catch (e) {
    errorMsg.value = e.message || '切换会话失败'
  }
}

async function deleteSession(sessionId) {
  const result = await Swal.fire({
    title: '确认删除',
    text: '确定要删除该会话吗？',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
  })
  if (!result.isConfirmed) return

  errorMsg.value = ''
  try {
    const headerVal = auth.getAuthenticatedSessionHeaderValue()
    const res = await fetch('/auth/user/delete_session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': headerVal,
      },
      credentials: 'include',
      body: JSON.stringify({ session_id: sessionId }),
    })
    const data = await res.json()
    if (data.success) {
      await loadSessions()
    } else {
      errorMsg.value = data.message || '删除会话失败'
    }
  } catch (e) {
    errorMsg.value = e.message || '删除会话失败'
  }
}

async function createSession() {
  if (maxSessions.value !== -1 && sessions.value.length >= maxSessions.value) {
    const result = await Swal.fire({
      title: '会话数量已达上限',
      html: `您已达到最大会话数量限制（${maxSessions.value}个）。<br><br>是否要自动删除最早的会话并创建新会话？`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: '确定，删除最旧会话',
      cancelButtonText: '取消',
    })
    if (!result.isConfirmed) return

    const nonCurrent = sessions.value
      .filter(s => s.session_id !== auth.sessionUUID)
      .sort((a, b) => (a.created_at || 0) - (b.created_at || 0))
    if (nonCurrent.length > 0) {
      try {
        const headerVal = auth.getAuthenticatedSessionHeaderValue()
        await fetch('/auth/user/delete_session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': headerVal,
          },
          credentials: 'include',
          body: JSON.stringify({ session_id: nonCurrent[0].session_id }),
        })
      } catch (_) {}
    }
  }

  const confirmed = await Swal.fire({
    title: '确认操作',
    text: '您确定要创建一个新的会话吗？',
    icon: 'question',
    showCancelButton: true,
    confirmButtonText: '确定',
    cancelButtonText: '取消',
  })
  if (!confirmed.isConfirmed) return

  creating.value = true
  errorMsg.value = ''
  const newUUID = crypto.randomUUID()
  try {
    const headerVal = auth.getAuthenticatedSessionHeaderValue()
    const res = await fetch('/auth/user/create_session_persistence', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': headerVal,
      },
      credentials: 'include',
      body: JSON.stringify({ session_id: newUUID }),
    })
    const data = await res.json()
    if (data.success) {
      const sid = data.session_id || newUUID
      auth.sessionUUID = sid
      emit('session-selected', sid)
    } else {
      errorMsg.value = data.message || '创建会话失败'
    }
  } catch (e) {
    errorMsg.value = e.message || '创建会话失败'
  } finally {
    creating.value = false
  }
}

onMounted(loadSessions)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold">选择会话</h3>
      <div class="flex items-center gap-3">
        <span class="text-sm" style="color: var(--ink-secondary)">
          会话数:
          <strong style="color: var(--ink)">{{ sessions.length }}</strong>
          <template v-if="maxSessions !== -1"> / {{ maxSessions }}</template>
          <template v-else> / 无限制</template>
        </span>
        <button class="btn btn-ghost text-sm p-1.5" :disabled="loading" @click="loadSessions" title="刷新">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
          </svg>
        </button>
      </div>
    </div>

    <p class="text-sm" style="color: var(--ink-muted)">
      每个会话都是独立的学校账号登录状态，请选择一个会话继续，或创建新会话。
    </p>

    <div v-if="errorMsg" class="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
      {{ errorMsg }}
    </div>

    <div v-if="loading" class="py-12 text-center" style="color: var(--ink-muted)">
      <div class="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-sky-500"></div>
      加载中...
    </div>

    <div v-else class="space-y-3">
      <div v-if="sessions.length === 0" class="py-8 text-center text-sm" style="color: var(--ink-muted)">
        暂无会话，请创建新会话
      </div>

      <div
        v-for="session in sessions"
        :key="session.session_id"
        class="rounded-lg border p-3 transition-shadow hover:shadow-md"
        :class="session.is_current ? 'border-sky-500 bg-sky-50 dark:bg-sky-900/20' : ''"
        :style="session.is_current ? '' : 'border-color: var(--border-color)'"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="break-all text-sm font-semibold" style="color: var(--ink)">
              会话 {{ session.session_id }}
            </p>
            <span
              v-if="session.is_current"
              class="ml-1 inline-block rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-600 dark:bg-sky-800 dark:text-sky-300"
            >(当前)</span>
            <p class="mt-1 text-xs" style="color: var(--ink-muted)">
              创建时间: {{ formatDate(session.created_at) }}
            </p>
            <p class="mt-1">
              <span
                class="rounded-full px-2 py-0.5 text-xs font-semibold"
                :class="session.login_success ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'"
              >
                {{ session.login_success ? '✓ 已登录' : '○ 未登录' }}
              </span>
              <span v-if="session.is_multi_account_mode" class="ml-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                多账号
              </span>
            </p>
          </div>
          <div class="flex shrink-0 flex-col gap-2">
            <template v-if="!session.is_current">
              <button class="btn btn-primary !px-3 !py-1 text-xs" @click="selectSession(session.session_id)">
                <svg class="mr-1 inline-block h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                进入
              </button>
              <button
                class="btn btn-ghost !px-3 !py-1 text-xs !text-red-600 border border-red-200 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20"
                @click="deleteSession(session.session_id)"
              >
                <svg class="mr-1 inline-block h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                删除
              </button>
            </template>
            <span v-else class="text-xs" style="color: var(--ink-muted)">当前会话</span>
          </div>
        </div>
      </div>
    </div>

    <button
      class="btn btn-primary w-full"
      :disabled="creating"
      @click="createSession"
    >
      <svg class="mr-2 inline-block h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
      </svg>
      {{ creating ? '创建中...' : '创建新会话' }}
    </button>

    <button class="btn btn-ghost w-full text-sm" @click="emit('back')">
      返回登录
    </button>
  </div>
</template>
