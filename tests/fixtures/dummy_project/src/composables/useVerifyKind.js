// Manual verification fixture: deliberately mismatched kinds
import { ref } from 'vue'

export function useVerifyKind() {
  const results = ref([])             // correct: data -> ref
  const isLoading = ref(false)        // MISMATCH: mixin method -> composable ref
  function total() {                  // MISMATCH: mixin computed -> composable function
    return results.value.length
  }
  function fetchData() {              // correct: method -> function
    results.value = [1, 2, 3]
  }

  return { results, isLoading, total, fetchData }
}
