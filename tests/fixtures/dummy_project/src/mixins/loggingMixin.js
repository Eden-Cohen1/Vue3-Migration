// Edge case: mixin with lifecycle hooks (created, mounted, beforeDestroy)
// Scenario: useLogging covers data+methods but lifecycle hooks need manual migration
export default {
  data() {
    return {
      logs: [],
    }
  },
  methods: {
    log(message) {
      this.logs.push({ message, time: Date.now() })
    },
  },
  created() {
    this.log('Component created')
  },
  mounted() {
    this.log('Component mounted')
  },
  beforeDestroy() {
    this.log('Component will be destroyed')
  },
}
