import { ref, computed } from 'vue'

export function useFormatting() {
  const prefix = ref('')
  const suffix = ref('')
  const locale = ref('en')
  const currency = ref('USD')

  const displayPrefix = computed(() => `[${prefix.value}]`)
  const currencySymbol = computed(() => {
    const symbols = { USD: '$', EUR: '€', GBP: '£' }
    return symbols[currency.value] || currency.value
  })

  function format(value) {
    return `${prefix.value}${value}${suffix.value}`
  }

  function formatCurrency(amount) {
    return `${currencySymbol.value}${amount.toFixed(2)} ${currency.value}`
  }

  function formatList(items) {
    return `${prefix.value}: ${items.join(', ')}${suffix.value}`
  }

  function buildLabel(key, count) {
    return `${locale.value}:${key} (${count})`
  }

  function wrapTag(tag, content) {
    return `<${tag} class="${prefix.value}">${content}</${tag}>`
  }

  return {
    prefix,
    suffix,
    locale,
    currency,
    displayPrefix,
    currencySymbol,
    format,
    formatCurrency,
    formatList,
    buildLabel,
    wrapTag
  }
}
