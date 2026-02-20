// Edge case: fuzzy composable match
// Scenario: candidates = ['useFilter'], but composable is named useAdvancedFilter
//           -> no exact match -> fuzzy: core_word 'filter' IN 'useadvancedfilter' -> MATCH
export default {
  data() {
    return {
      filterText: '',
      filterActive: false,
    }
  },
  computed: {
    filteredCount() {
      return 0 // placeholder
    },
  },
  methods: {
    applyFilter() {
      this.filterActive = true
    },
    clearFilter() {
      this.filterText = ''
      this.filterActive = false
    },
  },
}
