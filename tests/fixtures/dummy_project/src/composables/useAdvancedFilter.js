// Fuzzy-match target for filterMixin.
// filterMixin -> candidates: ['useFilter'], but THIS file is 'useAdvancedFilter'
// -> no exact match -> fuzzy: core_word 'filter' is a substring of 'useadvancedfilter' -> MATCH
import { ref, computed } from 'vue'

export function useAdvancedFilter() {
  const filterText = ref('')
  const filterActive = ref(false)

  const filteredCount = computed(() => 0) // placeholder

  function applyFilter() {
    filterActive.value = true
  }

  function clearFilter() {
    filterText.value = ''
    filterActive.value = false
  }

  return {
    filterText,
    filterActive,
    filteredCount,
    applyFilter,
    clearFilter,
  }
}
