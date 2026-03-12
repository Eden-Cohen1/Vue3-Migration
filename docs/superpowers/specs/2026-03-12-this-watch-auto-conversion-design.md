# Auto-convert `this.$watch()` to Vue 3 `watch()`

## Context

The vue3-migration tool already auto-converts declarative `watch: { ... }` mixin options into Vue 3 `watch()` composable calls. However, imperative `this.$watch()` calls inside methods and lifecycle hooks are only **warned about** — developers must manually rewrite them.

This feature adds automatic conversion of `this.$watch()` calls to `watch()` from Vue 3, covering both string-key and function-expression watchers.

## Conversion Patterns

### Pattern 1 — Simple string key
```js
// Vue 2
this.$watch('query', (val) => { this.fetchResults(val) })
// Vue 3 — bare ref (matches existing generate_watch_call convention)
watch(query, (val) => { fetchResults(val) })
```

### Pattern 2 — Dotted string key
```js
// Vue 2
this.$watch('user.name', handler)
// Vue 3 — getter function (matches existing dotted-key convention)
watch(() => user.value.name, handler)
```

### Pattern 3 — Function expression getter
```js
// Vue 2
this.$watch(() => this.x + this.y, handler)
// Vue 3 — rewrite this. refs in getter
watch(() => x.value + y.value, handler)
```

### Pattern 4 — With options (3rd argument)
```js
// Vue 2
this.$watch('query', handler, { deep: true, immediate: true })
// Vue 3
watch(query, handler, { deep: true, immediate: true })
```

### Pattern 5 — Unwatch capture (passthrough)
```js
// Vue 2
const unwatch = this.$watch('query', handler)
// Vue 3 (same pattern, just works)
const unwatch = watch(query, handler)
```

### Convention: Bare ref vs getter

**Must match existing `generate_watch_call()` convention** (composable_patcher.py:496-502):
- Simple key → bare ref name: `watch(query, handler)`
- Dotted key → getter function: `watch(() => user.value.name, handler)`
- Plain member (method) → bare name without `.value`: `watch(fetchResults, handler)`

This ensures a mixin with both declarative `watch:` and imperative `this.$watch()` on the same property produces identical output.

## Architecture

### Approach: Extend `rewrite_this_dollar_refs()` in `this_rewriter.py`

This function already handles `this.$nextTick`, `this.$set`, `this.$delete` auto-rewrites. Adding `this.$watch` here means:
- **Single integration point** — the function is already called in composable generation, patching, and lifecycle conversion
- **Automatic coverage** of all migration flows (full project, single component, single mixin)
- **Reuses** existing non-code-span detection infrastructure

### Ordering Dependency

`rewrite_this_dollar_refs()` (which will now rewrite `this.$watch`) runs **after** `rewrite_this_refs()` in both code paths:
- **Generator** (`composable_generator.py:337-341`): `rewrite_this_refs` runs at ~line 310, then `rewrite_this_dollar_refs` at line 338
- **Patcher** (`composable_patcher.py:715`): `rewrite_this_refs` runs during `generate_member_declaration`, then `rewrite_this_dollar_refs` on the full content

This means `this.x` references in the handler body are already rewritten to `x.value` before the `$watch` rewrite runs. The handler (2nd arg) is passed through unchanged because its `this.` refs are already gone. **This ordering must be preserved.**

### Paren Matching & Argument Splitting

The main challenge is extracting the full `this.$watch(...)` call arguments.

**`_extract_paren_args(code, open_paren_pos)`**: Match `(` / `)` while skipping strings/comments/regex (using existing `skip_non_code` from `js_parser.py`). Returns the content between the matched parens.

**`_split_top_level_args(args_str)`**: Split at commas that are at depth 0 across **all bracket types** — `()`, `[]`, `{}`. This is critical because arrow functions may contain object literals with commas: `() => ({ key: this.x, other: this.y })`.

### Argument Parsing

Given extracted arguments from `this.$watch(first_arg, handler[, options])`:

1. **First arg is a string literal** (`'key'` or `"key"`):
   - Simple key: `'query'` → bare ref `query`
   - Dotted key: `'user.name'` → getter `() => user.value.name`
   - Plain member (method): `'fetchResults'` → bare name `fetchResults` (no `.value`)
   - Apply ref_members/plain_members awareness via the same logic as `generate_watch_call()`

2. **First arg is a function expression** (`() => this.x + this.y` or `function() { return this.x }`):
   - Rewrite `this.` references inside the expression using `rewrite_this_refs()`
   - Keep the function expression structure intact

3. **Handler (2nd arg)**: Pass through unchanged — `this.` refs already rewritten by prior pass.

4. **Options (3rd arg)**: Pass through unchanged.

