<template>
  <div>{{ doSearch() }}</div>
</template>

<script>
import wordBoundaryMixin from '@/mixins/wordBoundaryMixin'

export default {
  name: 'WordBoundary',
  mixins: [wordBoundaryMixin],
}
</script>
