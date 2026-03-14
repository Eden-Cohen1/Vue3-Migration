<template>
  <div>
    <p>This component uses a lifecycle-only mixin for side effects.</p>
    <p>{{ title }}</p>
  </div>
</template>

<script>
import lifecycleOnlyMixin from '@/mixins/lifecycleOnlyMixin'

export default {
  name: 'LifecycleOnlyTest',
  mixins: [lifecycleOnlyMixin],
  data() {
    return {
      title: 'Hello',
    }
  },
}
</script>
