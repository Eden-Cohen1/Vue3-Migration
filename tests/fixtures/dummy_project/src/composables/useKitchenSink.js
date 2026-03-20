x// ⚠️ 25 manual steps needed — see migration report for details
import { ref, computed, watch, onMounted, nextTick } from 'vue'

export function useKitchenSink() {
  const items = ref([1, 2, 3])
  const config = ref({ theme: 'dark', lang: 'en' })
  const query = ref('')
  const isLoading = ref(false)
  const message = ref('hello, world')

  const filteredItems = computed(() => items.value.filter(i => i > 0))
  const fullName = computed({
    get: () => { return query.value + ' suffix' },
    set: (val) => { query.value = val.replace(' suffix', '') },
  })

  function fetchResults(q) {
    this.$emit('search', q)  // ❌ not available in composable — use defineEmits or emit param
    nextTick(() => {
      console.log('DOM updated')
    })
  }
  function navigate(path) {
    this.$router.push(path)  // ❌ not available in composable — use useRouter()
  }
  function loadPage() {
    const id = this.$route.params.id  // ❌ not available in composable — use useRoute() · this alias won't work — replace with direct refs
    this.$store.dispatch('load', { id })  // ❌ not available in composable — use Pinia store
  }
  function focusInput() {
    this.$refs.searchInput.focus()  // ❌ not available in composable — use template refs
  }
  function listenEvents() {
    this.$on('custom', this.handleCustom)  // ❌ removed in Vue 3 — use event bus or provide/inject · external dep — pass handleCustom as param, function arg, or use another composable
    this.$off('custom')  // ❌ removed in Vue 3 — use event bus or provide/inject
    this.$once('done', () => {})  // ❌ removed in Vue 3 — use event bus or provide/inject
  }
  function accessParent() {
    return this.$parent.someValue  // ❌ not available in composable — use provide/inject
  }
  function accessChildren() {
    return this.$children.length  // ❌ removed in Vue 3 — use template refs
  }
  function getListeners() {
    return Object.keys(this.$listeners)  // ❌ removed in Vue 3 — merged into $attrs
  }
  function readAttrs() {
    return this.$attrs.class  // ⚠️ not available in composable — use useAttrs()
  }
  function renderSlot() {
    return this.$slots.default  // ⚠️ not available in composable — use useSlots()
  }
  function watchManual() {
    watch(query, (n) => console.log(n))
  }
  function watchDotted() {
    watch(() => user.value.name, (val) => {
      isLoading.value = true
    })
  }
  function watchGetter() {
    watch(() => query.value + count.value, (sum) => console.log(sum))
  }
  function watchWithOptions() {
    watch(query, (val) => { fetchResults(val) }, { deep: true })
  }
  function forceRefresh() {
    this.$forceUpdate()  // ℹ️ rarely needed in Vue 3
  }
  function legacyCallback() {
    const self = this  // ⚠️ this alias won't work — replace with direct refs
    setTimeout(function() {
      self.query = 'updated'  // ⚠️ self.x won't auto-rewrite — use direct refs
    }, 100)
  }
  function saveItem(item) {
    items.value[0] = item
  }
  function removeItem(key) {
    delete config.value[key]
  }

  watch(query, (val, oldVal) => {
    isLoading.value = true
    fetchResults(val)
  })

  fetchResults(query.value)

  onMounted(() => {
    this.$el.classList.add('loaded')  // ❌ not available in composable — use template ref on root
    this.$parent.notifyChildMounted()  // ❌ not available in composable — use provide/inject
  })

  return { items, config, query, isLoading, message, filteredItems, fullName, fetchResults, navigate, loadPage, focusInput, listenEvents, accessParent, accessChildren, getListeners, readAttrs, renderSlot, watchManual, watchDotted, watchGetter, watchWithOptions, forceRefresh, legacyCallback, saveItem, removeItem }
}
