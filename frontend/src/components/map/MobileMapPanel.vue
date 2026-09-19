<script setup>
import { ref } from 'vue'
import MapContainer from '@/components/map/MapContainer.vue'

const mapRef = ref(null)

function zoomIn() {
  mapRef.value?.zoomIn()
}

function zoomOut() {
  mapRef.value?.zoomOut()
}

function resetView() {
  mapRef.value?.resetView()
}
</script>

<template>
  <div class="mobile-card flex h-full min-h-0 flex-col overflow-hidden p-0">
    <MapContainer
      ref="mapRef"
      container-id="mobile-map"
      class="min-h-0 flex-1"
    />

    <div class="flex flex-shrink-0 gap-2 bg-slate-50 p-3">
      <button
        class="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600"
        @click="zoomIn"
      >
        放大 +
      </button>
      <button
        class="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600"
        @click="zoomOut"
      >
        缩小 -
      </button>
      <button
        class="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600"
        @click="resetView"
      >
        复位 ⊙
      </button>
    </div>
  </div>
</template>
