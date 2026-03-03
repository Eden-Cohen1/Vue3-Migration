import { reactive } from 'vue'

export function useStorage() {
  const state = reactive({
    cache: {},
    ttl: 3600
  })

  function get(key) {
    const entry = state.cache[key]
    if (!entry) return null
    if (Date.now() - entry.timestamp > state.ttl * 1000) {
      delete state.cache[key]
      return null
    }
    return entry.value
  }

  function set(key, value) {
    state.cache[key] = { value, timestamp: Date.now() }
  }

  function clear() {
    state.cache = {}
  }

  return {
    state,
    get,
    set,
    clear
  }
}
