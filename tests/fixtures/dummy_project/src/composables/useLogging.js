// Covers loggingMixin's data + methods.
// Lifecycle hooks (created, mounted, beforeDestroy) need manual migration.
import { ref } from 'vue'

export function useLogging() {
  const logs = ref([])

  function log(message) {
    logs.value.push({ message, time: Date.now() })
  }

  return {
    logs,
    log,
  }
}
