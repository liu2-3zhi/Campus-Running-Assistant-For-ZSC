<script setup>
import { useAppStore } from '@/stores/app'
import { computed } from 'vue'

const app = useAppStore()

const runData = computed(() => app.runData || {})

function formatDistance(meters) {
  if (meters == null) return '--'
  const m = Number(meters)
  if (isNaN(m)) return '--'
  if (m >= 1000) return (m / 1000).toFixed(2) + ' km'
  return m.toFixed(0) + ' m'
}

function formatTime(seconds) {
  if (seconds == null) return '--'
  const s = Number(seconds)
  if (isNaN(s)) return '--'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
}

const gpsLabel = computed(() => {
  const rd = runData.value
  const lat = rd.latitude ?? rd.lat
  const lng = rd.longitude ?? rd.lng
  if (lat != null && lng != null) {
    return `${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}`
  }
  return '--, --'
})

const stats = computed(() => [
  {
    label: '已跑距离',
    value: formatDistance(runData.value.live_distance || runData.value.current_distance),
    icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6'
  },
  {
    label: '总距离',
    value: formatDistance(runData.value.total_distance),
    icon: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7'
  },
  {
    label: '已用时间',
    value: formatTime(runData.value.live_time || runData.value.elapsed_time),
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
  },
  {
    label: '预计时间',
    value: formatTime(runData.value.total_time),
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
  },
  {
    label: '预估剩余时间',
    value: formatTime(runData.value.remaining_time),
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
  }
])
</script>

<template>
  <div class="panel p-3">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold text-[var(--ink)]">实时状态</h3>
      <p class="text-xs font-mono text-[var(--ink-muted)]">
        当前位置GPS坐标: {{ gpsLabel }}
      </p>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
      <div
        v-for="(stat, i) in stats"
        :key="i"
        class="rounded-lg bg-[var(--glass)] border border-[var(--border-color)] p-2.5"
      >
        <div class="flex items-center gap-1.5 mb-1">
          <svg class="w-3.5 h-3.5 text-[var(--ink-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="stat.icon" />
          </svg>
          <span class="text-[11px] text-[var(--ink-muted)]">{{ stat.label }}</span>
        </div>
        <div class="text-sm font-semibold text-[var(--ink)] truncate">{{ stat.value }}</div>
      </div>
    </div>
  </div>
</template>
