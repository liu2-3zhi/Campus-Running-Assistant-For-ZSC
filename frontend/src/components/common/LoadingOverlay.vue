<template>
  <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-white/80 backdrop-blur-sm dark:bg-slate-900/80">
    <div class="text-center">
      <div class="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-sky-200 border-t-sky-500"></div>
      <p class="text-sm text-slate-500">{{ message }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '加载中...' },
})
</script>
