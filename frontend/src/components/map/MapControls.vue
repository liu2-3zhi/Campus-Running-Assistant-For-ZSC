<script setup>
defineProps({ zoomLevel: { type: Number, default: 17 } })
const emit = defineEmits(['zoom-in', 'zoom-out', 'reset-view'])
</script>

<template>
  <div class="absolute right-3 top-4 z-10 flex items-center space-x-1 rounded-full border border-slate-200 bg-white/80 p-1 shadow-md backdrop-blur-sm">
    <button class="h-9 w-9 rounded-full text-center text-xl font-bold text-slate-700 hover:bg-slate-100" title="放大" @click="emit('zoom-in')">+</button>
    <span class="w-8 select-none text-center font-mono text-xs">{{ zoomLevel }}</span>
    <button class="h-9 w-9 rounded-full text-center text-xl font-bold text-slate-700 hover:bg-slate-100" title="缩小" @click="emit('zoom-out')">-</button>
    <button class="flex h-9 w-9 items-center justify-center rounded-full text-lg font-bold text-slate-700 hover:bg-slate-100" title="复位视角" @click="emit('reset-view')">🎯</button>
  </div>
</template>
