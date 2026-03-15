<template>
  <div>
    <button @click="toggleSort('name')">Sort by Name {{ sortIndicator }}</button>
    <button @click="toggleSort('date')">Sort by Date</button>
    <button @click="clearSort">Reset</button>
    <p v-if="isSorted">Sorting by: {{ sortKey }} ({{ sortOrder }})</p>
    <ul>
      <li v-for="item in sortedItems" :key="item.id">{{ item.name }}</li>
    </ul>
  </div>
</template>

<script>
import createSortMixin from '@/mixins/sortMixin'

export default {
  name: 'SortTest',
  mixins: [createSortMixin('date')],
  data() {
    return {
      items: [
        { id: 1, name: 'Zebra', date: '2024-01-01' },
        { id: 2, name: 'Apple', date: '2024-06-15' },
        { id: 3, name: 'Mango', date: '2024-03-10' }
      ]
    }
  },
  computed: {
    sortedItems() {
      return [...this.items].sort((a, b) => {
        const val = a[this.sortKey] > b[this.sortKey] ? 1 : -1
        return this.sortOrder === 'asc' ? val : -val
      })
    }
  }
}
</script>
