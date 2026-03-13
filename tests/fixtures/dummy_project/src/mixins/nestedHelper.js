// Helper mixin used as a nested dependency by kitchenSinkMixin
export default {
  data() {
    return {
      helperActive: false,
      helperCount: 0,
    }
  },
  computed: {
    helperLabel() {
      return this.helperActive ? 'On' : 'Off'
    },
  },
  methods: {
    activateHelper() {
      this.helperActive = true
      this.helperCount++
    },
    resetHelper() {
      this.helperActive = false
      this.helperCount = 0
    },
  },
}
