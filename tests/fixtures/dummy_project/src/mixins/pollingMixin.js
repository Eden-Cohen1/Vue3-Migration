// Issue 2: Lifecycle-only mixin — report should NOT list steps for non-existent composable.
export default {
  data() {
    return {
      pollInterval: 30000,
      pollTimer: null,
      isPollActive: false,
      lastPollAt: null
    }
  },

  computed: {
    isPolling() {
      return this.isPollActive && this.pollTimer !== null
    }
  },

  methods: {
    startPolling(fn) {
      if (this.pollTimer) {
        this.stopPolling()
      }
      this._pollCallback = fn
      this.isPollActive = true
      this.pollTimer = setInterval(() => {
        this.lastPollAt = Date.now()
        if (typeof this._pollCallback === 'function') {
          this._pollCallback()
        }
      }, this.pollInterval)
    },

    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
      this.isPollActive = false
    }
  },

  mounted() {
    // Subclass can override to auto-start polling
  },

  beforeDestroy() {
    this.stopPolling()
  }
}
