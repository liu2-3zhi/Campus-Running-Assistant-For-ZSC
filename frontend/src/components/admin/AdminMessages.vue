<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const messages = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const newMessage = ref('')
const guestNickname = ref('')
const guestEmail = ref('')
const submitting = ref(false)

const isGuest = computed(() => auth.isGuest)
const canDeleteAny = computed(() => !!auth.permissions?.delete_any_messages || auth.isAdmin)
const canDeleteOwn = computed(() => !!auth.permissions?.delete_own_messages)

function canDelete(msg) {
  if (canDeleteAny.value) return true
  const isOwn = msg.auth_username === auth.username && !msg.is_guest
  return canDeleteOwn.value && isOwn
}

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr, ts) {
  if (dateStr) return dateStr
  if (ts != null) {
    const d = new Date(ts < 1e12 ? ts * 1000 : ts)
    if (!isNaN(d.getTime())) return d.toLocaleString('zh-CN')
  }
  return '--'
}

async function checkIPBan() {
  try {
    const res = await callRawAPI('/api/admin/check_ip_ban', 'POST', { scope: 'messages_only' })
    return res.is_banned === true
  } catch (_) {
    return false
  }
}

async function loadMessages() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/messages/list', 'GET')
    messages.value = res.messages || []
  } catch (e) {
    error.value = e.message || '加载留言失败'
  } finally {
    loading.value = false
  }
}

async function createMessage() {
  if (!newMessage.value.trim()) {
    error.value = '留言内容不能为空'
    return
  }
  if (isGuest.value && (!guestNickname.value.trim() || !guestEmail.value.trim())) {
    error.value = '游客发言需要填写昵称和邮箱'
    return
  }
  submitting.value = true
  clearMessages()
  try {
    if (await checkIPBan()) {
      error.value = '您的IP已被限制访问留言功能'
      return
    }
    const res = await callRawAPI('/api/messages/post', 'POST', {
      content: newMessage.value.trim(),
      nickname: guestNickname.value.trim(),
      email: guestEmail.value.trim(),
    })
    if (res && res.success === false) {
      error.value = res.message || '发布留言失败'
      return
    }
    success.value = '留言已发布'
    newMessage.value = ''
    await loadMessages()
  } catch (e) {
    error.value = e.message || '发布留言失败'
  } finally {
    submitting.value = false
  }
}

async function deleteMessage(id) {
  if (!confirm('确定要删除该留言吗？')) return
  clearMessages()
  try {
    const res = await callRawAPI('/api/messages/delete', 'POST', { message_id: id })
    if (res && res.success === false) {
      error.value = res.message || '删除留言失败'
      return
    }
    success.value = '留言已删除'
    await loadMessages()
  } catch (e) {
    error.value = e.message || '删除留言失败'
  }
}

onMounted(loadMessages)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">留言板</h2>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <!-- New message form -->
    <div class="panel p-4 space-y-3">
      <h3 class="font-medium text-[var(--ink)]">发布留言</h3>
      <div v-if="isGuest" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">昵称 *</label>
          <input v-model="guestNickname" class="input-field w-full" type="text" placeholder="您的昵称" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">邮箱 *</label>
          <input v-model="guestEmail" class="input-field w-full" type="email" placeholder="您的邮箱" />
        </div>
      </div>
      <textarea
        v-model="newMessage"
        class="input-field w-full"
        rows="3"
        maxlength="1000"
        placeholder="输入留言内容..."
      />
      <div class="flex items-center justify-between">
        <span class="text-xs text-[var(--ink-muted)]">{{ newMessage.length }} / 1000</span>
        <button class="btn btn-primary text-sm" :disabled="submitting" @click="createMessage">
          {{ submitting ? '发布中...' : '发布留言' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <template v-else>
      <div v-if="messages.length === 0" class="py-8 text-center text-[var(--ink-secondary)]">暂无留言</div>
      <div v-else class="space-y-3">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="panel p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center flex-wrap gap-2 mb-1">
                <span class="font-medium text-sm text-[var(--ink)]">{{ msg.nickname || '匿名' }}</span>
                <span v-if="msg.is_guest" class="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-600">游客</span>
                <span v-if="msg.ip_city" class="text-[10px] px-1.5 py-0.5 rounded bg-sky-100 text-sky-600">{{ msg.ip_city }}</span>
                <span v-if="msg.email" class="text-xs text-[var(--ink-muted)]">{{ msg.email }}</span>
                <span class="text-xs text-[var(--ink-muted)]">{{ formatDate(msg.datetime, msg.timestamp) }}</span>
              </div>
              <p class="text-sm text-[var(--ink-secondary)] whitespace-pre-wrap break-words">{{ msg.content || '' }}</p>
            </div>
            <button
              v-if="canDelete(msg)"
              class="btn btn-danger text-xs px-2 py-1 flex-shrink-0"
              @click="deleteMessage(msg.id)"
            >删除</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
