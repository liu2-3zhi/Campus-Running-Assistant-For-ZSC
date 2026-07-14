<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">日志查看</h2>

    <!-- Top controls bar -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Level filter -->
      <select v-model="levelFilter" class="select-field text-sm" @change="fetchLogs">
        <option value="">全部级别</option>
        <option value="DEBUG">DEBUG</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
      </select>

      <!-- Per-page selector -->
      <select v-model.number="perPage" class="select-field text-sm" @change="resetAndFetch">
        <option :value="50">50 行</option>
        <option :value="100">100 行</option>
        <option :value="200">200 行</option>
      </select>

      <!-- Auto-refresh toggle -->
      <button
        class="btn text-sm"
        :class="autoRefresh ? 'btn-primary' : 'btn-secondary'"
        @click="toggleAutoRefresh"
      >
        自动刷新: {{ autoRefresh ? '开' : '关' }}
        <span v-if="autoRefresh" class="ml-1 opacity-80">
          ({{ countdown }}s 后刷新)
        </span>
      </button>

      <!-- Refresh now -->
      <button
        class="btn btn-ghost text-sm"
        :disabled="loading"
        @click="fetchLogs"
      >
        {{ loading ? '加载中...' : '立即刷新' }}
      </button>
    </div>

    <!-- Error message -->
    <div
      v-if="errorMsg"
      class="px-4 py-2 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] text-sm"
    >
      {{ errorMsg }}
    </div>

    <!-- Log display area -->
    <div
      class="panel bg-gray-900 text-gray-200 font-mono text-xs leading-relaxed overflow-auto p-4 rounded-lg"
      style="max-height: 65vh"
    >
      <div v-if="loading && logLines.length === 0" class="text-center text-gray-500 py-8">
        加载中...
      </div>
      <div v-else-if="logLines.length === 0" class="text-center text-gray-500 py-8">
        暂无日志数据
      </div>
      <div v-else>
        <div v-for="(line, idx) in logLines" :key="idx">
          <span :class="getLineColorClass(line)">{{ line }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom pagination -->
    <div class="flex items-center justify-between text-sm text-[var(--ink-secondary)]">
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage <= 1 || loading"
        @click="goPage(currentPage - 1)"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage >= totalPages || loading"
        @click="goPage(currentPage + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { callRawAPI } from '@/services/api'

const levelFilter = ref('')
const perPage = ref(100)
const currentPage = ref(1)
const totalPages = ref(1)
const logContent = ref('')
const logLines = ref([])
const loading = ref(false)
const errorMsg = ref('')

const autoRefresh = ref(false)
const countdown = ref(10)
const REFRESH_INTERVAL = 10

let refreshTimer = null
let countdownTimer = null

function getLineColorClass(line) {
  if (/\bERROR\b/.test(line) || /\bCRITICAL\b/.test(line)) return 'text-red-500'
  if (/\bWARNING\b/.test(line)) return 'text-yellow-500'
  if (/\bINFO\b/.test(line)) return 'text-blue-400'
  if (/\bDEBUG\b/.test(line)) return 'text-gray-400'
  return ''
}

function parseLogLines(content) {
  if (!content) return []
  return content.split('\n').filter(line => line.length > 0)
}

async function fetchLogs() {
  loading.value = true
  errorMsg.value = ''
  try {
    const params = {
      page: currentPage.value,
      per_page: perPage.value,
    }
    if (levelFilter.value) {
      params.level = levelFilter.value
    }
    const data = await callRawAPI('/auth/admin/audit_logs?' + new URLSearchParams(params).toString(), 'GET')
    logContent.value = data.logs || ''
    logLines.value = parseLogLines(logContent.value)
    currentPage.value = data.page || 1
    totalPages.value = data.total_pages || 1
  } catch (e) {
    errorMsg.value = e.message || '获取日志失败'
  } finally {
    loading.value = false
  }
}

function resetAndFetch() {
  currentPage.value = 1
  fetchLogs()
}

function goPage(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  fetchLogs()
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  countdown.value = REFRESH_INTERVAL

  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      countdown.value = REFRESH_INTERVAL
    }
  }, 1000)

  refreshTimer = setInterval(() => {
    fetchLogs()
    countdown.value = REFRESH_INTERVAL
  }, REFRESH_INTERVAL * 1000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = REFRESH_INTERVAL
}

onMounted(fetchLogs)

onUnmounted(() => {
  stopAutoRefresh()
})
</script>
