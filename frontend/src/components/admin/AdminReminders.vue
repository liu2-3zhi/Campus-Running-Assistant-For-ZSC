<script setup>
import { ref, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const deletingId = ref('')
const togglingId = ref('')
const success = ref('')
const error = ref('')

const reminders = ref([])

// 编辑器状态
const showEditor = ref(false)
const editingId = ref('')
const form = ref({
  title: '',
  message: '',
  start_time: '',
  end_time: '',
  enabled: true,
})

// 删除确认
const deleteConfirmId = ref('')

// 手动检查结果
const checkResults = ref(null)

const TIME_PATTERN = /^([0-1][0-9]|2[0-3]):[0-5][0-9]$/

const stats = computed(() => {
  const total = reminders.value.length
  const enabled = reminders.value.filter(r => r.enabled).length
  return { total, enabled, disabled: total - enabled }
})

function clearAlerts() {
  success.value = ''
  error.value = ''
}

function showSuccess(msg) {
  success.value = msg
  error.value = ''
}

function showError(msg) {
  error.value = msg
  success.value = ''
}

function formatTime(ts) {
  if (!ts) return '-'
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
  } catch (_) {
    return '-'
  }
}

// 跨天判断：开始时间晚于结束时间视为跨天
function isOvernight(reminder) {
  return (reminder.start_time || '') > (reminder.end_time || '')
}

async function loadReminders() {
  loading.value = true
  clearAlerts()
  try {
    const data = await callRawAPI('/api/reminders/list', 'GET')
    if (data.success) {
      reminders.value = data.reminders || []
    } else {
      showError(data.message || '获取提醒列表失败')
    }
  } catch (e) {
    showError(e.message || '获取提醒列表失败')
  } finally {
    loading.value = false
  }
}

function openAddEditor() {
  editingId.value = ''
  form.value = { title: '', message: '', start_time: '', end_time: '', enabled: true }
  showEditor.value = true
  clearAlerts()
}

function openEditEditor(reminder) {
  editingId.value = reminder.id
  form.value = {
    title: reminder.title || '',
    message: reminder.message || '',
    start_time: reminder.start_time || '',
    end_time: reminder.end_time || '',
    enabled: reminder.enabled !== false,
  }
  showEditor.value = true
  clearAlerts()
}

function closeEditor() {
  showEditor.value = false
  editingId.value = ''
}

