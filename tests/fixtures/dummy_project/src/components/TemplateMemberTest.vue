<template>
  <div>
    <!-- Nested <template> tags: the first </template> is NOT the end of the SFC -->
    <template v-if="isLoading">
      <div>{{ loadingMessage }}</div>
    </template>
    <div v-else-if="hasError">
      <p>{{ error }}</p>
      <button v-if="canRetry" @click="retry(loadData)">Retry</button>
    </div>
    <template v-else>
      <p>Content loaded</p>
    </template>
  </div>
</template>

<script>
import loadingMixin from '@/mixins/loadingMixin'

export default {
  name: 'TemplateMemberTest',
  mixins: [loadingMixin],
  methods: {
    loadData() {
      this.startLoading('Loading data...')
    },
  },
}
</script>
