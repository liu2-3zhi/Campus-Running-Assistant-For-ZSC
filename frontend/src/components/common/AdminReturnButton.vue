<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function returnToAdministrator() {
  const origin = auth.adminOriginSession
  const invalid = auth.adminViewInvalid
  auth.clearAdminView()
  if (invalid || !origin) {
    auth.logout()
    router.push({ name: 'login' })
    return
  }
  auth.activateSession(origin)
  router.push({ name: 'session', params: { uuid: origin } })
}
</script>

<template>
  <button
    v-if="auth.adminOriginSession && auth.adminOriginSession !== auth.sessionUUID"
    type="button"
    class="btn btn-primary fixed top-4 left-4 z-[10000] shadow-lg"
    @click="returnToAdministrator"
  >{{ auth.adminViewInvalid ? '管理员会话失效，返回登录' : '返回管理员会话' }}</button>
</template>
