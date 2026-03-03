export default {
  data() {
    return {
      cache: {},
      ttl: 3600
    }
  },
  methods: {
    get(key) {
      const entry = this.cache[key]
      if (!entry) return null
      if (Date.now() - entry.timestamp > this.ttl * 1000) {
        delete this.cache[key]
        return null
      }
      return entry.value
    },
    set(key, value) {
      this.cache[key] = { value, timestamp: Date.now() }
    },
    clear() {
      this.cache = {}
    }
  }
}
