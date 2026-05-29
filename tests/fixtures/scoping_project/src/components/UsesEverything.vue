<template>
  <div>
    <p>{{ x }} / {{ dbl }}</p>
    <button @click="inc">+</button>
  </div>
</template>

<script>
import usesEverythingMixin from '@/mixins/usesEverythingMixin'

export default {
  name: 'UsesEverything',
  mixins: [usesEverythingMixin],
}
</script>
