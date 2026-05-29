<template>
  <div>
    <p>{{ alpha }}</p>
    <button @click="useAlpha">Use alpha</button>
  </div>
</template>

<script>
import basicSubsetMixin from '@/mixins/basicSubsetMixin'

export default {
  name: 'BasicSubset',
  mixins: [basicSubsetMixin],
}
</script>
