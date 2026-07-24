<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
const localBeian = ref(null)

const beian = computed(() => app.beianData || localBeian.value)
const icpText = computed(() => beian.value?.icp_text || '')
const icpLink = computed(() => beian.value?.icp_link || '')
const policeText = computed(() => beian.value?.police_text || '')
const policeLink = computed(() => beian.value?.police_link || '')
const show = computed(() => !!(icpText.value || policeText.value))

onMounted(async () => {
  if (app.beianData) return
  try {
    const res = await fetch('/api/get_initial_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([]),
    })
    if (res.ok) {
      const data = await res.json()
      if (data?.beian) {
        localBeian.value = data.beian
        app.beianData = data.beian
      }
    }
  } catch (_) {}
})
</script>

<template>
  <footer v-if="show" class="py-3 text-center text-xs text-slate-400">
    <a v-if="icpText" :href="icpLink" target="_blank" class="mx-2 hover:text-slate-600">{{ icpText }}</a>
    <a v-if="policeText" :href="policeLink" target="_blank" class="mx-2 hover:text-slate-600">{{ policeText }}</a>
  </footer>
</template>
