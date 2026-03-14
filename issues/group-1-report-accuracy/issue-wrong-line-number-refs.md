# Bug: Report references "mixin L1" for `this.$watch` but actual usage is on different lines

## Problem

The migration report generates steps for `this.$watch` migration that reference **"mixin L1"** as the location of the issue. But L1 in both affected mixin files is just the comment or export statement — the actual `this.$watch` calls are on completely different lines. This sends users to the wrong location.

## Affected composables

- `useWatcher` — report says "mixin L1", actual `this.$watch` calls at L28, L34, L44, L48
- `useWatchArray` — report says "mixin L1", actual `this.$watch` call at L14

## Report output (what the user sees)

```
### 🟡 `useWatcher` — 1 step

- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L1])
```

```
### 🟡 `useWatchArray` — 1 step

- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L1])
```

## Input mixin: `watcherMixin.js`

```js
// Edge case: this.$watch with ALL variants — string path, deep option, immediate option,    ← L1 (report points here)
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
      const unwatch1 = this.$watch('watchedValue', function (newVal, oldVal) {       // ← L28 (actual)
        this.watchLog.push({ field: 'watchedValue', newVal, oldVal })
      })
      this.unwatchFns.push(unwatch1)

      // Deep watcher with string path
      const unwatch2 = this.$watch('nested.deep.value', {                            // ← L34 (actual)
        handler(newVal) {
          this.watchLog.push({ field: 'nested.deep.value', newVal })
        },
        deep: true,
        immediate: true
      })
      this.unwatchFns.push(unwatch2)

      // Handler as method name string
      const unwatch3 = this.$watch('watchedValue', 'onWatchedValueChange')           // ← L44 (actual)
      this.unwatchFns.push(unwatch3)

      // Watcher with function expression
      const unwatch4 = this.$watch(                                                  // ← L48 (actual)
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

## Input mixin: `watchArrayMixin.js`

```js
// Edge case: this.$watch with array of handlers (Vue 2 feature) and handler    ← L1 (report points here)
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
    this.$watch('watchTarget', [                                                  // ← L14 (actual)
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

## What's wrong

The report's line number references for `this.$watch` steps always say "mixin L1" regardless of where the actual `this.$watch` calls are. This is likely a fallback/default when the tool can't determine the correct line, or it's pointing to the file start instead of the specific line.

For comparison, other steps in the report correctly reference specific lines:
- `useTheme`: "this.$el" at L52, L53 ← correct
- `useAudit`: "this.$store" at L21 ← correct
- `useBookmark`: "this.$emit" at L49, L58 ← correct

So the line-number resolution works for `this.$emit`, `this.$refs`, etc., but fails specifically for `this.$watch`.

## Expected behavior

```
### 🟡 `useWatcher` — 1 step
- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L28], [mixin L34], [mixin L44], [mixin L48])

### 🟡 `useWatchArray` — 1 step
- **Step 1:** Replace `this.$watch` → [see how](#recipe-thiswatch) ([mixin L14])
```

## Investigation

Find the code that generates line number references for report steps. For most Vue API patterns (`this.$emit`, `this.$refs`, etc.), the tool correctly locates the line number in the source mixin. But for `this.$watch`, it falls back to L1. Look for:

1. Where line numbers are resolved for different pattern types
2. Whether `this.$watch` uses a different detection path than other `this.$xxx` patterns
3. Whether the line number is being set to a default value (1 or 0) when the detection logic doesn't find a match

The fix should use the same line-resolution approach that works for `this.$emit` and others.
