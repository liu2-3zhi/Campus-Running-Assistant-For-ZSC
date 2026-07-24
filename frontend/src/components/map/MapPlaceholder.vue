<script setup>
defineProps({
  providerName: { type: String, default: '' },
  hasKey: { type: Boolean, default: false },
  errorReason: { type: String, default: '' },
})
</script>

<template>
  <div
    class="flex h-full w-full flex-col items-center justify-center gap-4 rounded-xl p-8"
    :class="[
      errorReason
        ? 'border-2 border-dashed border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-900/10'
        : !hasKey
          ? 'border-2 border-dashed border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-900/10'
          : 'border-2 border-dashed border-sky-300 bg-sky-50/50 dark:border-sky-800 dark:bg-sky-900/10'
    ]"
  >
    <!-- Map icon -->
    <div
      class="flex h-16 w-16 items-center justify-center rounded-full"
      :class="[
        errorReason
          ? 'bg-red-100 dark:bg-red-900/30'
          : !hasKey
            ? 'bg-amber-100 dark:bg-amber-900/30'
            : 'bg-sky-100 dark:bg-sky-900/30'
      ]"
    >
      <svg
        class="h-8 w-8"
        :class="[
          errorReason
            ? 'text-red-500'
            : !hasKey
              ? 'text-amber-500'
              : 'text-sky-500'
        ]"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.5"
          d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
        />
      </svg>
    </div>

    <!-- Provider name -->
    <h3 class="text-lg font-semibold" style="color: var(--ink)">
      {{ providerName || '地图' }}
    </h3>

    <!-- Status message -->
    <div class="max-w-xs text-center text-sm" style="color: var(--ink-secondary)">
      <template v-if="errorReason">
        <p class="mb-1 font-medium text-red-600 dark:text-red-400">
          地图加载失败
        </p>
        <p>{{ errorReason }}</p>
      </template>
      <template v-else-if="!hasKey">
        <p class="mb-1 font-medium text-amber-600 dark:text-amber-400">
          未配置 API Key
        </p>
        <p>请在设置中配置{{ providerName }}的 API Key 以启用地图显示</p>
      </template>
      <template v-else>
        <p>地图加载中...</p>
      </template>
    </div>

    <!-- Route planning hint -->
    <div
      class="mt-2 rounded-lg px-4 py-2 text-xs"
      style="background: var(--glass); color: var(--ink-muted)"
    >
      路线规划仍由后端执行
    </div>
  </div>
</template>
