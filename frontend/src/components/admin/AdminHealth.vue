<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const healthData = ref(null)
const loading = ref(false)
const error = ref('')
const autoRefresh = ref(true)
const countdown = ref(5)
const REFRESH_INTERVAL = 5

let refreshTimer = null
let countdownTimer = null

const componentOrder = ['core', 'payment', 'sms']

function statusColor(status) {
  if (status === 'healthy' || status === 'ok' || status === 'up') return 'bg-green-500'
  if (status === 'degraded' || status === 'slow' || status === 'warning') return 'bg-yellow-500'
  return 'bg-red-500'
}

function statusLabel(status) {
  if (status === 'healthy' || status === 'ok' || status === 'up') return '正常'
  if (status === 'degraded' || status === 'slow' || status === 'warning') return '异常'
  return '故障'
}

function formatUptime(seconds) {
  if (!seconds && seconds !== 0) return '--'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return d + '天 ' + h + '小时'
  if (h > 0) return h + '小时 ' + m + '分钟'
  return m + '分钟'
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '--'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB'
  return (bytes / 1073741824).toFixed(2) + ' GB'
}

async function fetchHealth() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/health', { cache: 'no-cache' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    healthData.value = await res.json()
  } catch (e) {
    error.value = e.message || '获取健康状态失败'
  } finally {
    loading.value = false
  }
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
    if (countdown.value <= 0) countdown.value = REFRESH_INTERVAL
  }, 1000)
  refreshTimer = setInterval(() => {
    fetchHealth()
    countdown.value = REFRESH_INTERVAL
  }, REFRESH_INTERVAL * 1000)
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  countdown.value = REFRESH_INTERVAL
}

onMounted(() => {
  fetchHealth()
  if (autoRefresh.value) startAutoRefresh()
})

onUnmounted(() => { stopAutoRefresh() })
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-[var(--ink)]">系统状态</h2>
      <div class="flex items-center gap-2">
        <button
          class="btn text-sm"
          :class="autoRefresh ? 'btn-primary' : 'btn-secondary'"
          @click="toggleAutoRefresh"
        >
          自动刷新: {{ autoRefresh ? '开' : '关' }}
          <span v-if="autoRefresh" class="ml-1 opacity-80">({{ countdown }}s)</span>
        </button>
        <button class="btn btn-ghost text-sm" :disabled="loading" @click="fetchHealth">
          {{ loading ? '加载中...' : '立即刷新' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <div v-if="loading && !healthData" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <template v-else-if="healthData">
      <!-- Component status cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div
          v-for="name in componentOrder"
          :key="name"
          class="panel p-4 flex items-center gap-3"
        >
          <span
            class="w-3 h-3 rounded-full flex-shrink-0"
            :class="statusColor(healthData.components?.[name]?.status || healthData[name + '_status'] || 'unknown')"
          />
          <div>
            <div class="font-medium text-[var(--ink)] capitalize">{{ name === 'core' ? '核心服务' : name === 'payment' ? '支付服务' : '短信服务' }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">
              {{ statusLabel(healthData.components?.[name]?.status || healthData[name + '_status'] || 'unknown') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Metrics -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">运行时间</div>
          <div class="text-lg font-semibold text-[var(--ink)]">
            {{ formatUptime(healthData.uptime || healthData.uptime_seconds) }}
          </div>
        </div>
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">响应时间</div>
          <div class="text-lg font-semibold text-[var(--ink)]">
            {{ healthData.response_time ? (healthData.response_time + ' ms') : '--' }}
          </div>
        </div>
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">内存使用</div>
          <div class="text-lg font-semibold text-[var(--ink)]">
            {{ healthData.memory_usage ? formatBytes(healthData.memory_usage) : (healthData.memory ? healthData.memory : '--') }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
