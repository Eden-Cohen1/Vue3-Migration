<template>
  <div>
    <input v-model.number="baseValue" type="number">
    <input v-model="label" placeholder="Label">
    <p>Doubled: {{ doubled }}</p>
    <p>Tripled: {{ tripled }}</p>
    <p>Formatted: {{ formatted }}</p>
    <p v-if="isPositive">Positive!</p>
    <p>Summary: {{ summary }}</p>
  </div>
</template>

<script>
import derivedMixin from '@/mixins/derivedMixin'

export default {
  name: 'ComputedOnlyMixin',
  mixins: [derivedMixin],
}
</script>
