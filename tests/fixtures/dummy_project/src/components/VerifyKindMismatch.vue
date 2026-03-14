<template>
  <div>
    <span v-if="isLoading()">Loading...</span>
    <span>Total: {{ total }}</span>
    <ul>
      <li v-for="r in results" :key="r">{{ r }}</li>
    </ul>
    <button @click="fetchData">Fetch</button>
  </div>
</template>

<script>
import verifyKindMixin from '../mixins/verifyKindMixin'
import verifyOptionsMixin from '../mixins/verifyOptionsMixin'

export default {
  name: 'VerifyKindMismatch',
  mixins: [verifyKindMixin, verifyOptionsMixin],
}
</script>
