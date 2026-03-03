export default {
  data() {
    return {
      rules: [],
      fieldErrors: {},
      isValidating: false,
      lastValidated: null
    }
  },
  computed: {
    isValid() {
      return !this.isValidating && Object.keys(this.fieldErrors).length === 0
    },
    errorCount() {
      return Object.keys(this.fieldErrors).length
    },
    firstError() {
      return this.errorCount > 0 ? Object.values(this.fieldErrors)[0] : null
    }
  },
  methods: {
    validateField(name, value) {
      const rule = this.rules.find(r => r.field === name)
      if (!rule) return true
      if (rule.required && !value) {
        this.fieldErrors[name] = `${name} is required`
        return false
      }
      if (rule.minLength && value.length < rule.minLength) {
        this.fieldErrors[name] = `${name} must be at least ${rule.minLength} characters`
        return false
      }
      delete this.fieldErrors[name]
      return true
    },
    validateAll() {
      this.isValidating = true
      this.fieldErrors = {}
      this.rules.forEach(rule => {
        this.validateField(rule.field, this[rule.field])
      })
      this.lastValidated = Date.now()
      this.isValidating = false
    },
    clearErrors() {
      this.fieldErrors = {}
      this.lastValidated = null
    },
    hasFieldError(name) {
      return !!this.fieldErrors[name]
    },
    addRule(rule) {
      this.rules.push(rule)
    }
  }
}
