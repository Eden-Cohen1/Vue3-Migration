<template>
  <div class="showcase">
    <input v-model="query" />
    <p>Total: {{ total }}</p>
    <p>Label: {{ fullLabel }}</p>
    <p>Count: {{ count }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
    <button @click="search('test')">Search</button>
    <button @click="addItem(99)">Add</button>
    <button @click="removeKey('theme')">Remove</button>
    <button @click="fetchData()">Fetch</button>
    <button @click="navigate('/home')">Go Home</button>
  </div>
</template>

<script>

import { onMounted, onBeforeUnmount} from 'vue'
import { useShowcase } from '@/composables/useShowcase'
export default {
  setup() {
    const { items, query, count, total, fullLabel, search, addItem, removeKey, fetchData, navigate, query, items } = useShowcase()
    fetchData()
    onMounted(() => {
        console.log('mounted with', items.value.length, 'items')
    })
    onBeforeUnmount(() => {
        console.log('cleaning up')
    })

    return { items, query, count, total, fullLabel, search, addItem, removeKey, fetchData, navigate, query, items }
  },
  name: 'Showcase',
}
</script>
