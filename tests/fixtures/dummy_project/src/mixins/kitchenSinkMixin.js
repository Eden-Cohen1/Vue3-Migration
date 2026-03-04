// Demo mixin: exercises every warning and edge case
export default {
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
    fetchResults(q) {
      this.$emit('search', q)
      this.$nextTick(() => {
        console.log('DOM updated')
      })
    },
    navigate(path) {
      this.$router.push(path)
    },
    saveItem(item) {
      this.$set(this.items, 0, item)
      this.$store.dispatch('save', item)
    },
    removeItem(key) {
      this.$delete(this.config, key)
    },
    focusInput() {
      this.$refs.searchInput.focus()
    },
    legacyBroadcast() {
      const self = this
      this.$on('legacy-event', function handler(data) {
        self.message = data
      })
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
