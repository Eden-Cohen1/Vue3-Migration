<template>
  <div>
    <div v-if="loading">Loading table...</div>
    <div v-if="error">{{ error }}</div>
    <div v-if="isEmpty">No data</div>

    <input :value="searchQuery" @input="search($event.target.value)" placeholder="Search...">

    <table v-if="!isEmpty">
      <thead>
        <tr>
          <th>
            <input type="checkbox" :checked="isAllSelected" @change="selectAll">
          </th>
          <th v-for="col in columns" :key="col.key" @click="sort(col.key)">
            {{ col.label }}
            <span v-if="sortColumn === col.key">{{ sortDirection }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in paginatedRows" :key="row.id" :class="{ expanded: expandedRows.includes(row.id) }">
          <td>
            <input type="checkbox" :checked="selectedRows.includes(row.id)" @change="selectRow(row)">
          </td>
          <td v-for="col in columns" :key="col.key">{{ row[col.key] }}</td>
          <td>
            <button @click="expandRow(row)">Expand</button>
            <button @click="collapseRow(row)">Collapse</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div>
      <span>{{ selectedCount }} selected</span>
      <button @click="clearSelection">Clear Selection</button>
    </div>

    <div>
      <span>Page {{ currentPage }} of {{ totalPages }} ({{ totalRows }} total, {{ pageSize }} per page)</span>
      <button :disabled="!hasPrevPage" @click="prevPage">Prev</button>
      <button :disabled="!hasNextPage" @click="nextPage">Next</button>
      <button @click="goToPage(1)">First</button>
      <button @click="refresh">Refresh</button>
      <button @click="exportData">Export</button>
    </div>

    <div>
      <span>Sorted: {{ sortedRows.length }}</span>
      <span>Filtered: {{ filteredRows.length }}</span>
      <pre>{{ filters }}</pre>
    </div>
  </div>
</template>

<script>
import tableMixin from '../mixins/tableMixin'

export default {
  name: 'LargeComponent',
  mixins: [tableMixin],
}
</script>
