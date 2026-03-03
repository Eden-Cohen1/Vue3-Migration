export default {
  data() {
    return {
      firstName: '',
      lastName: '',
      email: '',
      errors: [],
      isDirty: false,
      formConfig: {
        validateOnBlur: true,
        showErrors: true
      }
    }
  },
  computed: {
    hasErrors() {
      return this.errors.length > 0
    },
    isComplete() {
      return !!(this.firstName && this.lastName && this.email)
    },
    fullName: {
      get() {
        return this.firstName + ' ' + this.lastName
      },
      set(val) {
        const parts = val.split(' ')
        this.firstName = parts[0] || ''
        this.lastName = parts.slice(1).join(' ') || ''
      }
    },
    normalizedEmail: {
      get() {
        return this.email.toLowerCase()
      },
      set(val) {
        this.email = val.trim()
      }
    }
  },
  watch: {
    email(newVal) {
      this.isDirty = true
      this.validate()
    },
    isDirty: {
      immediate: true,
      handler(val) {
        if (val) {
          console.log('Form has been modified')
        }
      }
    }
  },
  methods: {
    validate() {
      this.errors = []
      if (!this.firstName) this.errors.push('First name is required')
      if (!this.lastName) this.errors.push('Last name is required')
      if (!this.email) this.errors.push('Email is required')
      if (this.email && !this.email.includes('@')) this.errors.push('Invalid email')
      return this.errors.length === 0
    },
    reset() {
      this.firstName = ''
      this.lastName = ''
      this.email = ''
      this.errors = []
      this.isDirty = false
    },
    addError(msg) {
      this.errors.push(msg)
    }
  }
}
