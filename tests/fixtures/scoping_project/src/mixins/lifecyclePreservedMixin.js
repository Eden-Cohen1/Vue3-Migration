// Scenario 4: lifecycle hooks are ALWAYS preserved, and pull their referenced
// members into the closure. Component uses ONLY `toggle` + `visible`.
// `mounted` calls `init` (unused by component) which sets `config` — both must
// be declared (private) so the preserved hook doesn't reference undeclared
// members, but neither is returned.
export default {
  data() {
    return {
      config: null,
      visible: false,
    }
  },
  methods: {
    init() {
      this.config = { ready: true }
    },
    toggle() {
      this.visible = !this.visible
    },
  },
  mounted() {
    this.init()
  },
}
