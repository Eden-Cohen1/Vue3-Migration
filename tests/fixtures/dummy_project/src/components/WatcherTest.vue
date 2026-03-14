<template>
  <div>
    <input v-model="watchedValue" />
    <ul>
      <li v-for="log in watchLog" :key="log.field">{{ log.field }}: {{ log.newVal }}</li>
    </ul>
  </div>
</template>

<script>
import watcherMixin from '@/mixins/watcherMixin'

export default {
  name: 'WatcherTest',
  mixins: [watcherMixin],
}
</script>
