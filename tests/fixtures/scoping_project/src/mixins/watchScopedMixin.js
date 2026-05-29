// Scenario 8: watch entries are scoped to their target. Component uses ONLY
// `query`. The `query` watcher is kept; the `page` watcher (and `page`) are
// dropped. Watch bodies here are self-contained (no cross-member refs).
export default {
  data() {
    return {
      query: '',
      page: 1,
    }
  },
  watch: {
    query(val) {
      console.log('query changed', val)
    },
    page(val) {
      console.log('page changed', val)
    },
  },
}
