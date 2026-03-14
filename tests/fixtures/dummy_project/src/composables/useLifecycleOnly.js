import { onMounted, onBeforeUnmount } from 'vue'

export function useLifecycleOnly() {
  onMounted(() => {
    console.log('Component mounted — lifecycle side effect')
    document.title = 'Mounted'
  })

  onBeforeUnmount(() => {
    console.log('Component about to be destroyed')
    document.title = ''
  })

  return {}
}
