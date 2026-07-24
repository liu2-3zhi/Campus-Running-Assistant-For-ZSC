<script setup>
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-red-900/90 backdrop-blur-sm">
    <div class="max-w-md rounded-2xl bg-white p-8 text-center shadow-2xl">
      <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
        <svg class="h-8 w-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
        </svg>
      </div>
      <h2 class="mb-2 text-xl font-bold text-red-600">账号已被封禁</h2>
      <p class="mb-6 text-sm text-slate-500">
        {{ auth.bannedData?.message || '您的账号已被管理员封禁，如有疑问请联系管理员。' }}
      </p>
      <a href="/" class="btn btn-primary">返回首页</a>
    </div>
  </div>
</template>
