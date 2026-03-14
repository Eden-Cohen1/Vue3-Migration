# Bug: Generated composable contains invalid JavaScript (object-literal syntax inside function body)

## Problem

The tool generates a composable for `eventBusMixin` where the `handleUserAction` function body contains object-literal syntax (`'key': value,`) instead of actual function code. This is **invalid JavaScript** that will crash at runtime. The migration report does not flag this error.

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
      this.$on('data-updated', this.handleDataUpdate)
      this.$on('user-action', this.handleUserAction)
      this.$on('error-occurred', (error) => {
        this.receivedEvents.push({ type: 'error', payload: error, timestamp: Date.now() })
      })

      // $once for one-time initialization
      this.$once('initialized', () => {
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

## Generated composable: `useEventBus.js` (BROKEN)

```js
// ⚠️ 4 manual steps needed — see migration report for details
import { ref, onBeforeUnmount } from 'vue'

export function useEventBus() {
  const eventHandlers = ref({})
  const receivedEvents = ref([])
  const isListening = ref(false)

  function registerEvents() {
    // $on with various handler patterns
    this.$on('data-updated', handleDataUpdate)  // ❌ removed in Vue 3 — use event bus or provide/inject
    this.$on('user-action', handleUserAction)  // ❌ removed in Vue 3 — use event bus or provide/inject
    this.$on('error-occurred', (error) => {  // ❌ removed in Vue 3 — use event bus or provide/inject
      receivedEvents.value.push({ type: 'error', payload: error, timestamp: Date.now() })
    })

    // $once for one-time initialization
    this.$once('initialized', () => {  // ❌ removed in Vue 3 — use event bus or provide/inject
      isListening.value = true
      receivedEvents.value.push({ type: 'init', timestamp: Date.now() })
    })

    eventHandlers.value = {
      'data-updated': handleDataUpdate,
      'user-action': handleUserAction
    }
  }
  function cleanupEvents() {
    // Matched $off for each $on
    this.$off('data-updated', handleDataUpdate)  // ❌ removed in Vue 3 — use event bus or provide/inject
    this.$off('user-action', handleUserAction)  // ❌ removed in Vue 3 — use event bus or provide/inject
    this.$off('error-occurred')  // ❌ removed in Vue 3 — use event bus or provide/inject

    isListening.value = false
  }
  function handleDataUpdate(payload) {
    receivedEvents.value.push({ type: 'data-updated', payload, timestamp: Date.now() })
  }
  function handleUserAction(action) {
    'data-updated': handleDataUpdate,
    'user-action': handleUserAction
  }
  function emitEvent(name, payload) {
    this.$emit(name, payload)  // ❌ not available in composable — use defineEmits or emit param
  }
  function clearEventLog() {
    receivedEvents.value = []
  }

  registerEvents()

  onBeforeUnmount(() => {
    cleanupEvents()
  })

  return { eventHandlers, receivedEvents, isListening, registerEvents, cleanupEvents, handleDataUpdate, handleUserAction, emitEvent, clearEventLog }
}
```

## The broken code (lines 39-42)

```js
  function handleUserAction(action) {
    'data-updated': handleDataUpdate,
    'user-action': handleUserAction
  }
```

This is object-literal syntax (`'key': value,`) inside a function body. The original mixin's `handleUserAction` method was:

```js
handleUserAction(action) {
  this.receivedEvents.push({ type: 'user-action', payload: action, timestamp: Date.now() })
}
```

It appears the tool replaced the function body with content from the `eventHandlers` object assignment (`registerEvents` method's `this.eventHandlers = { ... }` block), or mixed up method bodies during transformation.

## What's wrong

1. The generated `handleUserAction` function has the wrong body — it contains object property syntax instead of the actual method body
2. The actual body (`receivedEvents.value.push(...)`) is completely lost
3. The migration report does NOT flag this as an error — it only lists steps for `this.$on`, `this.$emit` etc., completely missing that the generated code is syntactically invalid

## Expected behavior

The generated `handleUserAction` function should be:
```js
function handleUserAction(action) {
  receivedEvents.value.push({ type: 'user-action', payload: action, timestamp: Date.now() })
}
```

## Investigation

Find the code that transforms mixin `methods` into composable functions. Something is going wrong when the mixin has an object assignment inside one method (`this.eventHandlers = { 'data-updated': ..., 'user-action': ... }` in `registerEvents`) and a separate method with the same name as one of those keys (`handleUserAction`). The tool may be confusing the object keys with method names, or incorrectly splicing method bodies.

Also investigate: why doesn't the tool validate that generated composable code is syntactically valid? Consider adding a parse-check step (e.g., using `acorn.parse()`) on the generated output to catch this class of error before writing files.
