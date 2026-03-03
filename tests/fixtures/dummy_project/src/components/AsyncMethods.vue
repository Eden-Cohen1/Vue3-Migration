<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-if="hasError">
      <p>Error: {{ error }}</p>
      <button @click="fetchData('/api/retry')" :disabled="!canRetry">
        Retry ({{ retryCount }}/3)
      </button>
    </div>
    <div v-if="result">
      <pre>{{ result }}</pre>
    </div>
    <button @click="fetchData('/api/data')">Fetch</button>
    <button @click="submitForm({ name: 'test' })">Submit</button>
    <button @click="batchProcess([{ id: 1 }, { id: 2 }])">Batch</button>
  </div>
</template>

<script>
import asyncMixin from '@/mixins/asyncMixin'

export default {
  name: 'AsyncMethods',
  mixins: [asyncMixin],
}
</script>
