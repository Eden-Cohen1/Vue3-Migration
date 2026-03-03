<template>
  <div>
    <p v-if="!isValid">Invalid ({{ errorCount }} errors)</p>
    <p v-if="firstError">First error: {{ firstError }}</p>
    <div v-for="rule in rules" :key="rule.field">
      <span :class="{ error: hasFieldError(rule.field) }">{{ rule.field }}</span>
    </div>
    <button @click="validateAll">Validate All</button>
    <button @click="clearErrors">Clear</button>
    <span>Validating: {{ isValidating }}</span>
    <span>Last: {{ lastValidated }}</span>
  </div>
</template>

<script>
import validationMixin from '@/mixins/validationMixin'

export default {
  name: 'ComplexThisPatterns',
  mixins: [validationMixin],
  created() {
    this.addRule({ field: 'username', required: true, minLength: 3 })
    this.addRule({ field: 'email', required: true })
  },
}
</script>
