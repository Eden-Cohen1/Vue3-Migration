<template>
  <div class="dashboard">
    <h1>Dashboard â€” Page {{ currentPage }}</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p>Total: {{ totalCount }}</p>
    <p>Last refresh: {{ lastRefresh }}</p>
    <ul>
      <li v-for="stat in stats" :key="stat.id">{{ stat.label }}: {{ stat.value }}</li>
    </ul>
    <button @click="refresh">Refresh</button>
  </div>
</template>

<script>

import { onBeforeUnmount } from 'vue'
import { useDashboard } from '@/composables/useDashboard'
export default {
  name: 'Dashboard',
  setup() {
    const { stats, error, lastRefresh, currentPage, totalCount, refresh, loadStats } = useDashboard()
    loadStats()
    onBeforeUnmount(() => {
        this.$off('stats-updated')
    })

    return { stats, error, lastRefresh, currentPage, totalCount, refresh, loadStats }
  },
  data() {
    return {
      isLoading: false,
    }
  },
}
</script>
