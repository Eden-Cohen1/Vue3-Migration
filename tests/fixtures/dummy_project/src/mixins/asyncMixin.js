export default {
  data() {
    return {
      loading: false,
      error: null,
      result: null,
      retryCount: 0
    }
  },
  computed: {
    hasError() {
      return !!this.error
    },
    canRetry() {
      return this.retryCount < 3
    }
  },
  methods: {
    async fetchData(url) {
      this.loading = true
      this.error = null
      try {
        const response = await fetch(url)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        this.result = await response.json()
      } catch (err) {
        this.error = err.message
        this.handleError(err)
      } finally {
        this.loading = false
      }
    },
    async submitForm(data) {
      this.loading = true
      try {
        const response = await fetch('/api/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        })
        this.result = await response.json()
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async batchProcess(items) {
      this.loading = true
      this.error = null
      try {
        const results = await Promise.all(
          items.map(item => fetch(`/api/process/${item.id}`).then(r => r.json()))
        )
        this.result = results
      } catch (err) {
        this.error = `Batch failed: ${err.message}`
      } finally {
        this.loading = false
      }
    },
    handleError(err) {
      this.retryCount++
      console.error(`Error (attempt ${this.retryCount}):`, err)
    }
  }
}
