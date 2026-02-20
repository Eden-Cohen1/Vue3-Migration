// Full composable coverage of selectionMixin — all members present AND returned
import { ref, computed } from 'vue'

export function useSelection() {
  const selectedItems = ref([])
  const selectionMode = ref('single')

  const hasSelection = computed(() => selectedItems.value.length > 0)
  const selectionCount = computed(() => selectedItems.value.length)

  function selectItem(item) {
    selectedItems.value.push(item)
  }

  function clearSelection() {
    selectedItems.value = []
  }

  function toggleItem(item) {
    const idx = selectedItems.value.indexOf(item)
    if (idx === -1) selectedItems.value.push(item)
    else selectedItems.value.splice(idx, 1)
  }

  return {
    selectedItems,
    selectionMode,
    hasSelection,
    selectionCount,
    selectItem,
    clearSelection,
    toggleItem,
  }
}
