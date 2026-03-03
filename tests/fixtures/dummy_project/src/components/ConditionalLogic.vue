<template>
  <div>
    <p v-if="!isValid">Invalid</p>
    <p>{{ errorCount }} errors</p>
    <p>{{ firstError }}</p>
    <button @click="processValidation">Process</button>
    <button @click="clearErrors">Clear</button>
    <span>{{ isValidating }}</span>
    <span>{{ lastValidated }}</span>
    <div v-for="rule in rules" :key="rule.field">{{ rule.field }}</div>
  </div>
</template>

<script>
import validationMixin from '@/mixins/validationMixin'

export default {
  name: 'ConditionalLogic',
  mixins: [validationMixin],
  methods: {
    processValidation() {
      if (this.isValidating) return

      if (!this.isValid && this.errorCount > 0) {
        this.clearErrors()
      }

      for (const rule of this.rules) {
        this.validateField(rule.field, rule.value)
      }

      let retries = 0
      while (this.errorCount > 0 && retries < 3) {
        this.validateAll()
        retries++
      }

      switch (this.errorCount) {
        case 0:
          this.onSuccess()
          break
        default:
          this.onFailure()
      }

      if (this.isValid) {
        if (this.errorCount === 0) {
          console.log('All clear')
        }
      }
    },
    onSuccess() {
      console.log('Validation passed')
    },
    onFailure() {
      console.log('Validation failed')
    },
  },
}
</script>
