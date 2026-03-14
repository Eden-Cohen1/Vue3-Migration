<template>
  <div>
    <p>Count: {{ count }}</p>
    <p>Label: {{ label }}</p>
    <p>Active: {{ isActive }}</p>
    <button @click="safeIncrement">Safe +1</button>
    <button @click="safeReset">Safe Reset</button>
    <p>{{ conditionalAccess() }}</p>
  </div>
</template>

<script>

import { useOptionalChain } from '@/composables/useOptionalChain'
export default {
  setup() {
    const { count, label, isActive, safeIncrement, safeReset, conditionalAccess } = useOptionalChain()

    return { count, label, isActive, safeIncrement, safeReset, conditionalAccess }
  },
  name: 'OptionalChainTest',
}
</script>
