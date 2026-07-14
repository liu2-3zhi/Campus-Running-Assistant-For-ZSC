<script setup>
import { ref, provide, computed } from 'vue'

const props = defineProps({
  tabs: { type: Array, required: true },
  modelValue: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const activeTab = computed({
  get: () => props.modelValue || props.tabs[0]?.key,
  set: (val) => emit('update:modelValue', val),
})
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap gap-1" :class="compact ? 'gap-0.5' : 'gap-1'">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-button"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>
    <div>
      <template v-for="tab in tabs" :key="tab.key">
        <div v-show="activeTab === tab.key">
          <slot :name="tab.key" />
        </div>
      </template>
    </div>
  </div>
</template>
