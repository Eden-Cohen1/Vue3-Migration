<template>
  <div>
    <p>Last query: {{ lastQuery }}</p>
    <button @click="search('test', 10)">Search</button>
    <p>{{ format(42.5) }}</p>
  </div>
</template>

<script>

import { useTypedMethods } from '@/composables/useTypedMethods'
export default {
  setup() {
    const { lastQuery, search, format } = useTypedMethods()

    return { lastQuery, search, format }
  },
  name: 'TypedMethodsTest',
}
</script>
