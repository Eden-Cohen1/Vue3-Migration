<template>
  <!-- Edge case: component uses 'resetPagination' which IS defined in usePagination
       but is NOT in its return statement -> BLOCKED_NOT_RETURNED -->
  <div>
    <p>Page {{ currentPage }}</p>
    <button @click="resetPagination">Reset</button>
  </div>
</template>

<script>
import paginationMixin from '@/mixins/paginationMixin'

export default {
  name: 'NotReturnedBlocker',
  mixins: [paginationMixin],
}
</script>
