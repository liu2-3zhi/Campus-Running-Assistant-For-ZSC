<script setup>
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { callAPI, callRawAPI } from '@/services/api'
import { checkOverdueBeforeStartByCurrentMode } from '@/composables/usePayment'

const app = useAppStore()

const progressPercent = computed(() => {
  const rd = app.runData
  if (!rd) return 0
  if (rd.progress != null) return Math.min(100, Math.max(0, Number(rd.progress)))
  if (rd.total_distance && rd.current_distance) {
    return Math.min(100, (rd.current_distance / rd.total_distance) * 100)
  }
  return 0
})

const progressText = computed(() => {
  if (app.isRunning) return '运行中'
  if (progressPercent.value >= 100) return '已完成'
  if (progressPercent.value > 0) return '已暂停'
  return '未开始'
})

function formatDistance(meters) {
  if (meters == null) return '0.00 km'
  const value = Number(meters)
  if (Number.isNaN(value)) return '0.00 km'
  return `${(value / 1000).toFixed(2)} km`
}

function formatTime(seconds) {
  if (seconds == null) return '00:00'
  const value = Number(seconds)
  if (Number.isNaN(value)) return '00:00'
  const minutes = Math.floor(value / 60)
  const remaining = Math.floor(value % 60)
  return `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

const summary = computed(() => {
  const rd = app.runData || {}
  const distance = rd.total_distance == null ? '-- km' : formatDistance(rd.total_distance)
  const duration = rd.total_time == null ? '--:--' : formatTime(rd.total_time)
  return `${distance} / ${duration}`
})

const locationText = computed(() => {
  const rd = app.runData || {}
  const lat = rd.latitude ?? rd.lat
  const lng = rd.longitude ?? rd.lng
  return lat != null && lng != null
    ? `${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}`
    : '--, --'
})

async function startTask() {
  try {
    const allowed = await checkOverdueBeforeStartByCurrentMode()
    if (!allowed) return
    const result = await callRawAPI('/api/background_task/start', 'POST', {
      task_indices: [app.selectedTaskIndex],
      auto_generate: false,
    })
    if (result?.success !== false) {
      app.isRunning = true
      app.addLog('执行已开始', 'INFO')
    }
  } catch (error) {
    app.addLog('启动失败: ' + (error.message || error), 'ERROR')
  }
}

async function stopTask() {
  try {
    await callRawAPI('/api/background_task/stop', 'POST')
    app.isRunning = false
    app.addLog('跑步已停止', 'INFO')
  } catch (error) {
    app.addLog('停止失败: ' + (error.message || error), 'ERROR')
  }
}

async function autoGeneratePath() {
  try {
    const result = await callAPI('auto_generate_path_with_provider', {
      min_t_m: 20,
      max_t_m: 30,
      min_d_m: 2000,
    })
    app.addLog(result?.message || '路径自动生成完成', 'INFO')
  } catch (error) {
    app.addLog('自动生成路径失败: ' + (error.message || error), 'ERROR')
  }
}

async function clearPath() {
  try {
    const result = await callAPI('clear_current_task_draft')
    app.addLog(result?.message || '路径已清除', 'INFO')
  } catch (error) {
    app.addLog('清除路径失败: ' + (error.message || error), 'ERROR')
  }
}

async function exportPath() {
  try {
    const result = await callAPI('export_task_data')
    if (!result?.data) return
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `path_${Date.now()}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    app.addLog('导出路径失败: ' + (error.message || error), 'ERROR')
  }
}
</script>

