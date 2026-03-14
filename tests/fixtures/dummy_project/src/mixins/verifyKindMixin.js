// Manual verification fixture: kind mismatch detection
// The composable useVerifyKind.js deliberately has isLoading as ref(false)
// instead of a function — should trigger kind-mismatch warning.
export default {
  data() {
    return {
      results: [],
    }
  },
  computed: {
    total() {
      return this.results.length
    },
  },
  methods: {
    isLoading() {
      return this.results.length === 0
    },
    fetchData() {
      this.results = [1, 2, 3]
    },
  },
}
