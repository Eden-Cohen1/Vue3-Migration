<template>
  <div>
    <canvas ref="chartCanvas"></canvas>
    <p v-if="hasData">Chart ready: {{ isChartReady }}</p>
  </div>
</template>

<script>
import chartMixin from '@/mixins/chartMixin'

export default {
  name: 'ChartTest',
  mixins: [chartMixin],
}
</script>
