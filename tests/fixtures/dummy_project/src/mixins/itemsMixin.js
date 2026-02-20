// Edge case: exact name match (itemsMixin -> useItems)
// Scenario: candidates = ['useItems'], composable useItems.js matches exactly -> READY
export default {
  data() {
    return {
      items: [],
      loading: false,
    }
  },
  methods: {
    fetchItems() {
      this.loading = true
      // fetch logic (intentionally omitted)
    },
    clearItems() {
      this.items = []
    },
  },
}
