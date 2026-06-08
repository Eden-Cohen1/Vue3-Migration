# Architecture

A developer deep-dive into how `vue3-migration` turns Vue 2 mixins into Vue 3
composables. For the user-facing overview, see the [README](../README.md). For
the *why* behind the design — hard-won lessons, invariants, and direction — see
[DEVELOPMENT.md](DEVELOPMENT.md).

---

## 1. Philosophy

Four ideas shape every module:

1. **Preview, then apply.** Nothing touches disk until the user confirms. Every
   analysis and transform produces plain data (`FileChange` objects); writing is
   a separate, final step. This makes the whole engine pure and testable.
2. **No AST.** All JavaScript/TypeScript parsing is hand-rolled string scanning
   (`core/js_parser.py`). No `@babel/*`, no `esprima`, no version chasing. The
   trade-off — less precision, more edge cases — is accepted deliberately and is
   the source of most historical bugs (see DEVELOPMENT.md).
3. **Never leave a component worse than you found it.** If the tool can't safely
   replace a mixin, it skips the change and emits a warning rather than removing
   a mixin with nothing to take its place.
4. **Single source of truth.** Shared decisions (member classification, kind
   labels, private-prop detection) live in one place so the generator, the
   warning system, and the report can't drift apart.

---

## 2. Layers & dependency direction

```
bin/cli.js  (Node wrapper)
   └─ python -m vue3_migration  →  cli.py:main()
        │
        ▼
   ┌──────────────┐   decides WHAT to do
   │  workflows/  │   auto_migrate · component · mixin
   └──────┬───────┘
          │ calls
   ┌──────▼───────┐   parsing + code generation
   │ core/  transform/ │
   └──────┬───────┘
          │ produces
   ┌──────▼───────┐   shared dataclasses & enums
   │  models.py   │   (depended on by everything, depends on nothing)
   └──────────────┘

   reporting/  renders models → diffs, markdown, terminal output
```

Dependencies point **downward only**. `models.py` imports nothing internal;
`core/` and `transform/` import `models` and `js_parser`; `workflows/` orchestrate
everything; `reporting/` reads models but never mutates them.

| Layer | Package | Responsibility |
|-------|---------|----------------|
| CLI | `cli.py`, `__main__.py` | Menu, subcommands, confirmation prompts, file writing |
| Workflows | `workflows/` | Orchestration — what to analyze, patch, inject |
| Core | `core/` | Parsing, classification, search, file resolution |
| Transform | `transform/` | Code generation and rewriting |
| Models | `models.py` | All shared dataclasses and enums |
| Reporting | `reporting/` | Diffs, markdown reports, terminal formatting |

---

## 3. The data model (`models.py`)

Everything flows through a handful of dataclasses. The two that drive control
flow are **`MemberClassification`** (the gap analysis) and **`MigrationStatus`**
(the readiness verdict).

### Enums

- **`MigrationStatus`** — `READY`, `BLOCKED_NO_COMPOSABLE`,
  `BLOCKED_MISSING_MEMBERS`, `BLOCKED_NOT_RETURNED`, `FORCE_UNBLOCKED`.
- **`ConfidenceLevel`** — `HIGH` / `MEDIUM` / `LOW` for a generated composable.

### Module constant

- **`MEMBER_KIND_LABELS`** — maps a mixin section to the Vue 3 construct it
  becomes (`data → ref`, `computed → computed`, `methods → function`). Used in
  kind-mismatch messages. Centralized here so every call site agrees.

### Core dataclasses

- **`MixinMembers`** — the four mixin sections: `data`, `computed`, `methods`,
  `watch` (lists of names). `all_names` returns the union (excluding dotted
  watch keys).
- **`ComposableCoverage`** — what an existing composable provides: `fn_name`,
  `import_path`, `declared_identifiers`, `return_keys`, and `identifier_kinds`
  (`name → ref|computed|function|unknown`). Its method **`classify_members()`**
  produces a `MemberClassification`.
