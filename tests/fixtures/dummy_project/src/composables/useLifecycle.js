import { ref, onBeforeMount, onMounted, onBeforeUpdate, onUpdated, onActivated, onDeactivated, onBeforeUnmount, onUnmounted, onErrorCaptured } from 'vue'

export function useLifecycle() {
  const hookLog = ref([])
  const mountCount = ref(0)
  const isActive = ref(false)

  function logHook(name) {
    hookLog.value.push(name)
  }

  return {
    hookLog,
    mountCount,
    isActive,
    logHook
  }
}
