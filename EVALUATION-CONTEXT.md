# Vue3-Migration Tool — Context for Test Repo Evaluation

> **What is this file?** Put this in the root of your test repo (or in `.claude/` as a CLAUDE.md).
> It gives Claude full context about how the migration tool works internally, so evaluation
> reports are precise, actionable, and map directly to fixable code locations in the tool's source.

---

## CRITICAL: Only Evaluate Changes Made by the Tool

**You must ONLY report bugs that appear in lines the tool changed.** Use `git diff` as your source of truth.

- If a composable file already existed before the tool ran and has pre-existing issues, those are **NOT tool bugs** — ignore them.
- If the tool modified a file, only evaluate the **changed lines** (the `+` lines in the diff). Pre-existing code in that file (context lines, unchanged sections) is out of scope.
- If a composable was **generated from scratch** by the tool (new file, entire content is `+` in the diff), then the entire file is in scope.
- If the tool **patched** an existing composable (added members, modified return), only the patched sections are in scope — don't report bugs in code the tool didn't touch.

**How to check:** Run `git diff` or `git diff --name-status`. For each file:
- New file (`A` status) → entire file is in scope
- Modified file (`M` status) → only the `+` lines (additions/changes) are in scope
- Unchanged file → completely out of scope, skip it

**Do NOT report:**
- Bugs in code that existed before the tool ran
- Issues in files the tool didn't touch
- Pre-existing style problems, missing features, or logic errors in unchanged code
- Problems in the original mixin files (those are inputs, not outputs)

The tool is responsible ONLY for what it changed. Everything else is someone else's problem.

---

## What the Tool Is

A Python CLI (`npx vue3-migration`) that converts Vue 2 **mixins** (Options API) into Vue 3 **composables** (Composition API) and rewires components to use them. It is **purely mechanical** — no LLM, no AI. It uses regex-based extraction and string manipulation to:

1. Parse mixin source code (data, computed, methods, watch, lifecycle hooks)
2. Generate a composable file with equivalent Vue 3 code
3. Modify components: remove mixin imports, inject `setup()` with composable destructuring

---

## How the Tool Transforms Code

The transformation is a **mechanical transliteration**. The tool extracts each section's function bodies verbatim, then rewrites `this.` references. It does NOT understand semantics or rewrite logic.

### Transformation Rules

| Vue 2 Mixin | Vue 3 Composable | Rule |
|---|---|---|
| `data() { return { x: 1 } }` | `const x = ref(1)` | Each data property → `ref()` with extracted default value |
| `computed: { foo() { return this.x } }` | `const foo = computed(() => x.value)` | Function body extracted, `this.x` → `x.value` |
| `computed: { foo: { get() {...}, set(v) {...} } }` | `const foo = computed({ get: () => {...}, set: (v) => {...} })` | Getter/setter form |
| `methods: { bar(a, b) { this.x = a + b } }` | `function bar(a, b) { x.value = a + b }` | Function body extracted, `this.x` → `x.value` |
| `watch: { x(newVal) { ... } }` | `watch(x, (newVal) => { ... })` | Handler extracted, options preserved |
| `watch: { x: { handler() {...}, deep: true } }` | `watch(x, () => {...}, { deep: true })` | Options object form |
| `mounted() { ... }` | `onMounted(() => { ... })` | Body extracted, wrapped in lifecycle call |
| `beforeDestroy() { ... }` | `onBeforeUnmount(() => { ... })` | Vue 2 → Vue 3 hook name mapping |
| `created() { ... }` | *(inlined at top of composable)* | No wrapper needed |
| `this.dataProperty` | `dataProperty.value` | Data/computed/watch members get `.value` |
| `this.methodName()` | `methodName()` | Methods are plain functions, no `.value` |
| `this.$nextTick(cb)` | `nextTick(cb)` | Auto-rewritten, import added |
| `this.$set(obj, k, v)` | `obj[k] = v` | Auto-rewritten |
| `this.$delete(obj, k)` | `delete obj[k]` | Auto-rewritten |
| `this.$emit(...)` | Left in place + warning comment | Requires manual migration |
| `this.$refs.x` | Left in place + warning comment | Requires manual migration |
| `this.$router` | Left in place + warning comment | Requires manual migration |
| `this.$el` | Left in place + warning comment | Requires manual migration |
| `this._privateProp` | `let _privateProp = null` (local variable) | Underscore-prefixed → local `let` |

