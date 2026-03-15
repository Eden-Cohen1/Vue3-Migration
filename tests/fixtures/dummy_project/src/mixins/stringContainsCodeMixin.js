// Edge case: String values containing this.$emit, this.$router.push, this.$store.
// These are documentation/log strings and should NOT trigger Vue API migration warnings.
export default {
  data() {
    return {
      logEntries: [],
      debugMode: false,
      apiDocumentation: 'Call this.$emit("update") to notify parent components'
    }
  },

  computed: {
    debugSummary() {
      return this.logEntries.map(e => e.message).join('\n')
    },

    recentLogs() {
      return this.logEntries.slice(-10)
    }
  },

  methods: {
    logEvent(eventName, payload) {
      const message = `Event fired: this.$emit("${eventName}") with payload: ${JSON.stringify(payload)}`
      this.logEntries.push({ message, timestamp: Date.now() })
    },

    buildDebugInfo() {
      return {
        navigation: 'Router: this.$router.push("/dashboard") navigates to dashboard',
        state: 'Store: this.$store.dispatch("fetchData") loads data',
        events: 'Events: this.$emit("change", value) notifies parent',
        refs: 'DOM: this.$refs.input.focus() sets focus',
        lifecycle: 'Hooks: this.$nextTick(() => { ... }) waits for DOM update'
      }
    },

    logRouteChange(from, to) {
      this.logEntries.push({
        message: `Route changed via this.$router.push from ${from} to ${to}`,
        timestamp: Date.now()
      })
    },

    getHelpText(topic) {
      const help = {
        events: 'Use this.$emit to send events to parent components. Example: this.$emit("save", data)',
        store: 'Access Vuex via this.$store.state.xxx or this.$store.getters.xxx',
        router: 'Navigate with this.$router.push({ name: "route-name" })'
      }
      return help[topic] || 'No help available'
    }
  }
}
