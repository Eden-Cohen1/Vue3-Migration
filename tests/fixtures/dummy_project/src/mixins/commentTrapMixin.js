// A1 stress test: members referenced ONLY in comments should NOT be detected as used
// This mixin defines many members, but the component only uses a few in real code.
// The rest appear only in comments.
export default {
  data() {
    return {
      activeItem: null,
      loadingState: false,
      errorMessage: '',
      retryCount: 0,
      cachedData: null
    }
  },
  computed: {
    isLoading() {
      return this.loadingState
    },
    hasError() {
      return !!this.errorMessage
    },
    canRetry() {
      return this.retryCount < 3
    }
  },
  methods: {
    loadData() {
      this.loadingState = true
      // simulate loading
      this.loadingState = false
    },
    clearError() {
      this.errorMessage = ''
      this.retryCount = 0
    },
    retryLoad() {
      this.retryCount++
      this.loadData()
    },
    resetCache() {
      this.cachedData = null
    }
  }
}