- **`MemberClassification`** — the central gap analysis between *what a component
  uses from a mixin* and *what the composable provides*:
  - `missing` / `truly_missing` — not declared in the composable (the second
    excludes members the component overrides itself).
  - `not_returned` / `truly_not_returned` — declared but absent from the
    composable's `return {…}`.
  - `overridden` / `overridden_not_returned` — covered by the component's own
    definitions, so safe to skip.
  - `injectable` — the members to actually destructure in `setup()`.
  - `kind_mismatched` — `(name, mixin_kind, comp_kind)` tuples (e.g. a method in
    the mixin but a `ref` in the composable).
  - **`is_ready`** — `not truly_missing and not truly_not_returned`. This single
    property gates whether auto-migration proceeds.
- **`MemberDivergence`** — a member the composable already implements but whose
  body differs from the mixin's (see §8).
- **`MigrationWarning`** — one detected problem: `category`, `message`,
  `action_required`, `severity` (`error|warning|info`), and source location
  (`source_file`, `source_lines`) for clickable report links.
- **`MixinEntry`** — the complete analysis of *one mixin as used by one
  component*: its members, lifecycle hooks, `used_members`, the matched
  `composable`, the `classification`, the `status`, `warnings`, `external_deps`,
  and `divergences`. **`compute_status()`** derives the `MigrationStatus`.
- **`FileChange`** — `file_path` + `original_content` + `new_content` +
  human-readable `changes`. `has_changes` is the gate for writing.
- **`MigrationPlan`** — `composable_changes` + `component_changes` +
  `entries_by_component`. The single object the CLI renders and then applies.
- **`MigrationConfig`** — project root, skip dirs, extensions, indent, and flags
  (`dry_run`, `auto_confirm`, `regenerate`).

---

## 4. The three-phase pipeline (`workflows/auto_migrate_workflow.py`)

All migration modes funnel through this module. The pipeline never writes files;
it returns a `MigrationPlan`.

### Phase 1 — Analyze · `collect_all_mixin_entries()`

For every `.vue` file (skipping `node_modules`, `dist`, `.git`, `__pycache__`):

1. Parse imports and the `mixins: […]` array (`core/component_analyzer.py`).
2. Extract the component's own members (override detection).
3. For each mixin, `_analyze_mixin_silent()`:
   - Resolve the import to a file (`core/file_resolver.py`).
   - Extract mixin members and lifecycle hooks (`core/mixin_analyzer.py`).
   - Find which members the component actually uses (`find_used_members`).
   - Find external `this.X` references and assigned private props.
   - Search for a matching composable (`core/composable_search.py`).
   - If found: build `ComposableCoverage`, `classify_members()`, and run
     **divergence detection**.
   - Collect warnings, then suppress those the composable already resolves.
   - `entry.compute_status()`.

Output: `list[tuple[Path, list[MixinEntry]]]` — components with processable mixins.

### Phase 2 — Prepare composables

- **`plan_composable_patches()`** — for `BLOCKED_MISSING_MEMBERS` /
  `BLOCKED_NOT_RETURNED`: add the missing declarations and return keys, plus any
  lifecycle hooks. Patches are **deduplicated** across components that share a
  composable.
- **`plan_new_composables()`** — for `BLOCKED_NO_COMPOSABLE`: generate a fresh
  composable via `transform/composable_generator.py`. In scoped (single-component)
  mode it computes the transitive closure of used members so unused helpers stay
  private.
- **`plan_regenerated_composables()`** — `--regenerate`: rebuild from scratch.

### Phase 3 — Inject · `plan_component_injections()`

Re-classify each component against the *updated* composables, then:

1. Detect name collisions across composables and against the component's `data()`
   and existing `setup()` identifiers.
2. Remove the mixin import and its entry in `mixins: […]`.
3. Add the composable import.
4. Create or **merge into** an existing `setup()`, destructuring only the
   injectable members.
5. For mixins that can't be injected (lifecycle-only with no matching hook, all
   members overridden, no usage), **skip removal and emit a warning** instead.

### Entry points

