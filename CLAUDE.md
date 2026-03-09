# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

vue3-migration automatically migrates Vue 2 mixins to Vue 3 composables. It's an npm package that delegates to Python for all logic. The tool analyzes Vue components, generates/patches composables, and rewrites component files — all in a preview-then-apply workflow.

## Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_composable_generator.py -v

# Run a single test by name
pytest tests/test_composable_generator.py -k "test_name" -v

# Run the tool (interactive menu)
python -m vue3_migration

# Run specific workflows (must pass project path AFTER the command)
python -m vue3_migration all              # full project migration (interactive)
python -m vue3_migration component <path> # single component
python -m vue3_migration mixin <name>     # retire one mixin
python -m vue3_migration status           # read-only report

# Test against the dummy project fixture
python -m vue3_migration all tests/fixtures/dummy_project
python -m vue3_migration status tests/fixtures/dummy_project
python -m vue3_migration component tests/fixtures/dummy_project/src/components/SearchTest.vue
python -m vue3_migration mixin searchMixin tests/fixtures/dummy_project
```

**Important:** The CLI does NOT accept `auto`, positional project paths without a command, or `--project` flags. Always use `<command> [project_path]` format.

No linter is configured. Uses `uv` for Python package management. Tests use real file I/O against `tests/fixtures/dummy_project/` (no mocks).

## Architecture

### Dual Entry Point
`bin/cli.js` (Node wrapper) → `python -m vue3_migration` → `cli.py:main()`

### Four Layers
- **CLI** (`cli.py`) — User interaction, menus, confirmation prompts
- **Workflows** (`workflows/`) — Orchestration; decides what to do
- **Core + Transform** (`core/`, `transform/`) — Parsing and code generation
- **Models** (`models.py`) — All shared dataclasses and enums

### The 3-Phase Pipeline (`auto_migrate_workflow.py`)

All migration modes (full-project, single-component, single-mixin) use the same pipeline:

1. **Analyze** — Parse `.vue` files, extract mixin members, find/match composables, classify gaps via `MemberClassification`, compute `MigrationStatus` (READY / BLOCKED_NO_COMPOSABLE / BLOCKED_MISSING_MEMBERS / BLOCKED_NOT_RETURNED), collect warnings
2. **Prepare Composables** — Generate new composables from mixin source OR patch existing ones (add missing members/return keys). Patches are deduplicated across components sharing a mixin.
3. **Inject into Components** — Re-classify against updated composables, remove mixin imports, add composable imports, create/extend `setup()` with destructured calls

Result is a `MigrationPlan` of `FileChange` objects shown as a diff before writing.

### No AST Library — Hand-Rolled Parsing

All JS parsing in `core/js_parser.py` is string manipulation: skip strings/comments/regex, extract brace blocks, extract property names. Zero external parsing dependencies.

### Key Model: `MemberClassification`

The central decision-maker. Gap analysis between what a component uses from a mixin vs. what the composable provides. Fields: `missing`, `truly_missing`, `not_returned`, `truly_not_returned`, `overridden`, `injectable`. The `is_ready` property gates whether auto-migration proceeds.

### Transform Patterns

| Mixin construct | Generated composable code |
|---|---|
| `data() { return { x: 0 } }` | `const x = ref(0)` |
| `computed: { y() {...} }` | `const y = computed(() => ...)` |
| `methods: { doIt() {...} }` | `function doIt() {...}` |
| `created() {...}` | Inlined at function top |
| `mounted() {...}` | `onMounted(() => {...})` |

`this_rewriter.py` handles `this.x` → `x.value` (refs/computed) or `x()` (methods), plus Vue 2 API rewrites (`this.$set` → direct assignment, `this.$nextTick` → `nextTick`).

### Warning & Confidence System

`warning_collector.py` detects 20+ patterns that can't auto-migrate (e.g., `this.$emit`, `this.$refs`, `this.$router`). Generated composables get a confidence rating (HIGH/MEDIUM/LOW) and inline warning comments.

## Test Fixtures

`tests/fixtures/dummy_project/` contains a full Vue project (35+ components, 15+ mixins) used for integration testing. `conftest.py` provides `dummy_project`, `mixins_dir`, `composables_dir`, `components_dir` fixtures.
