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

    <h3 class="text-lg font-semibold">多账号模式</h3>

    <p class="text-sm leading-relaxed" style="color: var(--ink-secondary)">
      多账号模式支持同时管理多个运动账号，批量执行跑步任务。
      您可以为每个账号独立配置路线、步数和速度参数，
      实时监控各账号运行状态。
    </p>

    <ul class="space-y-2 text-left text-sm" style="color: var(--ink-secondary)">
      <li class="flex items-start gap-2">
        <svg class="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        批量导入和管理多个账号
      </li>
      <li class="flex items-start gap-2">
        <svg class="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        每个账号独立配置跑步参数
      </li>
      <li class="flex items-start gap-2">
        <svg class="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        一键批量启动与停止任务
      </li>
      <li class="flex items-start gap-2">
        <svg class="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        实时状态看板，统一监控
      </li>
    </ul>

    <button
      class="btn btn-primary w-full"
      @click="emit('enter-multi')"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
      进入多账号模式
    </button>
  </div>
</template>
