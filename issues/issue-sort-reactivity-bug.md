# Bug: Generated composable uses plain `let` instead of `ref()` for reactive state — report step doesn't mention it

## Problem

When migrating a factory-function mixin (`createSortMixin(defaultKey)`), the tool generates a composable where `sortKey` is declared as `let sortKey = defaultKey` instead of `const sortKey = ref(defaultKey)`. This breaks reactivity — `sortKey` won't trigger re-renders when it changes. The generated composable even has a comment acknowledging the bug, but the migration report's step only mentions the factory function pattern and doesn't warn about the reactivity issue.

## Input mixin: `sortMixin.js` (factory function pattern)

```js
export default function createSortMixin(defaultKey = 'name') {
  return {
    data() {
      return {
        sortKey: defaultKey,
        sortOrder: 'asc',
        multiSort: [],
        sortHistory: []
      }
    },

    computed: {
      sortIndicator() {
        return this.sortOrder === 'asc' ? '▲' : '▼'
      },

      isSorted() {
        return !!this.sortKey
      }
    },

    methods: {
      toggleSort(key) {
        if (this.sortKey === key) {
          this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc'
        } else {
          this.sortHistory.push(this.sortKey)
          this.sortKey = key
          this.sortOrder = 'asc'
        }
      },

      clearSort() {
        this.sortKey = defaultKey
        this.sortOrder = 'asc'
        this.multiSort = []
        this.sortHistory = []
      },

      addSortLevel(key) {
        const existing = this.multiSort.find((s) => s.key === key)
        if (existing) {
          existing.order = existing.order === 'asc' ? 'desc' : 'asc'
        } else {
          this.multiSort.push({ key, order: 'asc' })
        }
      }
    }
  }
}
```

## Generated composable: `useSort.js` (BROKEN reactivity)

```js
// Edge case: sortKey is declared as a plain `let` instead of ref().
// This means it won't be reactive when used in templates. Tests type mismatch
// detection — the composable has the member but it's not properly reactive.
import { ref, computed } from 'vue'

export function useSort(defaultKey = 'name') {
  // BUG: sortKey is a plain let, not ref() — won't be reactive
  let sortKey = defaultKey                           // ← WRONG: should be ref(defaultKey)
  const sortOrder = ref('asc')
  const multiSort = ref([])
  const sortHistory = ref([])

  const sortIndicator = computed(() => {
    return sortOrder.value === 'asc' ? '▲' : '▼'
  })

  const isSorted = computed(() => {
    return sortKey !== ''                             // ← won't react to changes
  })

  function toggleSort(key) {
    if (sortKey === key) {
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey = key                                  // ← assignment won't trigger reactivity
      sortOrder.value = 'asc'
    }
    sortHistory.value.push({ key: sortKey, order: sortOrder.value })
  }

  function clearSort() {
    sortKey = ''                                     // ← assignment won't trigger reactivity
    sortOrder.value = 'asc'
    multiSort.value = []
  }

  function addSortLevel(key, order = 'asc') {
    multiSort.value.push({ key, order })
  }

  return {
    sortKey,                                         // ← returning a plain string, not a ref
    sortOrder,
    multiSort,
    sortHistory,
    sortIndicator,
    isSorted,
    toggleSort,
    clearSort,
    addSortLevel
  }
}
```

## Report output (what the user sees)

```
### 🟡 `useSort` — 1 step

- **Step 1:** Replace `structural:factory-function` → Create composable with matching parameters (defaultKey = 'name') ([mixin L1])

- ℹ️ No component imports 'sortMixin'. This mixin file can be safely deleted.
```

## What's wrong

1. **Reactivity bug**: `sortKey` is a plain `let` — not a `ref()`. Any template binding like `{{ sortKey }}` or computed referencing `sortKey` won't update when `toggleSort()` or `clearSort()` is called.
2. **Report doesn't warn**: The step only mentions the factory-function pattern. It says nothing about `sortKey` being non-reactive.
3. **Return value is broken**: `return { sortKey }` returns the initial string value, not a reactive reference. Destructuring `const { sortKey } = useSort()` gives a frozen snapshot.

## Expected generated code

```js
export function useSort(defaultKey = 'name') {
  const sortKey = ref(defaultKey)                    // ← ref() for reactivity
  const sortOrder = ref('asc')
  const multiSort = ref([])
  const sortHistory = ref([])

  const sortIndicator = computed(() => {
    return sortOrder.value === 'asc' ? '▲' : '▼'
  })

  const isSorted = computed(() => {
    return sortKey.value !== ''                       // ← .value access
  })

  function toggleSort(key) {
    if (sortKey.value === key) {                      // ← .value access
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey.value = key                            // ← .value assignment
      sortOrder.value = 'asc'
    }
    sortHistory.value.push({ key: sortKey.value, order: sortOrder.value })
  }

  function clearSort() {
    sortKey.value = defaultKey                        // ← .value assignment
    sortOrder.value = 'asc'
    multiSort.value = []
  }

  // ...
  return { sortKey, sortOrder, multiSort, sortHistory, sortIndicator, isSorted, toggleSort, clearSort, addSortLevel }
}
```

## Investigation

Find the code that transforms mixin `data()` properties into composable `ref()` declarations. For most mixins, this works correctly (e.g., `sortOrder` becomes `ref('asc')`). But `sortKey` is declared as `let sortKey = defaultKey` instead.

The likely cause: when the data property's initial value comes from a **function parameter** (e.g., `sortKey: defaultKey` where `defaultKey` is the factory function's argument), the tool may treat it differently than literal values. It might be skipping the `ref()` wrapper because it sees a variable reference instead of a literal.

Check:
1. The data-to-ref transformation logic — does it handle cases where the initial value is a variable/parameter?
2. Whether factory-function mixin parameters are resolved differently during the `data()` extraction phase
3. The `this.sortKey = ...` → `sortKey = ...` rewriting — does it add `.value` access when the target was declared as `let` instead of `ref()`?
