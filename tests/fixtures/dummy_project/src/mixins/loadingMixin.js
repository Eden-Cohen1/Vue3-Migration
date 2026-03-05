// Mixin for loading/error state management
export default {
  data() {
    return {
      isLoading: false,
      loadingMessage: '',
      error: null,
      retryCount: 0,
    }
  },
  computed: {
    hasError() {
      return !!this.error
    },
    canRetry() {
      return this.retryCount < 3
    },
  },
  methods: {
    startLoading(msg) {
      this.isLoading = true
      this.loadingMessage = msg || 'Loading...'
      this.error = null
    },
    stopLoading() {
      this.isLoading = false
      this.loadingMessage = ''
    },
    setError(err) {
      this.error = err
      this.isLoading = false
    },
    retry(fn) {
      this.retryCount++
      fn()
    },
  },
}
