// Issue 1: Mixin with lifecycle hooks — composable already has onMounted/onBeforeUnmount.
// The report should NOT emit skipped-lifecycle-only for this.
import { debounce } from '@/utils/helpers'

export default {
  data() {
    return {
      chartData: null,
      isChartReady: false,
      _debouncedResize: null
    }
  },

  computed: {
    hasData() {
      return !!this.chartData && this.chartData.length > 0
    }
  },

  methods: {
    updateChart() {
      this.isChartReady = true
      this.$nextTick(() => {
        // Chart DOM updated
      })
    },

    resizeChart() {
      if (this.$refs.chartCanvas) {
        this.$refs.chartCanvas.width = 800
      }
    }
  },

  mounted() {
    this._debouncedResize = debounce(this.resizeChart, 150)
    window.addEventListener('resize', this._debouncedResize)
    this.resizeChart()
  },

  beforeUnmount() {
    this.isChartReady = false
    if (this._debouncedResize) {
      window.removeEventListener('resize', this._debouncedResize)
    }
  }
}
