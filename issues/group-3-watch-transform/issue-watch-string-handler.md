# Bug: Generated composable passes string method name to `watch()` — invalid in Vue 3

## Problem

When the input mixin uses `this.$watch('prop', 'methodName')` (passing a string method name as the handler), the tool converts it to `watch(ref, 'methodName')`. This is **not valid** in Vue 3's Composition API — `watch()` requires a function callback, not a string.

## Input mixin: `watcherMixin.js`

```js
// Edge case: this.$watch with ALL variants — string path, deep option, immediate option,
// handler as method name string, array of handlers, and returns unwatch function.
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

      // Handler as method name string
      const unwatch3 = this.$watch('watchedValue', 'onWatchedValueChange')
      this.unwatchFns.push(unwatch3)

      // Watcher with function expression
      const unwatch4 = this.$watch(
        function () { return this.watchedValue + this.nested.deep.value },
        function (newVal) {
          this.watchLog.push({ field: 'computed_expression', newVal })
        }
      )
      this.unwatchFns.push(unwatch4)
    },

    teardownWatchers() {
      this.unwatchFns.forEach(unwatch => unwatch())
      this.unwatchFns = []
    },

    onWatchedValueChange(newVal, oldVal) {
      this.watchLog.push({ field: 'watchedValue_handler', newVal, oldVal })
    },

    clearWatchLog() {
      this.watchLog = []
    }
  }
}
```

## Generated composable: `useWatcher.js` (BROKEN at L32)

```js
// ⚠️ 1 manual step needed — see migration report for details
import { ref, onBeforeUnmount, watch } from 'vue'

export function useWatcher() {
  const watchedValue = ref(null)
  const unwatchFns = ref([])
  const watchLog = ref([])
  const nested = ref({
        deep: {
          value: ''
        }
      })

  function setupWatchers() {
    // String path watcher
    const unwatch1 = watch(watchedValue, function (newVal, oldVal) {
      watchLog.value.push({ field: 'watchedValue', newVal, oldVal })
    })
    unwatchFns.value.push(unwatch1)

    // Deep watcher with string path
    const unwatch2 = watch(() => nested.value.deep.value, {
      handler(newVal) {
        watchLog.value.push({ field: 'nested.deep.value', newVal })
      },
      deep: true,
      immediate: true
    })
    unwatchFns.value.push(unwatch2)

    // Handler as method name string
    const unwatch3 = watch(watchedValue, 'onWatchedValueChange')  // ← INVALID: string handler
    unwatchFns.value.push(unwatch3)

    // Watcher with function expression
    const unwatch4 = watch(function () { return watchedValue.value + nested.value.deep.value }, function (newVal) {
        watchLog.value.push({ field: 'computed_expression', newVal })
      })
    unwatchFns.value.push(unwatch4)
  }
  function teardownWatchers() {
    unwatchFns.value.forEach(unwatch => unwatch())
    unwatchFns.value = []
  }
  function onWatchedValueChange(newVal, oldVal) {
    watchLog.value.push({ field: 'watchedValue_handler', newVal, oldVal })
  }
  function clearWatchLog() {
    watchLog.value = []
  }

  setupWatchers()

  onBeforeUnmount(() => {
    teardownWatchers()
  })

  return { watchedValue, unwatchFns, watchLog, nested, setupWatchers, teardownWatchers, onWatchedValueChange, clearWatchLog }
}
```

## The broken code (line 32)

**Generated (invalid):**
```js
const unwatch3 = watch(watchedValue, 'onWatchedValueChange')
```

**Original mixin:**
```js
const unwatch3 = this.$watch('watchedValue', 'onWatchedValueChange')
```

**Should be:**
```js
const unwatch3 = watch(watchedValue, onWatchedValueChange)
```

In Vue 2, `this.$watch('prop', 'methodName')` resolves the string to `this.methodName` at runtime. In Vue 3 Composition API, `watch()` does NOT accept string handlers — it requires a direct function reference. The tool needs to resolve the string `'onWatchedValueChange'` to the actual function `onWatchedValueChange` during transformation.

## Report output

```
### 🟡 `useWatcher` — 1 step

- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L1])
```

The report step doesn't mention that the generated composable contains an invalid string handler pattern. The step only points to "mixin L1" which is just the export statement (see also: issue-wrong-line-number-refs.md).

## Investigation

Find the `this.$watch` transformation logic. The tool correctly converts `this.$watch('prop', callback)` to `watch(ref, callback)` when the handler is a function — but when the handler is a **string** (`'methodName'`), it passes the string through unchanged. The fix should detect string handler arguments and resolve them to function references:

- `this.$watch('watchedValue', 'onWatchedValueChange')` → `watch(watchedValue, onWatchedValueChange)`

The tool should look up the string in the mixin's `methods` to confirm the function exists, then emit the direct reference.
