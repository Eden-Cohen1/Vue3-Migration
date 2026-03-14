// Failure Mode 2: TypeScript parameter type annotations leak into generated code.
// _extract_func_params() captures everything between ( and ), including `: string`.
// The generated composable will have `function search(query: string, limit: number)`
// which is TS syntax — invalid if the output target is plain JS.

export default {
  data() {
    return {
      results: [],
      lastQuery: ''
    }
  },
  methods: {
    search(query: string, limit: number): void {
      this.lastQuery = query
      this.results = []
      console.log(`Searching for "${query}" with limit ${limit}`)
    },
    format(value: number, currency: string = 'USD'): string {
      return `${currency}${value.toFixed(2)}`
    },
    async fetchData(url: string, options?: { timeout: number }): Promise<void> {
      console.log('fetching', url, options)
    }
  }
}
