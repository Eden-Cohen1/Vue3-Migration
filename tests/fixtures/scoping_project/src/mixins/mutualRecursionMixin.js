// Scenario 12: mutual recursion must not hang the fixpoint. `ping` <-> `pong`.
// Component uses ONLY `ping`. Both pulled in (closure terminates), only `ping`
// returned. `lonely` dropped.
export default {
  methods: {
    ping(n) {
      if (n <= 0) return 'done'
      return this.pong(n - 1)
    },
    pong(n) {
      return this.ping(n - 1)
    },
    lonely() {
      return 'unused'
    },
  },
}
