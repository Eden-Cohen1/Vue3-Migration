# vue3-migration

A CLI tool that helps you migrate Vue 2 mixins to Vue 3 composables.

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

This opens an interactive menu with all options.

### Commands

| Command | Description |
|---|---|
| `npx vue3-migration` | Interactive menu |
| `npx vue3-migration scan` | Scan the project — lists all components still using mixins and shows which composables already exist |
| `npx vue3-migration component <path>` | Migrate a single component — matches its mixins to composables and injects `setup()` |
| `npx vue3-migration audit <mixin> [composable]` | Audit a mixin — shows every component that uses it and what members they rely on |

### Examples

```bash
# Scan the whole project
npx vue3-migration scan

# Migrate a specific component
npx vue3-migration component src/components/UserProfile.vue

# Audit a mixin
npx vue3-migration audit src/mixins/authMixin.js

# Audit a mixin and compare against its composable
npx vue3-migration audit src/mixins/authMixin.js src/composables/useAuth.js
```

## Workflow

1. Run **scan** to see which components still use mixins and which composables are already available.
2. Pick a component and run **component** to migrate it. The tool matches each mixin to a composable, reports what's missing, and injects `setup()` for every ready composable.
3. To focus on a single mixin across the codebase, run **audit** to see every component that depends on it and what members they use.
