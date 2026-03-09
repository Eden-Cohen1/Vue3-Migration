// B2: Pre-existing composable that already uses useRouter and a Pinia store.
// Warnings for this.$router, this.$route, this.$store should be suppressed.
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function useRouterStore() {
  const router = useRouter()
  const route = useRoute()
  const authStore = useAuthStore()

  const currentPage = ref('')
  const userData = ref(null)

  const routePath = computed(() => route.path)
  const routeParams = computed(() => route.params)
  const storeUser = computed(() => authStore.user)
  const isAuthenticated = computed(() => authStore.isAuthenticated)

  function navigate(path) {
    router.push(path)
  }

  function goBack() {
    router.go(-1)
  }

  function logout() {
    authStore.logout()
    router.push('/login')
  }

  function fetchUser() {
    userData.value = authStore.user
    currentPage.value = route.name
  }

  return {
    currentPage, userData, routePath, routeParams, storeUser,
    isAuthenticated, navigate, goBack, logout, fetchUser
  }
}
