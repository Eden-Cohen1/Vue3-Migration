# Architecture

This document explains how the vue3-migration tool works internally — its layers, data flow, parsing approach, and key design decisions. If you just want to use the tool, the [README](README.md) is enough. This is for understanding the code itself.

## Project Structure

```
vue3-migration/
  bin/
    cli.js                          # Node.js wrapper (finds Python, delegates)
  vue3_migration/                   # Python package (the actual engine)
    __init__.py
    __main__.py                     # python -m vue3_migration entry point
    cli.py                          # Interactive menu, argument parsing
    models.py                       # Dataclasses and enums shared across all layers
    core/                           # Parsing and analysis
      js_parser.py                  # Low-level JS lexer (strings, comments, braces)
      component_analyzer.py         # Parse .vue component script blocks
      mixin_analyzer.py             # Extract mixin members and lifecycle hooks
      composable_analyzer.py        # Inspect existing composable files
      composable_search.py          # Match mixin names to composable files
      file_resolver.py              # Resolve import paths (@/, relative, bare)
      file_utils.py                 # File I/O helpers (CRLF normalization)
      warning_collector.py          # Detect patterns that can't be auto-migrated
    transform/                      # Code generation and modification
      composable_generator.py       # Generate new composables from mixins
      composable_patcher.py         # Patch existing composables (add missing members)
      injector.py                   # Modify component files (imports, setup())
      lifecycle_converter.py        # Convert Vue 2 hooks to Composition API
      this_rewriter.py              # Rewrite this.x references
    workflows/                      # High-level orchestration
      auto_migrate_workflow.py      # Full project migration (the main brain)
      component_workflow.py         # Single component migration
      mixin_workflow.py             # Single mixin retirement
    reporting/                      # Output formatting
      diff.py                       # Unified diff generation and report writing
      markdown.py                   # Status report generation
      terminal.py                   # ANSI colors and formatting
  tests/
    fixtures/dummy_project/         # Real Vue project used for integration tests
    test_*.py                       # 30+ test files
```

## The Dual Entry Point

The tool ships as an npm package but runs Python internally. This is because npm is the natural distribution channel for Vue developers, while Python handles the text processing.

```
npx vue3-migration [args]
  --> bin/cli.js
        Finds Python on PATH (python3, python, py)
        Sets PYTHONPATH to package root
        Spawns: python -m vue3_migration [args]
  --> vue3_migration/__main__.py --> cli.py:main()
```

`bin/cli.js` is ~30 lines. It just finds Python and delegates. All logic is in Python.

## The 4 Layers

Data flows down through four layers:

```
CLI (cli.py)                    User interaction, menus, confirmation
  |
Workflows (workflows/)         Orchestration — decides WHAT to do
  |
Core + Transform (core/, transform/)   The actual work — parsing, generation
  |
Models (models.py)              Shared data structures
```

### Models — The Shared Language

Everything communicates through dataclasses in `models.py`. These are the key ones:

**`MixinMembers`** — What a mixin contains:
- `data`: property names from `data() { return {...} }`
- `computed`: computed property names
- `methods`: method names
- `watch`: watched property names

**`ComposableCoverage`** — What an existing composable provides:
- `fn_name`: the exported function name (e.g., `useAuth`)
- `declared_identifiers`: names with actual `const`/`let`/`function` declarations
- `return_keys`: what the composable exports in its return statement
- `classify_members(used, own)`: compares component needs against composable coverage

**`MemberClassification`** — The gap analysis. This is the core abstraction:

```
Component uses members:    [A, B, C, D]
Composable declares:       [A, B]       --> C, D are "missing"
Composable returns:        [A]          --> B is "not_returned"
Component defines its own: [C]          --> C is "overridden" (safe to skip)

Result:
  truly_missing:       [D]    -- blocker, composable needs patching
  truly_not_returned:  [B]    -- blocker, needs adding to return
  overridden:          [C]    -- safe, component's version wins
  injectable:          [A]    -- good to go, will be destructured in setup()
```

A mixin is `READY` only when `truly_missing` and `truly_not_returned` are both empty.

**`MigrationStatus`** — The verdict for each mixin:
- `READY` — composable covers everything, proceed with injection
- `BLOCKED_NO_COMPOSABLE` — no matching composable found, generate one
- `BLOCKED_MISSING_MEMBERS` — composable exists but lacks members, patch it
- `BLOCKED_NOT_RETURNED` — members exist but aren't in the return statement, patch it

**`FileChange`** — A planned edit: original content + new content + human-readable change descriptions. No file is written until the user confirms.

**`MigrationPlan`** — A collection of `FileChange` objects (composable changes + component changes). The entire migration is computed as a plan, shown as a diff, then applied.

### Core — Parsing Without an AST

All JavaScript parsing is hand-rolled. There's no Babel, no acorn, no AST library. Instead, `js_parser.py` provides lexer primitives that every other parser builds on:

