<script setup>
import { useAppStore } from '@/stores/app'
import { computed } from 'vue'

const app = useAppStore()

const runData = computed(() => app.runData || {})

function formatDistance(meters) {
  const value = Number(meters || 0)
  return `${(Number.isFinite(value) ? value / 1000 : 0).toFixed(2)} km`
}

function formatTime(seconds) {
  const value = Math.max(0, Number(seconds || 0))
  if (!Number.isFinite(value)) return '00:00'
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(Math.floor(value % 60)).padStart(2, '0')}`
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
    value: formatDistance((runData.value.total_run_distance_m ?? runData.value.total_distance)),
    icon: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7'
  },
  {
    label: '已用时间',
    value: formatTime(runData.value.live_time || runData.value.elapsed_time),
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
  },
  {
    label: '预计时间',
    value: formatTime((runData.value.total_run_time_s ?? runData.value.total_time)),
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
  <div id="status-panels" class="grid grid-cols-1 gap-4">
    <div class="panel flex flex-col gap-3 rounded-xl p-4">
      <div class="flex items-center justify-between">
        <h3 class="font-bold text-slate-800">实时状态</h3>
        <p class="text-sm font-mono text-slate-500">当前位置GPS坐标: {{ gpsLabel }}</p>
      </div>
      <div class="grid grid-cols-5 divide-x divide-slate-200 pt-2 text-center">
        <div v-for="stat in stats" :key="stat.label">
          <p class="text-sm text-slate-500">{{ stat.label }}</p>
          <p class="text-xl font-bold text-slate-700">{{ stat.value }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
