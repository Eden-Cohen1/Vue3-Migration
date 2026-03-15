// Factory function mixin — params should be forwarded to composable signature.
// data() values from parameters should still be wrapped in ref().
export default function createSortMixin(defaultKey = 'name') {
  return {
    data() {
      return {
        sortKey: defaultKey,
        sortOrder: 'asc',
        multiSort: [],
        sortHistory: []
      }
    },

    computed: {
      sortIndicator() {
        return this.sortOrder === 'asc' ? '▲' : '▼'
      },

      isSorted() {
        return !!this.sortKey
      }
    },

    methods: {
      toggleSort(key) {
        if (this.sortKey === key) {
          this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc'
        } else {
          this.sortHistory.push(this.sortKey)
          this.sortKey = key
          this.sortOrder = 'asc'
        }
      },

      clearSort() {
        this.sortKey = defaultKey
        this.sortOrder = 'asc'
        this.multiSort = []
        this.sortHistory = []
      },

      addSortLevel(key) {
        const existing = this.multiSort.find((s) => s.key === key)
        if (existing) {
          existing.order = existing.order === 'asc' ? 'desc' : 'asc'
        } else {
          this.multiSort.push({ key, order: 'asc' })
        }
      }
    }
  }
}
