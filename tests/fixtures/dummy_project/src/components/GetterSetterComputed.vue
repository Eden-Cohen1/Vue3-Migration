<template>
  <div>
    <input v-model="fullName" placeholder="Full name">
    <input v-model="normalizedEmail" placeholder="Email">
    <p v-if="hasErrors">Errors:</p>
    <ul>
      <li v-for="err in errors" :key="err">{{ err }}</li>
    </ul>
    <p v-if="isComplete">Form complete!</p>
    <p>Config: {{ formConfig.validateOnBlur }}</p>
    <input v-model="firstName">
    <input v-model="lastName">
    <input v-model="email">
    <span>Dirty: {{ isDirty }}</span>
    <button @click="validate">Validate</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script>
import formMixin from '@/mixins/formMixin'

export default {
  name: 'GetterSetterComputed',
  mixins: [formMixin],
}
</script>
