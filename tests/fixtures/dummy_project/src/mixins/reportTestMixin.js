// Test mixin for report quality chores — exercises all 5 bug fixes:
// 1. Checkbox rendering (now severity icons)
// 2. Report appearance (spacing, bold actions, summary line)
// 3. Confidence heading clarity ("Transformation confidence: X")
// 4. filters false positive (filters as data property, NOT Vue 2 filters)
// 5. $nextTick/$set/$delete warnings removed (auto-migrated)
export default {
  data() {
    return {
      filters: {},
      activeFilters: {},
      filterOptions: {},
      items: [],
      loading: false,
    }
  },
  computed: {
    activeFilterCount() {
      return Object.keys(this.activeFilters).length
    },
    isFiltered() {
      return this.activeFilterCount > 0
    },
    appliedFilterSummary() {
      return Object.keys(this.activeFilters).join(', ')
    },
  },
  methods: {
    applyFilter(key, value) {
      this.activeFilters = { ...this.activeFilters, [key]: value }
    },
    removeFilter(key) {
      const { [key]: _, ...remaining } = this.activeFilters
      this.activeFilters = remaining
    },
    clearAllFilters() {
      this.activeFilters = {}
    },
    getFilterOptions(key) {
      return this.filterOptions[key] || []
    },
    async loadData() {
      this.loading = true
      const page = this.$route.params.page
      const data = await this.$store.dispatch('fetchItems', { page })
      this.items = data
      this.loading = false
    },
    navigateTo(path) {
      this.$router.push(path)
    },
    notifyChange() {
      this.$emit('filters-changed', this.activeFilters)
    },
    refreshUI() {
      // $nextTick — should be auto-migrated, no warning expected
      this.$nextTick(() => {
        console.log('UI refreshed')
      })
    },
    addItem(item) {
      // $set — should be auto-migrated, no warning expected
      this.$set(this.items, this.items.length, item)
    },
    removeItemProp(key) {
      // $delete — should be auto-migrated, no warning expected
      this.$delete(this.items[0], key)
    },
  },
  watch: {
    activeFilters: {
      deep: true,
      handler(newFilters) {
        this.$emit('filters-changed', newFilters)
      },
    },
  },
  created() {
    this.loadData()
  },
  mounted() {
    console.log('reportTestMixin mounted')
  },
}
