<template>
  <!-- Edge case: component overrides some mixin members (selectionMode, clearSelection)
       overridden members are safe to skip -> classification.overridden populated -> READY -->
  <div>
    <p>{{ selectionCount }} items selected</p>
    <button @click="clearSelection">Clear All</button>
  </div>
</template>

<script>
import selectionMixin from '@/mixins/selectionMixin'

export default {
  name: 'WithOverrides',
  mixins: [selectionMixin],
  data() {
    return {
      selectionMode: 'multi', // overrides mixin's selectionMode
    }
  },
  methods: {
    clearSelection() { // overrides mixin's clearSelection
      this.selectedItems = []
      this.$emit('cleared')
    },
  },
}
</script>
