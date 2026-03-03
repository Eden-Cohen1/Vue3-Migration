import { ref, computed } from 'vue'

export function useMetrics() {
  const rawData = ref([10, 20, 30])
  const multiplier = ref(1.5)
  const offset = ref(100)
  const precision = ref(2)

  const sum = computed(() => rawData.value.reduce((a, b) => a + b, 0))
  const average = computed(() => rawData.value.length ? sum.value / rawData.value.length : 0)
  const scaled = computed(() => average.value * multiplier.value)
  const adjusted = computed(() => scaled.value + offset.value)
  const display = computed(() => `Result: ${adjusted.value.toFixed(precision.value)}`)
  const trend = computed(() => adjusted.value > offset.value ? 'up' : adjusted.value < offset.value ? 'down' : 'flat')

  function addDataPoint(val) {
    rawData.value.push(val)
  }

  function reset() {
    rawData.value = []
    multiplier.value = 1
    offset.value = 0
  }

  return {
    rawData,
    multiplier,
    offset,
    precision,
    sum,
    average,
    scaled,
    adjusted,
    display,
    trend,
    addDataPoint,
    reset
  }
}
