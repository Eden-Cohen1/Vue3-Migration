# Bug: Generated composable passes array of string handlers to `watch()` — invalid in Vue 3

## Problem

When the input mixin uses `this.$watch('prop', ['handler1', 'handler2', 'handler3'])` (an undocumented but valid Vue 2 feature — array of method name strings), the tool converts it to `watch(ref, ['handler1', 'handler2', 'handler3'])`. This is **not valid** in Vue 3's Composition API — `watch()` does not accept arrays of string handlers.

## Input mixin: `watchArrayMixin.js`

```js
// Edge case: this.$watch with array of handlers (Vue 2 feature) and handler
// as a string method name. Tests edge cases of $watch API.
export default {
  data() {
    return {
      watchTarget: '',
      changeLog: [],
      notificationQueue: []
    }
  },

  created() {
    // Array of handlers — undocumented but valid Vue 2 feature
    this.$watch('watchTarget', [
      'handleChange',
      'logChange',
      'notifyChange'
    ])
  },

  methods: {
    handleChange(newVal, oldVal) {
      if (newVal !== oldVal) {
        this.changeLog.push({
          type: 'change',
          from: oldVal,
          to: newVal,
          timestamp: Date.now()
        })
      }
    },

    logChange(newVal) {
      console.log(`[WatchArray] watchTarget changed to: ${newVal}`)
    },

    notifyChange(newVal) {
      this.notificationQueue.push({
        message: `Value updated to "${newVal}"`,
        read: false
      })
    },

    clearLog() {
      this.changeLog = []
    },

    clearNotifications() {
      this.notificationQueue = []
    }
  }
}
```

## Generated composable: `useWatchArray.js` (BROKEN at L36-40)

```js
// ⚠️ 1 manual step needed — see migration report for details
import { ref, watch } from 'vue'

export function useWatchArray() {
  const watchTarget = ref('')
  const changeLog = ref([])
  const notificationQueue = ref([])

  function handleChange(newVal, oldVal) {
    if (newVal !== oldVal) {
      changeLog.value.push({
        type: 'change',
        from: oldVal,
        to: newVal,
        timestamp: Date.now()
      })
    }
  }
  function logChange(newVal) {
    console.log(`[WatchArray] watchTarget changed to: ${newVal}`)
  }
  function notifyChange(newVal) {
    notificationQueue.value.push({
      message: `Value updated to "${newVal}"`,
      read: false
    })
  }
  function clearLog() {
    changeLog.value = []
  }
  function clearNotifications() {
    notificationQueue.value = []
  }

  // Array of handlers — undocumented but valid Vue 2 feature
  watch(watchTarget, [
    'handleChange',
    'logChange',
    'notifyChange'
  ])

  return { watchTarget, changeLog, notificationQueue, handleChange, logChange, notifyChange, clearLog, clearNotifications }
}
```

## The broken code (lines 36-40)

**Generated (invalid):**
```js
watch(watchTarget, [
  'handleChange',
  'logChange',
  'notifyChange'
])
```

**Original mixin:**
```js
this.$watch('watchTarget', [
  'handleChange',
  'logChange',
  'notifyChange'
])
```

**Should be:**
```js
watch(watchTarget, (newVal, oldVal) => {
  handleChange(newVal, oldVal)
  logChange(newVal, oldVal)
  notifyChange(newVal, oldVal)
})
```

In Vue 2, `this.$watch` could accept an array of method name strings, and it would call each method when the value changed. Vue 3's `watch()` does not support this. The tool needs to:
1. Resolve each string to its function reference
2. Wrap them in a single callback that calls all handlers

## Report output

```
### 🟡 `useWatchArray` — 1 step

- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L1])
```

The report step doesn't mention that the generated composable contains an invalid array-of-strings pattern. It also points to "mixin L1" which is the export statement, not the actual `this.$watch` call at mixin L14.

## Investigation

Find the `this.$watch` transformation logic. The tool handles `this.$watch('prop', callback)` correctly when the callback is a function, but when it encounters an **array argument**, it passes the array through unchanged. The fix should:

1. Detect when the second argument to `this.$watch` is an array
2. Resolve each string in the array to its corresponding function (from the mixin's methods)
3. Generate a single wrapper callback that invokes all handlers in order

Look for where `this.$watch` calls are parsed and transformed — the array case is likely not handled at all.
