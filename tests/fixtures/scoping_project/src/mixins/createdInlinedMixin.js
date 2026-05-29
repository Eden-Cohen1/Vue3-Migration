// Scenario 5: `created` hook (inlined at function top) pulls in `setup`, which
// reads `ready`. Component uses ONLY `bar`. created preserved+inlined,
// setup+ready declared private, only `bar` returned.
export default {
  data() {
    return {
      ready: false,
    }
  },
  created() {
    this.setup()
  },
  methods: {
    setup() {
      this.ready = true
    },
    bar() {
      return 'bar'
    },
  },
}
