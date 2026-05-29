// Scenario 2: transitive method chain submit -> validate -> sanitize, and
// validate reads `errors` (data). Component uses ONLY `submit`. All of
// {submit, validate, sanitize, errors} must be declared; only `submit`
// returned. `standalone` is dead code and must be dropped.
export default {
  data() {
    return {
      errors: [],
    }
  },
  methods: {
    submit() {
      if (this.validate()) {
        return 'ok'
      }
      return 'fail'
    },
    validate() {
      this.errors = []
      return this.sanitize()
    },
    sanitize() {
      return true
    },
    standalone() {
      return 'unused'
    },
  },
}
