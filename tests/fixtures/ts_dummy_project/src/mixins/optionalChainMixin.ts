// Failure Mode 4: Optional chaining `this?.x` is invisible to the parser.
// The regex `\bthis\.(\w+)` requires a literal dot, but optional chaining
// uses `?.` which doesn't match. These references are completely missed,
// causing missing member detection and broken migrations.

export default {
  data() {
    return {
      count: 0,
      label: 'test',
      isActive: false
    }
  },
  methods: {
    safeIncrement() {
      // Optional chaining on this — parser won't detect 'count'
      const current = this?.count ?? 0
      this.count = current + 1
    },
    safeReset() {
      // Optional chaining with method call — parser won't detect 'reset' ref
      this?.label
      this.isActive = false
    },
    conditionalAccess() {
      // Mix of normal and optional chain — only normal detected
      if (this.isActive) {
        return this?.count
      }
      return this?.label ?? 'none'
    }
  }
}
