// Edge case: no composable exists for this mixin -> BLOCKED_NO_COMPOSABLE
export default {
  data() {
    return {
      isAuthenticated: false,
      currentUser: null,
      token: null,
    }
  },
  computed: {
    isAdmin() {
      return this.currentUser?.role === 'admin'
    },
  },
  methods: {
    login(credentials) {
      // login logic (intentionally omitted)
    },
    logout() {
      this.isAuthenticated = false
      this.currentUser = null
      this.token = null
    },
    checkAuth() {
      // check stored token (intentionally omitted)
    },
  },
  created() {
    this.checkAuth()
  },
}
