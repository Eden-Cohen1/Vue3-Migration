# Plan 4: Watch/Computed Automation + Structural Warnings

**Depends on:** Plan 1 (Warning Infrastructure), Plan 3 (Parser Fixes — for `extract_value_at`)
**Estimated scope:** ~5-6 files modified

## Goal

Convert the two biggest remaining "TODO" categories (simple watch handlers and getter/setter computed) into working code, and add detection-only warnings for all structural patterns the tool can't auto-migrate.

## Part A: Simple Watch Auto-Conversion

### Current behavior
All watch handlers produce: `// watch: name — migrate manually`

### New behavior
Auto-convert simple watch handlers; warn on complex ones.

| Watch Form | Auto-Convert? | Output |
|-----------|--------------|--------|
| `count(val, oldVal) { ... }` | Yes | `watch(count, (val, oldVal) => { ... })` |
| `count: function(val) { ... }` | Yes | `watch(count, (val) => { ... })` |
| `count: { handler(val) {...}, deep: true }` | Yes | `watch(count, (val) => { ... }, { deep: true })` |
| `count: { handler(val) {...}, immediate: true }` | Yes | `watch(count, (val) => { ... }, { immediate: true })` |
| `'nested.path': function(val) { ... }` | Warn | Quoted key — can't resolve to ref name |
| `count: 'methodName'` | Warn | String handler — needs manual conversion |
| `count: [handler1, handler2]` | Warn | Array of handlers — needs manual conversion |

### Implementation

1. **Extract watch section body** — use existing `_extract_section_body('watch')` pattern from composable_generator
2. **Parse each watch entry:**
   - Simple shorthand: `name(params) { body }` → extract name, params, body
   - Function property: `name: function(params) { body }` → same
   - Options object: `name: { handler(params) { body }, deep: true }` → extract handler + options
   - String/array forms: detect and warn
3. **Generate watch call:**
   ```javascript
   watch(name, (val, oldVal) => {
     // rewritten body
   }, { deep: true })  // options if present
   ```
4. **Add `watch` to Vue imports** when any watch is auto-converted
5. **Rewrite `this.` references** in watch handler body using existing `rewrite_this_refs`

### Files to modify
- `vue3_migration/transform/composable_generator.py` — replace the `// watch: name` TODO with actual conversion logic
- `vue3_migration/core/mixin_analyzer.py` — currently `extract_mixin_members` doesn't extract watch members (only returns `data`, `computed`, `methods`). Add `watch` extraction.
- `vue3_migration/core/warning_collector.py` — warn on complex watch forms

## Part B: Getter/Setter Computed Auto-Conversion

### Current behavior
Detected by `re.search(r'\bget\s*\(', body)` → produces `// TODO: getter/setter computed`

### New behavior
Auto-convert to Vue 3 writable computed:

```javascript
// Vue 2
computed: {
  fullName: {
    get() { return this.first + ' ' + this.last },
    set(val) { const [first, last] = val.split(' '); this.first = first; this.last = last }
  }
}

// Vue 3 (generated)
const fullName = computed({
  get: () => { return first.value + ' ' + last.value },
  set: (val) => { const [first, last] = val.split(' '); first.value = first; last.value = last }
})
```

### Implementation

1. **Detect getter/setter form** — improve detection beyond just `get\s*\(`:
   - Look for `{ get(` or `{ get:` inside the computed entry body
   - Extract both `get` and `set` bodies separately
2. **Generate writable computed:**
   ```javascript
   const name = computed({
     get: () => { rewritten_get_body },
     set: (params) => { rewritten_set_body }
   })
   ```
3. **Rewrite `this.` in both bodies** using existing rewriter
4. **Warn if `set` body is missing** — read-only computed with getter object syntax (unusual but valid)

### Files to modify
- `vue3_migration/transform/composable_generator.py` — replace TODO with auto-conversion
- `vue3_migration/transform/composable_patcher.py` — same for `generate_member_declaration`

## Part C: Structural Warnings (Detect-Only)

Add detection for patterns the tool can't auto-migrate. Each produces a specific, actionable `MigrationWarning`.

### Mixin Options Detection

