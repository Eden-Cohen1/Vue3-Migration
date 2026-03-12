// Manual test mixin — every this.$watch pattern in one file
// Each method is annotated with the task it exercises

export default {
  data() {
    return {
      query: '',         // Task 1: simple watch target
      count: 0,          // Task 5: unwatch capture target
      user: { name: '' } // Task 2: dotted watch target (nested)
    }
  },
  computed: {
    total() {            // used in template
      return this.count * 2
    }
  },
  methods: {
    // Task 1: simple string key watch
    startWatchingQuery() {
      this.$watch('query', (val) => {
        console.log('query changed:', val)
      })
    },

    // Task 2: dotted string key watch
    startWatchingUserName() {
      this.$watch('user.name', (val) => {
        console.log('user name changed:', val)
      })
    },

    // Task 4: watch with options (3rd arg)
    startDeepWatch() {
      this.$watch('query', (val) => {
        this.count = val.length
      }, { deep: true, immediate: true })
    },

    // Task 5: unwatch capture — assignment must be preserved
    startWatchWithCleanup() {
      const unwatch = this.$watch('count', (n) => {
        console.log('count is', n)
      })
      return unwatch
    },

    // Task 6: unparseable — dynamic variable as first arg (should NOT convert)
    startDynamicWatch(propName) {
      this.$watch(propName, (val) => {
        console.log(val)
      })
    },

    fetchResults(val) {
      console.log('fetching', val)
    }
  },

  mounted() {
    // Task 3: function getter watch
    this.$watch(() => this.query + this.count, (sum) => {
      this.fetchResults(sum)
    })
  }
}
