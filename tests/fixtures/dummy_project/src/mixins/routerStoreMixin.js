// B2 stress test: mixin uses this.$router, this.$store, this.$route
// When there's an existing composable that already uses useRouter/useStore,
// warnings should be suppressed.
// Also tests B1: these are mixin-intrinsic warnings, not component-specific.
export default {
  data() {
    return {
      currentPage: '',
      userData: null
    }
  },
  computed: {
    routePath() {
      return this.$route.path
    },
    routeParams() {
      return this.$route.params
    },
    storeUser() {
      return this.$store.state.user
    },
    isAuthenticated() {
      return this.$store.getters.isAuthenticated
    }
  },
  methods: {
    navigate(path) {
      this.$router.push(path)
    },
    goBack() {
      this.$router.go(-1)
    },
    logout() {
      this.$store.dispatch('logout')
      this.$router.push('/login')
    },
    fetchUser() {
      this.userData = this.$store.state.user
      this.currentPage = this.$route.name
    }
  }
}
