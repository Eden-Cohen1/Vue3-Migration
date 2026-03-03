import { ref, computed } from 'vue'

export function useTable() {
  const rows = ref([])
  const columns = ref([])
  const sortColumn = ref('')
  const sortDirection = ref('asc')
  const searchQuery = ref('')
  const selectedRows = ref([])
  const pageSize = ref(10)
  const currentPage = ref(1)
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({})
  const expandedRows = ref([])

  const filteredRows = computed(() => {
    if (!searchQuery.value) return rows.value
    const q = searchQuery.value.toLowerCase()
    return rows.value.filter(row =>
      columns.value.some(col => String(row[col.key]).toLowerCase().includes(q))
    )
  })

  const sortedRows = computed(() => {
    const sorted = [...filteredRows.value]
    if (!sortColumn.value) return sorted
    return sorted.sort((a, b) => {
      const valA = a[sortColumn.value]
      const valB = b[sortColumn.value]
      const cmp = valA < valB ? -1 : valA > valB ? 1 : 0
      return sortDirection.value === 'asc' ? cmp : -cmp
    })
  })

  const paginatedRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return sortedRows.value.slice(start, start + pageSize.value)
  })

  const totalRows = computed(() => filteredRows.value.length)
  const totalPages = computed(() => Math.ceil(totalRows.value / pageSize.value))
  const hasNextPage = computed(() => currentPage.value < totalPages.value)
  const hasPrevPage = computed(() => currentPage.value > 1)
  const isEmpty = computed(() => rows.value.length === 0)
  const selectedCount = computed(() => selectedRows.value.length)
  const isAllSelected = computed(() => rows.value.length > 0 && selectedRows.value.length === rows.value.length)

  function sort(col) {
    if (sortColumn.value === col) {
      sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortColumn.value = col
      sortDirection.value = 'asc'
    }
  }

  function search(query) {
    searchQuery.value = query
    currentPage.value = 1
  }

  function selectRow(row) {
    const idx = selectedRows.value.indexOf(row.id)
    if (idx === -1) {
      selectedRows.value.push(row.id)
    } else {
      selectedRows.value.splice(idx, 1)
    }
  }

  function selectAll() {
    if (isAllSelected.value) {
      selectedRows.value = []
    } else {
      selectedRows.value = rows.value.map(r => r.id)
    }
  }

  function clearSelection() {
    selectedRows.value = []
  }

  function nextPage() {
    if (hasNextPage.value) currentPage.value++
  }

  function prevPage() {
    if (hasPrevPage.value) currentPage.value--
  }

  function goToPage(n) {
    if (n >= 1 && n <= totalPages.value) currentPage.value = n
  }

  function expandRow(row) {
    if (!expandedRows.value.includes(row.id)) {
      expandedRows.value.push(row.id)
    }
  }

  function collapseRow(row) {
    const idx = expandedRows.value.indexOf(row.id)
    if (idx !== -1) expandedRows.value.splice(idx, 1)
  }

  function refresh() {
    loading.value = true
    error.value = null
  }

  function exportData() {
    return sortedRows.value.map(row =>
      columns.value.map(col => row[col.key]).join(',')
    ).join('\n')
  }

  return {
    rows,
    columns,
    sortColumn,
    sortDirection,
    searchQuery,
    selectedRows,
    pageSize,
    currentPage,
    loading,
    error,
    filters,
    expandedRows,
    filteredRows,
    sortedRows,
    paginatedRows,
    totalRows,
    totalPages,
    hasNextPage,
    hasPrevPage,
    isEmpty,
    selectedCount,
    isAllSelected,
    sort,
    search,
    selectRow,
    selectAll,
    clearSelection,
    nextPage,
    prevPage,
    goToPage,
    expandRow,
    collapseRow,
    refresh,
    exportData
  }
}
