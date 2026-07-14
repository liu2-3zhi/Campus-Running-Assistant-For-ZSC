<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useMapStore } from '@/stores/map'
import { useNotificationStore } from '@/stores/notification'
import { callAPI } from '@/services/api'
import { connectWebSocket, disconnectWebSocket } from '@/services/socket'
import { useRouter } from 'vue-router'

import UserInfoBar from '@/components/main/UserInfoBar.vue'
import TaskPanel from '@/components/main/TaskPanel.vue'
import ControlTabs from '@/components/main/ControlTabs.vue'
import StatusPanels from '@/components/main/StatusPanels.vue'
import LogPanel from '@/components/main/LogPanel.vue'
import MobileHeader from '@/components/main/MobileHeader.vue'
import MobileSidebar from '@/components/main/MobileSidebar.vue'
import NotificationsPanel from '@/components/main/NotificationsPanel.vue'
import MapContainer from '@/components/map/MapContainer.vue'
import AdminPanel from '@/components/admin/AdminPanel.vue'
import AppModal from '@/components/common/AppModal.vue'
import BeianFooter from '@/components/common/BeianFooter.vue'

const app = useAppStore()
const auth = useAuthStore()
const theme = useThemeStore()
const mapStore = useMapStore()
const notifStore = useNotificationStore()
const router = useRouter()

// ── Mobile state ──
const sidebarVisible = ref(false)
const mobileActivePanel = ref('control')
const controlTab = ref('execute')
const collapsedSections = ref({})

function toggleSection(section) {
  collapsedSections.value[section] = !collapsedSections.value[section]
}

// 移动端侧边栏部分导航项对应控制面板内的 Tab（复刻 original：这些功能位于主控制区）
const NAV_TO_CONTROL_TAB = {
  checkpoints: 'checkpoints',
  attendance: 'attendance',
  history: 'history',
  settings: 'params',
}

function handleMobileNavigate(panel) {
  if (NAV_TO_CONTROL_TAB[panel]) {
    controlTab.value = NAV_TO_CONTROL_TAB[panel]
    mobileActivePanel.value = 'control'
  } else {
    mobileActivePanel.value = panel
  }
  sidebarVisible.value = false
}

// ── Modal state ──
const showNotifications = ref(false)
const showUserDetails = ref(false)
const showAdmin = ref(false)

// ── Timers ──
let userRefreshTimer = null
let resizeHandler = null

// ── Initial data load ──
async function loadInitialData() {
  app.isLoading = true
  try {
    const data = await callAPI('get_initial_data')
    if (data) {
      if (data.tasks) app.tasks = data.tasks
      if (data.users) app.users = data.users
      if (data.notifications || data.notices) {
        const notices = data.notices || data.notifications
        app.notifications = notices
        app.unreadCount = data.unreadCount ?? data.unread_count ?? 0
        notifStore.notifications = notices
        notifStore.unreadCount = data.unreadCount ?? data.unread_count ?? 0
      }
      if (data.params) app.pythonParams = data.params
      if (data.run_data) app.runData = data.run_data
      if (data.is_running != null) app.isRunning = data.is_running
      if (data.selected_task_index != null) app.selectedTaskIndex = data.selected_task_index

      const mapConfig = {}
      if (data.amap_key || data.amap_js_api_key) mapConfig.amapKey = data.amap_key || data.amap_js_api_key
      if (data.amap_security_key) mapConfig.amapSecurityKey = data.amap_security_key
      if (data.tencent_map_key) mapConfig.tencentKey = data.tencent_map_key
      if (data.tianditu_map_key) mapConfig.tiandituKey = data.tianditu_map_key
      if (data.baidu_map_ak) mapConfig.baiduKey = data.baidu_map_ak
      if (Object.keys(mapConfig).length > 0) mapStore.setConfig(mapConfig)
      if (data.map_provider) mapStore.setProvider(data.map_provider)

      if (data.beian) app.beianData = data.beian

      app.addLog('初始数据加载完成', 'INFO', 'System')
    }
  } catch (e) {
    app.addLog('加载初始数据失败: ' + (e.message || e), 'ERROR', 'System')
  } finally {
    app.isLoading = false
  }
}

async function refreshUsers() {
  try {
    const data = await callAPI('get_initial_data')
    if (data) {
      if (data.users) app.users = data.users
      if (data.tasks) app.tasks = data.tasks
      if (data.run_data) app.runData = data.run_data
      if (data.is_running != null) app.isRunning = data.is_running
    }
  } catch {
    // silent fail for background refresh
  }
}

function handleShowNotifications() {
  showNotifications.value = true
}

async function handleBack() {
  try {
    const { callAPI } = await import('@/services/api')
    await callAPI('logout')
  } catch (_) {}
  disconnectWebSocket()
  auth.logout()
  router.push('/')
}

