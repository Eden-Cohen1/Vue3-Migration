export default {
  data() {
    return {
      prefix: '',
      suffix: '',
      locale: 'en',
      currency: 'USD'
    }
  },
  computed: {
    displayPrefix() {
      return `[${this.prefix}]`
    },
    currencySymbol() {
      const symbols = { USD: '$', EUR: '\u20ac', GBP: '\u00a3' }
      return symbols[this.currency] || this.currency
    }
  },
  methods: {
    format(value) {
      return `${this.prefix}${value}${this.suffix}`
    },
    formatCurrency(amount) {
      return `${this.currencySymbol}${amount.toFixed(2)} ${this.currency}`
    },
    formatList(items) {
      return `${this.prefix}: ${items.join(', ')}${this.suffix}`
    },
    buildLabel(key, count) {
      return `${this.locale}:${key} (${count})`
    },
    wrapTag(tag, content) {
      return `<${tag} class="${this.prefix}">${content}</${tag}>`
    }
  }
}
