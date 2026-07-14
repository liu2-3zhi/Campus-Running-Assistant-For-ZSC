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

const componentOrder = ['running_core', 'payment_system', 'sms_system']

const componentLabels = {
  running_core: '核心服务（跑步执行）',
  payment_system: '支付服务',
  sms_system: '短信服务',
}

function statusColor(status) {
  if (status === 'healthy' || status === 'ok' || status === 'up') return 'bg-green-500'
  if (status === 'degraded' || status === 'slow' || status === 'warning') return 'bg-yellow-500'
  return 'bg-red-500'
}

function statusLabel(status) {
  if (status === 'healthy' || status === 'ok' || status === 'up') return '正常'
  if (status === 'degraded' || status === 'slow' || status === 'warning') return '部分异常'
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
      <!-- Summary -->
      <div v-if="healthData.summary" class="panel p-3 flex flex-wrap gap-4 text-sm">
        <span class="text-[var(--ink-secondary)]">核心异常组件：
          <b :class="healthData.summary.critical_failed_count ? 'text-red-500' : 'text-[var(--ink)]'">{{ healthData.summary.critical_failed_count }}</b>
        </span>
        <span class="text-[var(--ink-secondary)]">非核心异常组件：
          <b :class="healthData.summary.non_critical_failed_count ? 'text-yellow-500' : 'text-[var(--ink)]'">{{ healthData.summary.non_critical_failed_count }}</b>
        </span>
      </div>

      <!-- Component status cards -->
      <div v-if="healthData.components" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div
          v-for="name in componentOrder"
          :key="name"
          class="panel p-4 flex items-center gap-3"
        >
          <span
            class="w-3 h-3 rounded-full flex-shrink-0"
            :class="statusColor(healthData.components?.[name]?.status || 'unknown')"
          />
          <div class="min-w-0">
            <div class="font-medium text-[var(--ink)]">{{ componentLabels[name] }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">
              {{ statusLabel(healthData.components?.[name]?.status || 'unknown') }}
            </div>
            <div v-if="healthData.components?.[name]?.message" class="text-xs text-[var(--ink-muted)] mt-0.5 break-words">
              {{ healthData.components[name].message }}
            </div>
          </div>
        </div>
      </div>

      <!-- Metrics -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">整体状态</div>
          <div class="text-lg font-semibold text-[var(--ink)] flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full" :class="statusColor(healthData.status)" />
            {{ statusLabel(healthData.status) }}
          </div>
        </div>
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">运行时长</div>
          <div class="text-lg font-semibold text-[var(--ink)]">
            {{ healthData.uptime_formatted || formatUptime(healthData.uptime_seconds) }}
          </div>
        </div>
        <div class="panel p-4">
          <div class="text-xs text-[var(--ink-secondary)] mb-1">响应时间</div>
          <div class="text-lg font-semibold text-[var(--ink)]">
            {{ (healthData.response_time_ms != null) ? (healthData.response_time_ms + ' ms') : '--' }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
