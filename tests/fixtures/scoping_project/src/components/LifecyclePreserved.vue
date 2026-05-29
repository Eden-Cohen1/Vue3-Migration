<template>
  <div>
    <p v-if="visible">shown</p>
    <button @click="toggle">Toggle</button>
  </div>
</template>

<script>
import lifecyclePreservedMixin from '@/mixins/lifecyclePreservedMixin'

export default {
  name: 'LifecyclePreserved',
  mixins: [lifecyclePreservedMixin],
}
</script>
