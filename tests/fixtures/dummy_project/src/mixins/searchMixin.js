// Mixin for testing:
// - C1: inline icons on external deps (this.items, this._searchTimeout)
// - C3: ordering (data, computed, methods, watch)
// - B1: warning targeting (this.$refs is mixin-intrinsic, not component-specific)
export default {
  data() {
    return {
      searchQuery: '',
      searchResults: [],
      isSearching: false,
      searchHistory: []
    }
  },
  computed: {
    hasResults() {
      return this.searchResults.length > 0
    },
    resultCount() {
      return this.searchResults.length
    },
    recentSearches() {
      return this.searchHistory.slice(-5).reverse()
    }
  },
  methods: {
    search() {
      this.isSearching = true

      try {
        this.$refs.searchInput.focus() // B1: mixin-intrinsic warning, not component-specific
      } catch (e) {
        // searchInput ref may not be available
      }

      if (!this.searchQuery.trim()) {
        this.searchResults = []
        this.isSearching = false
        return
      }

      this.addToHistory(this.searchQuery)

      const query = this.searchQuery.toLowerCase()
      // C1: this.items is an external dep — should get inline ❌ icon
      this.searchResults = (this.items || []).filter((item) => {
        return JSON.stringify(item).toLowerCase().includes(query)
      })

      this.isSearching = false
    },
    clearSearch() {
      this.searchQuery = ''
      this.searchResults = []
    },
    addToHistory(query) {
      if (query && !this.searchHistory.includes(query)) {
        this.searchHistory.push(query)
      }
    }
  },
  watch: {
    searchQuery(newVal) {
      // C1: this._searchTimeout is an underscore external dep — should get inline icon after rewrite
      if (this._searchTimeout) {
        clearTimeout(this._searchTimeout)
      }
      this._searchTimeout = setTimeout(() => {
        this.search()
      }, 300)
    }
  }
}
