# vue3-migration

A CLI tool that migrates Vue 2 mixins to Vue 3 composables.

## Requirements

- Node.js >= 14
- Python >= 3.9

## Installation

```bash
npm install -D vue3-migration
```

## Usage

Run from the root of your Vue project:

```bash
npx vue3-migration
```

This opens an interactive menu with four options:

| # | Option | Description |
|---|--------|-------------|
| 1 | **Full project** | Migrate every component at once. Auto-patches and generates composables as needed. Shows a per-file change summary and requires confirmation before writing. |
| 2 | **Pick a component** | Choose one component from a list. Migrate only that file. Safe for large projects — low blast radius, easy to test and review. |
| 3 | **Pick a mixin** | Fully retire one mixin. Patches/generates its composable and updates every component that uses it. |
| 4 | **Project status** | Read-only. Generates a detailed markdown report of what's migrated, what's ready, and what's blocked. No files are changed. |

### Direct commands

```bash
npx vue3-migration all                                # Migrate entire project
npx vue3-migration component src/components/Foo.vue   # Migrate one component
npx vue3-migration mixin authMixin                    # Retire one mixin
npx vue3-migration status                             # Generate status report
```

### Output files

Every migration writes a `migration-diff-<timestamp>.md` with a full before/after diff of every changed file.

`npx vue3-migration status` writes a `migration-status-<timestamp>.md` with:
- Summary counts (total, ready, blocked)
- Mixin overview table
- Per-component status and blocking reason

## Workflow for large projects

For large codebases where each change is critical:

1. Run `npx vue3-migration status` to see the full picture.
2. Use **Pick a component** (option 2) to migrate one component at a time.
3. Test after each migration, then move on to the next.
4. When a mixin is fully covered and you're ready to retire it, use **Pick a mixin** (option 3).
