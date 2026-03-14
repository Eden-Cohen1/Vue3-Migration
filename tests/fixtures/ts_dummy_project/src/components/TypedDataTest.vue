<template>
  <div>
    <p>{{ count }} (doubled: {{ doubled }})</p>
    <p>{{ summary }}</p>
    <button @click="increment">+1</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script>

import { useTypedData } from '@/composables/useTypedData'
export default {
  setup() {
    const { count, doubled, summary, increment, reset } = useTypedData()

    return { count, doubled, summary, increment, reset }
  },
  name: 'TypedDataTest',
}
</script>