### What "Mechanical Transliteration" Means

The tool copies function bodies **character-for-character** and only changes `this.` references. It should NEVER:
- Change string literals, role names, or hardcoded values
- Replace `JSON.parse(JSON.stringify(x))` with `{ ...x }` (or any other algorithm change)
- Add/remove conditional branches
- Change property names being accessed (e.g. `.hidden` → `.visible`)
- Invent new logic that wasn't in the original
- Change the data shape assumptions

**If the generated composable has different logic, string values, property names, or algorithms than the original mixin, that is ALWAYS a bug.** The tool's job is to change syntax (`this.x` → `x.value`), not semantics.

---

## Tool Architecture (for mapping bugs to source locations)

### Pipeline Overview

```
1. SCAN          → collect_all_mixin_entries()
                    Parse every .vue file, find mixins: [...], analyze each mixin

2. GENERATE      → plan_new_composables() / plan_regenerated_composables()
                    For each mixin without a composable (or with --regenerate),
                    generate a fresh composable file

3. PATCH         → plan_composable_patches()
                    For existing composables missing members/returns, patch them

4. INJECT        → plan_component_injections()
                    Modify components: remove mixin, add import, inject setup()
```

### Key Source Files (in the tool repo)

| File | What It Does |
|---|---|
| `vue3_migration/transform/composable_generator.py` | **Generates composables from mixin source.** Contains `_extract_section_body()`, `_extract_func_body()`, `_extract_func_params()`. This is where most transformation bugs originate. |
| `vue3_migration/transform/composable_patcher.py` | **Patches existing composables** — adds missing members to return, generates member declarations, removes stale comments. Contains `add_keys_to_return()`, `generate_member_declaration()`, `patch_composable()`. |
| `vue3_migration/transform/this_rewriter.py` | **Rewrites `this.x` references.** `rewrite_this_refs()` handles `.value` addition. `rewrite_this_dollar_refs()` handles `$nextTick`/`$set`/`$delete`. Protects strings, comments, regex, template literals, and function parameter lists. |
| `vue3_migration/transform/lifecycle_converter.py` | **Converts lifecycle hooks.** `extract_hook_body()` extracts hook function bodies (with exclusion zones for methods/computed/watch blocks). `convert_lifecycle_hooks()` wraps in `onMounted()` etc. |
| `vue3_migration/transform/injector.py` | **Modifies components.** `inject_setup()` creates/merges setup() function. `remove_mixin_from_array()`, `remove_import_line()`, `add_composable_import()`. |
| `vue3_migration/core/mixin_analyzer.py` | **Extracts mixin member names** (data, computed, methods, watch). `extract_mixin_members()`, `extract_lifecycle_hooks()`, `find_external_this_refs()`. |
| `vue3_migration/core/component_analyzer.py` | **Analyzes components.** `find_used_members()` scans both `<template>` and `<script>` for member references. `extract_own_members()` finds component-defined members. |
| `vue3_migration/core/composable_analyzer.py` | **Analyzes composable files.** `extract_all_identifiers()`, `extract_return_keys()` (uses LAST return to skip early exits). |
| `vue3_migration/core/js_parser.py` | **Low-level JS parsing.** `extract_brace_block()` for nested brace extraction. `skip_non_code()` for strings/comments. `extract_property_names()` for object property enumeration. |
| `vue3_migration/workflows/auto_migrate_workflow.py` | **Orchestrator.** `run()` executes the full pipeline. `plan_component_injections()` handles the component modification phase. |
| `vue3_migration/core/warning_collector.py` | **Warning system.** Detects `this.$` patterns, data/setup collisions, factory mixins, transitive mixins. Emits inline `// ⚠ MIGRATION:` comments. |
| `vue3_migration/models.py` | **Data models.** `MixinMembers`, `MemberClassification`, `MixinEntry`, `ComposableCoverage`, `MigrationStatus`. |

