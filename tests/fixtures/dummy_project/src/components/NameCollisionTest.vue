<template>
  <div>
    <p v-if="isLoading">Loading...</p>
    <p>{{ loadingMessage }}</p>
    <p>{{ statusMessage }}</p>
    <button @click="startLoading('Fetching')">Start</button>
    <button @click="setStatus('OK')">Status</button>
  </div>
</template>

<script>
import loadingMixin from '@/mixins/loadingMixin'
import statusMixin from '@/mixins/statusMixin'

export default {
  name: 'NameCollisionTest',
  mixins: [loadingMixin, statusMixin],
}
</script>
