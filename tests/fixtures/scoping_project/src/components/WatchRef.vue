<template>
  <div>
    <input v-model="keyword" />
  </div>
</template>

<script>
import watchRefMixin from '@/mixins/watchRefMixin'

export default {
  name: 'WatchRef',
  mixins: [watchRefMixin],
}
</script>
