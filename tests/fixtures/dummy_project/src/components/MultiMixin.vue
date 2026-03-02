<template>
  <!-- Edge case: four mixins with different statuses in one component
       - selectionMixin  -> READY
       - paginationMixin -> BLOCKED_NOT_RETURNED (resetPagination defined but not returned)
       - authMixin       -> READY
       - loggingMixin    -> READY (lifecycle hooks need manual migration but don't block) -->
  <div>
    <!-- selectionMixin: data + computed -->
    <p>{{ selectionCount }} items selected (mode: {{ selectionMode }})</p>
    <p v-if="hasSelection">Selected: {{ selectedItems.join(', ') }}</p>
    <button @click="handleSelect('foo')">Select</button>
    <button @click="handleToggle('foo')">Toggle</button>
    <button @click="clearSelection">Clear</button>

    <!-- paginationMixin: data + computed + methods -->
    <p>Page {{ currentPage }} of {{ totalPages }} ({{ pageSize }} per page, {{ totalItems }} total)</p>
    <button :disabled="!hasPrevPage" @click="prevPage">Prev</button>
    <button :disabled="!hasNextPage" @click="nextPage">Next</button>
    <button @click="goToPage(1)">First</button>
    <button @click="resetPagination">Reset</button>

    <!-- authMixin: data + computed + methods -->
    <div v-if="isAuthenticated">
      <span>{{ currentUser.name }}</span>
      <span v-if="isAdmin">(Admin)</span>
      <span>Token: {{ token }}</span>
      <button @click="logout">Logout</button>
    </div>
    <button v-else @click="handleLogin">Login</button>

    <!-- loggingMixin: data + methods -->
    <ul>
      <li v-for="entry in logs" :key="entry.time">{{ entry.message }}</li>
    </ul>
    <button @click="log('manual log entry')">Log</button>
  </div>
</template>

<script>
import selectionMixin from '@/mixins/selectionMixin'
import paginationMixin from '@/mixins/paginationMixin'
import authMixin from '@/mixins/authMixin'
import loggingMixin from '@/mixins/loggingMixin'

export default {
  name: 'MultiMixin',
  mixins: [selectionMixin, paginationMixin, authMixin, loggingMixin],
  methods: {
    handleSelect(item) {
      this.selectItem(item)
      this.log(`Selected: ${item}`)
    },
    handleToggle(item) {
      this.toggleItem(item)
      this.log(`Toggled: ${item}`)
    },
    handleLogin() {
      this.login({ username: 'demo', password: 'secret' })
      this.log('Login attempted')
    },
  },
}
</script>
