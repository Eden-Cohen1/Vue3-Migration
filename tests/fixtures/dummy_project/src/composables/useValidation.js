import { ref, computed } from 'vue'

export function useValidation() {
  const rules = ref([])
  const fieldErrors = ref({})
  const isValidating = ref(false)
  const lastValidated = ref(null)

  const isValid = computed(() => !isValidating.value && Object.keys(fieldErrors.value).length === 0)
  const errorCount = computed(() => Object.keys(fieldErrors.value).length)
  const firstError = computed(() => errorCount.value > 0 ? Object.values(fieldErrors.value)[0] : null)

  function validateField(name, value) {
    const rule = rules.value.find(r => r.field === name)
    if (!rule) return true
    if (rule.required && !value) {
      fieldErrors.value[name] = `${name} is required`
      return false
    }
    if (rule.minLength && value.length < rule.minLength) {
      fieldErrors.value[name] = `${name} must be at least ${rule.minLength} characters`
      return false
    }
    delete fieldErrors.value[name]
    return true
  }

  function validateAll() {
    isValidating.value = true
    fieldErrors.value = {}
    rules.value.forEach(rule => {
      validateField(rule.field, rule.value)
    })
    lastValidated.value = Date.now()
    isValidating.value = false
  }

  function clearErrors() {
    fieldErrors.value = {}
    lastValidated.value = null
  }

  function hasFieldError(name) {
    return !!fieldErrors.value[name]
  }

  function addRule(rule) {
    rules.value.push(rule)
  }

  return {
    rules,
    fieldErrors,
    isValidating,
    lastValidated,
    isValid,
    errorCount,
    firstError,
    validateField,
    validateAll,
    clearErrors,
    hasFieldError,
    addRule
  }
}
