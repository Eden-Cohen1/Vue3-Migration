<template>
  <div class="report-test">
    <h2>Filter Panel</h2>
    <div>Active: {{ activeFilterCount }} filters</div>
    <div v-if="isFiltered">Summary: {{ appliedFilterSummary }}</div>
    <div v-if="loading">Loading...</div>
    <ul>
      <li v-for="item in items" :key="item.id">{{ item.name }}</li>
    </ul>
    <button @click="clearAllFilters">Clear</button>
    <button @click="refreshUI">Refresh</button>
    <button @click="navigateTo('/home')">Home</button>
  </div>
</template>

<script>

import { useReportTest } from '@/composables/useReportTest'
export default {
  setup() {
    const { filters, items, loading, activeFilterCount, isFiltered, appliedFilterSummary, clearAllFilters, navigateTo, refreshUI, loadData } = useReportTest()

    return { filters, items, loading, activeFilterCount, isFiltered, appliedFilterSummary, clearAllFilters, navigateTo, refreshUI, loadData }
  },
  name: 'ReportTest',
}
</script>
