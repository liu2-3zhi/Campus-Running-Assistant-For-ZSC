import { defineStore } from 'pinia'
import { ref } from 'vue'
import { callAPI } from '@/services/api'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const isLoading = ref(false)

  async function fetchNotifications() {
    isLoading.value = true
    try {
      const data = await callAPI('get_notifications')
      if (data?.notices) {
        notifications.value = data.notices
        unreadCount.value = data.unreadCount || 0
      }
    } catch (_) {}
    isLoading.value = false
  }

  async function markAllRead() {
    try {
      const unread = notifications.value.filter(n => !n.read)
      for (const n of unread) {
        await callAPI('mark_notification_read', { notice_id: n.id })
      }
      notifications.value.forEach(n => { n.read = true })
      unreadCount.value = 0
    } catch (_) {}
  }

  async function markRead(id) {
    try {
      await callAPI('mark_notification_read', { notice_id: id })
      const n = notifications.value.find(x => x.id === id)
      if (n && !n.read) {
        n.read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch (_) {}
  }

  return { notifications, unreadCount, isLoading, fetchNotifications, markAllRead, markRead }
})
