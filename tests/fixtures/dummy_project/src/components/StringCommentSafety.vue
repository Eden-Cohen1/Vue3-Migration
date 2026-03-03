<template>
  <!-- this.isValid shows validation state — should NOT be rewritten -->
  <div>
    <p v-if="!isValid">{{ errorCount }} errors found</p>
    <p>{{ firstError }}</p>
    <button @click="getHelp">Help</button>
    <button @click="debugInfo">Debug</button>
    <button @click="errorTemplate">Template</button>
    <button @click="validateAll">Validate</button>
    <button @click="clearErrors">Clear</button>
    <span>{{ isValidating }}</span>
    <span>{{ lastValidated }}</span>
    <div v-for="rule in rules" :key="rule.field">
      <span :class="{ error: hasFieldError(rule.field) }">{{ rule.field }}</span>
    </div>
  </div>
</template>

<script>
import validationMixin from '@/mixins/validationMixin'

export default {
  name: 'StringCommentSafety',
  mixins: [validationMixin],
  methods: {
    getHelp() {
      // This method returns a string containing "this." references that must NOT be rewritten
      return 'Use this.validate() to check all fields. Access this.errors for the error list.'
    },
    debugInfo() {
      // this.rules contains validation rules — this comment should NOT be rewritten
      const ruleCount = this.rules.length
      const info = "this.fieldErrors stores per-field errors"
      return info + ' (' + ruleCount + ' rules)'
    },
    errorTemplate() {
      const prefix = "Error in this.fieldErrors: "
      return prefix + this.errorCount
    },
  },
}
</script>
