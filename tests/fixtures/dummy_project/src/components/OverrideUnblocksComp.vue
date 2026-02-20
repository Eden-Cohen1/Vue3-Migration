<template>
  <!-- Edge case: composable is MISSING hasPrevPage + prevPage, but the COMPONENT
       defines them itself -> classification.overridden = [hasPrevPage, prevPage]
       -> truly_missing = [] -> READY despite the composable gap -->
  <div>
    <button @click="prevPage" :disabled="!hasPrevPage">Prev</button>
    <button @click="nextPage" :disabled="!hasNextPage">Next</button>
  </div>
</template>

<script>
import paginationMixin from '@/mixins/paginationMixin'

export default {
  name: 'OverrideUnblocksComp',
  mixins: [paginationMixin],
  computed: {
    hasPrevPage() {
      return this.currentPage > 1
    },
  },
  methods: {
    prevPage() {
      if (this.hasPrevPage) this.currentPage--
    },
  },
}
</script>
