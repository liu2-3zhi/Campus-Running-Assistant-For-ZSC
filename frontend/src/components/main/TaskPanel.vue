<script setup>
import { useAppStore } from '@/stores/app'
import { callAPI, callRawAPI } from '@/services/api'
import { ref, computed } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import TaskDetails from './TaskDetails.vue'
import { useMapStore } from '@/stores/map'
import { loadSelectedTask, taskName, taskStatus, taskPathStatus } from './taskData'

const app = useAppStore()
const mapStore = useMapStore()
const refreshing = ref(false)
const selecting = ref(false)
const showTaskDetail = ref(false)

const selectedTask = computed(() => {
  if (app.selectedTaskIndex < 0 || app.selectedTaskIndex >= app.tasks.length) return null
  return app.runData || app.tasks[app.selectedTaskIndex]
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

async function selectTask(index) {
  if (selecting.value) return
  selecting.value = true
  try {
    await loadSelectedTask(app, index, { callAPI, callRawAPI }, mapStore.isDrawing)
  } catch (error) {
    app.addLog(error.message || String(error), 'ERROR')
  } finally {
    selecting.value = false
  }
}

function statusLabel(status) {
  return taskStatus({ status }).label
}
</script>

<template>
  <div id="task-panel-desktop-inline" class="panel flex min-h-0 flex-grow flex-col rounded-xl p-4">
    <!-- Header -->
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-lg font-bold text-slate-800">
        任务列表
      </h3>
      <div class="flex gap-2">
      <button
        class="btn btn-ghost !px-3 !py-1"
        @click="openTaskDetail"
        title="查看任务详情"
      >
        任务详情
      </button>
      <button
        class="btn btn-ghost !px-3 !py-1"
        :disabled="refreshing"
        @click="refreshTasks"
        title="刷新任务"
      >
        刷新
      </button>
      </div>
    </div>

    <!-- Task list -->
    <div class="-mr-2 flex-grow space-y-1 overflow-y-auto pr-2">
      <div v-if="app.tasks.length === 0" class="text-center text-sm text-[var(--ink-muted)] py-4">
        暂无任务
      </div>
      <button
        v-for="(task, index) in app.tasks"
        :key="task.errand_schedule || task.id || index"
        class="w-full rounded-xl border border-transparent p-3 text-left transition-colors hover:bg-white/70"
        :class="{ 'selected bg-sky-50 border-sky-300': index === app.selectedTaskIndex, 'opacity-60': task.status === 1 }"
        :disabled="selecting || refreshing"
        @click="selectTask(index)"
      >
        <p class="truncate text-sm font-bold text-slate-700">{{ taskName(task, index) }}</p>
        <div class="mt-2 flex items-center justify-between gap-2 text-xs">
          <span class="flex shrink-0 items-center gap-1 font-semibold" :class="taskStatus(task).className">{{ taskStatus(task).icon }} {{ taskStatus(task).label }}</span>
          <span class="text-slate-500">{{ task.info_text || '' }}</span>
          <span class="badge">{{ taskPathStatus(task) }}</span>
        </div>
      </button>
    </div>

    <!-- Task detail modal -->
    <AppModal
      :visible="showTaskDetail"
      title="任务详情"
      width="max-w-md"
      @close="showTaskDetail = false"
    >
      <TaskDetails :task="selectedTask" />
    </AppModal>
  </div>
</template>
