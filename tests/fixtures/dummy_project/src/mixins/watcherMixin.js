// Issue 4: this.$watch with ALL variants — comment on line 1 contains "this.$watch"
// which previously caused the report to say "mixin L1" instead of the real lines.
export default {
  data() {
    return {
      watchedValue: null,
      unwatchFns: [],
      watchLog: [],
      nested: {
        deep: {
          value: ''
        }
      }
    }
  },

  created() {
    this.setupWatchers()
  },

  beforeUnmount() {
    this.teardownWatchers()
  },

  methods: {
    setupWatchers() {
      // String path watcher
      const unwatch1 = this.$watch('watchedValue', function (newVal, oldVal) {
        this.watchLog.push({ field: 'watchedValue', newVal, oldVal })
      })
      this.unwatchFns.push(unwatch1)

      // Deep watcher with string path
      const unwatch2 = this.$watch('nested.deep.value', {
        handler(newVal) {
          this.watchLog.push({ field: 'nested.deep.value', newVal })
        },
        deep: true,
        immediate: true
      })
      this.unwatchFns.push(unwatch2)

      // Watcher with function expression
      const unwatch3 = this.$watch(
        function () { return this.watchedValue + this.nested.deep.value },
        function (newVal) {
          this.watchLog.push({ field: 'computed_expression', newVal })
        }
      )
      this.unwatchFns.push(unwatch3)
    },

    teardownWatchers() {
      this.unwatchFns.forEach(unwatch => unwatch())
      this.unwatchFns = []
    },

    clearWatchLog() {
      this.watchLog = []
    }
  }
}
