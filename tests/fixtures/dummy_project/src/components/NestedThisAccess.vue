<template>
  <div>
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key">{{ col.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in paginatedRows" :key="row.id" :class="{ expanded: isRowExpanded(row) }">
          <td v-for="col in columns" :key="col.key">{{ getColumnValue(row, col.key) }}</td>
        </tr>
      </tbody>
    </table>
    <p>Selected from filtered: {{ sortedFilteredCount }}</p>
    <input :value="getFilterValue('status')" placeholder="Status filter">
    <span>{{ selectedRows.length }} selected</span>
    <span>{{ sortedRows.length }} sorted</span>
    <span>{{ expandedRows.length }} expanded</span>
    <span>{{ filters }}</span>
  </div>
</template>

<script>
import tableMixin from '@/mixins/tableMixin'

export default {
  name: 'NestedThisAccess',
  mixins: [tableMixin],
  computed: {
    sortedFilteredCount() {
      return this.sortedRows.filter(r => this.selectedRows.includes(r.id)).length
    },
  },
  methods: {
    getColumnValue(row, col) {
      const colDef = this.columns.find(c => c.key === col)
      return colDef && colDef.accessor ? row[colDef.accessor] : row[col]
    },
    isRowExpanded(row) {
      return this.expandedRows.includes(row.id)
    },
    getFilterValue(key) {
      return this.filters[key] || ''
    },
  },
}
</script>
