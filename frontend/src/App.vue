<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import BannedOverlay from '@/components/common/BannedOverlay.vue'
import NetworkErrorDialog from '@/components/common/NetworkErrorDialog.vue'

const app = useAppStore()
const theme = useThemeStore()
const auth = useAuthStore()

function handleResize() {
  app.detectMobile()
}

onMounted(() => {
  app.detectMobile()
  theme.initFromStorage()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div id="app-root" class="min-h-screen">
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>

    <LoadingOverlay v-if="app.isLoading" />
    <BannedOverlay v-if="auth.isBanned" />
    <NetworkErrorDialog />
  </div>
</template>
