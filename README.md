# vue3-migration

**Stop rewriting mixins by hand.** Automatically migrate your Vue 2 mixins to Vue 3 composables — data, computed, methods, watchers, lifecycle hooks, and all.

One command. Full before/after diffs. No files changed until you say yes.

## The Problem

Every Vue 2 project sitting on mixins is a migration bottleneck. Rewriting them by hand means:

- Reading every mixin, understanding every member, tracing every `this.` reference
- Creating composable files, converting `this.x` to `x.value`, rewriting lifecycle hooks
- Updating every component that imports the mixin — removing imports, adding `setup()`, destructuring return values
- Doing it again for the next mixin. And the next. Across dozens (or hundreds) of components.

**vue3-migration does all of this automatically.** It reads your mixins, generates (or patches) composables, rewrites your components, and shows you a clean diff before touching a single file.

## Install

```bash
npm install -D vue3-migration
```

Requires Node.js >= 14 and Python >= 3.9 (used internally for AST analysis).

## Quick Start

```bash
npx vue3-migration
```

That's it. An interactive menu walks you through four options:

| # | Mode | What it does |
|---|------|-------------|
| **1** | **Full project** | Migrates every component at once. Generates and patches composables, injects `setup()`, removes mixin imports. Shows a full change summary before writing. |
| **2** | **Pick a component** | Choose one component from a list. Migrate just that file. Low blast radius — perfect for large codebases. |
| **3** | **Pick a mixin** | Choose one mixin to fully retire. Updates the composable and every component that uses it. |
| **4** | **Project status** | Read-only scan. Generates a detailed markdown report: what's migrated, what's ready, what's blocked and why. |

### Direct Commands

```bash
npx vue3-migration all                                # Full project migration
npx vue3-migration component src/components/Foo.vue   # One component
npx vue3-migration mixin authMixin                    # Retire one mixin everywhere
npx vue3-migration status                             # Status report only
npx vue3-migration --root /path/to/project all        # Run from outside project root
```

## What It Actually Does

### Generates composables from scratch

No existing composable? The tool creates one. Given a mixin like:

```js
// mixins/authMixin.js
export default {
  data() {
    return { user: null, token: '' }
  },
  computed: {
    isLoggedIn() { return !!this.user }
  },
  methods: {
    async login(credentials) { /* ... */ }
  },
  mounted() {
    this.checkSession()
  }
}
```

It generates:

```js
// composables/useAuth.js
import { ref, computed, onMounted } from 'vue'

export function useAuth() {
  const user = ref(null)
  const token = ref('')

  const isLoggedIn = computed(() => !!user.value)

  async function login(credentials) { /* ... */ }

  onMounted(() => {
    checkSession()
  })

  return { user, token, isLoggedIn, login }
}
```

Every `this.x` reference is rewritten. Lifecycle hooks are converted. Getter/setter computed properties are handled. Watch expressions with `deep`, `immediate`, and handler options are converted.

### Patches incomplete composables

Already started writing composables manually? The tool detects what's missing and patches it — adds missing member declarations and updates the `return` statement. No duplicate work.

### Rewrites components automatically

For every component using a mixin, the tool:

1. **Removes** the mixin import line
2. **Adds** the composable import
3. **Removes** the mixin from the `mixins: [...]` array
4. **Injects** a `setup()` function with destructured composable calls
5. **Converts** lifecycle hooks to their Composition API equivalents
6. **Merges** into existing `setup()` if one already exists

**Before:**
```vue
<script>
import authMixin from '@/mixins/authMixin'

export default {
  mixins: [authMixin],
  data() { return { localState: true } }
}
</script>
```

**After:**
```vue
<script>
import { useAuth } from '@/composables/useAuth'

export default {
  setup() {
    const { user, token, isLoggedIn, login } = useAuth()
    return { user, token, isLoggedIn, login }
  },
  data() { return { localState: true } }
}
</script>
```

### Handles `this.$` patterns

