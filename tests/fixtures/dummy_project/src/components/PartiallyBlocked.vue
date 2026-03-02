<template>
  <!-- Edge case: two mixins, different statuses
       - selectionMixin  -> READY
       - paginationMixin -> BLOCKED_NOT_RETURNED (resetPagination defined but not returned) -->
  <div>
    <p>Page {{ currentPage }} of {{ totalPages }}</p>
    <button @click="nextPage" :disabled="!hasNextPage">Next</button>
    <button @click="resetPagination">Reset</button>
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
