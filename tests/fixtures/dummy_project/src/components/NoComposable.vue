<template>
  <!-- Edge case: mixin has NO matching composable -> BLOCKED_NO_COMPOSABLE -->
  <div>
    <p v-if="isAuthenticated">Welcome, {{ currentUser.name }}</p>
    <button v-if="isAdmin">Admin Panel</button>
    <button @click="logout">Logout</button>
  </div>
</template>

<script>
import authMixin from '@/mixins/authMixin'

export default {
  name: 'NoComposable',
  mixins: [authMixin],
}
</script>
