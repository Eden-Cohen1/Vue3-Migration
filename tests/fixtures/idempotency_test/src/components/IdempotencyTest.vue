<template>
  <div>
    <input ref="searchInput" type="text" />
    <div v-if="isLoading">Loading...</div>
    <ul v-if="hasItems">
      <li v-for="item in items" :key="item.id" @click="selectItem(item)">
        {{ item.name }}
      </li>
    </ul>
    <p>Selected: {{ selectedItemName }}</p>
    <p v-if="errorMessage">Error: {{ errorMessage }}</p>
    <button @click="navigateToItem(selectedItem?.id)">View Details</button>
    <button @click="clearSelection">Clear</button>
    <button @click="fetchItems" :disabled="!canRetry">Retry</button>
  </div>
</template>

<script>

import { useIdempotency } from '@/composables/useIdempotency'
export default {
  setup() {
    const { items, selectedItem, isLoading, errorMessage, hasItems, selectedItemName, canRetry, selectItem, navigateToItem, clearSelection, fetchItems } = useIdempotency()

    return { items, selectedItem, isLoading, errorMessage, hasItems, selectedItemName, canRetry, selectItem, navigateToItem, clearSelection, fetchItems }
  },
  name: 'IdempotencyTest',
}
</script>
