<template>
  <div>
    <!-- A1: These comments mention members that should NOT be detected as "used" -->
    <!-- TODO: use loadData to fetch from API -->
    <!-- retryLoad should be called on network failure -->
    <!-- resetCache clears stale data -->
    <!-- cachedData stores the last API response -->

    <!-- Only activeItem and isLoading are actually used in real code below -->
    <p v-if="isLoading">Loading...</p>
    <div v-if="activeItem">{{ activeItem.name }}</div>
    <button @click="clearError">Clear Error</button>
  </div>
</template>

<script>
import commentTrapMixin from '@/mixins/commentTrapMixin'

export default {
  name: 'CommentTrapTest',
  mixins: [commentTrapMixin],
  methods: {
    /*
     * A1: Block comment with member references that should be ignored:
     * Use this.loadData() to refresh the list
     * this.retryCount tracks retry attempts
     * this.cachedData holds cached responses
     */
    handleClick() {
      // A1: Single line comment — this.resetCache should not count
      // Also: this.canRetry is mentioned here but only in a comment
      this.clearError()
    }
  }
}
</script>