async function saveReminder() {
  const title = form.value.title.trim()
  const message = form.value.message.trim()
  const startTime = form.value.start_time.trim()
  const endTime = form.value.end_time.trim()

  // ===== 数据验证 =====
  if (!title) {
    showError('提醒标题不能为空')
    return
  }
  if (title.length > 50) {
    showError('提醒标题不能超过50个字符')
    return
  }
  if (!message) {
    showError('提醒内容不能为空')
    return
  }
  if (message.length > 500) {
    showError('提醒内容不能超过500个字符')
    return
  }
  if (!TIME_PATTERN.test(startTime)) {
    showError('开始时间格式错误，应为 HH:MM（如 19:00）')
    return
  }
  if (!TIME_PATTERN.test(endTime)) {
    showError('结束时间格式错误，应为 HH:MM（如 20:00）')
    return
  }

  saving.value = true
  clearAlerts()
  try {
    const body = {
      title,
      message,
      start_time: startTime,
      end_time: endTime,
      enabled: form.value.enabled,
    }
    let data
    if (editingId.value) {
      data = await callRawAPI('/api/reminders/update', 'POST', { id: editingId.value, ...body })
    } else {
      data = await callRawAPI('/api/reminders/add', 'POST', body)
    }
    if (data.success) {
      showSuccess(editingId.value ? '提醒更新成功' : '提醒添加成功')
      closeEditor()
      await loadReminders()
    } else {
      showError(data.message || '保存提醒失败')
    }
  } catch (e) {
    showError(e.message || '保存提醒失败')
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(reminder) {
  togglingId.value = reminder.id
  clearAlerts()
  try {
    const data = await callRawAPI('/api/reminders/update', 'POST', {
      id: reminder.id,
      enabled: !reminder.enabled,
    })
    if (data.success) {
      showSuccess(!reminder.enabled ? '提醒已启用' : '提醒已禁用')
      await loadReminders()
    } else {
      showError(data.message || '操作失败')
    }
  } catch (e) {
    showError(e.message || '操作失败')
  } finally {
    togglingId.value = ''
  }
}

function confirmDelete(reminder) {
  deleteConfirmId.value = reminder.id
  clearAlerts()
}

function cancelDelete() {
  deleteConfirmId.value = ''
}

async function deleteReminder(reminder) {
  deletingId.value = reminder.id
  clearAlerts()
  try {
    const data = await callRawAPI('/api/reminders/delete', 'POST', { id: reminder.id })
    if (data.success) {
      showSuccess('提醒删除成功')
      deleteConfirmId.value = ''
      await loadReminders()
    } else {
      showError(data.message || '删除提醒失败')
    }
  } catch (e) {
    showError(e.message || '删除提醒失败')
  } finally {
    deletingId.value = ''
  }
}

async function checkReminders() {
  checking.value = true
  clearAlerts()
  checkResults.value = null
  try {
    const data = await callRawAPI('/api/reminders/check', 'GET')
    if (data.success) {
      checkResults.value = data.reminders || []
      showSuccess(`检查完成，当前有 ${checkResults.value.length} 条待展示提醒`)
    } else {
      showError(data.message || '检查提醒失败')
    }
  } catch (e) {
    showError(e.message || '检查提醒失败')
  } finally {
    checking.value = false
  }
}

onMounted(loadReminders)
</script>

<template>
  <div class="space-y-6">
    <!-- 顶部标题与操作 -->
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <h2 class="text-lg font-semibold text-[var(--ink)]">定时提醒</h2>
      <div class="flex gap-2">
        <button @click="checkReminders" :disabled="checking" class="btn btn-secondary text-sm">
          {{ checking ? '检查中...' : '立即检查' }}
        </button>
        <button @click="openAddEditor" class="btn btn-primary text-sm">+ 添加定时提醒</button>
      </div>
    </div>

    <!-- Alerts -->
    <div v-if="success" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
      <span>{{ success }}</span>
      <button @click="success = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>
    <div v-if="error" class="p-3 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] flex items-center justify-between">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>

    <!-- 手动检查结果 -->
    <div v-if="checkResults !== null" class="panel p-4 space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-base font-semibold text-[var(--ink)]">当前待展示提醒</h3>
        <button @click="checkResults = null" class="text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]">收起</button>
      </div>
      <div v-if="checkResults.length === 0" class="text-sm text-[var(--ink-muted)] py-2">当前时间段没有需要展示的提醒</div>
      <div
        v-for="item in checkResults"
        :key="item.id"
        class="p-3 rounded-lg bg-[var(--glass)] border border-[var(--border-color)]"
      >
        <div class="font-medium text-[var(--ink)]">{{ item.title }}</div>
        <div class="text-sm text-[var(--ink-secondary)] whitespace-pre-wrap mt-1">{{ item.message }}</div>
      </div>
    </div>

    <!-- 编辑 / 新增 表单 -->
    <div v-if="showEditor" class="panel p-5 space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-base font-semibold text-[var(--ink)]">
          {{ editingId ? '编辑定时提醒' : '添加定时提醒' }}
        </h3>
        <button @click="closeEditor" class="text-[var(--ink-muted)] hover:text-[var(--ink)]">&times;</button>
      </div>

      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-1">📌 提醒标题 *</label>
        <input
          v-model="form.title"
          type="text"
          maxlength="50"
          class="input-field w-full"
          placeholder="例如：学校服务器关闭提醒"
        />
        <p class="text-xs text-[var(--ink-muted)] mt-1">最多50个字符</p>
      </div>

      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-1">📝 提醒内容 *</label>
        <textarea
          v-model="form.message"
          rows="4"
          maxlength="500"
          class="input-field w-full resize-y"
          placeholder="输入提醒内容（支持 Markdown）"
        ></textarea>
        <p class="text-xs text-[var(--ink-muted)] mt-1">最多500个字符（支持 Markdown）</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">⏰ 开始时间 *</label>
          <input v-model="form.start_time" type="time" class="input-field w-full" />
          <p class="text-xs text-[var(--ink-muted)] mt-1">24小时制（如 19:00）</p>
        </div>
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">⏰ 结束时间 *</label>
          <input v-model="form.end_time" type="time" class="input-field w-full" />
          <p class="text-xs text-[var(--ink-muted)] mt-1">24小时制（如 20:00）</p>
        </div>
      </div>

      <!-- 跨天说明 -->
      <div class="p-3 rounded-lg bg-[var(--accent)]/10 text-sm text-[var(--ink-secondary)]">
        💡 跨天时间说明：若开始时间晚于结束时间（如 23:00 - 06:00），将被视为跨天提醒；正常时间段（如 19:00 - 20:00）当天生效。
      </div>

      <label class="flex items-center gap-2 cursor-pointer">
        <input v-model="form.enabled" type="checkbox" class="rounded border-[var(--border-color)] text-[var(--accent)] focus:ring-[var(--accent)]" />
        <span class="text-sm text-[var(--ink)]">✅ 启用此提醒（取消勾选则暂时禁用，不会删除数据）</span>
      </label>

      <div class="flex justify-end gap-2">
        <button @click="closeEditor" class="btn btn-ghost">取消</button>
        <button @click="saveReminder" :disabled="saving" class="btn btn-primary">
          {{ saving ? '保存中...' : '保存提醒' }}
        </button>
      </div>
    </div>

    <!-- 统计 -->
    <div v-if="!loading" class="grid grid-cols-3 gap-3">
      <div class="panel p-4 text-center">
        <div class="text-2xl font-semibold text-[var(--ink)]">{{ stats.total }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">提醒总数</div>
      </div>
      <div class="panel p-4 text-center">
        <div class="text-2xl font-semibold text-[var(--success)]">{{ stats.enabled }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">已启用</div>
      </div>
      <div class="panel p-4 text-center">
        <div class="text-2xl font-semibold text-[var(--ink-muted)]">{{ stats.disabled }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">已禁用</div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-[var(--ink-muted)]">加载中...</div>

    <!-- 提醒列表 -->
    <template v-else>
      <div v-if="reminders.length === 0" class="panel p-8 text-center text-[var(--ink-muted)]">
        暂无定时提醒，点击右上角「添加定时提醒」创建
      </div>

      <div
        v-for="reminder in reminders"
        :key="reminder.id"
        class="panel p-4 space-y-3"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-center gap-2 min-w-0">
            <h3 class="text-base font-semibold text-[var(--ink)] truncate">{{ reminder.title }}</h3>
            <span
              class="text-xs px-2 py-0.5 rounded-full flex-shrink-0"
              :class="reminder.enabled
                ? 'bg-[var(--success)]/10 text-[var(--success)]'
                : 'bg-[var(--ink-muted)]/10 text-[var(--ink-muted)]'"
            >
              {{ reminder.enabled ? '已启用' : '已禁用' }}
            </span>
          </div>
        </div>

        <div class="text-sm text-[var(--ink-secondary)] whitespace-pre-wrap">{{ reminder.message }}</div>

        <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--ink-muted)]">
          <span>
            🕒 {{ reminder.start_time }} - {{ reminder.end_time }}
            <span v-if="isOvernight(reminder)" title="跨天提醒">🌙</span>
          </span>
          <span>创建：{{ formatTime(reminder.created_at) }}</span>
          <span v-if="reminder.updated_at">更新：{{ formatTime(reminder.updated_at) }}</span>
        </div>

        <!-- 删除确认 -->
        <div
          v-if="deleteConfirmId === reminder.id"
          class="px-3 py-2 rounded-lg bg-[var(--danger)]/10 border border-[var(--danger)]/30 flex items-center justify-between gap-2"
        >
          <span class="text-sm text-[var(--danger)]">确定删除提醒「{{ reminder.title }}」吗？此操作不可撤销。</span>
          <div class="flex gap-2 flex-shrink-0">
            <button class="btn btn-danger text-xs" :disabled="deletingId === reminder.id" @click="deleteReminder(reminder)">
              {{ deletingId === reminder.id ? '删除中...' : '确认删除' }}
            </button>
            <button class="btn btn-ghost text-xs" @click="cancelDelete">取消</button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div v-else class="flex flex-wrap gap-2">
          <button class="btn btn-ghost text-xs px-3 py-1" @click="openEditEditor(reminder)">编辑</button>
          <button
            class="btn btn-secondary text-xs px-3 py-1"
            :disabled="togglingId === reminder.id"
            @click="toggleEnabled(reminder)"
          >
            {{ togglingId === reminder.id ? '处理中...' : (reminder.enabled ? '禁用' : '启用') }}
          </button>
          <button class="btn btn-danger text-xs px-3 py-1" @click="confirmDelete(reminder)">删除</button>
        </div>
      </div>
    </template>
  </div>
</template>
