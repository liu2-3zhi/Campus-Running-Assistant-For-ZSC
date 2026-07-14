<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useMapStore } from '@/stores/map'
import { useNotificationStore } from '@/stores/notification'
import { callAPI, callRawAPI } from '@/services/api'
import { connectWebSocket, disconnectWebSocket } from '@/services/socket'
import MapContainer from '@/components/map/MapContainer.vue'
import NotificationsPanel from '@/components/main/NotificationsPanel.vue'
import AppModal from '@/components/common/AppModal.vue'

const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const notifStore = useNotificationStore()
const mapStore = useMapStore()

// --- State ---
const loading = ref(false)
const selectAll = ref(false)
const selectedIds = ref(new Set())
const showParamsModal = ref(false)
const showNotifications = ref(false)
const mobileTab = ref('accounts') // 'accounts' | 'map' | 'log'

// Random delay
const delaySettings = reactive({
  useDelay: true,
  minDelay: 0,
  maxDelay: 300,
  runOnlyIncomplete: true,
})

// Add account
const addAccountMode = ref('select') // 'select' | 'manual'
const selectedUser = ref('')
const manualInput = reactive({
  username: '',
  password: '',
  tag: '',
})

// Global params
const globalParams = reactive({
  distance: '',
  pace: '',
  runMode: '',
})

// Computed
const accounts = computed(() => appStore.multiAccounts)
const statuses = computed(() => appStore.multiStatus)
const logs = computed(() => appStore.logs)
const configUsers = computed(() => appStore.users)

let autoRefreshTimer = null

const selectedCount = computed(() => selectedIds.value.size)
const allSelected = computed(() =>
  accounts.value.length > 0 && selectedIds.value.size === accounts.value.length
)

