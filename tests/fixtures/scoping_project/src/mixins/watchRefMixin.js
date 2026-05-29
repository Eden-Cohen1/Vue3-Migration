// Scenario 16 (EDGE PROBE): a kept watcher's BODY references another member.
// Component uses ONLY `keyword` (template input). The `keyword` watcher is kept
// (target in closure) and its body calls `runSearch`, which reads `results`.
// This probes whether the closure follows references *inside watch bodies* —
// if it does not, the generated `keyword` watcher will reference an undeclared
// `runSearch`. This scenario exists to surface that question.
export default {
  data() {
    return {
      keyword: '',
      results: [],
    }
  },
  methods: {
    runSearch() {
      this.results = [this.keyword]
    },
  },
  watch: {
    keyword() {
      this.runSearch()
    },
  },
}
