<template>
  <AppModal
    :visible="visible"
    title="管理面板"
    :fullscreen="true"
    @close="emit('close')"
  >
    <div
      class="flex h-full"
      :class="isMobile ? 'flex-col' : ''"
    >
      <!-- Desktop Sidebar -->
      <aside
        v-if="!isMobile"
        class="w-56 border-r border-[var(--border-color)] overflow-y-auto p-2 flex-shrink-0 bg-[var(--glass)]"
      >
        <template v-for="(group, gi) in tabGroups" :key="gi">
          <div
            v-if="gi > 0 && filteredGroupTabs(group.tabs).length > 0"
            class="my-2 border-t border-[var(--border-color)]"
          />
          <div
            v-if="group.label && filteredGroupTabs(group.tabs).length > 0"
            class="px-3 py-1 text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider"
          >
            {{ group.label }}
          </div>
          <button
            v-for="tab in filteredGroupTabs(group.tabs)"
            :key="tab.key"
            class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2"
            :class="
              activeTab === tab.key
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--ink-secondary)] hover:bg-[var(--glass)]'
            "
            @click="activeTab = tab.key"
          >
            <span class="text-base leading-none">{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </template>
      </aside>

      <!-- Mobile Horizontal Tabs -->
      <div
        v-if="isMobile"
        class="flex overflow-x-auto gap-1 p-2 border-b border-[var(--border-color)] flex-shrink-0"
      >
        <button
          v-for="tab in visibleTabs"
          :key="tab.key"
          class="tab-button whitespace-nowrap px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1"
          :class="
            activeTab === tab.key
              ? 'bg-[var(--accent)] text-white'
              : 'text-[var(--ink-secondary)] hover:bg-[var(--glass)]'
          "
          @click="activeTab = tab.key"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <!-- Content Area -->
      <div class="flex-1 overflow-y-auto p-4 md:p-6">
        <Suspense>
          <component :is="currentComponent" />
          <template #fallback>
            <div class="flex items-center justify-center h-full min-h-[200px]">
              <div class="flex flex-col items-center gap-3 text-[var(--ink-muted)]">
                <svg
                  class="animate-spin h-8 w-8"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  />
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                <span class="text-sm">加载中...</span>
              </div>
            </div>
          </template>
        </Suspense>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { ref, computed, defineAsyncComponent, markRaw } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

const authStore = useAuthStore()
const appStore = useAppStore()

const isMobile = computed(() => appStore.isMobile)

const allTabs = [
  { key: 'users', label: '用户管理', icon: '👥', permission: 'manage_users' },
  { key: 'groups', label: '权限组', icon: '🔑', permission: 'manage_groups' },
  { key: 'logs', label: '日志查看', icon: '📋', permission: 'view_logs' },
  { key: 'sessions', label: '会话管理', icon: '💬', permission: 'manage_sessions' },
  { key: 'health', label: '系统状态', icon: '💚' },
  { key: 'profile', label: '个人信息', icon: '👤' },
  { key: 'messages', label: '留言板', icon: '📝' },
  { key: 'ipban', label: 'IP封禁', icon: '🚫', permission: 'manage_ip_bans' },
  { key: 'sms', label: '短信配置', icon: '📱', permission: 'manage_sms' },
  { key: 'config', label: '系统配置', icon: '⚙️', permission: 'manage_config' },
  { key: 'captcha', label: '验证码', icon: '🔒', permission: 'manage_captcha' },
  { key: 'reminders', label: '定时提醒', icon: '⏰', permission: 'manage_reminders' },
  { key: 'ssl', label: 'HTTPS', icon: '🔐', permission: 'manage_ssl' },
  { key: 'cdn', label: 'CDN', icon: '🌐', permission: 'manage_cdn' },
  { key: 'bruteforce', label: '暴力破解', icon: '🛡️', permission: 'manage_security' },
  { key: 'payment-logs', label: '支付日志', icon: '🧾', permission: 'view_payment_logs' },
  { key: 'payment-settings', label: '支付设置', icon: '💳', permission: 'manage_payment' },
  { key: 'pricing', label: '定价管理', icon: '💰', permission: 'manage_pricing' },
  { key: 'watermark', label: '水印管理', icon: '💧', permission: 'manage_watermark' },
  { key: 'billing', label: '账单管理', icon: '📄', permission: 'manage_billing' },
  { key: 'billing-logs', label: '账单日志', icon: '📊', permission: 'view_billing_logs' },
  { key: 'restore-account', label: '恢复账号', icon: '♻️', permission: 'restore_accounts' },
]

const tabGroups = [
  {
    label: '用户与权限',
    tabs: ['users', 'groups', 'sessions'],
  },
  {
    label: '系统',
    tabs: ['health', 'logs', 'config'],
  },
  {
    label: '个人',
    tabs: ['profile', 'messages'],
  },
  {
    label: '安全',
    tabs: ['ipban', 'captcha', 'bruteforce', 'ssl'],
  },
  {
    label: '通讯与提醒',
    tabs: ['sms', 'reminders'],
  },
  {
    label: '网络',
    tabs: ['cdn'],
  },
  {
    label: '支付与账单',
    tabs: ['payment-logs', 'payment-settings', 'pricing', 'billing', 'billing-logs'],
  },
  {
    label: '其他',
    tabs: ['watermark', 'restore-account'],
  },
]

const componentMap = {
  'users': () => import('./AdminUsers.vue'),
  'groups': () => import('./AdminGroups.vue'),
  'logs': () => import('./AdminLogs.vue'),
  'sessions': () => import('./AdminSessions.vue'),
  'health': () => import('./AdminHealth.vue'),
  'profile': () => import('./AdminProfile.vue'),
  'messages': () => import('./AdminMessages.vue'),
  'ipban': () => import('./AdminIPBan.vue'),
  'sms': () => import('./AdminSMS.vue'),
  'config': () => import('./AdminConfig.vue'),
  'captcha': () => import('./AdminCaptcha.vue'),
  'reminders': () => import('./AdminReminders.vue'),
  'ssl': () => import('./AdminSSL.vue'),
  'cdn': () => import('./AdminCDN.vue'),
  'bruteforce': () => import('./AdminBruteforce.vue'),
  'payment-logs': () => import('./AdminPaymentLogs.vue'),
  'payment-settings': () => import('./AdminPaymentSettings.vue'),
  'pricing': () => import('./AdminPricing.vue'),
  'watermark': () => import('./AdminWatermark.vue'),
  'billing': () => import('./AdminBilling.vue'),
  'billing-logs': () => import('./AdminBillingLogs.vue'),
  'restore-account': () => import('./AdminRestoreAccount.vue'),
}

function hasPermission(tab) {
  if (!tab.permission) return true
  return authStore.isAdmin || authStore.permissions?.[tab.permission]
}

const visibleTabs = computed(() => allTabs.filter(hasPermission))

const activeTab = ref(visibleTabs.value.length > 0 ? visibleTabs.value[0].key : 'health')

function filteredGroupTabs(tabKeys) {
  return tabKeys
    .map((key) => allTabs.find((t) => t.key === key))
    .filter((tab) => tab && hasPermission(tab))
}

const currentComponent = computed(() => {
  const loader = componentMap[activeTab.value]
  if (!loader) return null
  return markRaw(defineAsyncComponent(loader))
})
</script>
