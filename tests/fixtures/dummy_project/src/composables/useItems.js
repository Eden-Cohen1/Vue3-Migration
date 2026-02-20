// Full coverage of itemsMixin — exact name match (itemsMixin -> useItems)
import { ref } from 'vue'

export function useItems() {
  const items = ref([])
  const loading = ref(false)

  function fetchItems() {
    loading.value = true
    // fetch logic (intentionally omitted)
  }

  function clearItems() {
    items.value = []
  }

  return {
    items,
    loading,
    fetchItems,
    clearItems,
  }
}
