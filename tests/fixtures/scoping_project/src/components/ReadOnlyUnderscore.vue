<template>
  <div>{{ render() }}</div>
</template>

<script>
import readOnlyUnderscoreMixin from '@/mixins/readOnlyUnderscoreMixin'

export default {
  name: 'ReadOnlyUnderscore',
  mixins: [readOnlyUnderscoreMixin],
}
</script>
