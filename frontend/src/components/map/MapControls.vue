<script setup>
defineProps({
  zoomLevel: { type: Number, default: 13 },
})

const emit = defineEmits(['zoom-in', 'zoom-out', 'reset-view'])
</script>

<template>
  <div
    class="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-full px-2 py-1 shadow-sm"
    style="background: var(--card-bg); border: 1px solid var(--border-color); color: var(--ink)"
  >
    <!-- Zoom in -->
    <button
      class="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
      title="放大"
      @click="emit('zoom-in')"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v12M6 12h12" />
      </svg>
    </button>

    <!-- Zoom level display -->
    <div
      class="flex h-8 min-w-8 items-center justify-center px-1 text-sm font-medium"
      style="color: var(--ink-secondary)"
      title="当前缩放级别"
    >
      {{ zoomLevel }}
    </div>

    <!-- Zoom out -->
    <button
      class="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
      title="缩小"
      @click="emit('zoom-out')"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 12h12" />
      </svg>
    </button>

    <div class="mx-1 h-5 w-px" style="background: #cbd5e1"></div>

    <!-- Reset view -->
    <button
      class="flex h-8 w-8 items-center justify-center rounded-full text-sky-600 transition-colors hover:bg-sky-50"
      title="重置视图"
      @click="emit('reset-view')"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
      </svg>
    </button>
  </div>
</template>
