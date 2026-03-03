import { ref, computed } from 'vue'

export function useAsync() {
  const loading = ref(false)
  const error = ref(null)
  const result = ref(null)
  const retryCount = ref(0)

  const hasError = computed(() => !!error.value)
  const canRetry = computed(() => retryCount.value < 3)

  async function fetchData(url) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      result.value = await response.json()
    } catch (err) {
      error.value = err.message
      handleError(err)
    } finally {
      loading.value = false
    }
  }

  async function submitForm(data) {
    loading.value = true
    try {
      const response = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      result.value = await response.json()
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  async function batchProcess(items) {
    loading.value = true
    error.value = null
    try {
      const results = await Promise.all(
        items.map(item => fetch(`/api/process/${item.id}`).then(r => r.json()))
      )
      result.value = results
    } catch (err) {
      error.value = `Batch failed: ${err.message}`
    } finally {
      loading.value = false
    }
  }

  function handleError(err) {
    retryCount.value++
    console.error(`Error (attempt ${retryCount.value}):`, err)
  }

  return {
    loading,
    error,
    result,
    retryCount,
    hasError,
    canRetry,
    fetchData,
    submitForm,
    batchProcess,
    handleError
  }
}
