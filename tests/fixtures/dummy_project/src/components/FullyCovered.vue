<template>
  <!-- Edge case: ALL mixin members are used and fully covered -> READY -->
  <div>
    <p>{{ selectionCount }} items selected</p>
    <button @click="clearSelection">Clear</button>
    <span v-if="hasSelection">{{ selectedItems.length }}</span>
    <button @click="toggleItem(null)">Toggle</button>
  </div>
</template>

<script>
import selectionMixin from '@/mixins/selectionMixin'

export default {
  name: 'FullyCovered',
  mixins: [selectionMixin],
}
</script>
