<template>
  <!-- Edge case: composable found via FUZZY match only.
       filterMixin -> candidates: ['useFilter'], but composable is 'useAdvancedFilter'.
       No exact match -> fuzzy: 'filter' substring of 'useadvancedfilter' -> found! -->
  <div>
    <input v-model="filterText" placeholder="Filter...">
    <p>{{ filteredCount }} results</p>
    <button @click="clearFilter">Clear</button>
    <button @click="applyFilter">Apply</button>
  </div>
</template>

<script>
import filterMixin from '@/mixins/filterMixin'

export default {
  name: 'FuzzyMatch',
  mixins: [filterMixin],
}
</script>
