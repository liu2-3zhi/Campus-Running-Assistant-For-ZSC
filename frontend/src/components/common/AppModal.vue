<script setup>
import { watch, onUnmounted } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: 'max-w-lg' },
  closable: { type: Boolean, default: true },
  fullscreen: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

function close() {
  if (props.closable) emit('close')
}

watch(() => props.visible, (val) => {
  if (val) {
    document.body.classList.add('modal-visible')
  } else {
    setTimeout(() => {
      const others = document.querySelectorAll('[data-modal-open="true"]')
      if (others.length === 0) document.body.classList.remove('modal-visible')
    }, 50)
  }
})

onUnmounted(() => {
  if (props.visible) {
    setTimeout(() => {
      const others = document.querySelectorAll('[data-modal-open="true"]')
      if (others.length === 0) document.body.classList.remove('modal-visible')
    }, 50)
  }
})
</script>

<template>
  <teleport to="body">
    <transition name="fade">
      <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4" data-modal-open="true">
        <div class="modal-backdrop" @click="close"></div>
        <div
          class="modal-content relative z-10 w-full p-6"
          :class="[fullscreen ? 'h-full max-h-full max-w-full rounded-none' : width]"
        >
          <div v-if="title || closable" class="mb-4 flex items-center justify-between">
            <h3 v-if="title" class="text-lg font-semibold">{{ title }}</h3>
            <button v-if="closable" class="btn-ghost rounded-lg p-1.5" @click="close">
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <slot />
        </div>
      </div>
    </transition>
  </teleport>
</template>
