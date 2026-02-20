<template>
  <!-- Edge case: mixin has lifecycle hooks (created, mounted, beforeDestroy)
       useLogging covers data+methods but lifecycle hooks need manual migration.
       Status: READY for injection (hooks don't block), but report warns about manual work. -->
  <div>
    <ul>
      <li v-for="entry in logs" :key="entry.time">{{ entry.message }}</li>
    </ul>
  </div>
</template>

<script>
import loggingMixin from '@/mixins/loggingMixin'

export default {
  name: 'LifecycleHooks',
  mixins: [loggingMixin],
}
</script>