- `this.$nextTick(cb)` &rarr; `nextTick(cb)` (auto-imports from `'vue'`)
- `this.$set(obj, key, val)` &rarr; `obj[key] = val`
- `this.$delete(obj, key)` &rarr; `delete obj[key]`
- `this.$emit`, `this.$router`, `this.$store`, `this.$refs`, and 15+ more patterns are detected and flagged with actionable migration guidance

### Smart about what it can't automate

Some patterns need human judgment. The tool doesn't silently skip them — it flags them clearly:

- **`this.$emit`** &rarr; "Use `defineEmits` or pass `emit` from `setup()`"
- **`this.$router` / `this.$route`** &rarr; "Import `useRouter()` / `useRoute()` from `vue-router`"
- **`this.$store`** &rarr; "Import store directly from Pinia/Vuex"
- **`this.$refs`** &rarr; "Use template refs with `ref()`"
- **Mixin `props`, `inject`, `provide`** &rarr; "Must use `defineProps()` / `inject()` manually"
- **Nested mixins** &rarr; "Transitive members may be missed"
- **`filters`** &rarr; "Removed in Vue 3 — convert to methods"
- **This-aliasing** (`const self = this`) &rarr; "Manual replacement needed"

Each warning is injected as a comment directly in the generated code, so nothing gets lost.

## Safety Features

**Nothing changes until you confirm.** Every migration mode shows a complete change summary and asks for explicit `y/n` confirmation before writing any file.

**Full diff report.** Every migration writes a `migration-diff-<timestamp>.md` with unified diffs of every changed file — composables and components.

**Override-aware.** If a component defines its own `data`, `computed`, or `methods` that overlap with a mixin, the tool knows the component's version takes precedence and won't inject duplicates.

**Confidence scoring.** Generated composables include a confidence header:
- **HIGH** — Clean conversion, no remaining issues
- **MEDIUM** — Has TODOs or warnings that need review
- **LOW** — Remaining `this.` references or structural issues

**Blocked status.** If a mixin can't be safely migrated (e.g., missing composable, incomplete coverage), the tool marks it as blocked and tells you exactly why — it never partially migrates and leaves broken code.

## What It Supports

| Mixin feature | Auto-converted |
|--------------|---------------|
| `data()` properties | ref() with default values |
| `computed` (simple) | computed(() => ...) |
| `computed` (get/set) | computed({ get, set }) |
| `methods` (sync & async) | Plain functions |
| `watch` (handler + options) | watch() with deep/immediate |
| `mounted`, `created`, etc. | onMounted(), inlined, etc. |
| `beforeDestroy` / `destroyed` | onBeforeUnmount() / onUnmounted() |
| `this.x` references | x.value or x (context-aware) |
| `this.$nextTick` | nextTick() |
| `this.$set` / `this.$delete` | Direct assignment / delete |
| Multiple mixins per component | Multiple composable calls |
| Existing `setup()` function | Merges (doesn't overwrite) |
| `@/` and relative imports | Resolved and rewritten |

## Recommended Workflow for Large Projects

1. **Run `npx vue3-migration status`** to see the full picture — which mixins are used where, what's ready, what's blocked.
2. **Start with "Pick a component"** (option 2). Migrate one component, test it, commit.
3. **When a mixin is fully covered**, use "Pick a mixin" (option 3) to retire it across all components at once.
4. **Repeat** until the status report shows zero remaining mixins.

For smaller projects, "Full project" (option 1) handles everything in one pass.

## How It Finds Your Files

The tool searches recursively from your project root (or `--root` if specified):

- **Components:** Every `.vue` file in the project tree
- **Mixin files:** Resolved from import paths (`@/`, relative, bare imports)
- **Composables:** First checks directories named `composables/` (case-insensitive), then falls back to searching the entire project for any `use*.js` / `use*.ts` file

Skips `node_modules/`, `dist/`, `.git/`, and `__pycache__/` automatically.

## Requirements

- **Node.js** >= 14 (for the CLI wrapper)
- **Python** >= 3.9 (for the migration engine — auto-detected on your PATH)

## License

MIT
