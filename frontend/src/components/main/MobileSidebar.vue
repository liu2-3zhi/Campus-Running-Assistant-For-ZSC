<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import PaymentModal from '@/components/main/PaymentModal.vue'
import OrdersModal from '@/components/main/OrdersModal.vue'
import BillingModal from '@/components/main/BillingModal.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  isMultiMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['navigate', 'close', 'back'])

const auth = useAuthStore()

const navItems = [
  { key: 'control', label: '控制', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
  { key: 'map', label: '地图', icon: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7' },
  { key: 'tasks', label: '任务', icon: 'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z' },
  { key: 'task-details', label: '任务详情', icon: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z' },
  { key: 'notifications', label: '通知', icon: 'M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0' },
  { key: 'attendance', label: '签到', icon: 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z' },
  { key: 'log', label: '日志', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { key: 'checkpoints', label: '打卡点', iconPaths: ['M15 10.5a3 3 0 11-6 0 3 3 0 016 0z', 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z'] },
  { key: 'history', label: '历史记录', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'settings', label: '设置', icon: 'M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75' },
  { key: 'profile', label: '我的', icon: 'M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z' }
]

function handleNav(key) {
  emit('navigate', key)
  emit('close')
}

// 支付 / 订单 / 账单 弹窗（复刻 original 用户端入口）
const showPayment = ref(false)
const showOrders = ref(false)
const showBilling = ref(false)

const payNavItems = [
  { key: 'orders', label: '我的订单', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
  { key: 'billing', label: '我的账单', icon: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z' },
  { key: 'payment', label: '发起支付', icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
]

function openPayModal(kind) {
  if (kind === 'orders') showOrders.value = true
  else if (kind === 'billing') showBilling.value = true
  else if (kind === 'payment') showPayment.value = true
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 md:hidden"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-black/40 backdrop-blur-sm"
          @click="emit('close')"
        ></div>

        <!-- Sidebar panel -->
        <transition name="slide-left">
          <div
            v-if="visible"
            class="absolute top-0 left-0 bottom-0 w-64 bg-[var(--card-bg)] border-r border-[var(--border-color)] shadow-lg flex flex-col"
          >
            <!-- Header: Logo + Title -->
            <div class="p-4 border-b border-[var(--border-color)]">
              <div class="flex items-center gap-3">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-[var(--accent)]" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1-4.9-1-.4 2 7 1.4z" />
                </svg>
                <span class="text-base font-bold text-[var(--ink)]">跑步助手</span>
              </div>
            </div>

            <!-- Navigation -->
            <nav class="flex-1 overflow-y-auto py-2">
              <button
                v-for="item in navItems"
                :key="item.key"
                class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--ink-secondary)] hover:bg-[var(--glass)] hover:text-[var(--ink)] transition-colors"
                @click="handleNav(item.key)"
              >
                <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <template v-if="item.iconPaths">
                    <path v-for="(d, idx) in item.iconPaths" :key="idx" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="d" />
                  </template>
                  <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="item.icon" />
                </svg>
                {{ item.label }}
              </button>

              <!-- Divider -->
              <div class="my-2 mx-4 border-t border-[var(--border-color)]"></div>

              <!-- 支付 / 订单 / 账单 入口（复刻 original 用户端） -->
              <button
                v-for="item in payNavItems"
                :key="item.key"
                class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--ink-secondary)] hover:bg-[var(--glass)] hover:text-[var(--ink)] transition-colors"
                @click="openPayModal(item.key)"
              >
                <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="item.icon" />
                </svg>
                {{ item.label }}
              </button>

              <!-- Divider -->
              <div class="my-2 mx-4 border-t border-[var(--border-color)]"></div>

              <!-- Admin link (conditional) -->
              <button
                v-if="auth.isAdmin"
                class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--ink-secondary)] hover:bg-[var(--glass)] hover:text-[var(--ink)] transition-colors"
                @click="handleNav('admin')"
              >
                <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                管理面板
              </button>
            </nav>

            <!-- Back button (not logout) -->
            <div class="p-4 border-t border-[var(--border-color)]">
              <button
                class="btn btn-danger w-full justify-center text-sm"
                @click="emit('back')"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                返回
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </Teleport>

  <!-- 支付 / 订单 / 账单 弹窗（AppModal 自带 teleport，独立于侧边栏生命周期） -->
  <PaymentModal :visible="showPayment" @close="showPayment = false" @paid="showOrders = true" />
  <OrdersModal :visible="showOrders" @close="showOrders = false" />
  <BillingModal :visible="showBilling" @close="showBilling = false" />
</template>

<style scoped>
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
}
</style>
