// Scenario 6: the headline benefit. Component uses ONLY `tick` + `ticks`.
// The unused `notify` ($emit), `focusInput` ($refs), `goHome` ($router) methods
// — exactly the untestable, warning-heavy ones — must be dropped entirely, and
// their warnings must NOT appear in the generated composable.
export default {
  data() {
    return {
      ticks: 0,
    }
  },
  methods: {
    tick() {
      this.ticks++
    },
    notify() {
      this.$emit('notified')
    },
    focusInput() {
      this.$refs.input.focus()
    },
    goHome() {
      this.$router.push('/')
    },
  },
}
