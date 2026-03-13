<template>
  <div>
    <span v-if="isLoading">Loading...</span>
    <span>{{ loadingMessage }}</span>
    <span>{{ statusMessage }}</span>
    <button @click="startLoading('fetching')">Load</button>
    <button @click="clearStatus">Clear</button>
  </div>
</template>

<script>
import { useStatus } from '@/composables/useStatus'
import { useLoading } from '@/composables/useLoading'

export default {
  setup() {
    const { isLoading, loadingMessage, startLoading } = useLoading()
    const { statusMessage, clearStatus } = useStatus()

    return { isLoading, loadingMessage, startLoading, statusMessage, clearStatus }
  },
  name: 'CollisionTest',
}
</script>
