// Scenario 15: side-effect-only mixin. Component references NONE of its members
// directly — it includes the mixin purely for the `mounted` side effect. The
// closure is seeded from the hook: `logVisit` (private) + `logged` (private),
// `return {}` is empty, and the component still calls useSideEffectOnly().
export default {
  data() {
    return {
      logged: false,
    }
  },
  methods: {
    logVisit() {
      this.logged = true
      console.log('visited')
    },
  },
  mounted() {
    this.logVisit()
  },
}
