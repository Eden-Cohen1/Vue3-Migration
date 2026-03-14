// Issue 1: Pre-existing composable that ALREADY has converted lifecycle hooks.
// The report should NOT say "manually convert lifecycle hooks".
import { debounce } from '@/utils/helpers'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

export function useChart() {
  const chartData = ref(null)
  const isChartReady = ref(false)

  const hasData = computed(() => !!chartData.value && chartData.value.length > 0)

  function updateChart() {
    isChartReady.value = true
  }

  function resizeChart() {
    // Handle chart resize logic
    updateChart()
  }

  const _debouncedResize = ref(null)

  onMounted(() => {
    _debouncedResize.value = debounce(resizeChart, 150)
    window.addEventListener('resize', _debouncedResize.value)
    resizeChart()
  })

  onBeforeUnmount(() => {
    isChartReady.value = false
    if (_debouncedResize.value) {
      window.removeEventListener('resize', _debouncedResize.value)
    }
  })

  return {
    chartData, isChartReady, hasData,
    updateChart, resizeChart, _debouncedResize,
  }
}