### ref_members / plain_members Context

`rewrite_this_dollar_refs()` currently doesn't receive member classification info. To determine whether a string-key watch target is a ref (needs `.value`) or a plain member (method, no `.value`), we have two options:

- **Option A**: Thread `ref_members` and `plain_members` through as new parameters to `rewrite_this_dollar_refs()`
- **Option B**: Default to bare ref (no `.value` on the watch source itself — matching how `generate_watch_call` handles simple keys), since the watch source for a simple key is just the bare name regardless

Option B is simpler and matches the existing convention: `watch(query, handler)` works for both refs and computed values because Vue 3's `watch()` auto-unwraps refs passed as the first argument. **Use Option B.**

### Fallback Behavior

If the parser can't confidently extract/convert a `this.$watch(...)` call (unparseable arguments, dynamic variable as first arg, template literal, etc.), **leave it unchanged**. The existing warning still fires. No data loss.

### Warning Suppression

**Do NOT use `_RESOLVED_PATTERNS`** for suppression — that dict checks `composable_source` which may already contain `watch(` from declarative watchers, causing false suppression.

Instead: track successful `this.$watch` rewrites inside `rewrite_this_dollar_refs()`. After a successful rewrite, the `this.$watch` pattern no longer exists in the code, so `collect_mixin_warnings()` won't match it on the rewritten output. **No explicit suppression needed** — the warning naturally disappears because the pattern is gone.

## Files to Modify

### 1. `vue3_migration/transform/this_rewriter.py`
- Add `_extract_paren_args(code, open_paren_pos)` helper
- Add `_split_top_level_args(args_str)` helper — tracks depth across `()`, `[]`, `{}`
- Add `this.$watch(...)` rewrite block in `rewrite_this_dollar_refs()`:
  - Find `this.$watch(` matches (skip non-code spans)
  - Extract full arg list via `_extract_paren_args`
  - Split into individual args via `_split_top_level_args`
  - Parse first arg (string literal vs function expression)
  - Build `watch(source, handler[, options])` replacement
  - Add `"watch"` to imports (with dedup guard: `if "watch" not in imports`)
- Update docstring to list `this.$watch` as auto-rewritten

### 2. `vue3_migration/core/warning_collector.py`
- Update comment at line 62 to include `$watch` in the auto-migrated list:
  ```python
  # $nextTick, $set, $delete, $watch are auto-migrated by rewrite_this_dollar_refs()
  ```
- Do NOT modify `_RESOLVED_PATTERNS` — suppression happens naturally

### 3. `tests/test_this_dollar.py`
New test cases:
- `test_rewrite_watch_string_key` — `this.$watch('query', handler)` → `watch(query, handler)`
- `test_rewrite_watch_dotted_key` — `this.$watch('user.name', handler)` → `watch(() => user.value.name, handler)`
- `test_rewrite_watch_function_getter` — `this.$watch(() => this.x + this.y, handler)` → `watch(() => x.value + y.value, handler)`
- `test_rewrite_watch_with_options` — 3rd arg preserved
- `test_rewrite_watch_unwatch_capture` — `const unwatch = this.$watch(...)` → `const unwatch = watch(...)`
- `test_rewrite_watch_plain_member_key` — method name, no `.value`: `watch(fetchResults, handler)`
- `test_rewrite_watch_in_string_not_rewritten` — inside quotes, no rewrite
- `test_rewrite_watch_unparseable_fallback` — leaves unparseable calls unchanged
- `test_rewrite_watch_adds_import` — `"watch"` in returned imports
- `test_rewrite_watch_import_not_duplicated` — multiple `this.$watch` calls produce single `"watch"` import

### 4. `tests/fixtures/dummy_project/src/mixins/kitchenSinkMixin.js`
- Expand existing `this.$watch` usage to cover more patterns (dotted key, function getter, options arg)

### Implicitly affected (no changes needed):
- `vue3_migration/transform/composable_generator.py` (lines 337-341) — already calls `rewrite_this_dollar_refs()` and merges returned imports into `vue_imports`
- `vue3_migration/transform/composable_patcher.py` (line 715) — already calls `rewrite_this_dollar_refs()` on full content

## Verification

1. **Unit tests**: `pytest tests/test_this_dollar.py -v` — all new and existing tests pass
2. **Watch structural tests**: `pytest tests/test_watch_computed_structural.py -v` — existing declarative watch tests unaffected
3. **Integration**: `python -m vue3_migration status tests/fixtures/dummy_project` — `this.$watch` warning count should decrease
4. **Full migration dry run**: `python -m vue3_migration all tests/fixtures/dummy_project` — generated composables contain `watch()` calls where `this.$watch` was used
5. **Full test suite**: `pytest tests/ -v` — no regressions
