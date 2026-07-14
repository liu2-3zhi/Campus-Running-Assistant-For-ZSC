<script setup>
import { onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notification'

const notifStore = useNotificationStore()

function formatTime(time) {
  if (!time) return ''
  try {
    const d = new Date(time)
    if (isNaN(d.getTime())) return time
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin}分钟前`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}小时前`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 7) return `${diffDay}天前`
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch (_) {
    return time
  }
}

function handleMarkRead(id) {
  notifStore.markRead(id)
}

function handleMarkAllRead() {
  notifStore.markAllRead()
}

function handleRefresh() {
  notifStore.fetchNotifications()
}

onMounted(() => {
  notifStore.fetchNotifications()
})
</script>

<template>
  <div class="panel p-4">
    <!-- Header -->
    <div class="mb-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold" style="color: var(--ink)">
          通知
        </h3>
        <span
          v-if="notifStore.unreadCount > 0"
          class="flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-medium text-white"
          style="background: var(--danger)"
        >
          {{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          class="btn btn-ghost p-1.5 text-xs"
          :disabled="notifStore.unreadCount === 0"
          title="全部已读"
          @click="handleMarkAllRead"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
        <button
          class="btn btn-ghost p-1.5 text-xs"
          :disabled="notifStore.isLoading"
          title="刷新"
          @click="handleRefresh"
        >
          <svg
            class="h-4 w-4"
            :class="{ 'animate-spin': notifStore.isLoading }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Notification list -->
    <div class="max-h-80 space-y-2 overflow-y-auto">
      <div
        v-if="notifStore.notifications.length === 0 && !notifStore.isLoading"
        class="py-8 text-center text-sm"
        style="color: var(--ink-muted)"
      >
        <svg class="mx-auto mb-2 h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        暂无通知
      </div>

      <div
        v-if="notifStore.isLoading && notifStore.notifications.length === 0"
        class="py-8 text-center text-sm"
        style="color: var(--ink-muted)"
      >
        加载中...
      </div>

      <div
        v-for="notif in notifStore.notifications"
        :key="notif.id"
        class="group relative cursor-pointer rounded-lg p-3 transition-colors"
        :style="{
          background: notif.read ? 'transparent' : 'var(--glass)',
          borderLeft: notif.read ? '3px solid transparent' : '3px solid var(--accent)',
        }"
        @click="!notif.read && handleMarkRead(notif.id)"
      >
        <!-- Unread dot -->
        <div
          v-if="!notif.read"
          class="absolute right-2 top-2 h-2 w-2 rounded-full"
          style="background: var(--accent)"
        ></div>

        <!-- Title -->
        <div
          class="mb-1 text-sm font-medium"
          :style="{ color: notif.read ? 'var(--ink-secondary)' : 'var(--ink)' }"
        >
          {{ notif.title || '系统通知' }}
        </div>

        <!-- Message -->
        <div
          class="text-xs leading-relaxed"
          style="color: var(--ink-muted)"
        >
          {{ notif.message || notif.content || '' }}
        </div>

        <!-- Time -->
        <div
          class="mt-1.5 text-xs"
          style="color: var(--ink-muted)"
        >
          {{ formatTime(notif.time || notif.created_at) }}
        </div>
      </div>
    </div>
  </div>
</template>