- **`run(project_root, config)`** — full project.
- **`run_scoped(project_root, config, component_path=…, mixin_stem=…)`** — one
  component or one mixin.

---

## 5. The three entry flows

| Mode | CLI | Calls | Scope |
|------|-----|-------|-------|
| Full project | `vue3-migration all` | `run()` | Every component, batch |
| One component | `vue3-migration component <path>` | `run_scoped(component_path=…)` | One `.vue` file |
| One mixin | `vue3-migration mixin <name>` | `run_scoped(mixin_stem=…)` | One mixin everywhere |

`workflows/component_workflow.py` and `workflows/mixin_workflow.py` add the
interactive layer (composable search prompts, audit reports) but converge on the
same `run_scoped()` pipeline, so all three modes produce identical transforms —
guaranteed by `tests/test_cross_flow_consistency.py`.

---

## 6. Parsing internals (`core/js_parser.py`)

The foundation everything else stands on. Strategy: **scan character by
character, skipping anything that isn't code.**

- **`skip_non_code(source, pos) → (new_pos, did_skip)`** — skip a string,
  comment, or regex literal starting at `pos`. The workhorse: most false
  positives in this tool's history came from *not* routing a scan through this.
- **`skip_string` / `skip_regex_literal` / `is_regex_start`** — the primitives
  `skip_non_code` composes. `is_regex_start` disambiguates `/` as division vs.
  regex by inspecting the preceding token.
- **`extract_brace_block(source, open_pos) → str`** — return the content between
  matching `{ }`, tracking depth and skipping braces inside strings/comments.
- **`extract_value_at(source, pos) → str`** — extract a full JS expression value
  (delimited by a top-level `,` or `}`).
- **`extract_property_names(object_body) → list[str]`** — top-level keys of an
  object literal, via an expect-key state machine that ignores identifiers inside
  method bodies.
- **`extract_declaration_names(body) → set[str]`** — `const`/`let`/`var`,
  destructuring, and `function` declarations.
- **`strip_comments(source) → str`** — remove comments while preserving strings
  and regex.

> These functions are string-based, so TypeScript type syntax (`: Type`, `as T`,
> `<Generic>`, `this?.x`, `import type`) defeats some of them. Those gaps are
> pinned as `xfail` tests in `tests/test_typescript_failures.py`.

---

## 7. The transform layer (`transform/`)

| Module | Transforms |
|--------|-----------|
| `composable_generator.py` | A whole mixin → a new `useXxx()` composable |
| `composable_patcher.py` | Adds missing members/returns to an existing composable |
| `this_rewriter.py` | `this.x` → `x.value`/`x`; `this.$*` auto-rewrites |
| `lifecycle_converter.py` | Vue 2 hooks → `onMounted(…)` etc. |
| `injector.py` | Edits the component: imports, `mixins: []`, `setup()` |

### Generation map

| Mixin construct | Generated code |
|-----------------|----------------|
| `data() { return { x: 0 } }` | `const x = ref(0)` |
| `computed: { y() {…} }` | `const y = computed(() => …)` |
| `computed: { y: { get, set } }` | `const y = computed({ get, set })` |
| `methods: { doIt() {…} }` | `function doIt() {…}` |
| `watch: { x(v) {…} }` | `watch(x, (v) => {…})` |
| `created() {…}` | inlined at the top of the function |
| `mounted() {…}` | `onMounted(() => {…})` |
| `beforeDestroy` / `destroyed` | `onBeforeUnmount` / `onUnmounted` |

### `this_rewriter.py` — the rewrite rules

- `rewrite_this_refs(code, ref_members, plain_members)` — `this.ref` →
  `ref.value`, `this.method` → `method`. Skips strings, comments, regex, and
  function parameter lists; *does* descend into template-literal `${…}`.
- `rewrite_this_dollar_refs(code)` — auto-rewrites `this.$nextTick` → `nextTick`,
  `this.$set` → direct assignment, `this.$delete` → `delete`, and
  `this.$watch(…)` → `watch(…)`. Returns the set of `vue` imports it needs.
