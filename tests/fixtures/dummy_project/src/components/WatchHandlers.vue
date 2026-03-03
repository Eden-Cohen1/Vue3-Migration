<template>
  <div>
    <input v-model="email" placeholder="Email">
    <input v-model="firstName" placeholder="First name">
    <span v-if="isDirty">Modified</span>
    <ul>
      <li v-for="err in errors" :key="err">{{ err }}</li>
    </ul>
    <button @click="addError('Manual error')">Add Error</button>
  </div>
</template>

<script>
import formMixin from '@/mixins/formMixin'

export default {
  name: 'WatchHandlers',
  mixins: [formMixin],
  watch: {
    firstName: {
      handler: 'onNameChange',
      deep: false,
    },
  },
  methods: {
    onNameChange(newVal) {
      if (newVal.length > 50) {
        this.addError('Name too long')
      }
    },
  },
}
</script>