// ── Lifecycle ──
onMounted(() => {
  app.detectMobile()
  loadInitialData()
  connectWebSocket()
  notifStore.fetchNotifications()

  userRefreshTimer = setInterval(refreshUsers, 30000)

  // Handle resize for mobile detection
  resizeHandler = () => app.detectMobile()
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (userRefreshTimer) {
    clearInterval(userRefreshTimer)
    userRefreshTimer = null
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  disconnectWebSocket()
})
</script>

<template>
  <div class="min-h-screen bg-[var(--base-color)]">
    <!-- ==================== MOBILE LAYOUT ==================== -->
    <template v-if="app.isMobile">
      <MobileHeader @toggle-sidebar="sidebarVisible = !sidebarVisible" />
      <MobileSidebar
        :visible="sidebarVisible"
        :is-multi-mode="app.isMultiMode"
        @close="sidebarVisible = false"
        @navigate="handleMobileNavigate"
        @back="handleBack"
      />

      <!-- Loading overlay -->
      <div
        v-if="app.isLoading"
        class="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 backdrop-blur-sm"
        style="background: var(--base-color, rgba(255,255,255,0.9))"
      >
        <div class="flex flex-col items-center gap-4">
          <div class="w-16 h-16 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin"></div>
          <p class="text-sm font-medium" style="color: var(--ink-secondary)">加载中，请稍候...</p>
        </div>
      </div>

      <main class="pt-12 h-screen overflow-hidden">
        <!-- control panel -->
        <div v-show="mobileActivePanel === 'control'" class="h-full overflow-y-auto px-3 py-3 space-y-3">
          <ControlTabs :open-tab="controlTab" />
          <StatusPanels />
        </div>

        <!-- map panel -->
        <div v-show="mobileActivePanel === 'map'" class="h-full">
          <MapContainer container-id="mobile-map" />
        </div>

        <!-- tasks panel -->
        <div v-show="mobileActivePanel === 'tasks'" class="h-full overflow-y-auto px-3 py-3">
          <TaskPanel />
        </div>

        <!-- 打卡点/签到/历史/参数：已由侧边栏导航路由到「控制」面板对应 Tab（见 NAV_TO_CONTROL_TAB） -->

        <!-- notifications panel -->
        <div v-show="mobileActivePanel === 'notifications'" class="h-full overflow-y-auto px-3 py-3">
          <NotificationsPanel />
        </div>

        <!-- task-details panel -->
        <div v-show="mobileActivePanel === 'task-details'" class="h-full overflow-y-auto px-3 py-3">
          <div class="panel p-4 space-y-3">
            <h3 class="text-sm font-semibold text-[var(--ink)] mb-1">任务详情</h3>
            <div v-if="!app.selectedTask" class="text-sm text-[var(--ink-muted)] py-6 text-center">
              请先在「任务」中选择一个任务
            </div>
            <div v-else class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-[var(--ink-muted)]">任务名称</span>
                <span class="text-[var(--ink)] font-medium">{{ app.selectedTask.name || app.selectedTask.task_name || ('任务 #' + (app.selectedTaskIndex + 1)) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--ink-muted)]">状态</span>
                <span class="text-[var(--ink)]">{{ app.selectedTask.status || '待执行' }}</span>
              </div>
              <div v-if="app.selectedTask.distance != null" class="flex justify-between">
                <span class="text-[var(--ink-muted)]">距离</span>
                <span class="text-[var(--ink)]">{{ (Number(app.selectedTask.distance) / 1000).toFixed(2) }} km</span>
              </div>
              <div v-if="app.selectedTask.duration != null" class="flex justify-between">
                <span class="text-[var(--ink-muted)]">时长</span>
                <span class="text-[var(--ink)]">{{ app.selectedTask.duration }}</span>
              </div>
              <div v-if="app.selectedTask.target_points || app.selectedTask.checkpoints" class="flex justify-between">
                <span class="text-[var(--ink-muted)]">打卡点数</span>
                <span class="text-[var(--ink)]">{{ (app.selectedTask.target_points || app.selectedTask.checkpoints || []).length }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- log panel -->
        <div v-show="mobileActivePanel === 'log'" class="h-full overflow-y-auto px-3 py-3">
          <LogPanel :logs="app.logs" @clear="app.clearLogs()" />
        </div>

        <!-- profile panel -->
        <div v-show="mobileActivePanel === 'profile'" class="h-full overflow-y-auto px-3 py-3">
          <div class="panel p-4 space-y-3">
            <h3 class="text-sm font-semibold text-[var(--ink)] mb-3">个人信息</h3>
            <div class="flex items-center gap-3 pb-3 border-b border-[var(--border-color)]">
              <div class="w-14 h-14 rounded-full bg-[var(--accent)] flex items-center justify-center text-white text-xl font-semibold">
                <img v-if="auth.avatarUrl" :src="auth.avatarUrl" class="w-14 h-14 rounded-full object-cover" :alt="auth.displayName || auth.username" />
                <span v-else>{{ (auth.displayName || auth.username || '?').charAt(0).toUpperCase() }}</span>
              </div>
              <div>
                <div class="text-base font-semibold text-[var(--ink)]">{{ auth.displayName || auth.username }}</div>
                <div class="text-xs text-[var(--ink-muted)]">{{ auth.isAdmin ? '管理员' : (auth.isGuest ? '访客' : '用户') }}</div>
              </div>
            </div>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-[var(--ink-muted)]">用户名</span>
                <span class="text-[var(--ink)] font-medium">{{ auth.username || '--' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--ink-muted)]">会话 ID</span>
                <span class="text-[var(--ink)] font-mono text-xs">{{ auth.sessionUUID || '--' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- admin panel (mobile: opens fullscreen modal) -->
        <div v-show="mobileActivePanel === 'admin'" class="h-full overflow-y-auto px-3 py-3">
          <AdminPanel :visible="mobileActivePanel === 'admin'" @close="mobileActivePanel = 'control'" />
        </div>
      </main>
    </template>

    <!-- ==================== DESKTOP LAYOUT ==================== -->
    <template v-else>
      <div class="h-screen grid grid-cols-3 gap-4 p-4 overflow-hidden">
        <!-- Column 1: User info, tasks, controls -->
        <div class="col-span-1 flex flex-col gap-4 overflow-y-auto min-h-0 pr-1">
          <UserInfoBar
            @show-notifications="handleShowNotifications"
            @show-user-details="showUserDetails = true"
            @show-admin="showAdmin = true"
          />
          <TaskPanel />
          <div class="flex-1 min-h-0 overflow-y-auto">
            <ControlTabs />
          </div>
        </div>

        <!-- Columns 2-3: Map and status -->
        <div class="col-span-2 flex flex-col gap-4 overflow-hidden">
          <!-- Map area -->
          <div class="flex-1 min-h-0 panel p-0 overflow-hidden">
            <MapContainer container-id="main-map" />
          </div>
          <!-- Status panels -->
          <StatusPanels />
        </div>
      </div>
      <!-- Beian Footer -->
      <BeianFooter />
    </template>

    <!-- ==================== MODALS ==================== -->

    <!-- Notifications modal -->
    <AppModal
      :visible="showNotifications"
      title="通知"
      width="max-w-md"
      @close="showNotifications = false"
    >
      <NotificationsPanel />
    </AppModal>

    <!-- User details modal -->
    <AppModal
      :visible="showUserDetails"
      title="用户详情"
      width="max-w-sm"
      @close="showUserDetails = false"
    >
      <div class="space-y-3">
        <div class="flex items-center gap-3 pb-3 border-b border-[var(--border-color)]">
          <div class="w-14 h-14 rounded-full bg-[var(--accent)] flex items-center justify-center text-white text-xl font-semibold">
            <img
              v-if="auth.avatarUrl"
              :src="auth.avatarUrl"
              class="w-14 h-14 rounded-full object-cover"
              :alt="auth.displayName || auth.username"
            />
            <span v-else>{{ (auth.displayName || auth.username || '?').charAt(0).toUpperCase() }}</span>
          </div>
          <div>
            <div class="text-base font-semibold text-[var(--ink)]">{{ auth.displayName || auth.username }}</div>
            <div class="text-xs text-[var(--ink-muted)]">{{ auth.isAdmin ? '管理员' : (auth.isGuest ? '访客' : '用户') }}</div>
          </div>
        </div>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-[var(--ink-muted)]">用户名</span>
            <span class="text-[var(--ink)] font-medium">{{ auth.username || '--' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[var(--ink-muted)]">会话 ID</span>
            <span class="text-[var(--ink)] font-mono text-xs">{{ auth.sessionUUID || '--' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[var(--ink-muted)]">主题</span>
            <span class="text-[var(--ink)]">{{ theme.isDark ? '暗色' : '亮色' }} / {{ theme.currentStyle }}</span>
          </div>
          <div v-if="auth.sessionLimitInfo" class="flex justify-between">
            <span class="text-[var(--ink-muted)]">会话限制</span>
            <span class="text-[var(--ink)]">{{ auth.sessionLimitInfo.current || 0 }} / {{ auth.sessionLimitInfo.max || '?' }}</span>
          </div>
        </div>
      </div>
    </AppModal>

    <!-- Admin panel (full-featured) -->
    <AdminPanel :visible="showAdmin" @close="showAdmin = false" />
  </div>
</template>
