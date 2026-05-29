<template>
  <div>{{ initials }}</div>
</template>

<script>
import computedDepsMixin from '@/mixins/computedDepsMixin'

export default {
  name: 'ComputedDeps',
  mixins: [computedDepsMixin],
}
</script>