// --- Account status helpers ---
function getStatusBadge(account) {
  const username = account.username || account.name
  const status = statuses.value[username]
  if (!status) return { text: '空闲', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' }
  const state = status.state || status.status || 'idle'
  const map = {
    idle: { text: '空闲', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
    running: { text: '运行中', cls: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' },
    completed: { text: '已完成', cls: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' },
    failed: { text: '失败', cls: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' },
    stopped: { text: '已停止', cls: 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' },
    waiting: { text: '等待中', cls: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400' },
    queued: { text: '排队中', cls: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400' },
  }
  return map[state] || { text: state, cls: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' }
}

function getAccountName(account) {
  return account.username || account.name || account.id || ''
}

// --- Selection ---
function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value.clear()
    selectAll.value = false
  } else {
    accounts.value.forEach(a => selectedIds.value.add(getAccountName(a)))
    selectAll.value = true
  }
}

function toggleSelect(account) {
  const name = getAccountName(account)
  if (selectedIds.value.has(name)) {
    selectedIds.value.delete(name)
  } else {
    selectedIds.value.add(name)
  }
  selectAll.value = allSelected.value
}

function isSelected(account) {
  return selectedIds.value.has(getAccountName(account))
}

// --- API Actions ---
async function loadAccounts() {
  loading.value = true
  try {
    const data = await callAPI('get_multi_accounts')
    if (data?.accounts) {
      appStore.multiAccounts = data.accounts
    }
  } catch (e) {
    appStore.addLog(`加载账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
  loading.value = false
}

async function checkOverdue() {
  try {
    const result = await callAPI('check_overdue')
    if (result?.overdue) {
      window.Swal?.fire({ title: '账号欠费', text: '请先充值后再执行', icon: 'warning' })
      return true
    }
  } catch (_) {}
  return false
}

async function startAll() {
  if (await checkOverdue()) return
  try {
    await callAPI('start_all_accounts', {
      min_delay: delaySettings.minDelay,
      max_delay: delaySettings.maxDelay,
      use_delay: delaySettings.useDelay,
      only_incomplete: delaySettings.runOnlyIncomplete,
    })
    appStore.addLog('已发送全部启动指令', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部启动失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopAll() {
  try {
    await callAPI('stop_all_accounts')
    appStore.addLog('已发送全部停止指令', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部停止失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function startSelected() {
  if (selectedCount.value === 0) return
  if (await checkOverdue()) return
  try {
    await callAPI('start_selected_accounts', {
      usernames: [...selectedIds.value],
      min_delay: delaySettings.minDelay,
      max_delay: delaySettings.maxDelay,
      use_delay: delaySettings.useDelay,
      only_incomplete: delaySettings.runOnlyIncomplete,
    })
    appStore.addLog(`已启动 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`启动选中账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopSelected() {
  if (selectedCount.value === 0) return
  try {
    await callAPI('stop_selected_accounts', {
      usernames: [...selectedIds.value],
    })
    appStore.addLog(`已停止 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`停止选中账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function refreshAccount(account) {
  try {
    await callAPI('refresh_account', { username: getAccountName(account) })
    appStore.addLog(`已刷新 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function startAccount(account) {
  try {
    await callAPI('start_single_account', {
      username: getAccountName(account),
      min_delay: delaySettings.minDelay,
      max_delay: delaySettings.maxDelay,
    })
    appStore.addLog(`已启动 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`启动失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopAccount(account) {
  try {
    await callAPI('stop_single_account', { username: getAccountName(account) })
    appStore.addLog(`已停止 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`停止失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function removeAccount(account) {
  try {
    await callAPI('remove_account', { username: getAccountName(account) })
    selectedIds.value.delete(getAccountName(account))
    appStore.addLog(`已移除 ${getAccountName(account)}`, 'INFO', 'Multi')
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`移除失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function removeSelected() {
  if (selectedCount.value === 0) return
  const swalResult = await window.Swal?.fire({
    title: '确认移除选中',
    text: `确定要移除选中的 ${selectedCount.value} 个账号吗？此操作不可撤销。`,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: '确认移除',
    cancelButtonText: '取消',
  })
  if (!swalResult?.isConfirmed) return
  try {
    await callAPI('remove_accounts', { usernames: [...selectedIds.value] })
    appStore.addLog(`已移除 ${selectedCount.value} 个账号`, 'INFO', 'Multi')
    selectedIds.value.clear()
    selectAll.value = false
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`批量移除失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function removeAll() {
  const swalResult = await window.Swal?.fire({
    title: '确认移除全部',
    text: '确定要移除所有账号吗？此操作不可撤销，所有账号数据将丢失！',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: '确认移除',
    cancelButtonText: '取消',
  })
  if (!swalResult?.isConfirmed) return
  try {
    await callAPI('remove_all_accounts')
    selectedIds.value.clear()
    selectAll.value = false
    appStore.addLog('已移除全部账号', 'INFO', 'Multi')
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`移除全部失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function refreshSelected() {
  if (selectedCount.value === 0) return
  try {
    await callAPI('refresh_accounts', { usernames: [...selectedIds.value] })
    appStore.addLog(`已刷新 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`批量刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function refreshAll() {
  try {
    await callAPI('refresh_all_accounts')
    appStore.addLog('已刷新全部账号', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Add account ---
async function addFromConfig() {
  if (!selectedUser.value) return
  try {
    await callAPI('add_account', { username: selectedUser.value })
    appStore.addLog(`已添加账号: ${selectedUser.value}`, 'INFO', 'Multi')
    selectedUser.value = ''
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function addAllFromConfig() {
  try {
    await callRawAPI('/api/multi_load_accounts_from_config', 'POST', {})
    appStore.addLog('已添加全部配置用户', 'INFO', 'Multi')
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加全部失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function addManual() {
  if (!manualInput.username || !manualInput.password) return
  try {
    await callAPI('add_account', {
      username: manualInput.username,
      password: manualInput.password,
      tag: manualInput.tag || undefined,
    })
    appStore.addLog(`已添加账号: ${manualInput.username}`, 'INFO', 'Multi')
    manualInput.username = ''
    manualInput.password = ''
    manualInput.tag = ''
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Import/Export ---
async function importExcel() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.xlsx,.xls,.csv'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const reader = new FileReader()
      const base64 = await new Promise((resolve, reject) => {
        reader.onload = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      await callAPI('import_accounts_excel', {
        file_data: base64,
        file_name: file.name,
      })
      appStore.addLog(`Excel 导入成功: ${file.name}`, 'INFO', 'Multi')
      await loadAccounts()
    } catch (err) {
      appStore.addLog(`Excel 导入失败: ${err.message}`, 'ERROR', 'Multi')
    }
  }
  input.click()
}

async function exportExcel() {
  try {
    const data = await callAPI('export_accounts_excel')
    if (data?.file_data) {
      const link = document.createElement('a')
      link.href = data.file_data
      link.download = data.file_name || 'accounts.xlsx'
      link.click()
      appStore.addLog('Excel 导出成功', 'INFO', 'Multi')
    }
  } catch (e) {
    appStore.addLog(`Excel 导出失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function downloadTemplate() {
  try {
    const data = await callAPI('get_accounts_template')
    if (data?.file_data) {
      const link = document.createElement('a')
      link.href = data.file_data
      link.download = data.file_name || 'template.xlsx'
      link.click()
    }
  } catch (e) {
    appStore.addLog(`下载模板失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Global params ---
async function applyGlobalParams() {
  try {
    await callAPI('set_global_params', {
      distance: globalParams.distance ? parseFloat(globalParams.distance) : undefined,
      pace: globalParams.pace || undefined,
      run_mode: globalParams.runMode || undefined,
    })
    appStore.addLog('全局参数已应用', 'INFO', 'Multi')
    showParamsModal.value = false
  } catch (e) {
    appStore.addLog(`设置全局参数失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Navigation ---
function goToAdmin() {
  router.push({ name: 'main' })
}

// --- Auto refresh (task 8) ---
function startAutoRefresh() {
  stopAutoRefresh()
  autoRefreshTimer = setInterval(async () => {
    try {
      const result = await callAPI('get_multi_accounts')
      if (result?.accounts) {
        appStore.multiAccounts = result.accounts
      }
    } catch (_) {}
  }, 1000)
}
function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

// --- Sync runOnlyIncomplete to backend (task 10) ---
async function syncRunOnlyIncomplete() {
  try {
    await callAPI('set_multi_run_only_incomplete', { value: delaySettings.runOnlyIncomplete })
  } catch (_) {}
}

async function exitMultiMode() {
  stopAutoRefresh()
  try {
    await callRawAPI('/api/background_task/stop', 'POST')
  } catch (_) {}
  appStore.isMultiMode = false
  appStore.currentView = 'main'
  router.push({ name: 'main' })
}

// --- Log level color ---
function logLevelColor(level) {
  const colors = {
    INFO: 'var(--ink-secondary)',
    WARN: 'var(--warning)',
    WARNING: 'var(--warning)',
    ERROR: 'var(--danger)',
    SUCCESS: 'var(--success)',
    DEBUG: 'var(--ink-muted)',
  }
  return colors[(level || '').toUpperCase()] || 'var(--ink-secondary)'
}

// --- Lifecycle ---
onMounted(async () => {
  appStore.currentView = 'multi'
  appStore.isMultiMode = true
  try {
    await callAPI('enter_multi_account_mode')
    appStore.addLog('已进入多账号模式', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`进入多账号模式失败: ${e.message}`, 'ERROR', 'Multi')
  }
  await loadAccounts()

  // Load config users list if empty
  if (configUsers.value.length === 0) {
    try {
      const data = await callAPI('get_initial_data')
      if (data?.users) {
        appStore.users = data.users
      }
    } catch (_) {}
  }

  // Start auto refresh polling
  startAutoRefresh()
  connectWebSocket()
})

onUnmounted(() => {
  stopAutoRefresh()
  disconnectWebSocket()
  appStore.isMultiMode = false
})

const multiMapRef = ref(null)

watch(() => appStore.multiPositions, (positions) => {
  const mapComp = multiMapRef.value
  if (!mapComp) return
  mapComp.clearOverlays()
  const coords = []
  for (const [username, pos] of Object.entries(positions)) {
    if (pos.lon != null && pos.lat != null) {
      mapComp.addMarker([pos.lon, pos.lat], { title: pos.name || username })
      coords.push([pos.lon, pos.lat])
    }
  }
  if (coords.length > 0) {
    mapComp.fitView(coords)
  }
}, { deep: true })
</script>

<template>
  <div class="min-h-screen p-4 md:p-6" style="background: var(--base-color)">
    <!-- ====== TOP BAR ====== -->
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-bold" style="color: var(--ink)">
          多账号管理
        </h1>
        <span
          class="rounded-full px-2.5 py-0.5 text-xs font-medium"
          style="background: var(--glass); color: var(--ink-secondary); border: 1px solid var(--border-color)"
        >
          {{ accounts.length }} 个账号
        </span>
      </div>
      <div class="flex items-center gap-2">
        <!-- Notifications toggle -->
        <button
          class="btn btn-ghost relative p-2"
          title="通知"
          @click="showNotifications = !showNotifications"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span
            v-if="notifStore.unreadCount > 0"
            class="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs font-medium text-white"
            style="background: var(--danger)"
          >
            {{ notifStore.unreadCount > 9 ? '9+' : notifStore.unreadCount }}
          </span>
        </button>
        <button class="btn btn-secondary text-sm" @click="goToAdmin">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          管理面板
        </button>
        <button class="btn btn-danger text-sm" @click="exitMultiMode">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          退出多账号
        </button>
      </div>
    </div>

    <!-- Notifications dropdown -->
    <transition name="slide-up">
      <div v-if="showNotifications" class="mb-4">
        <NotificationsPanel />
      </div>
    </transition>

    <!-- ====== MOBILE TAB NAVIGATION ====== -->
    <div class="mb-4 flex gap-1 overflow-x-auto md:hidden">
      <button
        class="tab-button shrink-0"
        :class="{ active: mobileTab === 'accounts' }"
        @click="mobileTab = 'accounts'"
      >
        账号管理
      </button>
      <button
        class="tab-button shrink-0"
        :class="{ active: mobileTab === 'map' }"
        @click="mobileTab = 'map'"
      >
        地图
      </button>
      <button
        class="tab-button shrink-0"
        :class="{ active: mobileTab === 'log' }"
        @click="mobileTab = 'log'"
      >
        日志
      </button>
    </div>

    <!-- ====== MAIN GRID (desktop: 2 columns) ====== -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- ====== LEFT COLUMN: Account Management ====== -->
      <div
        class="space-y-4"
        :class="{ 'hidden md:block': mobileTab !== 'accounts' }"
      >
        <!-- Global Controls -->
        <div class="panel p-4">
          <h3 class="mb-3 text-sm font-semibold" style="color: var(--ink)">
            全局控制
          </h3>

          <!-- Start/Stop all -->
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn btn-success text-sm" @click="startAll">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              全部启动
            </button>
            <button class="btn btn-danger text-sm" @click="stopAll">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              全部停止
            </button>
            <button class="btn btn-secondary text-sm" @click="showParamsModal = true">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              全局参数
            </button>
          </div>

          <!-- Use random delay switch (task 4) -->
          <label class="mb-2 flex cursor-pointer items-center gap-2 text-sm font-semibold" style="color: var(--ink)">
            <input
              v-model="delaySettings.useDelay"
              type="checkbox"
              class="h-4 w-4 rounded"
            />
            启用随机启动延迟
          </label>

          <!-- Random delay settings -->
          <div class="mb-3 grid grid-cols-2 gap-2" :class="{ 'opacity-50 pointer-events-none': !delaySettings.useDelay }">
            <div>
              <label class="mb-1 block text-xs" style="color: var(--ink-secondary)">最小延迟(秒)</label>
              <input
                v-model.number="delaySettings.minDelay"
                type="number"
                min="0"
                max="300"
                class="input-field text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs" style="color: var(--ink-secondary)">最大延迟(秒)</label>
              <input
                v-model.number="delaySettings.maxDelay"
                type="number"
                min="0"
                max="300"
                class="input-field text-sm"
              />
            </div>
          </div>

          <!-- Run only incomplete (task 10: sync to backend on change) -->
          <label class="flex cursor-pointer items-center gap-2 text-sm" style="color: var(--ink-secondary)">
            <input
              v-model="delaySettings.runOnlyIncomplete"
              type="checkbox"
              class="h-4 w-4 rounded"
              @change="syncRunOnlyIncomplete"
            />
            仅运行未完成账号
          </label>
        </div>

        <!-- Account List Header -->
        <div class="panel p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-3">
              <label class="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  class="h-4 w-4 rounded"
                  @change="toggleSelectAll"
                />
                <span style="color: var(--ink-secondary)">全选</span>
              </label>
              <span class="text-xs" style="color: var(--ink-muted)">
                已选 {{ selectedCount }} / {{ accounts.length }}
              </span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <button class="btn btn-secondary px-2.5 py-1.5 text-xs" title="导入 Excel" @click="importExcel">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                导入
              </button>
              <button class="btn btn-secondary px-2.5 py-1.5 text-xs" title="导出 Excel" @click="exportExcel">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                导出
              </button>
              <button class="btn btn-secondary px-2.5 py-1.5 text-xs" title="下载模板" @click="downloadTemplate">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                模板
              </button>
            </div>
          </div>

          <!-- Account list -->
          <div class="max-h-[400px] space-y-2 overflow-y-auto">
            <div
              v-if="loading && accounts.length === 0"
              class="py-6 text-center text-sm"
              style="color: var(--ink-muted)"
            >
              加载中...
            </div>

            <div
              v-if="!loading && accounts.length === 0"
              class="py-6 text-center text-sm"
              style="color: var(--ink-muted)"
            >
              暂无账号，请添加
            </div>

            <div
              v-for="account in accounts"
              :key="getAccountName(account)"
              class="rounded-lg p-3 transition-colors"
              :style="{
                background: isSelected(account) ? 'var(--glass)' : 'transparent',
                border: '1px solid ' + (isSelected(account) ? 'var(--accent)' : 'var(--border-color)'),
              }"
            >
              <!-- Top row: checkbox, name, tag, status -->
              <div class="flex items-start gap-3">
                <!-- Checkbox -->
                <input
                  type="checkbox"
                  :checked="isSelected(account)"
                  class="mt-1 h-4 w-4 shrink-0 rounded"
                  @change="toggleSelect(account)"
                />

                <!-- Name + tag -->
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="truncate text-sm font-bold" style="color: var(--ink)">
                      {{ account.name || getAccountName(account) }}
                    </span>
                    <span
                      v-if="account.name && account.username && account.name !== account.username"
                      class="text-xs"
                      style="color: var(--ink-muted)"
                    >
                      ({{ account.username }})
                    </span>
                  </div>
                  <span
                    v-if="account.tag"
                    class="mt-0.5 inline-block rounded px-1.5 py-0.5 text-xs font-medium"
                    style="background: rgba(168,85,247,0.1); color: rgb(168,85,247)"
                  >
                    {{ account.tag }}
                  </span>
                </div>

                <!-- Status badge -->
                <span
                  class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="getStatusBadge(account).cls"
                >
                  {{ account.status_text || getStatusBadge(account).text }}
                </span>
              </div>

              <!-- Task summary stats (if available) -->
              <div v-if="account.summary" class="mt-2 border-t pt-2" style="border-color: var(--border-color)">
                <div class="grid grid-cols-5 gap-1 text-center text-xs" style="color: var(--ink-secondary)">
                  <div>
                    总数: <span class="font-bold" style="color: var(--ink)">{{ account.summary.total ?? 0 }}</span>
                  </div>
                  <div>
                    完成: <span class="font-bold" style="color: var(--success)">{{ account.summary.completed ?? 0 }}</span>
                  </div>
                  <div>
                    未开始: <span class="font-bold" style="color: var(--ink-secondary)">{{ account.summary.not_started ?? 0 }}</span>
                  </div>
                  <div>
                    可跑: <span class="font-bold" style="color: var(--warning)">{{ account.summary.executable ?? 0 }}</span>
                  </div>
                  <div>
                    过期: <span class="font-bold" style="color: var(--danger)">{{ account.summary.expired ?? 0 }}</span>
                  </div>
                </div>
                <!-- Attendance stats -->
                <div
                  v-if="account.summary.att_pending != null || account.summary.att_completed != null || account.summary.att_expired != null"
                  class="mt-1 grid grid-cols-3 gap-1 border-t pt-1 text-center text-xs"
                  style="border-color: var(--border-color); color: var(--ink-secondary)"
                >
                  <div title="待签到任务">
                    待签: <span class="font-bold" style="color: var(--accent)">{{ account.summary.att_pending ?? 0 }}</span>
                  </div>
                  <div title="已签到任务">
                    已签: <span class="font-bold" style="color: var(--success)">{{ account.summary.att_completed ?? 0 }}</span>
                  </div>
                  <div title="已过期签到">
                    过期: <span class="font-bold" style="color: var(--danger)">{{ account.summary.att_expired ?? 0 }}</span>
                  </div>
                </div>
                <!-- Progress bar -->
                <div v-if="account.summary.total > 0" class="mt-1.5">
                  <div class="h-1.5 overflow-hidden rounded-full" style="background: var(--glass)">
                    <div
                      class="h-1.5 rounded-full transition-all"
                      style="background: var(--accent)"
                      :style="{ width: Math.round((account.summary.completed / account.summary.total) * 100) + '%' }"
                    ></div>
                  </div>
                </div>
              </div>

              <!-- Action buttons -->
              <div class="mt-2 flex justify-end gap-1 border-t pt-2" style="border-color: var(--border-color)">
                <button
                  class="btn btn-ghost p-1.5"
                  title="刷新"
                  @click="refreshAccount(account)"
                >
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
                  </svg>
                </button>
                <button
                  class="btn btn-ghost p-1.5"
                  title="启动"
                  @click="startAccount(account)"
                >
                  <svg class="h-3.5 w-3.5" style="color: var(--success)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  </svg>
                </button>
                <button
                  class="btn btn-ghost p-1.5"
                  title="停止"
                  @click="stopAccount(account)"
                >
                  <svg class="h-3.5 w-3.5" style="color: var(--danger)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                  </svg>
                </button>
                <button
                  class="btn btn-ghost p-1.5"
                  title="移除"
                  @click="removeAccount(account)"
                >
                  <svg class="h-3.5 w-3.5" style="color: var(--danger)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- Batch operations -->
          <div v-if="accounts.length > 0" class="mt-3 flex flex-wrap gap-1.5 border-t pt-3" style="border-color: var(--border-color)">
            <button class="btn btn-secondary px-2.5 py-1.5 text-xs" :disabled="selectedCount === 0" @click="refreshSelected">
              刷新选中
            </button>
            <button class="btn btn-secondary px-2.5 py-1.5 text-xs" @click="refreshAll">
              刷新全部
            </button>
            <button class="btn btn-success px-2.5 py-1.5 text-xs" :disabled="selectedCount === 0" @click="startSelected">
              启动选中
            </button>
            <button class="btn btn-warning px-2.5 py-1.5 text-xs" :disabled="selectedCount === 0" @click="stopSelected">
              停止选中
            </button>
            <button class="btn btn-danger px-2.5 py-1.5 text-xs" :disabled="selectedCount === 0" @click="removeSelected">
              移除选中
            </button>
            <button class="btn btn-danger px-2.5 py-1.5 text-xs" @click="removeAll">
              移除全部
            </button>
          </div>
        </div>

        <!-- Add Account -->
        <div class="panel p-4">
          <h3 class="mb-3 text-sm font-semibold" style="color: var(--ink)">
            添加账号
          </h3>

          <!-- Mode toggle -->
          <div class="mb-3 flex gap-1">
            <button
              class="tab-button"
              :class="{ active: addAccountMode === 'select' }"
              @click="addAccountMode = 'select'"
            >
              从配置选择
            </button>
            <button
              class="tab-button"
              :class="{ active: addAccountMode === 'manual' }"
              @click="addAccountMode = 'manual'"
            >
              手动输入
            </button>
          </div>

          <!-- Select from config -->
          <div v-if="addAccountMode === 'select'" class="flex gap-2">
            <select
              v-model="selectedUser"
              class="select-field flex-1 text-sm"
            >
              <option value="">请选择用户</option>
              <option
                v-for="user in configUsers"
                :key="typeof user === 'string' ? user : user.username || user.name"
                :value="typeof user === 'string' ? user : user.username || user.name"
              >
                {{ typeof user === 'string' ? user : user.username || user.name }}
              </option>
            </select>
            <button
              class="btn btn-primary shrink-0 text-sm"
              :disabled="!selectedUser"
              @click="addFromConfig"
            >
              添加
            </button>
            <button
              class="btn btn-secondary shrink-0 text-sm"
              @click="addAllFromConfig"
            >
              添加全部
            </button>
          </div>

          <!-- Manual input -->
          <div v-else class="space-y-2">
            <input
              v-model="manualInput.username"
              type="text"
              class="input-field text-sm"
              placeholder="账号 (必填)"
            />
            <input
              v-model="manualInput.password"
              type="password"
              class="input-field text-sm"
              placeholder="密码 (必填)"
            />
            <input
              v-model="manualInput.tag"
              type="text"
              class="input-field text-sm"
              placeholder="标记 (可选，用于分组)"
            />
            <button
              class="btn btn-primary w-full text-sm"
              :disabled="!manualInput.username || !manualInput.password"
              @click="addManual"
            >
              添加账号
            </button>
          </div>
        </div>
      </div>

      <!-- ====== RIGHT COLUMN: Map + Log ====== -->
      <div class="space-y-4">
        <!-- Map -->
        <div
          class="panel overflow-hidden"
          :class="{ 'hidden md:block': mobileTab !== 'map' }"
        >
          <div class="h-[350px] md:h-[400px]">
            <MapContainer ref="multiMapRef" container-id="multi-map-container" :is-multi-account="true" />
          </div>
        </div>

        <!-- Log -->
        <div
          class="panel p-4"
          :class="{ 'hidden md:block': mobileTab !== 'log' }"
        >
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold" style="color: var(--ink)">
              日志
            </h3>
            <button
              class="btn btn-ghost px-2 py-1 text-xs"
              @click="appStore.clearLogs()"
            >
              清空
            </button>
          </div>
          <div
            class="h-[200px] overflow-y-auto rounded-lg p-3 font-mono text-xs md:h-[250px]"
            style="background: var(--glass); color: var(--ink-secondary)"
          >
            <div
              v-if="logs.length === 0"
              class="flex h-full items-center justify-center"
              style="color: var(--ink-muted)"
            >
              暂无日志
            </div>
            <div
              v-for="(entry, idx) in logs"
              :key="idx"
              class="mb-1 leading-relaxed"
            >
              <span style="color: var(--ink-muted)">{{ entry.time }}</span>
              <span class="mx-1.5" :style="{ color: logLevelColor(entry.level) }">
                [{{ entry.level }}]
              </span>
              <span v-if="entry.source" class="mr-1.5" style="color: var(--ink-muted)">
                ({{ entry.source }})
              </span>
              <span>{{ entry.msg }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Global Params Modal ====== -->
    <AppModal
      :visible="showParamsModal"
      title="全局参数设置"
      @close="showParamsModal = false"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1 block text-sm font-medium" style="color: var(--ink)">
            跑步距离 (公里)
          </label>
          <input
            v-model="globalParams.distance"
            type="number"
            step="0.1"
            min="0"
            class="input-field"
            placeholder="留空则使用各账号默认值"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium" style="color: var(--ink)">
            配速
          </label>
          <input
            v-model="globalParams.pace"
            type="text"
            class="input-field"
            placeholder="例如: 5:30 (分:秒/公里)"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium" style="color: var(--ink)">
            跑步模式
          </label>
          <select
            v-model="globalParams.runMode"
            class="select-field"
          >
            <option value="">默认</option>
            <option value="normal">普通模式</option>
            <option value="fast">快速模式</option>
            <option value="random">随机模式</option>
          </select>
        </div>
        <div class="flex gap-2 pt-2">
          <button class="btn btn-secondary flex-1" @click="showParamsModal = false">
            取消
          </button>
          <button class="btn btn-primary flex-1" @click="applyGlobalParams">
            应用
          </button>
        </div>
      </div>
    </AppModal>
  </div>
</template>
