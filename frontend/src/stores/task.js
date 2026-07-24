import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref([])
  const selectedIndex = ref(-1)
  const isRunning = ref(false)
  const runData = ref(null)
  const isLoading = ref(false)

  const selectedTask = computed(() =>
    selectedIndex.value >= 0 && selectedIndex.value < tasks.value.length
      ? tasks.value[selectedIndex.value]
      : null
  )

  const taskCount = computed(() => tasks.value.length)

  async function fetchTasks() {
    isLoading.value = true
    try {
      const data = await callAPI('load_tasks')
      if (data?.tasks) {
        tasks.value = data.tasks
        if (selectedIndex.value >= tasks.value.length) {
          selectedIndex.value = tasks.value.length > 0 ? 0 : -1
        }
      }
    } catch (_) {}
    isLoading.value = false
  }

  function selectTask(index) {
    selectedIndex.value = index
  }

  async function startRun(params = {}) {
    try {
      const data = await callRawAPI('/api/background_task/start', 'POST', {
        task_indices: params.task_indices || [selectedIndex.value],
        auto_generate: params.auto_generate || false
      })
      if (data && data.success !== false) {
        isRunning.value = true
        runData.value = data
      }
      return data
    } catch (e) {
      throw e
    }
  }

  async function stopRun() {
    try {
      const data = await callRawAPI('/api/background_task/stop', 'POST')
      isRunning.value = false
      runData.value = null
      return data
    } catch (e) {
      throw e
    }
  }

  function onTaskCompleted(taskIndex) {
    isRunning.value = false
    if (taskIndex !== undefined && taskIndex < tasks.value.length) {
      tasks.value[taskIndex].status = 'completed'
    }
  }

  function onRunStopped() {
    isRunning.value = false
    runData.value = null
  }

  // 运行统计
  const stats = ref({
    liveDistance: 0,
    totalDistance: 0,
    liveTime: 0,
    totalTime: 0,
    remainingTime: 0,
    currentLocation: '',
    processedPoints: 0,
    totalPoints: 0,
  })

  function updateStats(data) {
    Object.assign(stats.value, data)
  }

  return {
    tasks, selectedIndex, selectedTask, taskCount,
    isRunning, runData, isLoading, stats,
    fetchTasks, selectTask, startRun, stopRun,
    onTaskCompleted, onRunStopped, updateStats,
  }
})
