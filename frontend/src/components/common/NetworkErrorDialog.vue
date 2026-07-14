<script setup>
import { watch } from 'vue'
import { useNetworkStore } from '@/stores/network'

const network = useNetworkStore()

watch(() => network.isInErrorState, (val) => {
  if (val) {
    network.showErrorDialog()
  }
})
</script>

<template>
  <div />
</template>
