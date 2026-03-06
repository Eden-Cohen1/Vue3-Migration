// Test mixin covering multiple warning-triggering patterns for idempotency testing.
// Run the migration tool twice on this — second run should produce identical output.
export default {
  data() {
    return {
      items: [],
      selectedItem: null,
      isLoading: false,
      errorMessage: null,
      retryCount: 0,
    }
  },

  computed: {
    hasItems() {
      return this.items.length > 0
    },
    selectedItemName() {
      return this.selectedItem ? this.selectedItem.name : 'None'
    },
    canRetry() {
      return this.retryCount < 3
    },
  },

  watch: {
    selectedItem(newVal) {
      if (newVal) {
        this.fetchItemDetails(newVal.id)
      }
    },
  },

  methods: {
    // Case 1: this.$emit — triggers error warning
    selectItem(item) {
      this.selectedItem = item
      this.$emit('item-selected', item)
    },

    // Case 2: this.$router — triggers error warning
    navigateToItem(id) {
      this.$router.push({ name: 'item-detail', params: { id } })
    },

    // Case 3: this.$refs — triggers error warning
    focusInput() {
      this.$refs.searchInput.focus()
    },

    // Case 4: this.$store — triggers error warning
    fetchFromStore() {
      return this.$store.getters['items/allItems']
    },

    // Case 5: plain method (no warning)
    clearSelection() {
      this.selectedItem = null
      this.errorMessage = null
    },

    // Case 6: async method with this.$emit
    async fetchItems() {
      this.isLoading = true
      this.errorMessage = null
      try {
        const response = await fetch('/api/items')
        this.items = await response.json()
        this.$emit('items-loaded', this.items.length)
      } catch (error) {
        this.errorMessage = error.message
        this.retryCount++
      } finally {
        this.isLoading = false
      }
    },

    fetchItemDetails(id) {
      console.log('Fetching details for', id)
    },
  },

  // Case 7: created hook — inlined in setup (duplication-prone)
  created() {
    this.fetchItems()
  },

  // Case 8: mounted hook — wrapped in onMounted
  mounted() {
    console.log('Component mounted, items:', this.items.length)
    this.$emit('component-ready')
  },

  // Case 9: beforeDestroy hook — wrapped in onBeforeUnmount
  beforeDestroy() {
    console.log('Cleaning up')
    this.clearSelection()
  },
}
