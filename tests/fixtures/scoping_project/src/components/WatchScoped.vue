<template>
  <div>
    <input v-model="query" />
  </div>
</template>

<script>
import watchScopedMixin from '@/mixins/watchScopedMixin'

export default {
  name: 'WatchScoped',
  mixins: [watchScopedMixin],
}
</script>
