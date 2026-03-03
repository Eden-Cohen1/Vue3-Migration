import { ref, computed } from 'vue'

export function useDerived() {
  const baseValue = ref(10)
  const label = ref('item')

  const doubled = computed(() => baseValue.value * 2)
  const tripled = computed(() => baseValue.value * 3)
  const formatted = computed(() => `${label.value}: ${baseValue.value}`)
  const isPositive = computed(() => baseValue.value > 0)
  const summary = computed(() => isPositive.value ? formatted.value : 'N/A')

  return {
    baseValue,
    label,
    doubled,
    tripled,
    formatted,
    isPositive,
    summary
  }
}
