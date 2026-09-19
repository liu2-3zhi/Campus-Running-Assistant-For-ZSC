<script setup>
import { onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notification'

const notifStore = useNotificationStore()

function refresh() {
  notifStore.fetchNotifications()
}

function markRead(id) {
  notifStore.markRead(id)
}

onMounted(refresh)
</script>

<template>
  <div id="mobile-notification-panel" class="mobile-card flex h-screen flex-col overflow-hidden p-0">
    <div class="flex flex-col items-center border-b border-sky-100 p-4 pb-3 text-center">
      <div class="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-sky-500 text-white">
        <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      </div>
      <h3 class="text-xl font-bold text-sky-700">通知中心</h3>
    </div>

    <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
      <div
        v-if="notifStore.notifications.length === 0 && !notifStore.isLoading"
        class="flex h-full flex-col items-center justify-center py-12 text-center text-slate-400"
      >
        <svg class="mb-3 h-20 w-20 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        <p class="text-base font-medium">暂无通知</p>
        <p class="mt-1 text-sm text-slate-400">点击底部刷新按钮获取最新通知</p>
      </div>

      <button
        v-for="notification in notifStore.notifications"
        :key="notification.id"
        class="w-full rounded-xl border border-slate-200 bg-white p-3 text-left"
        @click="!notification.read && markRead(notification.id)"
      >
        <div class="flex items-start gap-2">
          <span
            class="mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full"
            :class="notification.read ? 'bg-slate-300' : 'bg-sky-500'"
          />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-slate-700">
              {{ notification.title || '系统通知' }}
            </p>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              {{ notification.message || notification.content || '' }}
            </p>
          </div>
        </div>
      </button>
    </div>

    <div class="flex-shrink-0 border-t border-slate-100 p-4">
      <button
        class="mobile-primary-btn"
        :disabled="notifStore.isLoading"
        @click="refresh"
      >
        {{ notifStore.isLoading ? '刷新中...' : '刷新' }}
      </button>
    </div>
  </div>
</template>
