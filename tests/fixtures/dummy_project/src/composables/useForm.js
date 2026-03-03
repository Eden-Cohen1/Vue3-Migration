import { ref, computed } from 'vue'

export function useForm() {
  const firstName = ref('')
  const lastName = ref('')
  const email = ref('')
  const errors = ref([])
  const isDirty = ref(false)
  const formConfig = ref({
    validateOnBlur: true,
    showErrors: true
  })

  const hasErrors = computed(() => errors.value.length > 0)
  const isComplete = computed(() => !!(firstName.value && lastName.value && email.value))

  const fullName = computed({
    get() {
      return firstName.value + ' ' + lastName.value
    },
    set(val) {
      const parts = val.split(' ')
      firstName.value = parts[0] || ''
      lastName.value = parts.slice(1).join(' ') || ''
    }
  })

  const normalizedEmail = computed({
    get() {
      return email.value.toLowerCase()
    },
    set(val) {
      email.value = val.trim()
    }
  })

  function validate() {
    errors.value = []
    if (!firstName.value) errors.value.push('First name is required')
    if (!lastName.value) errors.value.push('Last name is required')
    if (!email.value) errors.value.push('Email is required')
    if (email.value && !email.value.includes('@')) errors.value.push('Invalid email')
    return errors.value.length === 0
  }

  function reset() {
    firstName.value = ''
    lastName.value = ''
    email.value = ''
    errors.value = []
    isDirty.value = false
  }

  function addError(msg) {
    errors.value.push(msg)
  }

  return {
    firstName,
    lastName,
    email,
    errors,
    isDirty,
    formConfig,
    hasErrors,
    isComplete,
    fullName,
    normalizedEmail,
    validate,
    reset,
    addError
  }
}
