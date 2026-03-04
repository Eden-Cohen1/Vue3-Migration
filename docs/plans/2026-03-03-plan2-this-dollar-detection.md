# Plan 2: `this.$` Detection & Rewriting

**Depends on:** Plan 1 (Warning Infrastructure)
**Estimated scope:** ~4-5 files modified

## Goal

Detect all `this.$xxx` Vue instance property usage inside mixin source code. Auto-rewrite the trivial ones. Emit specific, actionable warnings for the ones requiring manual work. This is the highest-impact improvement — it catches the most common source of silently broken composable code.

## Cases to Handle

### Auto-Rewrite (modify generated composable code)

| Pattern | Rewrite To | Additional Action |
|---------|-----------|-------------------|
| `this.$nextTick(cb)` | `nextTick(cb)` | Add `import { nextTick } from 'vue'` |
| `this.$set(obj, key, val)` | `obj[key] = val` | None (Vue 3 reactivity handles it) |
| `this.$delete(obj, key)` | `delete obj[key]` | None |

### Warn + Guidance (emit warning with specific fix instructions)

| Pattern | Warning Message | Action Required |
|---------|----------------|-----------------|
| `this.$emit(...)` | `this.$emit used — composable needs emit parameter` | `Add emit param: export function useX(emit) { ... }; Pass from component: const { ... } = useX(emit)` |
| `this.$router` | `this.$router used — needs useRouter()` | `Add const router = useRouter() and import from 'vue-router'` |
| `this.$route` | `this.$route used — needs useRoute()` | `Add const route = useRoute() and import from 'vue-router'` |
| `this.$store` | `this.$store used — needs useStore()` | `Add const store = useStore() and import from vuex/pinia` |
| `this.$refs.xxx` | `this.$refs used — needs template ref setup` | `Add const xxx = ref(null), ensure template has ref="xxx"` |
| `this.$el` | `this.$el used — no composable equivalent` | `Use template ref on root element instead` |
| `this.$parent` | `this.$parent used — avoid in composables` | `Use provide/inject or props/emit instead` |
| `this.$children` | `this.$children removed in Vue 3` | `Use template refs or provide/inject` |
| `this.$on(...)` | `Event bus ($on) removed in Vue 3` | `Use mitt, tiny-emitter, or provide/inject` |
| `this.$off(...)` | `Event bus ($off) removed in Vue 3` | Same as above |
| `this.$once(...)` | `Event bus ($once) removed in Vue 3` | Same as above |
| `this.$listeners` | `$listeners removed in Vue 3` | `Listeners merged into $attrs` |
| `this.$attrs` | `this.$attrs used — needs useAttrs()` | `Add const attrs = useAttrs() and import from 'vue'` |
| `this.$slots` | `this.$slots used — needs useSlots()` | `Add const slots = useSlots() and import from 'vue'` |
| `this.$forceUpdate()` | `$forceUpdate — rarely needed in Vue 3` | `Reactive system usually handles it; review logic` |
| `this.$watch(...)` | `$watch — use watch() from vue instead` | `import { watch } from 'vue'` |

## Implementation Steps

### Step 1: `this.$` scanner in warning_collector

File: `vue3_migration/core/warning_collector.py`

Add function `detect_this_dollar_refs(mixin_source) -> list[MigrationWarning]`:
- Use regex `\bthis\.(\$\w+)` to find all `this.$xxx` references
- Skip matches inside strings/comments (use existing `skip_non_code`)
- Map each `$xxx` to its category and create appropriate `MigrationWarning`
- Call this from `collect_mixin_warnings()`

### Step 2: Auto-rewrite trivial patterns in this_rewriter

File: `vue3_migration/transform/this_rewriter.py`

Extend `rewrite_this_refs()` — or add a new function `rewrite_this_dollar_refs(code)`:
- `this.$nextTick(` → `nextTick(`
- `this.$set(obj, key, val)` → `obj[key] = val` (regex: `this\.\$set\((\w+(?:\.\w+)*),\s*([^,]+),\s*([^)]+)\)`)
- `this.$delete(obj, key)` → `delete obj[key]` (regex: `this\.\$delete\((\w+(?:\.\w+)*),\s*([^)]+)\)`)

Return a tuple: `(rewritten_code, list[str])` where the list contains import names needed (e.g. `['nextTick']`).

### Step 3: Wire into composable generator

File: `vue3_migration/transform/composable_generator.py`

- After `rewrite_this_refs()`, also call `rewrite_this_dollar_refs()`
- Merge any additional imports into the vue imports list
- Collect warnings from `detect_this_dollar_refs()` and attach to `MixinEntry`

### Step 4: Wire into composable patcher

File: `vue3_migration/transform/composable_patcher.py`

- Same as Step 3 but for patched composables

### Step 5: Tests

File: `tests/test_this_dollar.py` (new)

Test cases:
- `this.$nextTick(fn)` → `nextTick(fn)` with import added
- `this.$set(this.items, 0, val)` → `items.value[0] = val`
- `this.$delete(this.config, 'key')` → `delete config.value['key']`
- `this.$emit('change', val)` → left as-is + warning emitted
- `this.$router.push('/home')` → left as-is + warning with useRouter guidance
- `this.$refs.input.focus()` → left as-is + warning with template ref guidance
- `this.$on('event', handler)` → left as-is + warning about Vue 3 removal
- Verify warnings appear in MixinEntry.warnings
- Verify inline comments appear in generated composable

## Files Modified

| File | Change |
|------|--------|
| `vue3_migration/core/warning_collector.py` | Add `detect_this_dollar_refs()`, wire into `collect_mixin_warnings()` |
| `vue3_migration/transform/this_rewriter.py` | Add `rewrite_this_dollar_refs()` for $nextTick, $set, $delete |
| `vue3_migration/transform/composable_generator.py` | Call dollar-ref rewriter + collect warnings |
| `vue3_migration/transform/composable_patcher.py` | Same |
| `tests/test_this_dollar.py` | **New** — all auto-rewrite + warning tests |
