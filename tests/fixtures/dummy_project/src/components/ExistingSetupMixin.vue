<template>
  <div>
    <p>Local count: {{ localCount }}</p>
    <button @click="increment">Increment Local</button>
    <p>{{ selectionCount }} items selected</p>
    <button @click="clearSelection">Clear</button>
    <span v-if="hasSelection">Has selection</span>
    <button @click="toggleItem('test')">Toggle</button>
  </div>
</template>

<script>
import { ref } from 'vue'
import selectionMixin from '@/mixins/selectionMixin'

export default {
  name: 'ExistingSetupMixin',
  setup() {
    const localCount = ref(0)
    const increment = () => localCount.value++
    return { localCount, increment }
  },
  mixins: [selectionMixin],
}
</script>