Scan mixin source for these option keys and warn:

| Option Key | Warning | Guidance |
|-----------|---------|----------|
| `props` | `Mixin defines props — not migrated to composable` | `Use defineProps() in component or pass as composable params` |
| `inject` | `Mixin uses inject — not auto-migrated` | `Use inject() from 'vue' in composable` |
| `provide` | `Mixin uses provide — not auto-migrated` | `Use provide() from 'vue' in composable` |
| `filters` | `Mixin uses filters — REMOVED in Vue 3` | `Convert to methods or standalone functions` |
| `directives` | `Mixin registers local directives` | `Register in component or globally instead` |
| `components` | `Mixin registers local components` | `Move registration to component` |
| `extends` | `Mixin uses extends — complex inheritance` | `Flatten into composable manually` |
| `model` | `Mixin uses custom v-model — API changed in Vue 3` | `Use modelValue prop + update:modelValue emit` |

Implementation: Simple regex scan for `\b(props|inject|provide|...)\s*:` in mixin source, with `skip_non_code` to avoid false positives in strings/comments.

### Structural Pattern Detection

| Pattern | Detection Method | Warning |
|---------|-----------------|---------|
| **Dynamic mixins array** | `parse_mixins_array()` returns empty but `\bmixins\b` exists in source | `Dynamic mixins expression — cannot auto-analyze` |
| **Mixin factory function** | `export default function` instead of `export default {` | `Mixin factory function — cannot auto-convert` |
| **Mixin uses nested mixins** | `\bmixins\s*:` inside mixin source | `Mixin uses nested mixins — transitive members may be missed` |
| **Member name collisions** | Same member name in return of two composables for same component | `Member 'x' provided by both useA and useB — name collision` |
| **render() in mixin** | `\brender\s*\(` in mixin source | `Mixin defines render function — not supported in composable` |
| **serverPrefetch hook** | `\bserverPrefetch\b` in mixin source | `serverPrefetch not auto-converted` |
| **Vue class-component decorators** | `@Component` or `@Prop` in mixin source | `Class-component syntax not supported` |

### Files to modify
- `vue3_migration/core/warning_collector.py` — add all detection functions
- `vue3_migration/workflows/auto_migrate_workflow.py` — call name collision detection after planning

## Implementation Order

1. **Step 1:** Mixin analyzer — add watch member extraction
2. **Step 2:** Simple watch auto-conversion in composable_generator
3. **Step 3:** Getter/setter computed auto-conversion in composable_generator + composable_patcher
4. **Step 4:** All structural warning detections in warning_collector
5. **Step 5:** Name collision detection in workflow
6. **Step 6:** Tests for all new functionality

## Tests

File: `tests/test_watch_computed_structural.py` (new)

Watch tests:
- Simple shorthand watch → `watch()` call
- Function property watch → `watch()` call
- Watch with options (deep, immediate) → `watch()` with options object
- String handler watch → warning emitted
- Array handler watch → warning emitted
- Quoted key watch → warning emitted
- `this.` references rewritten in watch handler body

Computed tests:
- Getter/setter computed → `computed({ get, set })`
- Getter-only object form → `computed({ get })` + warning
- `this.` references rewritten in both get and set bodies

Structural warning tests:
- Mixin with `props:` → warning
- Mixin with `inject:` → warning
- Mixin with `filters:` → warning (with "removed" severity)
- Dynamic mixins array → warning
- Mixin factory function → warning
- Nested mixins → warning
- Member name collision → warning
- render() in mixin → warning
- serverPrefetch → warning
- @Component decorator → warning

## Files Modified

| File | Change |
|------|--------|
| `vue3_migration/core/mixin_analyzer.py` | Add watch member extraction |
| `vue3_migration/transform/composable_generator.py` | Watch auto-conversion, getter/setter computed |
| `vue3_migration/transform/composable_patcher.py` | Getter/setter computed in `generate_member_declaration` |
| `vue3_migration/core/warning_collector.py` | All structural warning detectors |
| `vue3_migration/workflows/auto_migrate_workflow.py` | Name collision detection |
| `tests/test_watch_computed_structural.py` | **New** — all tests |
