// Edge case: mixin with no corresponding composable -> BLOCKED_NO_COMPOSABLE
export default {
  data() {
    return {
      notifications: [],
      unreadCount: 0,
    }
  },
  computed: {
    hasNotifications() {
      return this.notifications.length > 0
    },
  },
  methods: {
    addNotification(message) {
      this.notifications.push({ message, id: Date.now() })
      this.unreadCount++
    },
    clearNotifications() {
      this.notifications = []
      this.unreadCount = 0
    },
  },
}
