<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

// eslint-disable-next-line no-unused-vars
const _apiRef = callAPI // 保留通用 API 句柄（当前面板仅用 REST 接口）

const POLL_INTERVAL = 3000 // 状态轮询间隔（毫秒）

const loading = ref(false)   // 首次加载态
const starting = ref(false)  // 启动任务加载态
const stopping = ref(false)  // 停止全部加载态
const success = ref('')
const error = ref('')

const accountsInput = ref('') // 目标账号（换行或逗号分隔）
const tasks = ref([])

let pollTimer = null

// 是否存在运行中的任务
const hasRunning = computed(() =>
  tasks.value.some((t) => (t.status || 'running') === 'running')
)

// 状态 → 颜色 / 图标 / 文本 映射（使用静态类名，避免被 Tailwind 清除）
function statusMeta(status) {
  switch (status) {
    case 'success':
      return {
        label: '成功',
        icon: '✅',
        card: 'border-[var(--success)]/30 bg-[var(--success)]/10',
        text: 'text-[var(--success)]',
      }
    case 'failed':
      return {
        label: '失败',
        icon: '❌',
        card: 'border-red-500/30 bg-red-500/10',
        text: 'text-red-500',
      }
    case 'stopped':
      return {
        label: '已停止',
        icon: '⏸️',
        card: 'border-orange-500/30 bg-orange-500/10',
        text: 'text-orange-500',
      }
    default:
      return {
        label: '运行中',
        icon: '⏳',
        card: 'border-[var(--line)] bg-[var(--surface-2)]',
        text: 'text-[var(--ink-secondary)]',
      }
  }
}

// 拉取任务状态；silent=true 时不显示整体 loading（用于轮询）
async function loadStatus(silent = false) {
  if (!silent) loading.value = true
  try {
    const data = await callRawAPI('/api/admin/bruteforce/status', 'GET')
    // 兼容后端不同返回字段
    const list = data.tasks || data.bruteforce_task_list || data.task_list || []
    tasks.value = Array.isArray(list) ? list : []
  } catch (e) {
    if (!silent) error.value = e.message || '加载任务状态失败'
  } finally {
    if (!silent) loading.value = false
  }
}

// 启动密码恢复任务
async function startBruteforce() {
  const accounts = accountsInput.value
    .split(/[\n,，]/)
    .map((a) => a.trim())
    .filter((a) => a.length > 0)

  if (accounts.length === 0) {
    error.value = '请输入至少一个目标账号'
    return
  }

  starting.value = true
  success.value = ''
  error.value = ''
  try {
    const data = await callRawAPI('/api/admin/bruteforce/start', 'POST', { accounts })
    if (data.success !== false) {
      success.value = `已启动 ${accounts.length} 个密码恢复任务`
      accountsInput.value = ''
      await loadStatus(true)
      startPolling()
    } else {
      error.value = data.message || '启动失败'
    }
  } catch (e) {
    error.value = e.message || '启动密码恢复任务失败'
  } finally {
    starting.value = false
  }
}

// 停止单个任务
async function stopBruteforce(account) {
  error.value = ''
  try {
    const data = await callRawAPI('/api/admin/bruteforce/stop', 'POST', { accounts: [account] })
    if (data.success === false) {
      error.value = data.message || '停止失败'
    }
  } catch (e) {
    error.value = e.message || '停止任务失败'
  } finally {
    // 1 秒后刷新，等待后端状态更新
    setTimeout(() => loadStatus(true), 1000)
  }
}

// 停止全部任务
async function stopAllBruteforce() {
  stopping.value = true
  success.value = ''
  error.value = ''
  try {
    const data = await callRawAPI('/api/admin/bruteforce/stop', 'POST', { all: true })
    if (data.success !== false) {
      success.value = '已请求停止全部任务'
    } else {
      error.value = data.message || '停止失败'
    }
  } catch (e) {
    error.value = e.message || '停止全部任务失败'
  } finally {
    stopping.value = false
    setTimeout(() => loadStatus(true), 1000)
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => loadStatus(true), POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadStatus()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <!-- Alerts -->
    <div v-if="success" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
      <span>{{ success }}</span>
      <button @click="success = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>
    <div v-if="error" class="p-3 rounded-lg bg-red-500/10 text-red-500 flex items-center justify-between">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>

    <!-- 安全提示 -->
    <div class="p-3 rounded-lg bg-orange-500/10 text-orange-500 text-sm">
      ⚠️ 密码恢复（暴力破解）为高危操作，仅超级管理员可用，所有操作均记录审计日志。请确认已获得授权后再执行。
    </div>

    <!-- 启动任务 -->
    <div class="panel p-5 space-y-4">
      <h3 class="text-base font-semibold text-[var(--ink)]">启动密码恢复任务</h3>

      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-1">目标账号</label>
        <textarea
          v-model="accountsInput"
          rows="4"
          class="input-field w-full font-mono text-sm"
          placeholder="输入需要恢复密码的账号，支持多个（每行一个，或用逗号分隔）"
        ></textarea>
        <p class="mt-1 text-xs text-[var(--ink-muted)]">支持换行或逗号（中/英文）分隔多个账号。</p>
      </div>

      <div class="flex flex-wrap gap-3 justify-end">
        <button @click="stopAllBruteforce" :disabled="stopping || !hasRunning" class="btn btn-secondary">
          {{ stopping ? '停止中...' : '停止全部任务' }}
        </button>
        <button @click="startBruteforce" :disabled="starting" class="btn btn-primary">
          {{ starting ? '启动中...' : '开始恢复密码' }}
        </button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="panel p-5 space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-base font-semibold text-[var(--ink)]">
          任务列表
          <span v-if="tasks.length" class="ml-1 text-xs text-[var(--ink-muted)]">（{{ tasks.length }}）</span>
        </h3>
        <button @click="loadStatus()" :disabled="loading" class="btn btn-secondary text-sm">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading && tasks.length === 0" class="text-center py-12 text-[var(--ink-muted)]">加载中...</div>

      <!-- 空态 -->
      <div v-else-if="tasks.length === 0" class="text-center py-8 text-sm text-[var(--ink-muted)]">
        暂无任务
      </div>

      <!-- 任务卡片 -->
      <div v-else class="space-y-3">
        <div
          v-for="(task, idx) in tasks"
          :key="task.account || idx"
          class="rounded-lg border p-4"
          :class="statusMeta(task.status || 'running').card"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span>{{ statusMeta(task.status || 'running').icon }}</span>
                <span class="font-medium text-[var(--ink)] truncate">{{ task.account }}</span>
                <span class="text-xs font-medium" :class="statusMeta(task.status || 'running').text">
                  {{ statusMeta(task.status || 'running').label }}
                </span>
              </div>

              <div class="mt-2 space-y-1 text-xs text-[var(--ink-secondary)]">
                <div v-if="task.attempts != null">尝试次数：{{ task.attempts }}</div>
                <div v-if="task.start_time">开始时间：{{ task.start_time }}</div>
                <div v-if="task.end_time">结束时间：{{ task.end_time }}</div>
                <div v-if="task.status === 'success' && task.password" class="font-bold text-[var(--success)]">
                  密码：{{ task.password }}
                </div>
              </div>
            </div>

            <button
              v-if="(task.status || 'running') === 'running'"
              @click="stopBruteforce(task.account)"
              class="btn btn-secondary text-xs shrink-0"
            >
              停止
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
