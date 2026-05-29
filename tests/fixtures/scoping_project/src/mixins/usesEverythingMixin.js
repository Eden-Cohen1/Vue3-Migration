// Scenario 13: component uses ALL members. Scoped output must equal the full
// output (nothing dropped) — scoping must be a no-op when everything is used.
export default {
  data() {
    return {
      x: 0,
    }
  },
  computed: {
    dbl() {
      return this.x * 2
    },
  },
  methods: {
    inc() {
      this.x++
    },
  },
}
