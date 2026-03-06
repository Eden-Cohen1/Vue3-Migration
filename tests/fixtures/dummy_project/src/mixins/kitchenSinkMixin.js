// Kitchen-sink mixin: triggers every possible warning category
import nestedHelper from './nestedHelper'

export default {
  mixins: [nestedHelper],

  props: {
    initialCount: { type: Number, default: 0 }
  },

  inject: ['theme'],

  provide() {
    return { sink: this }
  },

  filters: {
    uppercase(val) { return val.toUpperCase() }
  },

  directives: {
    focus: { mounted(el) { el.focus() } }
  },

  model: {
    prop: 'checked',
    event: 'change'
  },

  data() {
    return {
      items: [1, 2, 3],
      config: { theme: 'dark', lang: 'en' },
      query: '',
      isLoading: false,
      message: 'hello, world',
    }
  },
  computed: {
    filteredItems() {
      return this.items.filter(i => i > 0)
    },
    fullName: {
      get() {
        return this.query + ' suffix'
      },
      set(val) {
        this.query = val.replace(' suffix', '')
      },
    },
  },
  watch: {
    query(val, oldVal) {
      this.isLoading = true
      this.fetchResults(val)
    },
  },
  methods: {
    // --- errors: will crash at runtime ---
    fetchResults(q) {
      this.$emit('search', q)
      this.$nextTick(() => {
        console.log('DOM updated')
      })
    },
    navigate(path) {
      this.$router.push(path)
    },
    loadPage() {
      const id = this.$route.params.id
      this.$store.dispatch('load', { id })
    },
    focusInput() {
      this.$refs.searchInput.focus()
    },
    listenEvents() {
      this.$on('custom', this.handleCustom)
      this.$off('custom')
      this.$once('done', () => {})
    },
    accessParent() {
      return this.$parent.someValue
    },
    accessChildren() {
      return this.$children.length
    },
    getListeners() {
      return Object.keys(this.$listeners)
    },
    // --- warnings: has drop-in replacement ---
    readAttrs() {
      return this.$attrs.class
    },
    renderSlot() {
      return this.$slots.default
    },
    watchManual() {
      this.$watch('query', (n) => console.log(n))
    },
    // --- info ---
    forceRefresh() {
      this.$forceUpdate()
    },
    // --- this-aliasing ---
    legacyCallback() {
      const self = this
      setTimeout(function() {
        self.query = 'updated'
      }, 100)
    },
    // --- auto-migrated (no warning, just transformed) ---
    saveItem(item) {
      this.$set(this.items, 0, item)
    },
    removeItem(key) {
      this.$delete(this.config, key)
    },
  },
  created() {
    this.fetchResults(this.query)
  },
  mounted() {
    this.$el.classList.add('loaded')
    this.$parent.notifyChildMounted()
  },
}
