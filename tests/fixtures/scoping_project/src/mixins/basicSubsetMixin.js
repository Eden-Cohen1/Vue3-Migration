// Scenario 1: basic subset + dead-code-not-pulled-in.
// Component uses `alpha` + `useAlpha`. `beta` is only touched by `touchBeta`
// (unused), `gamma` is unused. All three should be dropped.
export default {
  data() {
    return {
      alpha: 1,
      beta: 2,
    }
  },
  computed: {
    gamma() {
      return 42
    },
  },
  methods: {
    useAlpha() {
      return this.alpha + 1
    },
    touchBeta() {
      this.beta = this.beta + 1
    },
  },
}