- `skip_string(src, pos)` — skips `'...'`, `"..."`, `` `...` `` with escape handling
- `skip_non_code(src, pos)` — skips comments (`//`, `/* */`), strings, and regex literals
- `extract_brace_block(src, start)` — finds the matching `}` for a `{`, respecting nesting
- `extract_property_names(src)` — extracts keys from an object literal at depth 0

To extract mixin members, the code: (1) finds `data()` with regex, (2) uses `extract_brace_block()` to grab the return object, (3) uses `extract_property_names()` to list the keys. Same pattern for `computed:`, `methods:`, `watch:`.

**`component_analyzer.py`** — Parses `.vue` files:
- `parse_imports()` — returns `{"selectionMixin": "../mixins/selectionMixin"}`
- `parse_mixins_array()` — returns `["selectionMixin", "authMixin"]`
- `find_used_members()` — scans both `<script>` and `<template>` for member references
- `extract_own_members()` — finds what the component defines itself (for override detection)

**`mixin_analyzer.py`** — Parses mixin `.js` files:
- `extract_mixin_members()` — returns `{data: [...], computed: [...], methods: [...], watch: [...]}`
- `extract_lifecycle_hooks()` — returns `["created", "mounted", "beforeDestroy"]`
- `find_external_this_refs()` — finds `this.X` where X is NOT a member of this mixin (external dependencies)

**`composable_analyzer.py`** — Inspects existing composable files:
- `extract_return_keys()` — what the composable exports
- `extract_declared_identifiers()` — what it actually declares (distinguishes "declared" from "just returned")

**`composable_search.py`** — Matches mixins to composables by name convention:
- `authMixin` looks for `useAuth.js` / `useAuth.ts`
- Searches all `composables/` directories first, then falls back to project-wide search
- Two-phase: exact stem match, then fuzzy substring match

**`file_resolver.py`** — Resolves import paths to disk locations:
- `@/mixins/authMixin` resolves to `src/mixins/authMixin.js`
- Relative paths resolved against the importing file
- `compute_import_path()` generates `@/composables/useAuth` for composable imports

**`warning_collector.py`** — Detects patterns the tool can't auto-migrate. It scans mixin source for `this.$emit`, `this.$refs`, `this.$router`, `this.$store`, `this.$on`/`$off`, `this.$parent`, `this.$children`, and more. Each detection becomes a `MigrationWarning` with a category, message, severity, and actionable instruction. Warnings are injected as comments in generated composables.

### Transform — Code Generation

**`composable_generator.py`** — Creates a new composable file from a mixin:

| Mixin pattern | Generated composable |
|---|---|
| `data() { return { x: 0 } }` | `const x = ref(0)` |
| `computed: { y() { return this.x } }` | `const y = computed(() => x.value)` |
| `methods: { doIt() { ... } }` | `function doIt() { ... }` |
| `created() { this.init() }` | Inlined at top of function body |
| `mounted() { ... }` | `onMounted(() => { ... })` |

Also copies non-Vue imports (adjusting paths), adds a confidence header (`HIGH`/`MEDIUM`/`LOW`), and injects warning comments.

**`composable_patcher.py`** — Patches an existing composable that's incomplete:
- `BLOCKED_MISSING_MEMBERS`: generates declarations for missing members and inserts them before the return statement
- `BLOCKED_NOT_RETURNED`: adds missing keys to the return statement
- Idempotent — running it twice produces the same output

**`this_rewriter.py`** — Rewrites `this.` references for composable context:
- `this.dataField` becomes `dataField.value` (refs need `.value`)
- `this.computedProp` becomes `computedProp.value`
- `this.someMethod()` becomes `someMethod()` (plain functions, no `.value`)
- `this.$nextTick(cb)` becomes `nextTick(cb)` (auto-imports from `'vue'`)
- `this.$set(obj, k, v)` becomes `obj[k] = v`
- `this.$delete(obj, k)` becomes `delete obj[k]`
- Skips rewrites inside strings, comments, regex, and template literals

**`lifecycle_converter.py`** — Converts Vue 2 lifecycle hooks:
- `created`/`beforeCreate` are inlined directly (no wrapper needed in setup)
- `mounted` becomes `onMounted(() => { ... })`
- `beforeDestroy` becomes `onBeforeUnmount(() => { ... })`
- Returns `(inline_lines, wrapped_lines)` — inline goes at function top, wrapped at bottom

**`injector.py`** — Modifies the component `.vue` file:
- `remove_import_line()` — deletes the mixin import
- `remove_mixin_from_array()` — removes from `mixins: [...]`, cleans up empty array
- `add_composable_import()` — inserts the composable import
- `add_vue_import()` — merges into existing `import { ... } from 'vue'`
- `inject_setup()` — creates or extends `setup()` with `const { a, b } = useComposable()` and return statement

### Workflows — The Orchestrators

**`auto_migrate_workflow.py`** is the main brain. It runs three phases:

**Phase 1: Analyze** (`collect_all_mixin_entries`)
- Walk every `.vue` file in the project
- Parse imports and mixins array
- For each mixin: resolve the file, extract members, find used members, search for composable, classify members, compute status, collect warnings
- Output: `Dict[component_path, List[MixinEntry]]`