---

## How the Tool Determines Which Members to Include

The tool decides what goes into the composable's return and the component's `setup()` destructuring through **member classification**:

1. **Mixin members** = all names from data + computed + methods + watch sections
2. **Used members** = mixin members referenced in the component's `<template>` AND `<script>` (word-boundary regex match)
3. **Composable identifiers** = all `const/let/var/function` declarations in the composable
4. **Return keys** = members in the composable's `return { ... }` (uses LAST return statement)
5. **Component own members** = data/computed/methods/watch the component defines itself

Classification:
- **injectable**: used by component AND available in composable return → goes into `setup()` destructuring
- **truly_missing**: used by component but NOT in composable at all → **BLOCKER**, tool tries to generate it
- **truly_not_returned**: exists in composable but NOT in return → **BLOCKER**, tool adds to return
- **overridden**: missing but component defines its own version → safe to skip

---

## The Two-Pass System

### Pass 1: Composable Generation/Patching

- **New composables** (`plan_new_composables`): Generates from scratch using `composable_generator.py`
- **Existing composables** (`plan_composable_patches`): Patches using `composable_patcher.py`
  - Step 1: Add missing keys to `return { }`
  - Step 2: Generate missing member declarations (data→ref, computed→computed(), etc.)
  - Step 3: Add missing lifecycle hooks
  - Step 4: Rewrite `this.$` patterns
  - Step 5: Remove stale "NOT defined" comments
- **Regenerated composables** (`plan_regenerated_composables`, with `--regenerate` flag): Replaces existing composable entirely with fresh generation from mixin source

### Pass 2: Component Injection

- Remove mixin import line
- Add composable import
- Remove mixin from `mixins: [...]`
- Inject `setup()` with destructured composable call
- Merge into existing `setup()` if present

---

## Known Limitations (by design)

These are intentional — the tool emits warnings for them:

