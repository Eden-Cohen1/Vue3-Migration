// Scenario 7: a $emit method that IS used must be KEPT, warning and all.
// Scoping must never drop a needed member just because it carries a warning.
// `announce` reads `count`, so `count` is pulled in (private), `announce`
// returned, and the $emit warning should still be present.
export default {
  data() {
    return {
      count: 0,
    }
  },
  methods: {
    announce() {
      this.$emit('announce', this.count)
    },
  },
}
