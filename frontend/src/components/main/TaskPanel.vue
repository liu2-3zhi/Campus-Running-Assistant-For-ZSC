<script setup>
import { useAppStore } from '@/stores/app'
import { callAPI } from '@/services/api'
import { ref, computed } from 'vue'
import AppModal from '@/components/common/AppModal.vue'

const app = useAppStore()
const refreshing = ref(false)
const showTaskDetail = ref(false)

const selectedTask = computed(() => {
  if (app.selectedTaskIndex < 0 || app.selectedTaskIndex >= app.tasks.length) return null
  return app.tasks[app.selectedTaskIndex]
})

function openTaskDetail() {
  if (!selectedTask.value) {
    app.addLog('请先选择一个任务', 'WARN')
    return
  }
  showTaskDetail.value = true
}

async function refreshTasks() {
  refreshing.value = true
  try {
    const data = await callAPI('load_tasks')
    if (data && data.tasks) {
      app.tasks = data.tasks
    }
  } catch (e) {
    app.addLog('刷新任务列表失败: ' + (e.message || e), 'ERROR')
  } finally {
    refreshing.value = false
  }
}

function selectTask(index) {
  app.selectedTaskIndex = index
}

function statusBadgeClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'running') return 'bg-green-500/15 text-green-600'
  if (s === 'paused') return 'bg-amber-500/15 text-amber-600'
  if (s === 'completed') return 'bg-blue-500/15 text-blue-600'
  return 'bg-gray-500/15 text-gray-500'
}

function statusLabel(status) {
  const s = (status || '').toLowerCase()
  if (s === 'running') return '运行中'
  if (s === 'paused') return '已暂停'
  if (s === 'completed') return '已完成'
  if (s === 'pending') return '等待中'
  return status || '未知'
}
</script>

<template>
  <div class="panel p-3">
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold text-[var(--ink)]">
        任务列表
        <span class="text-xs text-[var(--ink-muted)] font-normal ml-1">({{ app.tasks.length }})</span>
      </h3>
      <div class="flex gap-2">
      <button
        class="btn btn-ghost text-xs px-2 py-1"
        @click="openTaskDetail"
        title="查看任务详情"
      >
        任务详情
      </button>
      <button
        class="btn btn-ghost text-xs px-2 py-1"
        :disabled="refreshing"
        @click="refreshTasks"
        title="刷新任务"
      >
        <svg
          class="w-3.5 h-3.5 transition-transform"
          :class="{ 'animate-spin': refreshing }"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
      </div>
    </div>

    <!-- Task list -->
    <div class="max-h-48 overflow-y-auto space-y-1">
      <div v-if="app.tasks.length === 0" class="text-center text-sm text-[var(--ink-muted)] py-4">
        暂无任务
      </div>
      <button
        v-for="(task, index) in app.tasks"
        :key="task.id || index"
        class="w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center justify-between gap-2"
        :class="[
          index === app.selectedTaskIndex
            ? 'bg-[var(--accent)]/10 border border-[var(--accent)]/30'
            : 'hover:bg-[var(--glass)] border border-transparent'
        ]"
        @click="selectTask(index)"
      >
        <div class="min-w-0 flex-1">
          <div class="text-sm text-[var(--ink)] truncate">
            {{ task.name || task.task_name || `任务 ${index + 1}` }}
          </div>
        </div>
        <span
          class="text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0"
          :class="statusBadgeClass(task.status)"
        >
          {{ statusLabel(task.status) }}
        </span>
      </button>
    </div>

    <!-- Task detail modal -->
    <AppModal
      :visible="showTaskDetail"
      title="任务详情"
      width="max-w-md"
      @close="showTaskDetail = false"
    >
      <div v-if="selectedTask" class="text-sm space-y-2">
        <div class="flex justify-between">
          <span class="text-[var(--ink-muted)]">任务名</span>
          <span class="text-[var(--ink)] font-medium">{{ selectedTask.name || selectedTask.task_name || '--' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-[var(--ink-muted)]">状态</span>
          <span
            class="text-[10px] font-medium px-2 py-0.5 rounded-full"
            :class="statusBadgeClass(selectedTask.status)"
          >{{ statusLabel(selectedTask.status) }}</span>
        </div>
        <div v-if="selectedTask.distance != null" class="flex justify-between">
          <span class="text-[var(--ink-muted)]">距离</span>
          <span class="text-[var(--ink)]">{{ (Number(selectedTask.distance) / 1000).toFixed(2) }} km</span>
        </div>
        <div v-if="selectedTask.total_distance != null" class="flex justify-between">
          <span class="text-[var(--ink-muted)]">总距离</span>
          <span class="text-[var(--ink)]">{{ (Number(selectedTask.total_distance) / 1000).toFixed(2) }} km</span>
        </div>
        <div v-if="selectedTask.duration || selectedTask.time" class="flex justify-between">
          <span class="text-[var(--ink-muted)]">时间</span>
          <span class="text-[var(--ink)]">{{ selectedTask.duration || selectedTask.time }}</span>
        </div>
        <div v-if="selectedTask.start_time" class="flex justify-between">
          <span class="text-[var(--ink-muted)]">开始时间</span>
          <span class="text-[var(--ink)]">{{ selectedTask.start_time }}</span>
        </div>
        <div v-if="selectedTask.end_time" class="flex justify-between">
          <span class="text-[var(--ink-muted)]">结束时间</span>
          <span class="text-[var(--ink)]">{{ selectedTask.end_time }}</span>
        </div>
        <!-- Checkpoints list -->
        <div v-if="selectedTask.checkpoints || selectedTask.points" class="border-t border-[var(--border-color)] pt-2 mt-2">
          <h4 class="text-xs font-semibold text-[var(--ink)] mb-1">打卡点列表</h4>
          <div class="max-h-40 overflow-y-auto space-y-1">
            <div
              v-for="(cp, i) in (selectedTask.checkpoints || selectedTask.points || [])"
              :key="i"
              class="flex items-center gap-2 px-2 py-1 rounded bg-[var(--glass)] text-xs"
            >
              <span class="w-5 h-5 rounded-full bg-[var(--accent)]/15 text-[var(--accent)] text-[10px] font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              <span class="text-[var(--ink)]">{{ cp.name || cp.label || `点 ${i + 1}` }}</span>
              <span v-if="cp.lat != null && cp.lng != null" class="text-[var(--ink-muted)] ml-auto">{{ Number(cp.lat).toFixed(4) }}, {{ Number(cp.lng).toFixed(4) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-center text-sm text-[var(--ink-muted)] py-4">
        请先选择一个任务
      </div>
    </AppModal>
  </div>
</template>
