<template>
  <!-- Edge case: mixin with no matching composable -> BLOCKED_NO_COMPOSABLE -->
  <div>
    <p v-if="hasNotifications">{{ unreadCount }} unread</p>
    <ul>
      <li v-for="n in notifications" :key="n.id">{{ n.message }}</li>
    </ul>
    <button @click="clearNotifications">Clear</button>
  </div>
</template>

<script>
import notificationMixin from '@/mixins/notificationMixin'

export default {
  name: 'NoComposable',
  mixins: [notificationMixin],
}
</script>
