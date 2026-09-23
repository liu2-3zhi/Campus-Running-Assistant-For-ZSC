<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useMapStore } from '@/stores/map'
import { useNotificationStore } from '@/stores/notification'
import { callAPI, callRawAPI } from '@/services/api'
import { connectWebSocket, disconnectWebSocket, isWebSocketConnected, onWebSocketStatus } from '@/services/socket'
import MapContainer from '@/components/map/MapContainer.vue'
import NotificationsPanel from '@/components/main/NotificationsPanel.vue'
import AppModal from '@/components/common/AppModal.vue'
import AdminPanel from '@/components/admin/AdminPanel.vue'
import { checkOverdueBeforeStart } from '@/composables/usePayment'
import { paramDefs, paramGroups } from '@/utils/legacyParams'

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
const showAdmin = ref(false)
const showAddModal = ref(false)
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
const globalParams = reactive({})

async function checkedAPI(method, ...args) {
  const result = await callAPI(method, ...args)
  if (result?.success === false) throw new Error(result.message || '操作失败')
  return result
}

// Computed
const accounts = computed(() => appStore.multiAccounts)
const statuses = computed(() => appStore.multiStatus)
const logs = computed(() => appStore.logs)
const logText = computed(() => logs.value.map(entry => `[${entry.time}][${entry.level}] ${entry.msg}`).join('\n'))
const configUsers = computed(() => appStore.users)

