// Mixin that uses various i18n patterns (A2 test)
// Also has external deps (C1 test), watch with dotted keys (C2 test),
// members only in comments (A1 test), and unused members (D1 test)
export default {
  data() {
    return {
      greeting: '',
      locale: 'en',
      formattedDate: '',
      formattedPrice: '',
      // <!-- TODO: use translationCache later --> (A1: should NOT detect translationCache as used)
      unusedCounter: 0 // D1: this member is defined but never used by any component
    }
  },
  computed: {
    welcomeMessage() {
      return this.$t('welcome.message')
    },
    itemCount() {
      return this.$tc('items.count', this.items.length)
    },
    hasTranslation() {
      return this.$te('some.key')
    },
    // D1: this computed is never used by any component
    unusedComputed() {
      return this.locale.toUpperCase()
    }
  },
  methods: {
    formatDate(date) {
      return this.$d(date, 'short')
    },
    formatPrice(amount) {
      return this.$n(amount, 'currency')
    },
    getGreeting() {
      // Combines i18n with external dep (this.userName is external)
      this.greeting = this.$t('greeting', { name: this.userName })
    },
    // D1: this method is never used by any component
    unusedMethod() {
      return 'never called'
    }
  },
  watch: {
    locale(newVal) {
      this.greeting = this.$t('welcome.message')
    },
    // C2: dotted watch key
    'settings.language'(newVal) {
      this.locale = newVal
    }
  }
}
