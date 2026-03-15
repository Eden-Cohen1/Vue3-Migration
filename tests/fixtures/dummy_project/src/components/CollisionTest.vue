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
import loadingMixin from '@/mixins/loadingMixin'
import statusMixin from '@/mixins/statusMixin'

export default {
  name: 'CollisionTest',
  mixins: [loadingMixin, statusMixin],
}
</script>
