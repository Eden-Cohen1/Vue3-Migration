# Bug: Report flags "skipped-lifecycle-only" for composable that already has converted lifecycle hooks

## Problem

The migration report says `useChart` needs a manual step: "Replace `skipped-lifecycle-only` → Manually convert lifecycle hooks to the composable." But the generated composable **already contains** correctly converted Vue 3 lifecycle hooks (`onMounted`, `onBeforeUnmount`). The step misleadingly tells users to convert something that's already done.

Additionally, the generated composable's header comment says "⚠️ 2 manual steps needed" but the report only lists 1 step — an inconsistency.

## Input mixin: `chartMixin.js`

```js
import { useTasksStore } from '@/stores/tasks'
import { useSettingsStore } from '@/stores/settings'
import { debounce } from '@/utils/helpers'

export default {
  data() {
    return {
      chartData: null,
      chartOptions: {},
      chartType: 'bar',
      isChartReady: false,
      _debouncedResize: null
    }
  },

  computed: {
    formattedChartData() {
      if (!this.chartData || this.chartData.length === 0) {
        return { labels: [], datasets: [] }
      }
      return {
        labels: this.chartData.map(d => d.label),
        datasets: [{
          data: this.chartData.map(d => d.value),
          backgroundColor: this.chartColors
        }]
      }
    },

    chartColors() {
      const settingsStore = useSettingsStore()
      const isDark = settingsStore.theme === 'dark'
      if (isDark) {
        return [
          '#66BB6A', '#42A5F5', '#FFA726', '#EF5350',
          '#AB47BC', '#26C6DA', '#FFEE58', '#8D6E63'
        ]
      }
      return [
        '#4CAF50', '#2196F3', '#FF9800', '#F44336',
        '#9C27B0', '#00BCD4', '#FFEB3B', '#795548'
      ]
    },

    hasData() {
      return !!this.chartData && this.chartData.length > 0
    }
  },

  methods: {
    prepareChartData(raw) {
      this.chartData = raw.map(item => ({
        label: item.name || item.label,
        value: item.value || item.count || 0
      }))
    },

    async loadTaskChartData(projectId) {
      const tasksStore = useTasksStore()
      await tasksStore.fetchTasks(projectId)
      const byStatus = tasksStore.tasksByStatus
      const raw = Object.entries(byStatus).map(([status, tasks]) => ({
        label: status,
        value: tasks.length
      }))
      this.prepareChartData(raw)
    },

    updateChart() {
      this.isChartReady = true
      this.$nextTick(() => {
        // Chart DOM updated
      })
    },

    resizeChart() {
      const width = this.$el.offsetWidth
      if (this.$refs.chartCanvas) {
        this.$refs.chartCanvas.width = width
        this.$refs.chartCanvas.height = width * 0.6
      }
    },

    exportChart(format) {
      const canvas = this.$refs.chartCanvas
      if (!canvas) return null

      if (format === 'png') {
        return canvas.toDataURL('image/png')
      } else if (format === 'jpg') {
        return canvas.toDataURL('image/jpeg')
      }
      return null
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
  },

  watch: {
    chartData: {
      deep: true,
      handler() {
        this.updateChart()
      }
    }
  }
}
```

## Generated composable: `useChart.js` (lifecycle hooks already converted)

```js
// ⚠️ 2 manual steps needed — see migration report for details
import { debounce } from '@/utils/helpers'
import { useTasksStore } from '@/stores/tasks'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

export function useChart() {
  const chartData = ref(null)
  const chartOptions = ref({})
  const chartType = ref('bar')
  const isChartReady = ref(false)

  const formattedChartData = computed(() => {
    if (!chartData.value) return null
    return {
      labels: chartData.value.labels || [],
      datasets: chartData.value.datasets || []
    }
  })

  const chartColors = computed(() => {
    return chartOptions.value.colors || ['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0']
  })

  const hasData = computed(() => chartData.value !== null)

  function prepareChartData(raw) {
    if (!raw) return
    chartData.value = {
      labels: raw.labels || [],
      datasets: (raw.datasets || []).map((ds, i) => ({
        ...ds,
        backgroundColor: chartColors.value[i % chartColors.value.length]
      }))
    }
    isChartReady.value = true
  }

  function updateChart() {
    if (chartData.value) {
      isChartReady.value = false
      // Trigger re-render
      isChartReady.value = true
    }
  }

  function resizeChart() {
    // Handle chart resize logic
    updateChart()
  }

  function exportChart(format) {
    if (!isChartReady.value) return null
    return {
      type: chartType.value,
      format: format || 'png',
      data: formattedChartData.value
    }
  }

  async function loadTaskChartData(projectId) {
    const tasksStore = useTasksStore()
    await tasksStore.fetchTasks(projectId)
    const byStatus = tasksStore.tasksByStatus
    const raw = Object.entries(byStatus).map(([status, tasks]) => ({
      label: status,
      value: tasks.length
    }))
    prepareChartData(raw)
  }
  const _debouncedResize = ref(null)
  onMounted(() => {                                          // ← Already converted!
    _debouncedResize.value = debounce(resizeChart, 150)
    window.addEventListener('resize', _debouncedResize.value)
    resizeChart()
  })
  onBeforeUnmount(() => {                                    // ← Already converted!
    isChartReady.value = false
    if (_debouncedResize.value) {
      window.removeEventListener('resize', _debouncedResize.value)
    }
  })
  return {
    chartData, chartOptions, chartType, isChartReady,
    formattedChartData, chartColors, hasData,
    prepareChartData, updateChart, resizeChart, exportChart,
    loadTaskChartData, _debouncedResize,
  }
}
```

## Report output (what the user sees)

```
### 🟡 `useChart` — 1 step

- **Step 1:** Replace `skipped-lifecycle-only` → Manually convert lifecycle hooks to the composable, or remove the mixin if unused.

> **Unused members:** `_debouncedResize`, `formattedChartData`, `updateChart`, `exportChart` — consider removing from composable return
```

## What's wrong

1. **False step**: The composable already has `onMounted()` (L74) and `onBeforeUnmount()` (L79) — correct Vue 3 lifecycle hooks. There's nothing for the user to manually convert.
2. **Inconsistent header**: The composable file says `// ⚠️ 2 manual steps needed` but the report only lists 1 step.
3. **Misleading guidance**: A user reading "manually convert lifecycle hooks" will waste time looking for unconverted hooks that don't exist.

## Expected behavior

Since the lifecycle hooks were successfully converted to `onMounted`/`onBeforeUnmount`, the report should NOT list a `skipped-lifecycle-only` step for this composable. The tool should check whether lifecycle hooks were already converted before emitting this warning.

## Investigation

Find the logic that decides to emit the `skipped-lifecycle-only` warning/step. It likely fires based on the mixin having `mounted`/`beforeUnmount`/etc. hooks, without checking whether the generated composable already contains the corresponding Vue 3 equivalents (`onMounted`, `onBeforeUnmount`, etc.). The fix should:

1. After generating the composable, check if `onMounted`/`onBeforeUnmount`/etc. calls are present
2. Only emit `skipped-lifecycle-only` if the hooks were NOT converted
3. Also fix the file header comment count to match the actual number of report steps