<template>
  <div id="mobile-control-panel" class="mobile-card">
    <div class="mb-4 flex items-center gap-2 border-b border-orange-100 pb-3">
      <svg
        class="h-6 w-6 text-orange-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
        />
      </svg>
      <h3 class="text-xl font-bold text-orange-700">控制面板</h3>
    </div>

    <div class="mb-4 rounded-lg bg-slate-50 p-3">
      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-medium text-slate-600">当前状态</span>
        <span id="mobile-status-indicator" class="rounded-full bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-600">
          {{ app.isRunning ? '运行中' : '未启动' }}
        </span>
      </div>
      <div class="text-xs text-slate-500">
        {{ app.isRunning ? '任务正在执行' : '等待执行任务' }}
      </div>
    </div>

    <div class="mb-4 grid grid-cols-1 gap-3">
      <button
        id="mobile-start-btn"
        class="flex min-h-[72px] items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-green-500 to-green-600 px-4 py-3 text-sm font-bold text-white shadow-lg transition hover:shadow-xl"
        :disabled="app.isRunning || app.selectedTaskIndex < 0"
        @click="startTask"
      >
        <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
            clip-rule="evenodd"
          />
        </svg>
        开始
      </button>
      <button
        id="mobile-stop-btn"
        class="flex min-h-[72px] items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-red-500 to-red-600 px-4 py-3 text-sm font-bold text-white shadow-lg transition hover:shadow-xl"
        :disabled="!app.isRunning"
        @click="stopTask"
      >
        <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z"
            clip-rule="evenodd"
          />
        </svg>
        停止
      </button>
    </div>

    <div
      id="mobile-run-stats-block"
      class="mt-4 rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50 p-3 text-center"
    >
      <p class="mb-1 text-xs text-slate-600">已选任务总览</p>
      <p id="mobile-run-stats-label" class="text-lg font-bold text-emerald-600">{{ summary }}</p>
    </div>

    <div id="mobile-single-progress-block" class="mt-3 rounded-xl bg-slate-50 p-3">
      <div class="mb-2 h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          id="mobile-single-progress-fill"
          class="h-2 bg-gradient-to-r from-sky-500 to-blue-500 transition-all duration-300"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
      <div class="flex justify-between text-xs">
        <span id="mobile-single-progress-text" class="text-slate-600">{{ progressText }}</span>
        <span id="mobile-single-progress-extra" class="text-slate-400">{{ progressPercent.toFixed(1) }}%</span>
      </div>
    </div>

    <div class="mt-4 border-t border-slate-100 pt-3">
      <h4 class="mb-2 flex items-center gap-1 text-xs font-semibold text-slate-700">
        <svg class="h-4 w-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
        </svg>
        路径工具
      </h4>
      <div class="grid grid-cols-2 gap-2">
        <button id="mobile-auto-gen-button" class="rounded-lg bg-slate-50 px-3 py-2.5 text-xs font-medium text-slate-600" @click="autoGeneratePath">
          自动生成
        </button>
        <button id="mobile-clear-button" class="rounded-lg bg-amber-50 px-3 py-2.5 text-xs font-medium text-amber-600" @click="clearPath">
          清除路径
        </button>
        <button id="mobile-export-button" class="col-span-2 rounded-lg bg-violet-50 px-3 py-2.5 text-xs font-medium text-violet-600" @click="exportPath">
          导出路径
        </button>
      </div>
    </div>

    <div class="mt-4 border-t border-slate-100 pt-3">
      <h4 class="mb-2 flex items-center gap-1 text-xs font-semibold text-slate-700">
        <svg class="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
            clip-rule="evenodd"
          />
        </svg>
        实时状态
      </h4>
      <div class="grid grid-cols-2 gap-2">
        <div class="rounded-lg bg-blue-50 p-2 text-center">
          <p class="mb-1 text-xs text-slate-500">已跑距离</p>
          <p id="mobile-live-dist-label" class="text-sm font-bold text-blue-600">{{ formatDistance(app.runData?.live_distance || app.runData?.current_distance) }}</p>
        </div>
        <div class="rounded-lg bg-green-50 p-2 text-center">
          <p class="mb-1 text-xs text-slate-500">总距离</p>
          <p id="mobile-total-dist-label" class="text-sm font-bold text-green-600">{{ formatDistance(app.runData?.total_distance) }}</p>
        </div>
        <div class="rounded-lg bg-purple-50 p-2 text-center">
          <p class="mb-1 text-xs text-slate-500">已用时间</p>
          <p id="mobile-live-time-label" class="text-sm font-bold text-purple-600">{{ formatTime(app.runData?.live_time || app.runData?.elapsed_time) }}</p>
        </div>
        <div class="rounded-lg bg-orange-50 p-2 text-center">
          <p class="mb-1 text-xs text-slate-500">预计时间</p>
          <p id="mobile-total-time-label" class="text-sm font-bold text-orange-600">{{ formatTime(app.runData?.total_time) }}</p>
        </div>
        <div class="col-span-2 rounded-lg bg-amber-50 p-2 text-center">
          <p class="mb-1 text-xs text-slate-500">预估剩余时间</p>
          <p id="mobile-remaining-time-label" class="text-sm font-bold text-amber-600">{{ formatTime(app.runData?.remaining_time) }}</p>
        </div>
      </div>
      <p id="mobile-current-location-label" class="mt-2 text-center text-xs font-mono text-slate-500">当前位置: {{ locationText }}</p>
    </div>
  </div>
</template>
