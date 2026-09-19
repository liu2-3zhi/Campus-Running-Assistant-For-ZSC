<template>
  <teleport to="body">
    <transition name="fade">
      <div
        v-if="visible"
        id="admin-panel-modal"
        class="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-4"
      >
        <div
          class="absolute inset-0 bg-gradient-to-br from-black/50 to-slate-900/60 backdrop-blur-sm"
          @click="emit('close')"
        />
        <div
          class="panel admin-dialog relative flex h-[100dvh] max-h-[100dvh] w-full max-w-full flex-col space-y-4 overflow-hidden rounded-none border-2 border-white/20 p-4 shadow-2xl md:h-auto md:max-h-[85vh] md:w-[65rem] md:space-y-5 md:rounded-3xl md:p-8"
        >
          <div class="relative mb-2 flex flex-shrink-0 items-center justify-between gap-2 text-center md:block">
            <div class="flex min-w-0 items-center justify-center gap-2 md:gap-3">
              <svg
                class="h-6 w-6 shrink-0 text-sky-500 md:h-8 md:w-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <h3 class="inline-block bg-gradient-to-r from-sky-600 to-blue-600 bg-clip-text text-xl font-bold text-transparent md:text-3xl">
                管理面板
              </h3>
            </div>
            <button
              class="btn btn-ghost admin-close shrink-0 !px-3 !py-2 rounded-xl hover:bg-red-50 hover:text-red-600 md:absolute md:right-0 md:top-1/2 md:-translate-y-1/2 md:!px-4"
              @click="emit('close')"
            >
              <svg class="mr-1 inline h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              关闭
            </button>
          </div>

          <div class="flex flex-shrink-0 gap-1 overflow-x-auto border-b-2 border-slate-200 pb-0">
            <button
              v-for="tab in visibleTabs"
              :key="tab.key"
              class="whitespace-nowrap rounded-t-lg px-5 py-3 font-semibold transition-all duration-200"
              :class="activeTab === tab.key
                ? 'border-b-[3px] border-sky-600 text-sky-600'
                : 'border-b-[3px] border-transparent text-slate-400 hover:bg-slate-50 hover:text-slate-600'"
              @click="activeTab = tab.key"
            >
              <AdminTabIcon :name="tab.key" />
              {{ tab.label }}
            </button>
          </div>

          <div class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
            <Suspense>
              <component :is="currentComponent" />
              <template #fallback>
                <div class="flex min-h-[200px] items-center justify-center">
                  <span class="text-sm text-slate-400">加载中...</span>
                </div>
              </template>
            </Suspense>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent, markRaw } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { callRawAPI } from '@/services/api'
import AdminTabIcon from './AdminTabIcon.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

const authStore = useAuthStore()
const requirePayment = ref(false)

async function loadPricingVisibility() {
  requirePayment.value = false
  try {
    const result = await callRawAPI('/api/config/pricing', 'GET')
    requirePayment.value = result.success !== false && result.config?.require_payment === true
  } catch (_) {
    // 配置读取失败时仍保留管理员的支付历史入口。
  }
}
const allTabs = [
  { key: 'users', label: '用户管理', icon: '👥', permission: 'manage_users' },
  { key: 'groups', label: '权限组', icon: '🔑', permission: 'manage_permissions' },
  { key: 'logs', label: '日志查看', icon: '📋', permission: 'view_logs' },
  { key: 'health', label: '系统状态', icon: '💚' },
  { key: 'profile', label: '个人信息', icon: '👤', permission: 'no_guest' },
  { key: 'sessions', label: '会话管理', icon: '💬' },
  { key: 'messages', label: '留言板', icon: '📝' },
  { key: 'ipban', label: 'IP封禁', icon: '🚫', permission: 'manage_system' },
  { key: 'sms', label: '短信配置', icon: '📱', permission: 'modify_config' },
  { key: 'config', label: '系统配置', icon: '⚙️', permission: 'modify_config' },
  { key: 'captcha', label: '验证码', icon: '🔒', permission: 'view_captcha_history' },
  { key: 'reminders', label: '定时提醒', icon: '⏰', permission: 'view_logs' },
  { key: 'ssl', label: 'HTTPS', icon: '🔐', permission: 'view_logs' },
  { key: 'cdn', label: 'CDN', icon: '🌐', permission: 'modify_config' },
  { key: 'bruteforce', label: '密码恢复', icon: '🛡️', permission: 'admin' },
  { key: 'payment-logs', label: '支付历史', icon: '🧾', permission: 'view_audit_logs' },
  { key: 'payment-settings', label: '支付设置', icon: '💳', permission: 'modify_config' },
  { key: 'pricing', label: '定价管理', icon: '💰', permission: 'modify_config' },
  { key: 'watermark', label: '水印管理', icon: '💧', permission: 'admin' },
  { key: 'billing', label: '账单管理', icon: '📄', permission: 'admin' },
  { key: 'billing-logs', label: '账单日志', icon: '📊', permission: 'admin' },
  { key: 'restore-account', label: '恢复账号', icon: '♻️', permission: 'admin' },
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
  if (tab.key === 'payment-logs') return authStore.isAdmin || requirePayment.value || !!authStore.permissions?.view_audit_logs
  if (tab.permission === 'no_guest') return !authStore.isGuest
  if (tab.permission === 'admin') return authStore.isAdmin
  return !!authStore.permissions?.[tab.permission]
}

const visibleTabs = computed(() => allTabs.filter(hasPermission))

const activeTab = ref('sessions')

watch(visibleTabs, tabs => {
  if (!tabs.some(tab => tab.key === activeTab.value)) activeTab.value = 'sessions'
})

watch(() => props.visible, async visible => {
  if (visible) {
    activeTab.value = 'sessions'
    await Promise.all([
      loadPricingVisibility(),
      authStore.loadPermissions([
        ...allTabs.map(tab => tab.permission).filter(key => key && !['admin', 'no_guest'].includes(key)),
        'view_all_sessions', 'manage_user_sessions',
      ]),
    ])
  }
}, { immediate: true })

const currentComponent = computed(() => {
  const loader = componentMap[activeTab.value]
  if (!loader) return null
  return markRaw(defineAsyncComponent(loader))
})
</script>

<style scoped>
.admin-dialog {
  border-radius: 24px;
}
.admin-close {
  border-radius: 12px;
}
@media (max-width: 767px) {
  .admin-dialog {
    border-radius: 0;
  }
}
</style>
