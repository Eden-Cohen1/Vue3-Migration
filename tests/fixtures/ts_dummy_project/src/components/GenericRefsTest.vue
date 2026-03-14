<template>
  <div>
    <p v-if="hasSelection">Selected: {{ selected }}</p>
    <p>{{ entryCount }} entries</p>
    <button @click="select('item-1')">Select</button>
    <button @click="addEntry(1, 'test')">Add</button>
  </div>
</template>

<script>

import { useGenericRefs } from '@/composables/useGenericRefs'
export default {
  setup() {
    const { selected, entries, hasSelection, entryCount, select, addEntry } = useGenericRefs()

    return { selected, entries, hasSelection, entryCount, select, addEntry }
  },
  name: 'GenericRefsTest',
}
</script>
