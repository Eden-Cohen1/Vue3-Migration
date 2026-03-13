// ✅ 0 issues — all mixin members have composable equivalents
import { ref, computed } from 'vue'

export function useLoading() {
  const isLoading = ref(false)
  const loadingMessage = ref('')
  const error = ref(null)
  const retryCount = ref(0)

  const hasError = computed(() => !!error.value)
  const canRetry = computed(() => retryCount.value < 3)

  function startLoading(msg) {
    isLoading.value = true
    loadingMessage.value = msg || 'Loading...'
    error.value = null
  }

  function stopLoading() {
    isLoading.value = false
    loadingMessage.value = ''
  }

  function setError(err) {
    error.value = err
    isLoading.value = false
  }

  function retry(fn) {
    retryCount.value++
    fn()
  }

  return {
    isLoading,
    startLoading,
    stopLoading,
    setError,
    loadingMessage,
  }
}
