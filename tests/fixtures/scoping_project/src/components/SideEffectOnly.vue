<template>
  <div>side-effect only</div>
</template>

<script>
import sideEffectOnlyMixin from '@/mixins/sideEffectOnlyMixin'

export default {
  name: 'SideEffectOnly',
  mixins: [sideEffectOnlyMixin],
}
</script>
