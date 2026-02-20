<template>
  <!-- Edge case: two mixins, different statuses
       - selectionMixin -> READY
       - paginationMixin -> BLOCKED (hasPrevPage and prevPage missing from composable) -->
  <div>
    <p>Page {{ currentPage }} of {{ totalPages }}</p>
    <button @click="prevPage" :disabled="!hasPrevPage">Prev</button>
    <button @click="nextPage" :disabled="!hasNextPage">Next</button>
    <p>{{ selectionCount }} selected</p>
  </div>
</template>

<script>
import paginationMixin from '@/mixins/paginationMixin'
import selectionMixin from '@/mixins/selectionMixin'

export default {
  name: 'PartiallyBlocked',
  mixins: [paginationMixin, selectionMixin],
}
</script>
