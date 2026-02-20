// Partial composable — demonstrates two blocker scenarios:
//   1. hasPrevPage and prevPage are MISSING entirely (not defined anywhere)
//   2. resetPagination IS defined but NOT in the return statement (not_returned)
import { ref, computed } from 'vue'

export function usePagination() {
  const currentPage = ref(1)
  const pageSize = ref(20)
  const totalItems = ref(0)

  const totalPages = computed(() => Math.ceil(totalItems.value / pageSize.value))
  const hasNextPage = computed(() => currentPage.value < totalPages.value)
  // hasPrevPage intentionally absent (MISSING)

  function nextPage() {
    if (hasNextPage.value) currentPage.value++
  }
  // prevPage intentionally absent (MISSING)

  function goToPage(page) {
    currentPage.value = page
  }

  function resetPagination() {
    currentPage.value = 1
  }
  // resetPagination intentionally excluded from return (NOT_RETURNED)

  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    hasNextPage,
    nextPage,
    goToPage,
  }
}
