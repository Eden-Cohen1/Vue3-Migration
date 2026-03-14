// Failure Mode 3: TypeScript type assertions and generics break extract_value_at().
// The `as Type` syntax and `Array<{...}>` generics confuse depth tracking
// because <> are not tracked as brackets in the parser.

export default {
  data() {
    return {
      selected: null as string | null,
      entries: [] as Array<{ id: number; name: string }>,
      config: {} as Record<string, unknown>,
      count: 0 as number
    }
  },
  computed: {
    hasSelection(): boolean {
      return this.selected !== null
    },
    entryCount(): number {
      return this.entries.length
    }
  },
  methods: {
    select(value: string): void {
      this.selected = value
    },
    addEntry(id: number, name: string): void {
      this.entries.push({ id, name })
    }
  }
}
