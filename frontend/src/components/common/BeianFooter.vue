<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
const localBeian = ref(null)

const beian = computed(() => app.beianData || localBeian.value)
const icpText = computed(() => beian.value?.icp_text || beian.value?.icp_number || '')
const icpLink = computed(() => beian.value?.icp_link || '')
const policeText = computed(() => beian.value?.police_text || beian.value?.police_number || '')
const policeLink = computed(() => beian.value?.police_link || '')
const show = computed(() => {
  const icpVisible = beian.value?.show_icp !== false && !!icpText.value
  const policeVisible = beian.value?.show_police !== false && !!policeText.value
  return icpVisible || policeVisible
})

onMounted(async () => {
  if (app.beianData) return
  try {
    const res = await fetch('/api/public/beian_config', { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      if (data?.data || data?.beian) {
        const next = data.data || data.beian
        localBeian.value = next
        app.beianData = next
      }
    }
  } catch (_) {}
})
</script>

<template>
  <footer
    v-if="show"
    class="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-center text-xs text-slate-400"
  >
    <a
      v-if="icpText"
      :href="icpLink || 'https://beian.miit.gov.cn'"
      target="_blank"
      rel="noopener noreferrer"
      class="flex items-center gap-1 transition-colors hover:text-sky-600"
    >
      <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <span>{{ icpText }}</span>
    </a>
    <a
      v-if="policeText"
      :href="policeLink || 'https://beian.mps.gov.cn'"
      target="_blank"
      rel="noopener noreferrer"
      class="flex items-center gap-1 transition-colors hover:text-sky-600"
    >
      <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
        />
      </svg>
      <span>{{ policeText }}</span>
    </a>
  </footer>
</template>
