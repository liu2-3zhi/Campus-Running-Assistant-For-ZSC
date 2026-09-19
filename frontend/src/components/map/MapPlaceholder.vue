<script setup>
defineProps({
  providerName: { type: String, default: '' },
  hasKey: { type: Boolean, default: false },
  errorReason: { type: String, default: '' },
})
</script>

<template>
  <div
    class="flex h-full w-full items-center justify-center bg-slate-100/70"
    :aria-label="providerName ? `${providerName}地图占位` : '地图占位'"
  >
    <div
      v-if="errorReason"
      class="max-w-xs rounded-lg border border-red-200 bg-red-50 p-4 text-center text-sm text-red-600"
    >
      地图加载失败：{{ errorReason }}
    </div>
  </div>
</template>
