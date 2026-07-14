<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { callAPI, callRawAPI } from '@/services/api'
import TabPanel from '@/components/common/TabPanel.vue'
import LogPanel from '@/components/main/LogPanel.vue'
import AppModal from '@/components/common/AppModal.vue'

const app = useAppStore()
const activeTab = ref('execute')

const tabs = [
  { key: 'execute', label: '执行' },
  { key: 'path', label: '路径' },
  { key: 'checkpoints', label: '打卡点' },
  { key: 'attendance', label: '签到' },
  { key: 'history', label: '历史' },
  { key: 'params', label: '参数' },
  { key: 'log', label: '日志' }
]

// ── Execute tab ──
const ignoreCompleted = ref(false)
const autoGenAll = ref(false)

const showAutoGenModal = ref(false)
const autoGenConfig = reactive({
  minTime: 20,
  maxTime: 30,
  minDist: 2000
})

async function startRun() {
  try {
    const result = await callRawAPI('/api/background_task/start', 'POST', {
      task_indices: [app.selectedTaskIndex],
      auto_generate: autoGenAll.value
    })
    if (result && result.success !== false) {
      app.isRunning = true
      app.addLog('执行已开始', 'INFO')
    } else {
      app.addLog('启动失败: ' + (result?.message || '未知错误'), 'ERROR')
    }
  } catch (e) {
    app.addLog('启动失败: ' + (e.message || e), 'ERROR')
  }
}

async function startAll() {
  try {
    const result = await callAPI('start_all_runs', {
      ignore_completed: ignoreCompleted.value,
      auto_generate: autoGenAll.value
    })
    if (result && result.success !== false) {
      app.isRunning = true
      app.addLog('所有任务已开始执行', 'INFO')
    } else {
      app.addLog('执行所有失败: ' + (result?.message || '未知错误'), 'ERROR')
    }
  } catch (e) {
    app.addLog('执行所有失败: ' + (e.message || e), 'ERROR')
  }
}

async function stopRun() {
  try {
    await callRawAPI('/api/background_task/stop', 'POST')
    app.isRunning = false
    app.addLog('跑步已停止', 'INFO')
  } catch (e) {
    app.addLog('停止失败: ' + (e.message || e), 'ERROR')
  }
}

// ── Path tools ──
async function autoGenPath() {
  showAutoGenModal.value = false
  try {
    const result = await callAPI('auto_generate_path_with_provider', {
      min_t_m: autoGenConfig.minTime,
      max_t_m: autoGenConfig.maxTime,
      min_d_m: autoGenConfig.minDist
    })
    app.addLog(result?.message || '路径自动生成完成', 'INFO')
  } catch (e) {
    app.addLog('自动生成路径失败: ' + (e.message || e), 'ERROR')
  }
}

async function processPath() {
  try {
    const result = await callAPI('process_path')
    app.addLog(result?.message || '路径处理完成', 'INFO')
  } catch (e) {
    app.addLog('处理路径失败: ' + (e.message || e), 'ERROR')
  }
}

async function clearPath() {
  try {
    const result = await callAPI('clear_current_task_draft')
    app.addLog(result?.message || '路径已清除', 'INFO')
  } catch (e) {
    app.addLog('清除路径失败: ' + (e.message || e), 'ERROR')
  }
}

