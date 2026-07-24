<script setup>
const emit = defineEmits(['enter-multi'])
</script>

<template>
  <div class="space-y-4 text-center">
    <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full" style="background: var(--glass)">
      <svg class="h-7 w-7" style="color: var(--accent)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    </div>

    <div class="space-y-1">
      <h3 class="text-xl font-bold" style="color: var(--ink)">掌上莲峰</h3>
      <p class="text-lg font-semibold" style="color: var(--accent)">多账号模式</p>
    </div>

    <ul class="space-y-2 text-left text-sm" style="color: var(--ink-secondary)">
      <li class="flex items-start gap-2">
        <span class="shrink-0">✨</span>
        支持批量导入账号
      </li>
      <li class="flex items-start gap-2">
        <span class="shrink-0">🎯</span>
        统一管理所有任务
      </li>
      <li class="flex items-start gap-2">
        <span class="shrink-0">⚡</span>
        一键执行全部流程
      </li>
    </ul>

    <button
      class="btn btn-secondary w-full py-3.5"
      title="多账号"
      aria-label="多账号"
      @click="emit('enter-multi')"
    >
      进入多账号控制台
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
    </button>
  </div>
</template>
