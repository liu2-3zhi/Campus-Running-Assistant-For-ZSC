<script setup>
import { watch, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: 'max-w-lg' },
  closable: { type: Boolean, default: true },
  fullscreen: { type: Boolean, default: false },
  panel: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

function close() {
  if (props.closable) emit('close')
}

function syncModalVisibility() {
  document.body.classList.toggle('modal-visible', !!document.querySelector('[data-modal-open="true"]'))
}

watch(() => props.visible, (val) => {
  if (val) {
    document.body.classList.add('modal-visible')
  } else {
    nextTick(syncModalVisibility)
  }
}, { immediate: true })

onUnmounted(() => nextTick(syncModalVisibility))
</script>

<template>
  <teleport to="body">
    <transition name="fade" @after-leave="syncModalVisibility">
      <div v-if="visible" class="app-modal fixed inset-0 flex items-center justify-center p-4" data-modal-open="true">
        <div class="modal-backdrop" @click="close"></div>
        <div
          class="modal-content relative z-10 w-full p-6"
          :class="[fullscreen ? 'h-full max-h-full max-w-full rounded-none' : width, { 'legacy-panel-dialog': panel }]"
          role="dialog"
          aria-modal="true"
          :aria-label="title || '对话框'"
        >
          <button v-if="panel && closable" class="legacy-panel-close absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-red-600" aria-label="关闭" @click="close">
            <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" clip-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" /></svg>
          </button>
          <div v-if="title || closable || $slots.header" class="relative mb-4 flex items-center justify-center" :class="{ 'mt-4': panel }">
            <slot name="header">
            <h3 v-if="title" class="text-lg font-semibold" :class="{ 'w-full': panel }">{{ title }}</h3>
            </slot>
            <button
              v-if="closable && !panel"
              aria-label="关闭"
              class="btn-ghost absolute right-0 top-1/2 -translate-y-1/2 rounded-lg p-1.5"
              @click="close"
            >
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
