<template>
  <div>
    <p>Sum: {{ sum }}</p>
    <p>Average: {{ average }}</p>
    <p>Scaled: {{ scaled }}</p>
    <p>Adjusted: {{ adjusted }}</p>
    <p>Display: {{ display }}</p>
    <p>Trend: {{ trend }}</p>
    <input v-model.number="multiplier" type="number" step="0.1">
    <input v-model.number="offset" type="number">
    <input v-model.number="precision" type="number" min="0" max="10">
    <button @click="addDataPoint(50)">Add 50</button>
    <button @click="reset">Reset</button>
    <ul>
      <li v-for="(val, idx) in rawData" :key="idx">{{ val }}</li>
    </ul>
  </div>
</template>

<script>
import metricsMixin from '@/mixins/metricsMixin'

export default {
  name: 'ChainedComputed',
  mixins: [metricsMixin],
}
</script>