let autoRefreshTimer = null
let autoRefreshRequestId = 0
let socketStatusUnsubscribe = null
let viewMounted = false

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
    const data = await checkedAPI('multi_get_all_accounts_status')
    if (data?.accounts) {
      appStore.multiAccounts = data.accounts
    }
  } catch (e) {
    appStore.addLog(`加载账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
  loading.value = false
}

async function startAll() {
  if (!accounts.value.length) return
  try {
    if (!(await checkOverdueBeforeStart(accounts.value.map(getAccountName)))) return
    await checkedAPI('multi_start_all_accounts', {
      min_delay: delaySettings.minDelay,
      max_delay: delaySettings.maxDelay,
      use_delay: delaySettings.useDelay,
      run_only_incomplete: delaySettings.runOnlyIncomplete,
    })
    appStore.addLog('已发送全部启动指令', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部启动失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopAll() {
  try {
    await checkedAPI('multi_stop_all_accounts')
    appStore.addLog('已发送全部停止指令', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部停止失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function startSelected() {
  if (selectedCount.value === 0) return
  try {
    if (!(await checkOverdueBeforeStart([...selectedIds.value]))) return
    for (const username of selectedIds.value) {
      if (delaySettings.useDelay && delaySettings.maxDelay >= delaySettings.minDelay) {
        const delay = Math.random() * (delaySettings.maxDelay - delaySettings.minDelay) + delaySettings.minDelay
        await new Promise(resolve => setTimeout(resolve, delay * 10))
      }
      await checkedAPI('multi_start_single_account', { username, run_only_incomplete: delaySettings.runOnlyIncomplete })
    }
    appStore.addLog(`已启动 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`启动选中账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopSelected() {
  if (selectedCount.value === 0) return
  try {
    for (const username of selectedIds.value) await checkedAPI('multi_stop_single_account', { username })
    appStore.addLog(`已停止 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`停止选中账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function refreshAccount(account) {
  try {
    await checkedAPI('multi_refresh_single_status', { username: getAccountName(account) })
    appStore.addLog(`已刷新 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function startAccount(account) {
  try {
    if (!(await checkOverdueBeforeStart([getAccountName(account)]))) return
    await checkedAPI('multi_start_single_account', {
      username: getAccountName(account),
      run_only_incomplete: delaySettings.runOnlyIncomplete,
    })
    appStore.addLog(`已启动 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`启动失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function stopAccount(account) {
  try {
    await checkedAPI('multi_stop_single_account', { username: getAccountName(account) })
    appStore.addLog(`已停止 ${getAccountName(account)}`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`停止失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function removeAccount(account) {
  try {
    await checkedAPI('multi_remove_account', { username: getAccountName(account) })
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
    await checkedAPI('multi_remove_selected_accounts', { usernames: [...selectedIds.value] })
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
    await checkedAPI('multi_remove_all_accounts')
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
    for (const username of selectedIds.value) await checkedAPI('multi_refresh_single_status', { username })
    appStore.addLog(`已刷新 ${selectedCount.value} 个选中账号`, 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`批量刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function refreshAll() {
  try {
    await checkedAPI('multi_refresh_all_statuses')
    appStore.addLog('已刷新全部账号', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`全部刷新失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Add account ---
async function addFromConfig() {
  if (!selectedUser.value) {
    openManualAccount()
    return
  }
  try {
    const result = await callAPI('multi_add_account', { username: selectedUser.value, password: '' })
    if (result?.action === 'request_password') {
      manualInput.username = selectedUser.value
      addAccountMode.value = 'manual'
      showAddModal.value = true
      return
    }
    if (result?.success === false) throw new Error(result.message || '添加账号失败')
    appStore.addLog(`已添加账号: ${selectedUser.value}`, 'INFO', 'Multi')
    selectedUser.value = ''
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function addAllFromConfig() {
  try {
    const result = await callRawAPI('/api/multi_load_accounts_from_config', 'POST', {})
    if (result?.success === false) throw new Error(result.message || '添加全部失败')
    appStore.addLog('已添加全部配置用户', 'INFO', 'Multi')
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加全部失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function addManual() {
  if (!manualInput.username || !manualInput.password) return
  try {
    await checkedAPI('multi_add_account', {
      username: manualInput.username,
      password: manualInput.password,
      tag: manualInput.tag || undefined,
    })
    appStore.addLog(`已添加账号: ${manualInput.username}`, 'INFO', 'Multi')
    manualInput.username = ''
    manualInput.password = ''
    manualInput.tag = ''
    showAddModal.value = false
    await loadAccounts()
  } catch (e) {
    appStore.addLog(`添加账号失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

function openManualAccount() {
  showAddModal.value = true
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
      await checkedAPI('multi_import_accounts', {
        base64_content: String(base64).split(',')[1],
        filename: file.name,
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
    const data = await checkedAPI('multi_export_accounts_summary')
    if (data?.content) {
      const link = document.createElement('a')
      link.href = `data:${data.mimetype || 'application/octet-stream'};base64,${data.content}`
      link.download = data.filename || 'accounts.xlsx'
      link.click()
      appStore.addLog('Excel 导出成功', 'INFO', 'Multi')
    }
  } catch (e) {
    appStore.addLog(`Excel 导出失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function downloadTemplate() {
  try {
    const data = await checkedAPI('multi_download_import_template')
    if (data?.content) {
      const link = document.createElement('a')
      link.href = `data:${data.mimetype || 'application/octet-stream'};base64,${data.content}`
      link.download = data.filename || 'template.xlsx'
      link.click()
    }
  } catch (e) {
    appStore.addLog(`下载模板失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Global params ---
function isCheckboxParam(key) {
  return paramDefs[key]?.type === 'checkbox' || key === 'api_fallback_line' || key === 'ignore_task_time'
}

async function saveGlobalParam(key) {
  try {
    await checkedAPI('update_param', { key, value: globalParams[key] })
  } catch (e) {
    appStore.addLog(`设置全局参数失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

async function applyGlobalParams() {
  try {
    for (const [key, value] of Object.entries(globalParams)) {
      if (paramDefs[key]) await checkedAPI('update_param', { key, value })
    }
    appStore.addLog('全局参数已应用', 'INFO', 'Multi')
    showParamsModal.value = false
  } catch (e) {
    appStore.addLog(`设置全局参数失败: ${e.message}`, 'ERROR', 'Multi')
  }
}

// --- Navigation ---
function goToAdmin() {
  showAdmin.value = true
}

// --- Auto refresh fallback: WebSocket pushes take priority ---
function scheduleAutoRefresh() {
  if (!viewMounted || isWebSocketConnected()) return
  autoRefreshTimer = setTimeout(pollAccountsFallback, 1000)
}

async function pollAccountsFallback() {
  if (!viewMounted || isWebSocketConnected()) return
  const requestId = ++autoRefreshRequestId
  try {
    const result = await checkedAPI('multi_get_all_accounts_status')
    if (
      !viewMounted ||
      isWebSocketConnected() ||
      requestId !== autoRefreshRequestId
    ) {
      return
    }
    if (result?.accounts) {
      appStore.multiAccounts = result.accounts
    }
  } catch (_) {
  } finally {
    if (
      viewMounted &&
      !isWebSocketConnected() &&
      requestId === autoRefreshRequestId
    ) {
      scheduleAutoRefresh()
    }
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  scheduleAutoRefresh()
}

function stopAutoRefresh() {
  autoRefreshRequestId++
  if (autoRefreshTimer) {
    clearTimeout(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

function syncAutoRefreshWithSocket(connected) {
  if (connected || !viewMounted) {
    stopAutoRefresh()
  } else {
    startAutoRefresh()
  }
}

// --- Sync runOnlyIncomplete to backend (task 10) ---
async function syncRunOnlyIncomplete() {
  try {
    await checkedAPI('set_multi_run_only_incomplete', { flag: delaySettings.runOnlyIncomplete })
  } catch (_) {}
}

async function exitMultiMode() {
  stopAutoRefresh()
  try {
    await checkedAPI('exit_multi_account_mode')
  } catch (e) {
    appStore.addLog(`退出多账号失败: ${e.message}`, 'ERROR', 'Multi')
    startAutoRefresh()
    return
  }
  appStore.isMultiMode = false
  appStore.currentView = 'login'
  router.push({ name: 'session', params: { uuid: authStore.sessionUUID } })
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
  viewMounted = true
  appStore.currentView = 'multi'
  appStore.isMultiMode = true
  try {
    const result = await checkedAPI('enter_multi_account_mode')
    Object.assign(globalParams, result?.params || {})
    appStore.addLog('已进入多账号模式', 'INFO', 'Multi')
  } catch (e) {
    appStore.addLog(`进入多账号模式失败: ${e.message}`, 'ERROR', 'Multi')
  }
  await loadAccounts()

  // Load config users list if empty
  if (configUsers.value.length === 0) {
    try {
      const data = await checkedAPI('multi_get_all_config_users')
      if (data?.users) {
        appStore.users = data.users
      }
    } catch (_) {}
  }

  // WebSocket is the primary channel; polling is only the disconnected fallback.
  socketStatusUnsubscribe = onWebSocketStatus(syncAutoRefreshWithSocket)
  connectWebSocket()
})

onUnmounted(() => {
  viewMounted = false
  if (socketStatusUnsubscribe) {
    socketStatusUnsubscribe()
    socketStatusUnsubscribe = null
  }
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
<main
        id="multi-account-app" v-if="!appStore.isMobile"
        class="h-screen w-screen grid grid-cols-1 lg:grid-cols-[530px_1fr] xl:grid-cols-[530px_1fr] gap-4 p-4"
      >
        <div class="flex flex-col gap-4 h-full min-h-0">
          <div class="panel rounded-xl p-4 flex-shrink-0">
            <div class="flex justify-between items-center mb-3">
              <h2 class="text-lg font-bold text-slate-800 card-title">
                多账号控制台
              </h2>
              <div class="flex gap-2">
                <button
                  id="show-admin-panel-multi" @click="goToAdmin"
                  class="btn btn-ghost !py-1 !px-3"
                  title="管理面板"
                >
                  管理面板
                </button>
                <button
                  id="exit-multi-mode-btn" @click="exitMultiMode"
                  class="btn btn-ghost !py-1 !px-3"
                >
                  返回登录页
                </button>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <button id="multi-start-all-btn" @click="startAll" class="btn btn-primary">
                全部开始
              </button>
              <button id="multi-stop-all-btn" @click="stopAll" class="btn btn-danger">
                全部停止
              </button>
            </div>
            <div class="mt-4 space-y-2 text-sm border-t pt-3">
              <label
                class="flex items-center gap-2 cursor-pointer font-semibold text-slate-700"
              >
                <input
                  type="checkbox"
                  id="multi-use-delay-check" v-model="delaySettings.useDelay"

                  class="w-4 h-4 accent-sky-600 rounded"
                  aria-label="multi use delay check"
                  title="multi use delay check"
                />
                启用随机启动延迟
                <div class="flex items-center gap-2 pl-6">
                  <input
                    type="number"
                    id="multi-min-delay-input" v-model.number="delaySettings.minDelay"
                    class="input-field !py-1 w-20 text-center"
                    aria-label="multi min delay input"
                    title="multi min delay input"
                    placeholder="multi min delay input"
                  />
                  <span>-</span>
                  <input
                    type="number"
                    id="multi-max-delay-input" v-model.number="delaySettings.maxDelay"
                    class="input-field !py-1 w-20 text-center"
                    aria-label="multi max delay input"
                    title="multi max delay input"
                    placeholder="multi max delay input"
                  />
                  <span>秒</span>
                </div>
              </label>
              <label
                class="flex items-center gap-2 cursor-pointer font-semibold text-slate-700 mt-2"
              >
                <input
                  type="checkbox"
                  id="multi-run-only-incomplete-check" v-model="delaySettings.runOnlyIncomplete" @change="syncRunOnlyIncomplete"

                  class="w-4 h-4 accent-sky-600 rounded"
                  aria-label="multi run only incomplete check"
                  title="multi run only incomplete check"
                />
                仅执行未完成的任务
              </label>
            </div>
          </div>
          <div class="panel rounded-xl p-4 flex-grow flex flex-col min-h-0">
            <div class="flex justify-between items-center mb-1">
              <div class="flex items-center gap-2">
                <h2 class="text-lg font-bold text-slate-800">
                  账号列表 (<span id="multi-account-count">{{ accounts.length }}</span>)
                </h2>
                <input
                  type="checkbox"
                  id="multi-select-all-check" :checked="allSelected" @change="toggleSelectAll" v-show="accounts.length"
                  class="w-4 h-4 accent-sky-600 rounded"
                  title="全选/取消全选"

                />
              </div>
              <div class="flex gap-2">
                <button
                  id="multi-import-excel-btn" @click="importExcel"
                  class="btn btn-ghost !py-1 !px-3"
                  title="从文件导入"
                >
                  导入
                </button>
                <button
                  id="multi-export-excel-btn" @click="exportExcel"
                  class="btn btn-ghost !py-1 !px-3"
                  title="导出汇总"
                >
                  导出
                </button>
                <button
                  id="multi-download-template-btn" @click="downloadTemplate"
                  class="btn btn-ghost !py-1 !px-3"
                  title="下载导入模板"
                >
                  下载模板
                </button>
              </div>
            </div>

            <div
              class="flex items-center justify-between mb-3 text-xs border-b pb-2"
            >
              <!-- 左侧：刷新 -->
              <div class="flex items-center gap-2">
                <button
                  id="multi-refresh-selected-btn" @click="refreshSelected"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-blue-600"
                >
                  刷新选中
                </button>
                <button
                  id="multi-refresh-all-btn" @click="refreshAll"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-blue-600"
                >
                  刷新全部
                </button>
              </div>

              <!-- 中央：控制 -->
              <div class="flex items-center gap-2">
                <button
                  id="multi-start-selected-btn" @click="startSelected"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-green-600"
                >
                  开始选中
                </button>
                <button
                  id="multi-stop-selected-btn" @click="stopSelected"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-green-600"
                >
                  停止选中
                </button>
              </div>

              <!-- 右侧：移除 -->
              <div class="flex items-center gap-2">
                <button
                  id="multi-remove-selected-btn" @click="removeSelected"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-red-600"
                >
                  移除选中
                </button>
                <button
                  id="multi-remove-all-btn" @click="removeAll"
                  class="btn btn-ghost !py-0.5 !px-2 text-sm text-red-600"
                >
                  移除全部
                </button>
              </div>
            </div>

            <div
              id="multi-account-list"
              class="flex-grow overflow-y-auto -mr-2 pr-2"
              style="max-height: 42vh"
            >
              <p v-if="!accounts.length" class="text-slate-400 text-center py-10">请先添加或导入账号</p>
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
            <div class="mt-2 border-t pt-3 flex items-center gap-2">
              <select
                id="multi-config-user-select" v-model="selectedUser"
                class="select-field !py-1 flex-grow"
                aria-label="从配置添加用户"
              ><option value="">(新用户/手动输入)</option><option v-for="user in configUsers" :key="typeof user === 'string' ? user : user.username" :value="typeof user === 'string' ? user : user.username">{{ typeof user === "string" ? user : user.username }}</option></select>
              <button
                id="multi-add-from-config-btn" @click="addFromConfig"
                class="btn btn-ghost !py-1 !px-2 flex-shrink-0"
              >
                添加
              </button>
              <button
                id="multi-load-all-from-config-btn" @click="addAllFromConfig"
                class="btn btn-ghost !py-1 !px-2 flex-shrink-0"
              >
                添加全部
              </button>
            </div>
          </div>
          <div class="panel rounded-xl p-4 flex-shrink-0">
            <h3 class="font-bold text-slate-800 mb-2">全局参数</h3>
            <div id="multi-global-params-container" class="h-40 space-y-4 overflow-y-auto pr-1">
          <section v-for="group in paramGroups" :key="group.title">
            <h4 class="mb-2 border-b border-slate-200 pb-1 font-bold text-sky-700">{{ group.title }}</h4>
            <div v-for="key in group.keys" :key="key" class="mb-3 text-sm">
              <label class="flex items-center gap-2 font-semibold text-slate-700">
                <input v-if="isCheckboxParam(key)" v-model="globalParams[key]" type="checkbox" class="h-5 w-5 rounded accent-sky-600" @change="saveGlobalParam(key)" />
                {{ paramDefs[key].label }}
              </label>
              <div v-if="!isCheckboxParam(key)" class="mt-1 flex items-center gap-2">
                <input v-model.number="globalParams[key]" type="number" :step="key.endsWith('_s') || key.endsWith('_mps') ? 0.1 : 1" class="input-field !py-1" :aria-label="paramDefs[key].label" @change="saveGlobalParam(key)" />
                <span class="shrink-0 text-xs text-slate-500">{{ paramDefs[key].unit }}</span>
              </div>
              <p class="mt-1 text-xs text-slate-500">{{ paramDefs[key].help }}</p>
            </div>
          </section>
        </div>
          </div>
        </div>
        <div class="flex flex-col gap-4 h-full min-h-0">
          <div class="flex-grow min-h-0 rounded-xl overflow-hidden border border-slate-200 bg-slate-200"><MapContainer ref="multiMapRef" container-id="multi-map-container" :is-multi-account="true" /></div>
          <div class="panel rounded-xl p-4 h-48 flex flex-col">
            <h3 class="font-bold text-slate-800 mb-2">全局日志</h3>
            <textarea
              id="multi-log-text" :value="logText"
              readonly=""
              class="w-full flex-grow bg-white/80 border border-slate-200 rounded-md p-2 text-xs text-slate-700 resize-none focus:outline-none leading-snug"
              aria-label="multi log text"
              title="multi log text"
              placeholder=""
            ></textarea>
          </div>
        </div>
      </main>
<div v-else class="multi-mobile pt-14 pb-4"><div class="mobile-card" id="mobile-multi-account-panel" v-show="mobileTab === 'accounts'">
            <div
              class="flex items-center justify-between mb-5 pb-4 border-b-2 border-purple-200"
            >
              <div class="flex items-center gap-3">
                <div
                  class="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-lg"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-6 h-6 text-white"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path
                      d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05c1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"
                    ></path>
                  </svg>
                </div>
                <h3 class="text-2xl font-bold text-purple-700 tracking-tight">
                  账号管理
                </h3>
              </div>
              <div
                class="text-sm font-bold text-white bg-gradient-to-r from-purple-500 to-purple-600 px-4 py-1.5 rounded-full shadow-md"
                id="mobile-multi-account-count"
              >
                {{ accounts.length }} 个账号
              </div>
            </div>

            <div
              class="bg-white rounded-xl shadow-md p-4 mb-5 border border-purple-100"
            >
              <div class="flex items-center gap-2 mb-4">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="w-5 h-5 text-purple-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"
                  ></path>
                </svg>
                <h4 class="text-base font-bold text-slate-800">➕ 添加账号</h4>
              </div>

              <select
                id="mobile-multi-config-user-select" v-model="selectedUser"
                class="w-full px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-lg text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all mb-3 shadow-sm"
                aria-label="从配置添加用户"
              >
                <option value="">(新用户/手动输入)</option><option v-for="user in configUsers" :key="typeof user === 'string' ? user : user.username" :value="typeof user === 'string' ? user : user.username">{{ typeof user === "string" ? user : user.username }}</option>
              </select>

              <div class="grid grid-cols-3 gap-2">
                <button
                  class="py-2.5 px-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-lg text-sm font-bold hover:from-purple-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1"
                  @click="addFromConfig"
                >
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="2.5"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M12 4v16m8-8H4"
                    ></path>
                  </svg>
                  添加选中
                </button>
                <button
                  class="py-2.5 px-3 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-lg text-sm font-bold hover:from-purple-700 hover:to-purple-800 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1"
                  @click="addAllFromConfig"
                >
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="2.5"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    ></path>
                  </svg>
                  添加全部
                </button>
                <button
                  class="py-2.5 px-3 bg-gradient-to-r from-teal-500 to-teal-600 text-white rounded-lg text-sm font-bold hover:from-teal-600 hover:to-teal-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1"
                  id="mobile_multi_account_manual_input_button"
                  @click="openManualAccount"
                  style="display: none"
                >
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="2.5"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                    ></path>
                  </svg>
                  手动添加
                </button>
              </div>
            </div>

            <div
              class="bg-gradient-to-r from-purple-50 to-purple-100 rounded-xl p-4 mb-5 border-2 border-purple-200 shadow-sm"
            >
              <div class="flex items-center justify-between">
                <label class="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    id="mobile-select-all-accounts" :checked="allSelected"
                    class="w-6 h-6 text-purple-600 rounded-md shadow-sm cursor-pointer"
                    @change="toggleSelectAll"
                    aria-label="mobile select all accounts"
                    title="mobile select all accounts"
                  />
                  <span class="text-sm font-bold text-slate-800"
                    >✅ 全选账号</span
                  >
                </label>
                <div class="flex gap-2">
                  <button
                    class="py-2 px-4 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-sm font-bold hover:from-green-600 hover:to-green-700 transition-all shadow-md hover:shadow-lg"
                    @click="startSelected"
                  >
                    ▶️ 启动
                  </button>
                  <button
                    class="py-2 px-4 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg text-sm font-bold hover:from-red-600 hover:to-red-700 transition-all shadow-md hover:shadow-lg"
                    @click="stopSelected"
                  >
                    ⏹️ 停止
                  </button>
                </div>
              </div>
            </div>

            <div
              id="mobile-multi-account-list"
              class="space-y-3 overflow-y-auto pr-2 mb-5"
            >
              <div v-if="!accounts.length" class="text-center py-12">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="w-20 h-20 mx-auto text-slate-300 mb-4"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path
                    d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05c1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"
                  ></path>
                </svg>
                <p class="text-slate-400 text-sm font-medium">
                  暂无账号，请先添加
                </p>
                <p class="text-slate-300 text-xs mt-1">
                  从上方选择配置文件或手动添加
                </p>
              </div><div
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

            <div
              class="bg-white rounded-xl shadow-md p-4 border border-purple-100"
            >
              <div class="flex items-center gap-2 mb-4">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="w-5 h-5 text-purple-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
                  ></path>
                </svg>
                <h4 class="text-base font-bold text-slate-800">🔧 批量操作</h4>
              </div>

              <div class="space-y-2" id="mobile-multi-account-batch-operations">
                <div class="grid grid-cols-3 gap-2">
                  <button
                    class="py-2.5 px-2 bg-blue-50 text-blue-600 rounded-lg text-xs font-bold hover:bg-blue-100 transition flex flex-col items-center justify-center gap-1 border-2 border-blue-200"
                    @click="importExcel"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
                      ></path>
                    </svg>
                    <span>导入</span>
                  </button>
                  <button
                    class="py-2.5 px-2 bg-green-50 text-green-600 rounded-lg text-xs font-bold hover:bg-green-100 transition flex flex-col items-center justify-center gap-1 border-2 border-green-200"
                    @click="exportExcel"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      ></path>
                    </svg>
                    <span>导出</span>
                  </button>
                  <button
                    class="py-2.5 px-2 bg-amber-50 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-100 transition flex flex-col items-center justify-center gap-1 border-2 border-amber-200"
                    @click="downloadTemplate"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      ></path>
                    </svg>
                    <span>模板</span>
                  </button>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    class="py-2.5 px-2 bg-slate-50 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-100 transition flex items-center justify-center gap-2 border-2 border-slate-200"
                    @click="refreshSelected"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      ></path>
                    </svg>
                    <span>刷新选中</span>
                  </button>
                  <button
                    class="py-2.5 px-2 bg-indigo-50 text-indigo-600 rounded-lg text-xs font-bold hover:bg-indigo-100 transition flex items-center justify-center gap-2 border-2 border-indigo-200"
                    @click="refreshAll"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      ></path>
                    </svg>
                    <span>刷新全部</span>
                  </button>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    class="py-3 px-4 bg-red-50 text-red-600 rounded-lg text-sm font-bold hover:bg-red-100 transition flex items-center justify-center gap-2 border-2 border-red-200"
                    @click="removeSelected"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      ></path>
                    </svg>
                    删除选中
                  </button>
                  <button
                    class="py-3 px-4 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg text-sm font-bold hover:from-red-600 hover:to-red-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
                    @click="removeAll"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      stroke-width="2.5"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      ></path>
                    </svg>
                    删除全部
                  </button>
                </div>
              </div>
            </div>
          </div><div class="mobile-card flex flex-wrap gap-2"><button class="btn btn-ghost" @click="mobileTab='accounts'">账号管理</button><button class="btn btn-ghost" @click="mobileTab='map'">地图</button><button class="btn btn-ghost" @click="mobileTab='log'">日志</button><button class="btn btn-ghost" @click="showParamsModal=true">全局参数</button><button class="btn btn-ghost" @click="goToAdmin">管理面板</button><button class="btn btn-ghost" @click="exitMultiMode">返回登录页</button></div>
<div v-if="mobileTab==='map'" class="mobile-card h-[70vh]"><MapContainer ref="multiMapRef" container-id="mobile-multi-map-container" :is-multi-account="true" /></div>
<div v-if="mobileTab==='log'" class="mobile-card"><h3 class="font-bold mb-2">全局日志</h3><textarea class="input-field h-[60vh] text-xs" readonly :value="logText"></textarea></div></div>
    <!-- ====== Global Params Modal ====== -->
    <AppModal
      :visible="showParamsModal"
      title="全局参数设置"
      @close="showParamsModal = false"
    >
      <div class="space-y-4">
        <section v-for="group in paramGroups" :key="group.title">
          <h4 class="mb-2 border-b border-slate-200 pb-1 font-bold text-sky-700">{{ group.title }}</h4>
          <div v-for="key in group.keys" :key="key" class="mb-3 text-sm">
            <label class="flex items-center gap-2 font-semibold text-slate-700">
              <input v-if="isCheckboxParam(key)" v-model="globalParams[key]" type="checkbox" class="h-5 w-5 rounded accent-sky-600" />
              {{ paramDefs[key].label }}
            </label>
            <div v-if="!isCheckboxParam(key)" class="mt-1 flex items-center gap-2">
              <input v-model.number="globalParams[key]" type="number" :step="key.endsWith('_s') || key.endsWith('_mps') ? 0.1 : 1" class="input-field !py-1" :aria-label="paramDefs[key].label" />
              <span class="shrink-0 text-xs text-slate-500">{{ paramDefs[key].unit }}</span>
            </div>
            <p class="mt-1 text-xs text-slate-500">{{ paramDefs[key].help }}</p>
          </div>
        </section>
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
    <AdminPanel :visible="showAdmin" @close="showAdmin = false" />
<AppModal :visible="showAddModal" title="添加账号" @close="showAddModal=false"><div class="space-y-3"><input v-model="manualInput.username" class="input-field" placeholder="账号"/><input v-model="manualInput.password" type="password" class="input-field" placeholder="密码"/><input v-model="manualInput.tag" class="input-field" placeholder="标记 (可选)"/><button class="btn btn-primary w-full" @click="addManual">添加账号</button></div></AppModal>
</template>
<style scoped>
.multi-mobile :deep(.grid-cols-3) { grid-template-columns: 1fr; }
.multi-mobile #mobile-multi-account-panel > div:first-child > div:first-child { flex-direction: column; align-items: flex-start; }
.multi-mobile #mobile-multi-account-panel > div:nth-child(2) > div:first-child { flex-direction: column; }
.multi-mobile #mobile-multi-account-panel > div:nth-child(3) > div > label { flex-direction: column; }
.multi-mobile #mobile-multi-account-panel > div:nth-child(3) > div > div { flex-direction: column; flex: 1; }
.multi-mobile #mobile-multi-config-user-select { min-height: 54px; font-size: 16px; border-radius: 12px; }
</style>
