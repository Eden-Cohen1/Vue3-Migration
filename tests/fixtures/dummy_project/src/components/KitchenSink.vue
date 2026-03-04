<template>
  <div class="kitchen-sink">
    <input ref="searchInput" v-model="query" placeholder="Search..." />
    <p v-if="isLoading">Loading...</p>
    <ul>
      <li v-for="item in filteredItems" :key="item">{{ item }}</li>
    </ul>
    <span>{{ fullName }}</span>
    <span>{{ message }}</span>
    <button @click="navigate('/home')">Home</button>
    <button @click="saveItem('new')">Save</button>
    <button @click="removeItem('theme')">Remove</button>
    <button @click="focusInput">Focus</button>
  </div>
</template>

<script>

import { onMounted } from 'vue'
import { useKitchenSink } from '@/composables/useKitchenSink'
export default {
  setup() {
    const { query, isLoading, message, filteredItems, fullName, navigate, saveItem, removeItem, focusInput, fetchResults } = useKitchenSink()
    fetchResults(query.value)
    onMounted(() => {
        this.$el.classList.add('loaded')
        this.$parent.notifyChildMounted()
    })

    return { query, isLoading, message, filteredItems, fullName, navigate, saveItem, removeItem, focusInput, fetchResults }
  },
  name: 'KitchenSink',
}
</script>
