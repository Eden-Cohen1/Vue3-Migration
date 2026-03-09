<template>
  <div>
    <p>Current page: {{ currentPage }}</p>
    <p>Route: {{ routePath }}</p>
    <p v-if="isAuthenticated">Welcome {{ storeUser.name }}</p>
    <button @click="navigate('/home')">Home</button>
    <button @click="goBack">Back</button>
    <button @click="logout">Logout</button>
  </div>
</template>

<script>
import routerStoreMixin from '@/mixins/routerStoreMixin'

export default {
  name: 'RouterStoreTest',
  mixins: [routerStoreMixin]
}
</script>
