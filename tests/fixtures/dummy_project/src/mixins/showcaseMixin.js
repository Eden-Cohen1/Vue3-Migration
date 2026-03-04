// Showcase mixin: triggers every automated transformation from Plans 1-4
export default {
  data() {
    return {
      items: [1, 2, 3],
      config: { theme: 'dark', lang: 'en' },
      query: '',
      count: 0,
      isVisible: true,
    }
  },
  computed: {
    total() {
      return this.items.length + this.count
    },
    fullLabel: {
      get() {
        return this.query + ' (' + this.count + ')'
      },
      set(val) {
        this.query = val.split(' (')[0]
      },
    },
  },
  watch: {
    query(val, oldVal) {
      this.count = val.length
      this.search(val)
    },
    items: {
      handler(newItems) {
        this.count = newItems.length
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    search(term) {
      this.$nextTick(() => {
        console.log('searching', term)
      })
      this.$emit('search-changed', term)
    },
    addItem(item) {
      this.$set(this.items, this.items.length, item)
    },
    removeKey(key) {
      this.$delete(this.config, key)
    },
    async fetchData() {
      const page = this.$route.params.page
      const data = await this.$store.dispatch('load', { page })
      this.items = data
    },
    navigate(path) {
      this.$router.push(path)
    },
    legacyHandler() {
      const self = this
      setTimeout(function () {
        self.count++
      }, 100)
    },
    readBracket() {
      return this['count'] + this['query']
    },
  },
  created() {
    this.fetchData()
  },
  mounted() {
    console.log('mounted with', this.items.length, 'items')
  },
  beforeDestroy() {
    console.log('cleaning up')
  },
}
