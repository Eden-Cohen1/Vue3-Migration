<template>
  <div>
    <input ref="searchInput" v-model="searchQuery" />
    <p v-if="hasResults">{{ resultCount }} results</p>
    <ul>
      <li v-for="result in searchResults" :key="result.id">{{ result.name }}</li>
    </ul>
    <button @click="clearSearch">Clear</button>
    <div>Recent: {{ recentSearches }}</div>
  </div>
</template>

<script>
import searchMixin from '@/mixins/searchMixin'

export default {
  name: 'SearchTest',
  mixins: [searchMixin],
  data() {
    return {
      items: [
        { id: 1, name: 'Apple' },
        { id: 2, name: 'Banana' },
        { id: 3, name: 'Cherry' }
      ]
    }
  }
}
</script>
