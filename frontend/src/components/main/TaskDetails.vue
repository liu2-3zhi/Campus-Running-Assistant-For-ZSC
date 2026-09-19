<script setup>
import { computed } from 'vue'
import { taskName, taskStatus, taskPoints } from './taskData'

const props = defineProps({ task: { type: Object, default: null }, mobile: Boolean })
const basicInfo = computed(() => ({
  任务名称: taskName(props.task), 任务状态: taskStatus(props.task).label,
  任务ID: props.task?.errand_id, 计划ID: props.task?.errand_schedule,
}))
const timeInfo = computed(() => ({
  开始时间: props.task?.start_time, 结束时间: props.task?.end_time, 上传时间: props.task?.upload_time,
}))
const points = computed(() => taskPoints(props.task || {}))
function coordinate(value) {
  return value == null || !Number.isFinite(Number(value)) ? '--' : Number(value).toFixed(5)
}
</script>

<template>
  <div v-if="!task" class="py-8 text-center text-sm text-slate-400">请先在任务列表中选择一个任务</div>
  <div v-else class="space-y-4 text-sm">
    <section :class="mobile ? 'rounded-xl border border-blue-200 bg-blue-50 p-4' : ''">
      <h4 v-if="mobile" class="mb-3 font-semibold text-blue-700">基本信息</h4>
      <div v-for="(value, label) in basicInfo" :key="label" class="flex items-start gap-2 py-1">
        <span class="min-w-20 font-semibold text-slate-500">{{ label }}:</span>
        <span class="min-w-0 flex-1 break-all text-slate-800">{{ value ?? 'NULL' }}</span>
      </div>
    </section>
    <section :class="mobile ? 'rounded-xl border border-green-200 bg-green-50 p-4' : ''">
      <h4 v-if="mobile" class="mb-3 font-semibold text-green-700">时间信息</h4>
      <div v-for="(value, label) in timeInfo" :key="label" class="flex items-start gap-2 py-1">
        <span class="min-w-20 font-semibold text-slate-500">{{ label }}:</span>
        <span class="min-w-0 flex-1 break-all text-slate-800">{{ value || 'NULL' }}</span>
      </div>
    </section>
    <section :class="mobile ? 'rounded-xl border border-purple-200 bg-purple-50 p-4' : ''">
      <h4 class="mb-3 font-semibold" :class="mobile ? 'text-purple-700' : 'text-slate-500'">打卡点列表</h4>
      <div v-for="(point, index) in points" :key="index" class="mb-2 rounded-lg p-2" :class="mobile ? 'border border-purple-200 bg-white' : ''">
        <div class="flex items-center gap-2 text-slate-800"><span class="font-mono">{{ index + 1 }}.</span>{{ point.name }}</div>
        <p class="mt-1 pl-5 text-xs text-slate-400">坐标: {{ coordinate(point.lng) }}, {{ coordinate(point.lat) }}</p>
      </div>
      <p v-if="!points.length" class="py-4 text-center text-slate-400">该任务暂无打卡点数据</p>
    </section>
    <section v-if="mobile" class="rounded-xl border border-amber-200 bg-amber-50 p-4">
      <h4 class="mb-3 font-semibold text-amber-700">历史记录</h4>
      <p v-for="(record, index) in (task.history || [])" :key="index" class="break-all border-b border-amber-200 py-2 last:border-0">{{ index + 1 }}. {{ typeof record === 'string' ? record : JSON.stringify(record) }}</p>
      <p v-if="!task.history?.length" class="py-4 text-center text-slate-400">暂无历史记录</p>
    </section>
  </div>
</template>
