// Demo mixin 2: named import, lifecycle hooks, $route/$store, async method
import { helperUtil } from '../utils/helpers'

export default {
  data() {
    return {
      stats: [],
      error: null,
      lastRefresh: null,
    }
  },
  computed: {
    currentPage() {
      return this.$route.params.page || 1
    },
    totalCount() {
      return this.stats.length
    },
  },
  methods: {
    async loadStats() {
      this.error = null
      this.isLoading = true
      try {
        const page = this.$route.params.page
        const data = await this.$store.dispatch('fetchStats', { page })
        this.stats = data
        this.lastRefresh = Date.now()
      } catch (e) {
        this.error = e.message
        this.$emit('stats-error', e)
      }
    },
    refresh() {
      this.$nextTick(() => {
        this.loadStats()
      })
    },
  },
  created() {
    this.loadStats()
  },
  beforeDestroy() {
    this.$off('stats-updated')
  },
}
