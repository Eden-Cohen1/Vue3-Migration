// Failure Mode 1: Type annotations on data() return type and computed return types.
// The current parser has a defensive regex for data(): Type { ... } which works,
// BUT the generated composable will have `const count: number = ref(0)` —
// and extract_declaration_names() can't detect 'count' because the regex
// expects `const count =` (no colon/type between name and =).

export default {
  data(): { count: number; label: string; items: string[] } {
    return {
      count: 0,
      label: 'default',
      items: []
    }
  },
  computed: {
    doubled(): number {
      return this.count * 2
    },
    summary(): string {
      return `${this.label}: ${this.count} items`
    }
  },
  methods: {
    increment(): void {
      this.count++
    },
    reset(): void {
      this.count = 0
      this.label = 'default'
      this.items = []
    }
  }
}
