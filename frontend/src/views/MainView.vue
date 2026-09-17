<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useMapStore } from '@/stores/map'
import { useNotificationStore } from '@/stores/notification'
import { callAPI } from '@/services/api'
import { hydrateMapProviderSecrets } from '@/services/mapKeyRuntime'
import { connectWebSocket, disconnectWebSocket } from '@/services/socket'
import { useRouter } from 'vue-router'
import Swal from 'sweetalert2'

import UserInfoBar from '@/components/main/UserInfoBar.vue'
import TaskPanel from '@/components/main/TaskPanel.vue'
import ControlTabs from '@/components/main/ControlTabs.vue'
import MobileControlPanel from '@/components/main/MobileControlPanel.vue'
import MobileTaskPanel from '@/components/main/MobileTaskPanel.vue'
import StatusPanels from '@/components/main/StatusPanels.vue'
import LogPanel from '@/components/main/LogPanel.vue'
import MobileHeader from '@/components/main/MobileHeader.vue'
import MobileSidebar from '@/components/main/MobileSidebar.vue'
import NotificationsPanel from '@/components/main/NotificationsPanel.vue'
import MapContainer from '@/components/map/MapContainer.vue'
import MobileMapPanel from '@/components/map/MobileMapPanel.vue'
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
  if (NAV_TO_CONTROL_TAB[panel]) controlTab.value = NAV_TO_CONTROL_TAB[panel]
  mobileActivePanel.value = panel
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
    const responseData = await callAPI('get_initial_data')
    const data = await hydrateMapProviderSecrets(responseData)
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
      const providers = data.map_providers || {}
      if (providers.amap?.js_key) mapConfig.amapKey = providers.amap.js_key
      if (providers.amap?.security_key) mapConfig.amapSecurityKey = providers.amap.security_key
      if (providers.tencent?.map_key) mapConfig.tencentKey = providers.tencent.map_key
      if (providers.tianditu?.token) mapConfig.tiandituKey = providers.tianditu.token
      if (providers.baidu?.ak) mapConfig.baiduKey = providers.baidu.ak
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

async function openHelp() {
  await Swal.fire({
    title: '新手帮助',
    html: `
      <div class="text-left text-sm leading-6 text-slate-600">
        <p>控制面板用于启动、停止并查看当前任务状态。</p>
        <p class="mt-2">地图、任务、通知和个人信息可通过底部导航切换。</p>
      </div>
    `,
    confirmButtonText: '我知道了',
    customClass: {
      confirmButton: 'btn btn-primary',
    },
  })
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
  <div class="min-h-screen">
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
      <button
        id="newbie-help-btn"
        type="button"
        class="btn btn-ghost fixed z-[1001] !px-4 !py-2"
        style="
          top: 100px;
          right: 1rem;
          min-height: 48px;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          background: rgba(255, 255, 255, 0.8);
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
        "
        @click="openHelp"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        帮助
      </button>

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

      <main class="h-screen overflow-hidden pb-16 pt-14">
        <!-- control panel -->
        <div v-show="mobileActivePanel === 'control'" class="h-full overflow-y-auto">
          <MobileControlPanel />
        </div>

        <!-- map panel -->
        <div v-show="mobileActivePanel === 'map'" class="h-full">
          <MobileMapPanel />
        </div>

        <!-- tasks panel -->
        <div v-show="mobileActivePanel === 'tasks'" class="h-full overflow-y-auto">
          <MobileTaskPanel />
        </div>

        <!-- 打卡点/签到/历史/参数：复用统一控制组件中的对应 Tab -->
        <div
          v-show="['checkpoints', 'attendance', 'history', 'settings'].includes(mobileActivePanel)"
          class="h-full overflow-y-auto"
        >
          <ControlTabs :open-tab="controlTab" />
        </div>

        <!-- notifications panel -->
        <div v-show="mobileActivePanel === 'notifications'" class="h-full overflow-y-auto">
          <NotificationsPanel />
        </div>

        <!-- task-details panel -->
        <div v-show="mobileActivePanel === 'task-details'" class="h-full overflow-y-auto">
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
        <div v-show="mobileActivePanel === 'log'" class="h-full overflow-y-auto">
          <LogPanel :logs="app.logs" @clear="app.clearLogs()" />
        </div>

        <!-- profile panel -->
        <div v-show="mobileActivePanel === 'profile'" class="h-full overflow-y-auto">
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
        <div v-show="mobileActivePanel === 'admin'" class="h-full overflow-y-auto">
          <AdminPanel :visible="mobileActivePanel === 'admin'" @close="mobileActivePanel = 'control'" />
        </div>
      </main>
      <nav class="mobile-bottom-nav">
        <button
          class="mobile-nav-btn"
          :class="{ active: mobileActivePanel === 'control' }"
          @click="handleMobileNavigate('control')"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
          <span>控制</span>
        </button>
        <button
          class="mobile-nav-btn"
          :class="{ active: mobileActivePanel === 'map' }"
          @click="handleMobileNavigate('map')"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <span>地图</span>
        </button>
        <button
          class="mobile-nav-btn"
          :class="{ active: mobileActivePanel === 'tasks' }"
          @click="handleMobileNavigate('tasks')"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span>任务</span>
        </button>
        <button
          class="mobile-nav-btn"
          :class="{ active: mobileActivePanel === 'notifications' }"
          @click="handleMobileNavigate('notifications')"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span>通知</span>
        </button>
        <button
          class="mobile-nav-btn"
          :class="{ active: mobileActivePanel === 'profile' }"
          @click="handleMobileNavigate('profile')"
        >
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          <span>我的</span>
        </button>
      </nav>
    </template>

    <!-- ==================== DESKTOP LAYOUT ==================== -->
    <template v-else>
      <div class="grid h-screen grid-cols-1 gap-4 overflow-hidden p-4 lg:grid-cols-3 xl:grid-cols-4">
        <!-- Column 1: User info, tasks, controls -->
        <div class="col-span-1 flex min-h-0 min-w-[320px] flex-col gap-4 overflow-y-auto pr-1">
          <UserInfoBar
            @show-notifications="handleShowNotifications"
            @show-user-details="showUserDetails = true"
            @show-admin="showAdmin = true"
          />
          <TaskPanel />
          <ControlTabs />
        </div>

        <!-- Columns 2-3: Map and status -->
        <div class="col-span-1 flex flex-col gap-4 overflow-hidden lg:col-span-2 xl:col-span-3">
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
