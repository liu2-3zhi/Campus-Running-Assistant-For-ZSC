<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { useThemeStore } from '@/stores/theme'
import { useNotificationStore } from '@/stores/notification'
import { callAPI } from '@/services/api'
import { disconnectWebSocket } from '@/services/socket'
import { useRouter } from 'vue-router'
import PaymentModal from '@/components/main/PaymentModal.vue'
import OrdersModal from '@/components/main/OrdersModal.vue'
import BillingModal from '@/components/main/BillingModal.vue'

const auth = useAuthStore()
const app = useAppStore()
const theme = useThemeStore()
const notifStore = useNotificationStore()
const router = useRouter()

const emit = defineEmits(['show-notifications', 'show-user-details', 'show-admin'])

// 支付 / 订单 / 账单 弹窗（复刻 original 用户端入口）
const showPayment = ref(false)
const showOrders = ref(false)
const showBilling = ref(false)

async function handleLogout() {
  try {
    await callAPI('logout')
  } catch (_) {
    // proceed with logout even if API fails
  }
  disconnectWebSocket()
  auth.logout()
  router.push('/')
}
</script>

<template>
  <div class="panel p-3">
    <!-- User avatar and name -->
    <div class="flex items-center gap-3 mb-3">
      <div class="w-10 h-10 rounded-full bg-[var(--accent)] flex items-center justify-center text-white font-semibold shrink-0">
        <img
          v-if="auth.avatarUrl"
          :src="auth.avatarUrl"
          class="w-10 h-10 rounded-full object-cover"
          :alt="auth.displayName || auth.username"
        />
        <span v-else>{{ (auth.displayName || auth.username || '?').charAt(0).toUpperCase() }}</span>
      </div>
      <div class="min-w-0 flex-1">
        <div class="text-sm font-semibold text-[var(--ink)] truncate">
          姓名: {{ auth.realName || auth.displayName || auth.username || '--' }}
        </div>
        <div class="text-xs text-[var(--ink-muted)] truncate">
          学号: {{ auth.studentId || '--' }}
        </div>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex flex-wrap gap-1.5">
      <!-- Notifications -->
      <button
        class="btn btn-ghost text-xs relative"
        @click="emit('show-notifications')"
        title="通知"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        通知
        <span
          v-if="notifStore.unreadCount > 0"
          class="absolute -top-1 -right-1 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-[var(--danger)] text-white text-[10px] font-bold px-1"
        >
          {{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}
        </span>
      </button>

      <!-- User details -->
      <button
        class="btn btn-ghost text-xs"
        @click="emit('show-user-details')"
        title="用户详情"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        详情
      </button>

      <!-- 我的订单 -->
      <button
        class="btn btn-ghost text-xs"
        @click="showOrders = true"
        title="我的订单"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        订单
      </button>

      <!-- 我的账单 -->
      <button
        class="btn btn-ghost text-xs"
        @click="showBilling = true"
        title="我的账单"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z" />
        </svg>
        账单
      </button>

      <!-- 发起支付 -->
      <button
        class="btn btn-ghost text-xs"
        @click="showPayment = true"
        title="发起支付"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
        支付
      </button>

      <!-- Admin panel -->
      <button
        v-if="auth.isAdmin"
        class="btn btn-ghost text-xs"
        @click="emit('show-admin')"
        title="管理面板"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        管理
      </button>

      <!-- Dark mode toggle -->
      <button
        class="btn btn-ghost text-xs"
        @click="theme.toggleDark()"
        :title="theme.isDark ? '切换亮色' : '切换暗色'"
      >
        <svg v-if="theme.isDark" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      </button>

      <!-- Logout -->
      <button
        class="btn btn-danger text-xs ml-auto"
        @click="handleLogout"
        title="退出登录"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        退出
      </button>
    </div>

    <!-- 支付 / 订单 / 账单 弹窗（复刻 original 用户端） -->
    <PaymentModal :visible="showPayment" @close="showPayment = false" @paid="showOrders = true" />
    <OrdersModal :visible="showOrders" @close="showOrders = false" />
    <BillingModal :visible="showBilling" @close="showBilling = false" />
  </div>
</template>
