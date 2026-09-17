<script setup>
import { ref } from 'vue'
import { useAppStore } from '@/stores/app'
import { callAPI } from '@/services/api'

const app = useAppStore()
const refreshing = ref(false)

async function refreshTasks() {
  refreshing.value = true
  try {
    const result = await callAPI('load_tasks')
    if (result?.tasks) app.tasks = result.tasks
  } catch (error) {
    app.addLog('刷新任务列表失败: ' + (error.message || error), 'ERROR')
  } finally {
    refreshing.value = false
  }
}

function selectTask(index) {
  app.selectedTaskIndex = index
}
</script>

<template>
  <div class="mobile-card flex min-h-screen flex-col p-0">
    <div class="mb-4 flex items-center justify-between border-b border-green-100 p-4 pb-3">
      <div class="flex items-center gap-2">
        <svg class="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
          />
        </svg>
        <h3 class="text-xl font-bold text-green-700">任务列表</h3>
      </div>
      <div class="rounded-full bg-green-50 px-3 py-1 text-sm text-slate-600">
        {{ app.tasks.length }} 个任务
      </div>
    </div>

    <div class="flex-1 space-y-2 px-4">
      <button
        v-for="(task, index) in app.tasks"
        :key="task.id || index"
        class="w-full rounded-xl border p-3 text-left transition"
        :class="index === app.selectedTaskIndex ? 'border-sky-300 bg-sky-50' : 'border-slate-200 bg-white'"
        @click="selectTask(index)"
      >
        <div class="flex items-center justify-between gap-3">
          <span class="truncate text-sm font-medium text-slate-700">
            {{ task.name || task.task_name || `任务 ${index + 1}` }}
          </span>
          <span class="text-xs text-slate-400">{{ task.status || '待执行' }}</span>
        </div>
      </button>
      <p v-if="app.tasks.length === 0" class="py-8 text-center text-sm text-slate-400">
        暂无任务
      </p>
    </div>

    <div class="mt-auto grid grid-cols-2 gap-2 border-t border-slate-100 p-4">
      <button
        class="flex items-center justify-center gap-1 rounded-lg bg-green-50 px-4 py-2 text-sm font-medium text-green-600"
        :disabled="refreshing"
        @click="refreshTasks"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
    </div>
  </div>
</template>
