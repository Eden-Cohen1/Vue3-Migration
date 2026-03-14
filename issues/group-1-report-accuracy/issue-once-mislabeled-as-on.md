# Bug: Report labels `this.$once` as `this.$on` — different APIs with different migration paths

## Problem

The migration report step for `useEventBus` lists `this.$on` at lines L11, L12, L13, **L18**. But L18 in the generated composable is actually `this.$once(...)`, not `this.$on(...)`. While both were removed in Vue 3, they have different semantics and require different migration approaches:

- `this.$on(event, handler)` — persistent listener, needs `bus.on()` + `bus.off()` cleanup
- `this.$once(event, handler)` — one-time listener, needs `bus.on()` + manual removal after first call, or a custom `once()` wrapper

Grouping them under the same label causes users to apply the wrong fix.

## Input mixin: `eventBusMixin.js`

```js
// Edge case: this.$on/this.$off/this.$once in matched pairs (mount/destroy cleanup).
// Vue 3 removed instance event bus — these need migration to external emitter.
export default {
  data() {
    return {
      eventHandlers: {},
      receivedEvents: [],
      isListening: false
    }
  },

  created() {
    this.registerEvents()
  },

  beforeDestroy() {
    this.cleanupEvents()
  },

  methods: {
    registerEvents() {
      // $on with various handler patterns
      this.$on('data-updated', this.handleDataUpdate)          // L23 — this.$on
      this.$on('user-action', this.handleUserAction)           // L24 — this.$on
      this.$on('error-occurred', (error) => {                  // L25 — this.$on
        this.receivedEvents.push({ type: 'error', payload: error, timestamp: Date.now() })
      })

      // $once for one-time initialization
      this.$once('initialized', () => {                        // L30 — this.$once (NOT $on!)
        this.isListening = true
        this.receivedEvents.push({ type: 'init', timestamp: Date.now() })
      })

      this.eventHandlers = {
        'data-updated': this.handleDataUpdate,
        'user-action': this.handleUserAction
      }
    },

    cleanupEvents() {
      // Matched $off for each $on
      this.$off('data-updated', this.handleDataUpdate)
      this.$off('user-action', this.handleUserAction)
      this.$off('error-occurred')

      this.isListening = false
    },

    handleDataUpdate(payload) {
      this.receivedEvents.push({ type: 'data-updated', payload, timestamp: Date.now() })
    },

    handleUserAction(action) {
      this.receivedEvents.push({ type: 'user-action', payload: action, timestamp: Date.now() })
    },

    emitEvent(name, payload) {
      this.$emit(name, payload)
    },

    clearEventLog() {
      this.receivedEvents = []
    }
  }
}
```

## Generated composable: `useEventBus.js` (relevant lines)

```js
  function registerEvents() {
    // $on with various handler patterns
    this.$on('data-updated', handleDataUpdate)  // ❌ removed in Vue 3    — L11 in composable
    this.$on('user-action', handleUserAction)  // ❌ removed in Vue 3     — L12 in composable
    this.$on('error-occurred', (error) => {  // ❌ removed in Vue 3       — L13 in composable
      receivedEvents.value.push({ type: 'error', payload: error, timestamp: Date.now() })
    })

    // $once for one-time initialization
    this.$once('initialized', () => {  // ❌ removed in Vue 3             — L18 in composable
      isListening.value = true
      receivedEvents.value.push({ type: 'init', timestamp: Date.now() })
    })
```

## Report output (what the user sees)

```
### 🔴 `useEventBus` — 2 steps

- **Step 1:** Replace `this.$emit` → [see how](#recipe-thisemit) (L44)
- **Step 2:** Replace `this.$on` → [see how](#recipe-thison) (L11, L12, L13, L18)
```

Note: Step 2 lists L18 under `this.$on`, but L18 is `this.$once`.

## What's wrong

1. `this.$once` at L18 is labeled as `this.$on` in the report step
2. The migration recipe for `this.$on` (`bus.on()` + `bus.off()` in cleanup) is incorrect for `$once`:
   - `$on` pattern: `bus.on('event', handler)` in setup + `bus.off('event', handler)` in cleanup
   - `$once` pattern: needs either `bus.on('event', handler)` with self-removal inside the handler, or a custom `once()` utility

3. The report's `#recipe-thison` section only covers `$on`/`$off`, not `$once`

## Expected behavior

The report should have a separate step (or at least a separate line) for `$once`:

```
- **Step 2:** Replace `this.$on` → [see how](#recipe-thison) (L11, L12, L13)
- **Step 3:** Replace `this.$once` → [see how](#recipe-thisonce) (L18)
```

Or at minimum, L18 should not be grouped under the `$on` label.

## Investigation

Find the detection/classification logic for `this.$on`, `this.$off`, and `this.$once`. The tool likely:
1. Uses a single regex or pattern that matches all three (`this.$on`, `this.$off`, `this.$once`)
2. Groups them all under the `$on` category in the report

The fix should:
1. Detect `this.$once` separately from `this.$on`
2. Generate a separate report step (or at least a separate label) for `$once`
3. Ideally, add a `#recipe-thisonce` section to the report with the correct migration pattern for one-time listeners
