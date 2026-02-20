<template>
  <!-- Edge case: four mixins with different statuses in one component
       - selectionMixin  -> READY
       - paginationMixin -> BLOCKED (missing members in usePagination)
       - authMixin       -> BLOCKED_NO_COMPOSABLE
       - loggingMixin    -> READY (lifecycle hooks need manual migration but don't block) -->
  <div>
    <p>{{ selectionCount }} items selected on page {{ currentPage }}</p>
    <div v-if="isAuthenticated">{{ currentUser.name }}</div>
    <ul>
      <li v-for="entry in logs" :key="entry.time">{{ entry.message }}</li>
    </ul>
  </div>
</template>

<script>
import selectionMixin from "@/mixins/selectionMixin";
import paginationMixin from "@/mixins/paginationMixin";
import authMixin from "@/mixins/authMixin";
import loggingMixin from "@/mixins/loggingMixin";

export default {
  name: "MultiMixin",
  mixins: [selectionMixin, paginationMixin, authMixin, loggingMixin],
};
</script>
