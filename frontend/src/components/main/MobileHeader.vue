<script setup>
const emit = defineEmits(['toggle-sidebar'])
</script>

<template>
  <header class="fixed top-0 left-0 right-0 z-40 h-12 flex items-center px-3 bg-[var(--card-bg)] border-b border-[var(--border-color)] backdrop-blur-md md:hidden">
    <button
      class="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-[var(--glass)] transition-colors"
      @click="emit('toggle-sidebar')"
      aria-label="打开菜单"
    >
      <svg class="w-5 h-5 text-[var(--ink)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
    <div class="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 flex items-center whitespace-nowrap">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-[var(--accent)]" viewBox="0 0 24 24" fill="currentColor">
        <path d="M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1-4.9-1-.4 2 7 1.4z"></path>
      </svg>
      <span class="ml-2 text-lg font-bold text-[var(--ink)]">跑步助手</span>
    </div>
    <div class="w-9"></div>
  </header>
</template>
