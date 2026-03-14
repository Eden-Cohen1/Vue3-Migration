<template>
  <div>
    <p>Valid: {{ isValid }}</p>
    <button @click="apply({ name: 'test', theme: 'dark', locale: 'en' })">Apply</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script>

import { useImportType } from '@/composables/useImportType'
export default {
  setup() {
    const { isValid, apply, reset } = useImportType()

    return { isValid, apply, reset }
  },
  name: 'ImportTypeTest',
}
</script>
