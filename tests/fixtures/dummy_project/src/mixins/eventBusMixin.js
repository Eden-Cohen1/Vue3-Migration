// Issue 3: this.$on AND this.$once in same mixin.
// Report must show SEPARATE steps — $once should NOT be grouped under $on.
export default {
  data() {
    return {
      eventHandlers: {},
      receivedEvents: [],
      isListening: false
    }
  },

  created() {
    this.registerEvents()
  },

  beforeDestroy() {
    this.cleanupEvents()
  },

  methods: {
    registerEvents() {
      this.$on('data-updated', this.handleDataUpdate)
      this.$on('user-action', this.handleUserAction)
      this.$on('error-occurred', (error) => {
        this.receivedEvents.push({ type: 'error', payload: error })
      })

      this.$once('initialized', () => {
        this.isListening = true
      })

      this.eventHandlers = {
        'data-updated': this.handleDataUpdate,
        'user-action': this.handleUserAction
      }
    },

    cleanupEvents() {
      this.$off('data-updated', this.handleDataUpdate)
      this.$off('user-action', this.handleUserAction)
      this.$off('error-occurred')
      this.isListening = false
    },

    handleDataUpdate(payload) {
      this.receivedEvents.push({ type: 'data-updated', payload })
    },

    handleUserAction(action) {
      this.receivedEvents.push({ type: 'user-action', payload: action })
    },

    emitEvent(name, payload) {
      this.$emit(name, payload)
    }
  }
}
