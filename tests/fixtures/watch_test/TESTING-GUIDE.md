# Manual Test Guide: this.$watch Auto-Conversion

## How to run

From the project root:

```bash
python -c "
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_generator import generate_composable_from_mixin
source = open('tests/fixtures/watch_test/src/mixins/watchMixin.js').read()
members = MixinMembers(
    data=['query', 'count', 'user'],
    computed=['total'],
    methods=['startWatchingQuery', 'startWatchingUserName', 'startDeepWatch',
             'startWatchWithCleanup', 'startDynamicWatch', 'fetchResults'],
)
print(generate_composable_from_mixin(source, 'watchMixin', members, ['mounted']))
"
```

## Task 1: Simple string key

**Look at:** `startWatchingQuery()` body
**Expect:**
- `watch(query, (val) => {` — bare ref name, no `.value`, no getter wrapper
- `this.$watch` is gone

## Task 2: Dotted string key

**Look at:** `startWatchingUserName()` body
**Expect:**
- `watch(() => user.value.name, (val) => {` — getter with `.value` on root
- NOT `watch('user.name', ...)` — string key must not survive

## Task 3: Function getter

**Look at:** `onMounted(...)` block
**Expect:**
- `watch(() => query.value + count.value, (sum) => {`
- Both `this.query` and `this.count` rewritten to `.value` form
- `fetchResults(sum)` — method call has no `.value`

## Task 4: Options (3rd arg)

**Look at:** `startDeepWatch()` body
**Expect:**
- `watch(query, (val) => {` ... `}, { deep: true, immediate: true })`
- Options object preserved verbatim as 3rd argument
- `this.count` in handler rewritten to `count.value`

## Task 5: Unwatch capture

**Look at:** `startWatchWithCleanup()` body
**Expect:**
- `const unwatch = watch(count, (n) => {` — assignment preserved
- `return unwatch` — still returns the unwatch function

## Task 6: Unparseable fallback

**Look at:** `startDynamicWatch()` body
**Expect:**
- `this.$watch(propName, ...)` — left unchanged (dynamic variable, not a string literal)
- Inline warning comment: `not available in composable`
- The function should NOT crash or produce `watch(propName, ...)`

## Task 7: Import deduplication

**Look at:** First line of generated composable
**Expect:**
- `import { ref, computed, onMounted, watch } from 'vue'`
- `watch` appears exactly once despite 5+ conversions

## Quick Checklist

- [ ] Task 1: `watch(query,` in startWatchingQuery
- [ ] Task 2: `watch(() => user.value.name,` in startWatchingUserName
- [ ] Task 3: `watch(() => query.value + count.value,` in onMounted
- [ ] Task 4: `{ deep: true, immediate: true }` preserved as 3rd arg
- [ ] Task 5: `const unwatch = watch(count,` — assignment kept
- [ ] Task 6: `this.$watch(propName,` left unchanged with warning
- [ ] Task 7: Single `watch` in import line
