<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['clear'])

const logContainer = ref(null)
const autoScroll = ref(true)

function levelColor(level) {
  const l = (level || '').toUpperCase()
  if (l === 'ERROR') return 'text-red-500'
  if (l === 'WARNING') return 'text-amber-500'
  if (l === 'INFO') return 'text-blue-500'
  if (l === 'DEBUG') return 'text-gray-400'
  return 'text-[var(--ink-secondary)]'
}

function levelBg(level) {
  const l = (level || '').toUpperCase()
  if (l === 'ERROR') return 'bg-red-500/10'
  if (l === 'WARNING') return 'bg-amber-500/10'
  return ''
}

function formatTime(time) {
  if (!time) return ''
  if (typeof time === 'string') return time
  const d = new Date(time)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

function scrollToBottom() {
  if (logContainer.value && autoScroll.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

function handleScroll() {
  if (!logContainer.value) return
  const el = logContainer.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScroll.value = atBottom
}

watch(() => props.logs.length, () => {
  nextTick(scrollToBottom)
})
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs text-[var(--ink-muted)]">{{ logs.length }} 条日志</span>
      <button class="btn btn-ghost text-xs px-2 py-1" @click="emit('clear')">
        清空
      </button>
    </div>
    <div
      ref="logContainer"
      class="flex-1 overflow-y-auto min-h-0 space-y-0.5 font-mono text-xs"
      @scroll="handleScroll"
    >
      <div v-if="logs.length === 0" class="text-center text-[var(--ink-muted)] py-8">
        暂无日志
      </div>
      <div
        v-for="(log, i) in logs"
        :key="i"
        class="flex gap-2 px-2 py-0.5 rounded"
        :class="levelBg(log.level)"
      >
        <span class="text-[var(--ink-muted)] shrink-0 w-16">{{ formatTime(log.time) }}</span>
        <span class="shrink-0 w-12 font-semibold" :class="levelColor(log.level)">
          {{ (log.level || 'INFO').toUpperCase() }}
        </span>
        <span class="text-[var(--ink-secondary)] shrink-0" v-if="log.source">[{{ log.source }}]</span>
        <span class="text-[var(--ink)] break-all">{{ log.msg }}</span>
      </div>
    </div>
    <div v-if="!autoScroll" class="text-center mt-1">
      <button
        class="text-xs text-[var(--accent)] hover:underline"
        @click="autoScroll = true; scrollToBottom()"
      >
        滚动到底部
      </button>
    </div>
  </div>
</template>