async function exportPath() {
  try {
    const result = await callAPI('export_task_data')
    if (result?.data) {
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `path_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      app.addLog('路径已导出', 'INFO')
    } else {
      app.addLog(result?.message || '导出路径完成', 'INFO')
    }
  } catch (e) {
    app.addLog('导出路径失败: ' + (e.message || e), 'ERROR')
  }
}

// ── Checkpoints ──
const checkpoints = ref([])

async function loadCheckpoints() {
  try {
    const result = await callAPI('get_task_details', { index: app.selectedTaskIndex })
    checkpoints.value = result?.target_points || result?.checkpoints || result?.points || []
  } catch (e) {
    app.addLog('获取目标点失败: ' + (e.message || e), 'ERROR')
  }
}

// ── Attendance ──
const autoAttendance = ref(false)
const attendanceInterval = ref(30)
const attendanceRadius = ref(100)

async function toggleAutoAttendance() {
  try {
    await callAPI('update_param', { key: 'auto_attendance_enabled', value: autoAttendance.value })
    if (autoAttendance.value) {
      await callAPI('update_param', { key: 'auto_attendance_interval', value: attendanceInterval.value })
      await callAPI('update_param', { key: 'auto_attendance_radius', value: attendanceRadius.value })
    }
    app.addLog(autoAttendance.value ? '自动考勤已开启' : '自动考勤已关闭', 'INFO')
  } catch (e) {
    app.addLog('设置考勤失败: ' + (e.message || e), 'ERROR')
  }
}

// ── History ──
const historyList = ref([])

async function loadHistory() {
  try {
    const result = await callAPI('get_task_history', { index: app.selectedTaskIndex })
    historyList.value = result?.history || result?.records || []
  } catch (e) {
    app.addLog('获取历史记录失败: ' + (e.message || e), 'ERROR')
  }
}

// ── Parameters ──
const paramValues = reactive({})
const paramKeys = computed(() => Object.keys(app.pythonParams))
const hasParams = computed(() => paramKeys.value.length > 0)

function initParamValues() {
  for (const [k, v] of Object.entries(app.pythonParams)) {
    if (!(k in paramValues)) {
      paramValues[k] = v
    }
  }
}

async function loadParams() {
  try {
    const result = await callAPI('get_params')
    if (result) {
      app.pythonParams = result
      initParamValues()
    }
  } catch (e) {
    app.addLog('获取参数失败: ' + (e.message || e), 'ERROR')
  }
}

async function saveParams() {
  try {
    for (const [key, value] of Object.entries(paramValues)) {
      if (app.pythonParams[key] !== value) {
        await callAPI('update_param', { key, value })
      }
    }
    app.pythonParams = { ...paramValues }
    app.addLog('参数已保存', 'INFO')
  } catch (e) {
    app.addLog('保存参数失败: ' + (e.message || e), 'ERROR')
  }
}

function resetParams() {
  for (const k of Object.keys(paramValues)) {
    paramValues[k] = app.pythonParams[k]
  }
}

// ── Run data sync ──
const progressPercent = computed(() => {
  const rd = app.runData
  if (!rd) return 0
  if (rd.progress != null) return Math.min(100, Math.max(0, Number(rd.progress)))
  if (rd.total_distance && rd.current_distance) {
    return Math.min(100, (rd.current_distance / rd.total_distance) * 100)
  }
  return 0
})

const progressStatusText = computed(() => {
  if (app.isRunning) return '进行中'
  if (progressPercent.value >= 100) return '已完成'
  if (progressPercent.value > 0) return '已暂停'
  return '未开始'
})

function formatDuration(seconds) {
  if (seconds == null) return '--'
  const s = Number(seconds)
  if (isNaN(s)) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

function onTabChange(tab) {
  if (tab === 'checkpoints') loadCheckpoints()
  if (tab === 'history') loadHistory()
  if (tab === 'params') loadParams()
}

onMounted(() => {
  initParamValues()
})
</script>

<template>
  <div class="panel p-3">
    <TabPanel
      v-model="activeTab"
      :tabs="tabs"
      compact
      @update:model-value="onTabChange"
    >
      <!-- Execute tab -->
      <template #execute>
        <div class="space-y-3 pt-3">
          <div class="text-center p-3 rounded-lg border border-[var(--border-color)] bg-[var(--glass)]">
            <p class="text-sm text-[var(--ink-muted)]">已选任务总览</p>
            <p class="font-bold text-2xl text-[var(--accent)]">
              {{ app.runData?.total_distance != null ? (Number(app.runData.total_distance) / 1000).toFixed(2) + ' km' : '-- km' }}
              /
              {{ app.runData?.total_time != null ? formatDuration(app.runData.total_time) : '--:--' }}
            </p>
          </div>

          <div>
            <div class="h-2 bg-[var(--glass)] rounded-full overflow-hidden">
              <div
                class="h-full bg-[var(--accent)] rounded-full transition-all duration-500"
                :style="{ width: progressPercent + '%' }"
              ></div>
            </div>
            <div class="flex justify-between text-xs mt-1">
              <span class="text-[var(--ink-muted)]">{{ progressStatusText }}</span>
              <span class="text-[var(--ink-muted)]">{{ progressPercent.toFixed(1) }}%</span>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2">
            <button
              class="btn btn-primary justify-center"
              :disabled="app.isRunning || app.selectedTaskIndex < 0"
              @click="startRun"
            >
              开始执行
            </button>
            <button
              class="btn btn-danger justify-center"
              :disabled="!app.isRunning"
              @click="stopRun"
            >
              停止
            </button>
            <button
              class="btn btn-secondary justify-center"
              :disabled="app.isRunning"
              @click="startAll"
            >
              执行所有
            </button>
          </div>

          <div class="flex items-center justify-center space-x-4 pt-1">
            <label class="flex items-center gap-1.5 text-xs text-[var(--ink-secondary)] cursor-pointer">
              <input type="checkbox" v-model="ignoreCompleted" class="w-4 h-4 rounded accent-[var(--accent)]" />
              <span class="font-semibold">忽略已完成状态</span>
            </label>
            <label class="flex items-center gap-1.5 text-xs text-[var(--ink-secondary)] cursor-pointer">
              <input type="checkbox" v-model="autoGenAll" class="w-4 h-4 rounded accent-[var(--accent)]" />
              <span class="font-semibold">自动生成路径</span>
            </label>
          </div>
        </div>
      </template>

      <!-- Path tools tab -->
      <template #path>
        <div class="grid grid-cols-2 gap-2 pt-3">
          <button class="btn btn-primary justify-center" @click="showAutoGenModal = true">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            自动生成
          </button>
          <button class="btn btn-secondary justify-center" @click="processPath">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            处理路径
          </button>
          <button class="btn btn-danger justify-center" @click="clearPath">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            清除路径
          </button>
          <button class="btn btn-secondary justify-center" @click="exportPath">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            导出路径
          </button>
        </div>
      </template>

      <!-- Checkpoints tab -->
      <template #checkpoints>
        <div class="pt-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-[var(--ink-muted)]">{{ checkpoints.length }} 个打卡点</span>
            <button class="btn btn-ghost text-xs px-2 py-1" @click="loadCheckpoints">刷新</button>
          </div>
          <div class="max-h-60 overflow-y-auto space-y-1">
            <div v-if="checkpoints.length === 0" class="text-center text-sm text-[var(--ink-muted)] py-4">
              暂无打卡点
            </div>
            <div
              v-for="(cp, i) in checkpoints"
              :key="i"
              class="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--glass)] border border-[var(--border-color)]"
            >
              <span class="w-6 h-6 rounded-full bg-[var(--accent)]/15 text-[var(--accent)] text-xs font-bold flex items-center justify-center shrink-0">
                {{ i + 1 }}
              </span>
              <div class="min-w-0 flex-1">
                <div class="text-sm text-[var(--ink)] truncate">{{ cp.name || cp.label || `点 ${i + 1}` }}</div>
                <div class="text-[10px] text-[var(--ink-muted)]" v-if="cp.lat != null && cp.lng != null">
                  {{ Number(cp.lat).toFixed(6) }}, {{ Number(cp.lng).toFixed(6) }}
                </div>
              </div>
              <span
                v-if="cp.reached || cp.checked"
                class="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-600"
              >已达</span>
            </div>
          </div>
        </div>
      </template>

      <!-- Attendance tab -->
      <template #attendance>
        <div class="space-y-2 pt-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              v-model="autoAttendance"
              class="w-5 h-5 rounded accent-[var(--accent)] cursor-pointer flex-shrink-0"
              @change="toggleAutoAttendance()"
            />
            <span class="text-[var(--ink)] font-semibold">开启自动签到</span>
          </label>
          <p class="text-xs text-amber-600 leading-relaxed">
            ⏱ 自动签到启用后将在 120 分钟内自动关闭。
          </p>

          <div class="flex items-center gap-2">
            <label class="text-sm text-[var(--ink)] font-semibold flex-shrink-0">刷新间隔(秒)</label>
            <input
              type="number"
              v-model.number="attendanceInterval"
              class="input-field !py-1 w-full"
              min="10" max="300" step="5"
            />
          </div>

          <div class="flex items-center gap-2">
            <label class="text-sm text-[var(--ink)] font-semibold flex-shrink-0">随机半径(米)</label>
            <input
              type="number"
              v-model.number="attendanceRadius"
              class="input-field !py-1 w-full"
              min="0" max="1000" step="1"
            />
          </div>
          <p class="text-xs text-amber-600 leading-relaxed">
            ⚠ 若随机半径超过签到允许的最大范围，将自动缩减至该上限。
          </p>
        </div>
      </template>

      <!-- History tab -->
      <template #history>
        <div class="pt-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-[var(--ink-muted)]">{{ historyList.length }} 条记录</span>
            <button class="btn btn-ghost text-xs px-2 py-1" @click="loadHistory">刷新</button>
          </div>
          <div class="max-h-60 overflow-y-auto space-y-1">
            <div v-if="historyList.length === 0" class="text-center text-sm text-[var(--ink-muted)] py-4">
              暂无历史记录
            </div>
            <div
              v-for="(record, i) in historyList"
              :key="record.id || i"
              class="px-3 py-2 rounded-lg bg-[var(--glass)] border border-[var(--border-color)]"
            >
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-[var(--ink)]">{{ record.name || record.task_name || `记录 ${i + 1}` }}</span>
                <span
                  class="text-[10px] px-1.5 py-0.5 rounded-full"
                  :class="record.status === 'completed' ? 'bg-green-500/15 text-green-600' : 'bg-gray-500/15 text-gray-500'"
                >
                  {{ record.status === 'completed' ? '完成' : record.status || '--' }}
                </span>
              </div>
              <div class="flex gap-3 text-[10px] text-[var(--ink-muted)] mt-1">
                <span v-if="record.distance">{{ (Number(record.distance) / 1000).toFixed(2) }} km</span>
                <span v-if="record.duration">{{ record.duration }}</span>
                <span v-if="record.date || record.time">{{ record.date || record.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Parameters tab -->
      <template #params>
        <div class="pt-3 space-y-4">
          <div v-if="!hasParams" class="text-center text-sm text-[var(--ink-muted)] py-4">
            暂无参数数据
          </div>
          <template v-else>
            <div class="space-y-2">
              <div v-for="key in paramKeys" :key="key">
                <div v-if="typeof paramValues[key] === 'boolean'">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" v-model="paramValues[key]" class="w-4 h-4 rounded accent-[var(--accent)]" />
                    <span class="text-sm text-[var(--ink)]">{{ key }}</span>
                  </label>
                </div>
                <div v-else>
                  <label class="text-xs text-[var(--ink-muted)] block mb-1">{{ key }}</label>
                  <input
                    v-if="typeof paramValues[key] === 'number'"
                    type="number"
                    v-model.number="paramValues[key]"
                    class="input-field"
                  />
                  <input
                    v-else
                    type="text"
                    v-model="paramValues[key]"
                    class="input-field"
                  />
                </div>
              </div>
            </div>
            <div class="flex gap-2 pt-2 border-t border-[var(--border-color)]">
              <button class="btn btn-primary flex-1 justify-center" @click="saveParams">保存参数</button>
              <button class="btn btn-secondary flex-1 justify-center" @click="resetParams">恢复默认</button>
            </div>
          </template>
        </div>
      </template>

      <!-- Log tab -->
      <template #log>
        <div class="pt-3 h-64">
          <LogPanel :logs="app.logs" @clear="app.clearLogs()" />
        </div>
      </template>
    </TabPanel>

    <!-- Auto-generate path config modal -->
    <AppModal
      :visible="showAutoGenModal"
      title="自动生成路线配置"
      width="max-w-sm"
      @close="showAutoGenModal = false"
    >
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <label class="w-32 text-[var(--ink)] font-semibold">最短时间(分钟)</label>
          <input type="number" v-model.number="autoGenConfig.minTime" class="input-field w-full" />
        </div>
        <div class="flex items-center gap-2">
          <label class="w-32 text-[var(--ink)] font-semibold">最长时间(分钟)</label>
          <input type="number" v-model.number="autoGenConfig.maxTime" class="input-field w-full" />
        </div>
        <div class="flex items-center gap-2">
          <label class="w-32 text-[var(--ink)] font-semibold">最短距离(米)</label>
          <input type="number" v-model.number="autoGenConfig.minDist" class="input-field w-full" />
        </div>
        <div class="flex justify-end gap-3 pt-4">
          <button class="btn btn-ghost border border-[var(--border-color)]" @click="showAutoGenModal = false">取消</button>
          <button class="btn btn-primary" @click="autoGenPath">生成</button>
        </div>
      </div>
    </AppModal>
  </div>
</template>
