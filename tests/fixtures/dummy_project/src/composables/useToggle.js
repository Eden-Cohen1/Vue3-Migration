import { ref } from 'vue'

export function useToggle() {
  const isOpen = ref(false)
  const label = ref('Toggle')

  function toggle() {
    isOpen.value = !isOpen.value
  }

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
  }

  const api = {
    isOpen,
    label,
    toggle,
    open,
    close
  }

  return api
}
