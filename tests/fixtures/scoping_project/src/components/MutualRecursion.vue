<template>
  <div>{{ ping(5) }}</div>
</template>

<script>
import mutualRecursionMixin from '@/mixins/mutualRecursionMixin'

export default {
  name: 'MutualRecursion',
  mixins: [mutualRecursionMixin],
}
</script>