**Phase 2: Prepare composables** (`plan_composable_patches` + `plan_new_composables`)
- `BLOCKED_MISSING_MEMBERS` / `BLOCKED_NOT_RETURNED`: patch the composable
- `BLOCKED_NO_COMPOSABLE`: generate a new composable from the mixin
- Deduplication: if two components share a mixin, patches are merged
- Output: `List[FileChange]` for composable files

**Phase 3: Inject into components** (`plan_component_injections`)
- Re-read composables (they may have been patched in Phase 2)
- Re-classify members against updated composables
- Remove mixin imports and mixins array entries
- Add composable imports
- Inject `setup()` with destructured calls
- Output: `List[FileChange]` for component files

**`component_workflow.py`** and **`mixin_workflow.py`** are scoped variants. They use the same core analysis and transform functions but limit scope to a single component or a single mixin respectively.

### CLI — User Interface

`cli.py` provides four modes:

1. **Full project** (`vue3-migration all`) — `auto_migrate_workflow.run()`
2. **Pick a component** (`vue3-migration component <path>`) — `component_workflow`
3. **Pick a mixin** (`vue3-migration mixin <name>`) — `mixin_workflow`
4. **Project status** (`vue3-migration status`) — read-only report via `reporting/markdown.py`

After computing a `MigrationPlan`, the CLI shows a unified diff (via `reporting/diff.py`), asks for `y/n` confirmation, writes files if confirmed, and saves a `migration-diff-<timestamp>.md` report.

## The Warning and Confidence System

`warning_collector.py` detects patterns that can't be auto-migrated:

| Pattern | Severity | Why |
|---|---|---|
| `this.$emit(...)` | error | Composables can't emit component events |
| `this.$refs` | error | Need template refs instead |
| `this.$router` / `this.$route` | error | Must use `useRouter()` / `useRoute()` |
| `this.$store` | error | Must import store directly |
| `this.$on` / `$off` / `$once` | error | Removed in Vue 3 |
| `this.$parent` / `$children` | error | Anti-pattern in Vue 3 |
| External `this.X` deps | warning | Member from another mixin or the component |

Warnings are injected as inline comments in generated composables with specific action instructions.

**Confidence scoring** rates generated composables:
- **HIGH** — No remaining `this.`, no TODOs, no warnings
- **MEDIUM** — Has TODOs or warnings but no remaining `this.`
- **LOW** — Still has `this.$` references or structural issues

## End-to-End Data Flow

```
npx vue3-migration all
  |
  v
cli.py:main() --> MigrationConfig
  |
  v
auto_migrate_workflow.run(project_root, config)
  |
  |-- Phase 1: collect_all_mixin_entries()
  |     For each .vue file:
  |       component_analyzer --> imports + mixins array
  |       mixin_analyzer     --> members + hooks + external deps
  |       composable_search  --> find matching useXxx.js
  |       composable_analyzer --> coverage check
  |       classify_members() --> MemberClassification
  |       compute_status()   --> READY / BLOCKED_*
  |       warning_collector  --> MigrationWarning[]
  |     Result: Dict[Path, List[MixinEntry]]
  |
  |-- Phase 2: plan_composable_patches() + plan_new_composables()
  |     BLOCKED entries --> composable_patcher / composable_generator
  |     Result: List[FileChange] for composables
  |
  |-- Phase 3: plan_component_injections()
  |     Re-classify against patched composables
  |     READY entries --> injector (remove mixin, add composable, inject setup)
  |     Result: List[FileChange] for components
  |
  v
MigrationPlan
  |
  v
cli.py: show diff --> confirm --> write files --> save report
```

## Testing Strategy

The test suite has 30 test files with ~9,500 lines, organized bottom-up:

- **Unit tests** for each module (parsing, rewriting, generation, patching, injection)
- **Integration tests** against a real fixture project at `tests/fixtures/dummy_project/` with 35+ Vue components and 15+ mixins
- **Cross-flow consistency tests** — verify that full-project, single-component, and single-mixin flows produce identical output for the same mixin
- **Idempotency tests** — running the tool twice produces the same result

Tests use actual file I/O against fixtures rather than mocks, making them closer to real-world behavior.

## Key Design Decisions

1. **No AST library.** All parsing is hand-rolled string manipulation via `js_parser.py`. This keeps dependencies at zero but means parsing is regex + brace-counting, not a full parse tree.

2. **Classification-driven.** `MemberClassification` is the central decision point. Everything flows from "what does the component need vs. what does the composable provide."

3. **Patch before inject.** Composables are fixed first (Phase 2), then components are updated (Phase 3). This ensures components always reference working composables.

4. **Three scopes, same core.** Full-project, single-component, and single-mixin workflows all use the same analysis and transform functions, just scoped differently.

5. **Plan-then-apply.** `FileChange` objects are the boundary between "what should change" and "actually writing files." This enables diff preview, dry-run mode, and the safety confirmation flow.