- `rewrite_this_i18n_refs(code)` — `this.$t(…)` → `t(…)` (with `useI18n()`).

> **Critical ordering:** `rewrite_this_refs` must run *before*
> `rewrite_this_dollar_refs`. By the time the `$watch` rewrite runs, the handler
> body's `this.x` refs are already `x.value`, so the handler passes through
> untouched. Both the generator and the patcher preserve this order.

---

## 8. Warnings, confidence & divergence

### Warning collector (`core/warning_collector.py`)

`collect_mixin_warnings()` scans mixin source for 20+ patterns that can't
auto-migrate — `this.$emit`, `this.$refs`, `this.$router`, `this.$store`, i18n,
`this.$options`, factory functions, nested mixins, render functions, this-aliasing,
and external `this.X` dependencies. Each becomes a `MigrationWarning` with a
severity and an `action_required` hint.

Two suppressors keep noise down:

- **`suppress_resolved_warnings()`** — drop a warning the composable already
  handles (e.g. it imports `useRouter` for a `this.$router` warning).
- **`suppress_covered_member_warnings()`** — drop warnings whose source lines sit
  inside a member the composable fully replaces.

> Auto-rewritten patterns (`$nextTick`, `$set`, `$delete`, `$watch`) need *no*
> explicit suppression: once rewritten, the pattern is gone from the output, so
> the detector simply doesn't match it.

### Confidence (`compute_confidence`)

`HIGH` = no remaining `this.$`, no TODOs, no warnings · `MEDIUM` = TODOs/warnings
but no `this.$` · `LOW` = remaining `this.$` or an `error`-severity warning.

### Divergence detection (`core/divergence_detector.py`)

When a composable *already* implements a member, the tool verifies the logic
matches. The trick: **re-generate and diff.** It runs the mixin member back
through `generate_member_declaration()` (which encodes every Vue 2→3 transform
the tool knows), normalizes both sides, and diffs. Any remaining difference is a
genuine divergence — syntax-only differences (`this.x` vs `x.value`) cancel out
automatically. Results land in `MixinEntry.divergences` and render as collapsible
tables in the report.

---

## 9. Reporting (`reporting/`)

- **`diff.py`** — unified diffs per file and the `migration-diff-<timestamp>.md`
  report written after applying.
- **`markdown.py`** — the human-readable reports: per-component status, mixin
  audit, project status, and the tiered **action plan** with clickable
  `file:line` links. (This is the largest module; it owns all report layout.)
- **`terminal.py`** — ANSI color/style helpers.

---

## 10. Extending the tool

| To add… | Do this |
|---------|---------|
| A new `this.$x` warning | Append a tuple to `_THIS_DOLLAR_PATTERNS` in `warning_collector.py`; add a suppression rule if it's auto-resolvable. |
| A new auto-rewrite | Add the rule to `rewrite_this_dollar_refs` (or a sibling) in `this_rewriter.py`, return any needed `vue` import, and keep it *after* `rewrite_this_refs`. |
| A new lifecycle hook | Extend the maps in `lifecycle_converter.py` and `mixin_analyzer.py`. |
| A new member kind | Update `MEMBER_KIND_LABELS` and `classify_identifier_kind`. |

Whenever a change affects both code generation *and* warnings/classification,
route both through one shared helper so they can't diverge (see
`find_internal_private_props` for the canonical example).

---

## 11. Testing

Tests run against the real fixture project at `tests/fixtures/dummy_project/`
(35+ components, 15+ mixins) with **no mocks** — real file I/O. `conftest.py`
exposes `dummy_project`, `mixins_dir`, `composables_dir`, `components_dir`.

- `pytest tests/` — full suite (1000+ tests; known parser gaps are `xfail`).
- `pytest tests/test_cross_flow_consistency.py` — proves the three modes agree.
- `pytest tests/test_idempotency.py` — proves a second run is a no-op.

See [DEVELOPMENT.md](DEVELOPMENT.md) for the conventions behind these and the
`xfail` policy.
