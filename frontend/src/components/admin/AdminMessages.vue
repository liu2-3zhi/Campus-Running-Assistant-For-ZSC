<script setup>
import { ref, onMounted } from 'vue'
import { callAPI } from '@/services/api'

const messages = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const newMessage = ref('')
const submitting = ref(false)

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

async function loadMessages() {
  loading.value = true
  clearMessages()
  try {
    const res = await callAPI('get_messages')
    messages.value = res.messages || res || []
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
  submitting.value = true
  clearMessages()
  try {
    await callAPI('create_message', { content: newMessage.value.trim() })
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
    await callAPI('delete_message', { id })
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
      <textarea
        v-model="newMessage"
        class="input-field w-full"
        rows="3"
        placeholder="输入留言内容..."
      />
      <button class="btn btn-primary text-sm" :disabled="submitting" @click="createMessage">
        {{ submitting ? '发布中...' : '发布留言' }}
      </button>
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
              <div class="flex items-center gap-2 mb-1">
                <span class="font-medium text-sm text-[var(--ink)]">{{ msg.author || msg.username || '匿名' }}</span>
                <span class="text-xs text-[var(--ink-muted)]">{{ formatDate(msg.created_at || msg.date) }}</span>
              </div>
              <p class="text-sm text-[var(--ink-secondary)] whitespace-pre-wrap break-words">{{ msg.content || msg.text || '' }}</p>
            </div>
            <button
              v-if="msg.is_own || msg.can_delete"
              class="btn btn-danger text-xs px-2 py-1 flex-shrink-0"
              @click="deleteMessage(msg.id)"
            >删除</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
