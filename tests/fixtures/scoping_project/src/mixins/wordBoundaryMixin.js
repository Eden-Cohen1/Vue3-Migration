// Scenario 11: word-boundary correctness. `doSearch` reads `search` but NOT
// `searchResults`. Using `doSearch` must pull in `search` only — `searchResults`
// must NOT be dragged in by a naive substring match.
export default {
  data() {
    return {
      search: '',
      searchResults: [],
    }
  },
  methods: {
    doSearch() {
      return this.search.length
    },
  },
}
