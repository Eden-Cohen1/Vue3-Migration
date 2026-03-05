<template>
  <div>
    <div v-if="isLoading">{{ loadingMessage }}</div>
    <div v-else-if="hasError">
      <p>{{ error }}</p>
      <button v-if="canRetry" @click="retry(loadData)">Retry</button>
    </div>
    <div v-else>
      <p>Content loaded</p>
    </div>
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
