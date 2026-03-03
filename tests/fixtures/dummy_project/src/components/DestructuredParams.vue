<template>
  <div>
    <div v-if="loading">Processing...</div>
    <div v-if="hasError">{{ error }}</div>
    <div v-if="result">{{ result }}</div>
    <p>Retries: {{ retryCount }}</p>
    <button @click="handleResponse({ data: { ok: true }, status: 200 })">Handle Response</button>
    <button @click="processItem({ id: 1, name: 'test', extra: 'data' })">Process Item</button>
    <button @click="onEvent({ type: 'submit', payload: { value: 42 } })">Submit Event</button>
    <button @click="onEvent({ type: 'error' })">Error Event</button>
  </div>
</template>

<script>
import asyncMixin from '@/mixins/asyncMixin'

export default {
  name: 'DestructuredParams',
  mixins: [asyncMixin],
  methods: {
    handleResponse({ data, status }) {
      if (status >= 200 && status < 300) {
        this.result = data
      } else {
        this.error = `Status ${status}`
      }
    },
    processItem({ id, name, ...rest }) {
      this.fetchData(`/api/items/${id}`)
      console.log(`Processing ${name}`, rest)
    },
    onEvent({ type, payload = {} }) {
      switch (type) {
        case 'submit':
          this.submitForm(payload)
          break
        case 'error':
          this.handleError(new Error('Event error'))
          break
        default:
          this.result = { type, payload }
      }
    },
  },
}
</script>
