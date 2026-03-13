import { ref } from 'vue'

export function useStatus() {
  const isLoading = ref(false)
  const statusMessage = ref('')

  function setStatus(msg) {
    statusMessage.value = msg
  }

  function clearStatus() {
    statusMessage.value = ''
    isLoading.value = false
  }

  return {
    isLoading,
    statusMessage,
    setStatus,
    clearStatus,
  }
}
