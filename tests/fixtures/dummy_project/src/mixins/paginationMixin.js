// Edge case: partial composable coverage
// Scenario: usePagination is MISSING hasPrevPage + prevPage,
//           and resetPagination is defined but NOT returned -> BLOCKED
export default {
  data() {
    return {
      currentPage: 1,
      pageSize: 20,
      totalItems: 0,
    }
  },
  computed: {
    totalPages() {
      return Math.ceil(this.totalItems / this.pageSize)
    },
    hasNextPage() {
      return this.currentPage < this.totalPages
    },
    hasPrevPage() {
      return this.currentPage > 1
    },
  },
  methods: {
    nextPage() {
      if (this.hasNextPage) this.currentPage++
    },
    prevPage() {
      if (this.hasPrevPage) this.currentPage--
    },
    goToPage(page) {
      this.currentPage = page
    },
    resetPagination() {
      this.currentPage = 1
    },
  },
}