- `this.$emit` — left in place (composables don't have component context)
- `this.$refs` — left in place (needs template ref migration)
- `this.$el` — left in place (no direct equivalent)
- `this.$router`/`this.$route`/`this.$store` — left in place (needs `useRouter()`/`useRoute()`/store import)
- `this.$on`/`this.$off`/`this.$once` — left in place (event bus removed in Vue 3)
- `this.$parent`/`this.$children` — left in place (removed in Vue 3)
- Props, inject, provide — not migrated (different mechanism needed)
- Vuex `mapGetters`/`mapActions` spread — not handled
- `this` aliasing (`const self = this`) — not detected
- Factory function mixins (`export default function() { return { ... } }`) — detected but not transformed
- Transitive mixins (mixin A uses mixin B) — detected but members not carried forward

---

## How to Write an Effective Evaluation Report

### The Goal

Your report will be used by a developer working **in the tool's source repo** (not this test repo). They need:

1. **The exact mixin input** (original Vue 2 code) — so they can reproduce the bug
2. **The exact tool output** (what was generated) — so they can see what went wrong
3. **The expected output** (what should have been generated) — so they know the fix target
4. **Root cause hypothesis** — which tool source file/function likely has the bug

### Report Structure

```markdown
# Bug N: [Short description]

**Severity:** Critical | High | Medium | Low
**Affected file(s):** [composable/component file names]
**Likely root cause:** [tool source file and function name]

## Mixin Input (original Vue 2 code)
\`\`\`js
// The COMPLETE mixin source, or at minimum the relevant section
export default {
  data() { return { ... } },
  computed: { ... },
  methods: { ... },
  mounted() { ... }
}
\`\`\`

## Tool Output (what was generated)
\`\`\`js
// The COMPLETE generated composable, or the broken section
// Annotate the specific broken lines with // ← BUG: description
\`\`\`

## Expected Output (what it should generate)
\`\`\`js
// What a correct mechanical transliteration would produce
\`\`\`

## Root Cause Analysis
[Which tool function is likely responsible and why]
```

### Critical Rules for Evaluation

1. **Always include complete code blocks.** The tool developer does NOT have access to this test repo. Every bug report must be self-contained with full input/output/expected.

2. **Check the mixin source FIRST.** Before reporting a bug in the generated composable, read the original mixin file. The generated code should be a mechanical transliteration. If it differs, that's a bug.

3. **Distinguish tool bugs from design limitations.** If `this.$emit` is left in place with a warning comment, that's intentional (see Known Limitations above). If `this.$emit` is silently deleted or rewritten incorrectly, that's a bug.

4. **Map bugs to tool source files.** Use this mapping:
   - Wrong/missing function body → `composable_generator.py` (`_extract_func_body`, `_extract_section_body`)
   - Wrong parameters → `composable_generator.py` (`_extract_func_params`)
   - Missing `.value` or wrong `.value` → `this_rewriter.py` (`rewrite_this_refs`)
   - Lifecycle hook in wrong scope → `composable_generator.py` (assembly logic) or `lifecycle_converter.py` (`extract_hook_body`)
   - Missing lifecycle hook → `lifecycle_converter.py` or `mixin_analyzer.py` (`extract_lifecycle_hooks`)
   - Member missing from composable → `composable_generator.py` (member loop) or `mixin_analyzer.py` (`extract_mixin_members`)
   - Member missing from return → `composable_generator.py` (return assembly) or `composable_patcher.py` (`add_keys_to_return`)
   - Member missing from setup() destructuring → `injector.py` (`inject_setup`) or `auto_migrate_workflow.py` (`plan_component_injections`)
   - Template-referenced member not in setup() → `component_analyzer.py` (`find_used_members`)
   - Mixin not detected at all → `mixin_analyzer.py` (doesn't recognize the mixin pattern)
   - data/setup name collision → `auto_migrate_workflow.py` (collision detection)
   - Wrong import path → `core/file_resolver.py` or `core/composable_search.py`
   - Stale comments not cleaned → `composable_patcher.py` (`_remove_stale_comments`)
   - Wrong indentation → `composable_generator.py` (`_normalize_indentation`) or `composable_patcher.py` (`add_keys_to_return`)

5. **Verify with the actual diff.** Run `git diff` to see what the tool actually changed. The migration report may not show everything.

6. **Test with `--regenerate`.** If composables already existed from a previous tool run, they may contain bugs from an older version. Running with `--regenerate` (`-R`) replaces them entirely with fresh output from the current version. Always test with `--regenerate` before reporting composable logic bugs.

7. **Check ALL members, not just the broken ones.** When one member is wrong, check every member in that composable. Multiple bugs often cluster in the same file.

8. **Report the COMPLETE mixin, not just the broken section.** The tool processes the entire mixin file. Context matters — bugs often depend on the structure of sibling sections (e.g., lifecycle hooks getting nested inside computed because of how the sections are ordered).

### Severity Guide

| Severity | Criteria | Examples |
|---|---|---|
| **Critical** | Generated code throws at runtime | SyntaxError, ReferenceError, TypeError, lifecycle hooks in wrong scope |
| **High** | Generated code produces wrong results silently | Different algorithms, missing methods, wrong property names, lost watchers |
| **Medium** | Code works but is incomplete or needs manual fixup | Missing warnings, `this.$` causing TypeError in composable context, members not returned |
| **Low** | Cosmetic or non-functional issues | Wrong indentation, stale comments, unnecessary blank lines |

### Evaluating Component Modifications

When checking how the tool modified components:

1. **Read the `<template>` section.** Every member referenced in the template (`v-if="isOpen"`, `{{ title }}`, `@click="handleClick"`, `:data="formData"`) must be in the `setup()` return.

2. **Check `data()` for collisions.** If the component's `data()` defines a property with the same name as something returned from `setup()`, Vue 3's `data()` will shadow `setup()`. This causes the composable's value to be invisible to the template.

3. **Verify the destructuring is complete.** The `const { a, b, c } = useXxx()` must include every member the component uses from the mixin. Missing members silently resolve to `undefined`.

4. **Check that component's own members are preserved.** The tool should NOT remove data/computed/methods that the component defines itself (not from the mixin).

### Evaluating Factory Mixins

Some mixins use a factory function pattern:
```js
export default function createMixin(option) {
  return {
    data() { ... },
    methods: { ... }
  }
}
```

Components use these as `mixins: [createMixin('value')]`. The tool currently does NOT transform these — it should emit a warning. If you find a factory mixin that the tool silently ignored (no warning, no composable), that's a bug in detection.

### Evaluating Transitive Mixins

If a mixin imports and uses other mixins:
```js
import otherMixin from './otherMixin'
export default {
  mixins: [otherMixin],
  data() { ... }
}
```

The tool should either:
- Compose the sub-composables (`const { ... } = useOther()`) in the generated composable, OR
- Emit a clear warning listing the transitive members that need manual attention

If transitive members silently disappear, that's a bug.

---

## Quick Reference: Bug Patterns We've Already Found

These have been found in previous evaluations. Check if they're still present:

| Pattern | Description | Status |
|---|---|---|
| Lifecycle hooks inside `computed()` | `onMounted()` emitted inside a `computed(() => { ... })` callback instead of at composable top level | Known, may still exist |
| Methods dropped when only used by lifecycle | If a method is only called inside `mounted()` / `beforeUnmount()` (not in template/script), it may be omitted from the composable | Known |
| Template members missing from setup() | Members used only in `<template>` (not in `<script>`) may be missing from `setup()` destructuring | Known |
| Logic rewritten instead of transliterated | Composable has completely different algorithms, string values, or data shapes than the original mixin | Check if `--regenerate` fixes it |
| data/setup name collision | Component's `data()` and `setup()` both define same property name, `data()` shadows silently | Warning exists, no auto-fix |
| Factory mixins ignored | `export default function()` pattern not recognized, no composable generated, no warning | Known |
| Transitive mixin members lost | Mixin includes other mixins, their members not carried into the composable | Known |
| Stale "NOT defined" comments | Comments saying member is not defined appear right above where it IS defined | Partially fixed |
| Appended members wrong indentation | Members added by the patcher use different indentation than existing code | Known |
| `this.$` in composable body causes TypeError | `this.$emit`/`this.$el` left as code (not commented out) in composable functions where `this` is undefined | Known |

---

## What a Perfect Evaluation Report Looks Like

A perfect report lets the tool developer:
1. Read the bug description and immediately understand the problem
2. See the exact input → output → expected output
3. Know which source file and function to fix
4. Write a regression test from the provided code blocks
5. Fix the bug without needing access to the test repo

**Bad:** "The composable is wrong"
**Good:** "usePermission's `canEdit` checks `'write'` but the original mixin checks `'update'`. The tool rewrote the string literal instead of preserving it. Root cause: `composable_generator.py:_extract_func_body()` likely failed to extract the computed body, and a fallback generated new logic."

**Bad:** "Some members are missing from setup()"
**Good:** "`isOpen` is used in `<template>` (`v-if="isOpen"`) but missing from the `setup()` destructuring in ModalView.vue. The tool's `find_used_members()` in `component_analyzer.py` does scan `<template>`, so either the member name extraction failed or `plan_component_injections()` filtered it out."
