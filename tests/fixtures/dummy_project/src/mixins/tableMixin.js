export default {
  data() {
    return {
      rows: [],
      columns: [],
      sortColumn: '',
      sortDirection: 'asc',
      searchQuery: '',
      selectedRows: [],
      pageSize: 10,
      currentPage: 1,
      loading: false,
      error: null,
      filters: {},
      expandedRows: []
    }
  },
  computed: {
    filteredRows() {
      if (!this.searchQuery) return this.rows
      const q = this.searchQuery.toLowerCase()
      return this.rows.filter(row =>
        this.columns.some(col => String(row[col.key]).toLowerCase().includes(q))
      )
    },
    sortedRows() {
      const sorted = [...this.filteredRows]
      if (!this.sortColumn) return sorted
      return sorted.sort((a, b) => {
        const valA = a[this.sortColumn]
        const valB = b[this.sortColumn]
        const cmp = valA < valB ? -1 : valA > valB ? 1 : 0
        return this.sortDirection === 'asc' ? cmp : -cmp
      })
    },
    paginatedRows() {
      const start = (this.currentPage - 1) * this.pageSize
      return this.sortedRows.slice(start, start + this.pageSize)
    },
    totalRows() {
      return this.filteredRows.length
    },
    totalPages() {
      return Math.ceil(this.totalRows / this.pageSize)
    },
    hasNextPage() {
      return this.currentPage < this.totalPages
    },
    hasPrevPage() {
      return this.currentPage > 1
    },
    isEmpty() {
      return this.rows.length === 0
    },
    selectedCount() {
      return this.selectedRows.length
    },
    isAllSelected() {
      return this.rows.length > 0 && this.selectedRows.length === this.rows.length
    }
  },
  methods: {
    sort(col) {
      if (this.sortColumn === col) {
        this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortColumn = col
        this.sortDirection = 'asc'
      }
    },
    search(query) {
      this.searchQuery = query
      this.currentPage = 1
    },
    selectRow(row) {
      const idx = this.selectedRows.indexOf(row.id)
      if (idx === -1) {
        this.selectedRows.push(row.id)
      } else {
        this.selectedRows.splice(idx, 1)
      }
    },
    selectAll() {
      if (this.isAllSelected) {
        this.selectedRows = []
      } else {
        this.selectedRows = this.rows.map(r => r.id)
      }
    },
    clearSelection() {
      this.selectedRows = []
    },
    nextPage() {
      if (this.hasNextPage) this.currentPage++
    },
    prevPage() {
      if (this.hasPrevPage) this.currentPage--
    },
    goToPage(n) {
      if (n >= 1 && n <= this.totalPages) this.currentPage = n
    },
    expandRow(row) {
      if (!this.expandedRows.includes(row.id)) {
        this.expandedRows.push(row.id)
      }
    },
    collapseRow(row) {
      const idx = this.expandedRows.indexOf(row.id)
      if (idx !== -1) this.expandedRows.splice(idx, 1)
    },
    refresh() {
      this.loading = true
      this.error = null
    },
    exportData() {
      return this.sortedRows.map(row =>
        this.columns.map(col => row[col.key]).join(',')
      ).join('\n')
    }
  },
  created() {
    this.refresh()
  },
  beforeDestroy() {
    this.selectedRows = []
    this.expandedRows = []
  }
}
