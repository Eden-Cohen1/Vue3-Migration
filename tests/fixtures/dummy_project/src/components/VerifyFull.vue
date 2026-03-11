<template>
  <div>
    <input v-model="query" placeholder="Search..." />
    <p v-if="hasResults">Found {{ results.length }} items</p>
    <button @click="search">Search</button>
    <button @click="clearSearch">Clear</button>
    <span>Status: {{ status }}</span>
  </div>
</template>

<script>

import { useVerify } from '@/composables/useVerify'
export default {
  name: 'VerifyFull',
  setup() {
    const { query, results, hasResults, search, clearSearch } = useVerify()

    return { query, results, hasResults, search, clearSearch }
  },
  data() {
    return {
      // Task 9: 'status' collides with mixin's 'status' returned from setup()
      // Report should explain data() shadows setup() value
      status: 'ready',
      externalItems: [
        { name: 'Apple' },
        { name: 'Banana' },
        { name: 'Cherry' },
      ]
    }
  }
}
</script>
