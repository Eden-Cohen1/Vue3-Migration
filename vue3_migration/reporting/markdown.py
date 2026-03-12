"""
Markdown report generation for migration analysis results.
"""

from pathlib import Path

from ..core.file_utils import read_source
from ..models import ConfidenceLevel, FileChange, MigrationWarning, MixinEntry
from .terminal import md_green, md_yellow

_SKIPPED_CATEGORIES = frozenset({
    "skipped-all-overridden",
    "skipped-lifecycle-only",
    "skipped-no-usage",
})

# Categories that the tool rewrites automatically — no manual step needed
_AUTO_REWRITTEN_CATEGORIES = frozenset({
    "this.$t", "this.$tc", "this.$te", "this.$d", "this.$n",  # i18n → useI18n()
    "this.$nextTick",   # → nextTick()
    "this.$set",        # → direct assignment
    "this.$delete",     # → delete obj[key]
})

_CONF_DOT = {
    ConfidenceLevel.LOW: "\U0001f534",      # red dot
    ConfidenceLevel.MEDIUM: "\U0001f7e1",   # yellow dot
    ConfidenceLevel.HIGH: "\U0001f7e2",      # green dot
}

# ---------------------------------------------------------------------------
# Migration Recipes — before/after code snippets for each warning category
# ---------------------------------------------------------------------------

_MIGRATION_RECIPES: dict[str, dict[str, str]] = {
    "this.$emit": {
        "title": "`this.$emit` → `defineEmits`",
        "why": "Composables don't have a component instance, so `this.$emit` won't work.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  submit() {\n"
            '    this.$emit("update", this.value)\n'
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable — accept emit as a parameter\n"
            "export function useAuth(emit) {\n"
            "  function submit() {\n"
            "    emit('update', value.value)\n"
            "  }\n"
            "  return { submit }\n"
            "}\n"
            "\n"
            "// In component\n"
            "const emit = defineEmits(['update'])\n"
            "const { submit } = useAuth(emit)"
        ),
        "alt": "Return a callback and let the component wire up the emit.",
    },
    "this.$router": {
        "title": "`this.$router` → `useRouter()`",
        "why": "Vue Router's `useRouter()` composable replaces `this.$router`.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  navigate() {\n"
            "    this.$router.push('/login')\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { useRouter } from 'vue-router'\n"
            "\n"
            "export function useNav() {\n"
            "  const router = useRouter()\n"
            "  function navigate() {\n"
            "    router.push('/login')\n"
            "  }\n"
            "  return { navigate }\n"
            "}"
        ),
    },
    "this.$route": {
        "title": "`this.$route` → `useRoute()`",
        "why": "Vue Router's `useRoute()` composable replaces `this.$route`.",
        "before": (
            "// In mixin\n"
            "computed: {\n"
            "  currentPage() {\n"
            "    return this.$route.params.page\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { useRoute } from 'vue-router'\n"
            "import { computed } from 'vue'\n"
            "\n"
            "export function useNav() {\n"
            "  const route = useRoute()\n"
            "  const currentPage = computed(() => route.params.page)\n"
            "  return { currentPage }\n"
            "}"
        ),
    },
    "this.$store": {
        "title": "`this.$store` → Pinia store",
        "why": "Import and use a Pinia store directly instead of `this.$store`.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  load() {\n"
            "    return this.$store.dispatch('fetchData', this.id)\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { useDataStore } from '@/stores/data'\n"
            "\n"
            "export function useLoader() {\n"
            "  const store = useDataStore()\n"
            "  function load(id) {\n"
            "    return store.fetchData(id)\n"
            "  }\n"
            "  return { load }\n"
            "}"
        ),
        "alt": "For Vuex 4: `import { useStore } from 'vuex'` + `const store = useStore()`.",
    },
    "this.$refs": {
        "title": "`this.$refs` → template refs",
        "why": "Use Vue's `ref()` + template `ref` attribute instead of `this.$refs`.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  focusInput() {\n"
            "    this.$refs.input.focus()\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { ref } from 'vue'\n"
            "\n"
            "export function useInput() {\n"
            "  const inputRef = ref(null)\n"
            "  function focusInput() {\n"
            "    inputRef.value?.focus()\n"
            "  }\n"
            "  return { inputRef, focusInput }\n"
            "}\n"
            "\n"
            "// In template: <input ref=\"inputRef\" />"
        ),
    },
    "this.$t": {
        "title": "`this.$t` / `$tc` / `$te` / `$d` / `$n` → `useI18n()`",
        "why": "Vue I18n's `useI18n()` composable replaces `this.$t` and friends.",
        "before": (
            "// In mixin\n"
            "computed: {\n"
            "  greeting() {\n"
            "    return this.$t('hello')\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { useI18n } from 'vue-i18n'\n"
            "import { computed } from 'vue'\n"
            "\n"
            "export function useGreeting() {\n"
            "  const { t } = useI18n()\n"
            "  const greeting = computed(() => t('hello'))\n"
            "  return { greeting }\n"
            "}"
        ),
    },
    "this.$on": {
        "title": "`this.$on` / `$off` / `$once` → event bus",
        "why": "`$on`, `$off`, `$once` were removed in Vue 3. Use an external event bus.",
        "before": (
            "// In mixin\n"
            "mounted() {\n"
            "  this.$on('resize', this.handleResize)\n"
            "},\n"
            "beforeDestroy() {\n"
            "  this.$off('resize', this.handleResize)\n"
            "}"
        ),
        "after": (
            "// In composable — use mitt\n"
            "import mitt from 'mitt'\n"
            "import { onMounted, onBeforeUnmount } from 'vue'\n"
            "\n"
            "const bus = mitt()  // shared instance\n"
            "\n"
            "export function useResize() {\n"
            "  function handleResize() { /* ... */ }\n"
            "  onMounted(() => bus.on('resize', handleResize))\n"
            "  onBeforeUnmount(() => bus.off('resize', handleResize))\n"
            "  return { handleResize }\n"
            "}"
        ),
        "alt": "For parent-child: use props/emit or provide/inject instead.",
    },
    "this.$el": {
        "title": "`this.$el` → template ref on root element",
        "why": "Use a `ref` on the root element instead of `this.$el`.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  measure() {\n"
            "    return this.$el.getBoundingClientRect()\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable\n"
            "import { ref } from 'vue'\n"
            "\n"
            "export function useMeasure() {\n"
            "  const rootRef = ref(null)\n"
            "  function measure() {\n"
            "    return rootRef.value?.getBoundingClientRect()\n"
            "  }\n"
            "  return { rootRef, measure }\n"
            "}\n"
            "\n"
            "// In template: <div ref=\"rootRef\">..."
        ),
    },
    "this.$parent": {
        "title": "`this.$parent` → `provide` / `inject`",
        "why": "`this.$parent` creates tight coupling. Use provide/inject instead.",
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  callParent() {\n"
            "    this.$parent.refresh()\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In parent component\n"
            "import { provide } from 'vue'\n"
            "provide('refresh', refresh)\n"
            "\n"
            "// In composable\n"
            "import { inject } from 'vue'\n"
            "\n"
            "export function useChild() {\n"
            "  const refresh = inject('refresh')\n"
            "  function callParent() {\n"
            "    refresh()\n"
            "  }\n"
            "  return { callParent }\n"
            "}"
        ),
    },
    "this.$attrs": {
        "title": "`this.$attrs` → `useAttrs()`",
        "why": "Vue 3's `useAttrs()` composable replaces `this.$attrs`.",
        "before": "const cls = this.$attrs.class",
        "after": (
            "import { useAttrs } from 'vue'\n"
            "const attrs = useAttrs()\n"
            "const cls = attrs.class"
        ),
    },
    "this.$slots": {
        "title": "`this.$slots` → `useSlots()`",
        "why": "Vue 3's `useSlots()` composable replaces `this.$slots`.",
        "before": "const hasDefault = !!this.$slots.default",
        "after": (
            "import { useSlots } from 'vue'\n"
            "const slots = useSlots()\n"
            "const hasDefault = !!slots.default"
        ),
    },
    "this.$watch": {
        "title": "`this.$watch` → `watch()`",
        "why": "Use Vue's `watch()` composable instead of `this.$watch`.",
        "before": "this.$watch('count', handler)",
        "after": (
            "import { watch } from 'vue'\n"
            "watch(count, handler)"
        ),
    },
    "external-dependency": {
        "title": "External dependency → 3 options",
        "why": (
            "The mixin accesses `this.someVar` where `someVar` is not defined in the mixin itself "
            "(it comes from the component's data/props). There are three ways to resolve this."
        ),
        "before": (
            "// In mixin — uses this.items which is defined in the component, not the mixin\n"
            "methods: {\n"
            "  search() {\n"
            "    return this.items.filter(i => i.name.includes(this.query))\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// Option 1: Composable parameter (best for data shared across methods)\n"
            "export function useSearch(items) {\n"
            "  function search() {\n"
            "    return items.value.filter(i => i.name.includes(query.value))\n"
            "  }\n"
            "  return { search }\n"
            "}\n"
            "// In component: const { search } = useSearch(toRef(props, 'items'))\n"
            "\n"
            "// Option 2: Function argument (best when used in only one method)\n"
            "export function useSearch() {\n"
            "  function search(items) {\n"
            "    return items.filter(i => i.name.includes(query.value))\n"
            "  }\n"
            "  return { search }\n"
            "}\n"
            "// In component: search(this.items)\n"
            "\n"
            "// Option 3: Import from another composable\n"
            "import { useStore } from './useStore'\n"
            "export function useSearch() {\n"
            "  const { items } = useStore()\n"
            "  function search() {\n"
            "    return items.value.filter(i => i.name.includes(query.value))\n"
            "  }\n"
            "  return { search }\n"
            "}"
        ),
    },
    "this-alias": {
        "title": "`this` alias → direct refs",
        "why": (
            "The mixin stores `this` in a variable (e.g. `const self = this`). "
            "In composables, there's no `this` — use reactive refs directly."
        ),
        "before": (
            "// In mixin\n"
            "methods: {\n"
            "  delayed() {\n"
            "    const self = this\n"
            "    setTimeout(() => { self.count++ }, 100)\n"
            "  }\n"
            "}"
        ),
        "after": (
            "// In composable — no alias needed\n"
            "function delayed() {\n"
            "  setTimeout(() => { count.value++ }, 100)\n"
            "}"
        ),
    },
    "mixin-option:props": {
        "title": "Mixin props → `defineProps()`",
        "why": "Props defined in a mixin must be moved to the component's `defineProps()`.",
        "before": (
            "// In mixin\n"
            "props: {\n"
            "  title: { type: String, required: true },\n"
            "  items: { type: Array, default: () => [] }\n"
            "}"
        ),
        "after": (
            "// In component — move props here\n"
            "const props = defineProps({\n"
            "  title: { type: String, required: true },\n"
            "  items: { type: Array, default: () => [] }\n"
            "})"
        ),
    },
    "mixin-option:filters": {
        "title": "Filters → standalone functions",
        "why": "Filters were removed in Vue 3. Convert them to plain functions.",
        "before": (
            "// In mixin\n"
            "filters: {\n"
            "  capitalize(val) {\n"
            "    return val.charAt(0).toUpperCase() + val.slice(1)\n"
            "  }\n"
            "}\n"
            "// In template: {{ name | capitalize }}"
        ),
        "after": (
            "// Convert to a function\n"
            "function capitalize(val) {\n"
            "  return val.charAt(0).toUpperCase() + val.slice(1)\n"
            "}\n"
            "// In template: {{ capitalize(name) }}"
        ),
    },
    "mixin-option:inject": {
        "title": "Mixin `inject` → `inject()` in setup",
        "why": "Move inject options to explicit `inject()` calls in the composable.",
        "before": (
            "// In mixin\n"
            "inject: ['theme', 'locale']"
        ),
        "after": (
            "import { inject } from 'vue'\n"
            "\n"
            "const theme = inject('theme')\n"
            "const locale = inject('locale')"
        ),
    },
    "mixin-option:provide": {
        "title": "Mixin `provide` → `provide()` in setup",
        "why": "Move provide options to explicit `provide()` calls.",
        "before": (
            "// In mixin\n"
            "provide() {\n"
            "  return { theme: this.theme }\n"
            "}"
        ),
        "after": (
            "import { provide } from 'vue'\n"
            "\n"
            "provide('theme', themeRef)"
        ),
    },
    "data-setup-collision": {
        "title": "Data / Setup Name Collision",
        "why": (
            "In Vue 3, when a component has both `data()` and `setup()` returning "
            "a property with the same name, `data()` wins — the `setup()` value is "
            "silently ignored. After migration, composable values returned via "
            "`setup()` can be shadowed by leftover `data()` properties."
        ),
        "before": (
            "export default {\n"
            "  mixins: [searchMixin],  // provides 'query' via composable\n"
            "  data() {\n"
            "    return { query: '' }  // shadows the composable value!\n"
            "  },\n"
            "  setup() {\n"
            "    const { query } = useSearch()\n"
            "    return { query }\n"
            "  }\n"
            "}"
        ),
        "after": (
            "export default {\n"
            "  // Option A: Remove from data() — use the composable value\n"
            "  data() {\n"
            "    return { /* query removed — now comes from composable */ }\n"
            "  },\n"
            "  setup() {\n"
            "    const { query } = useSearch()\n"
            "    return { query }\n"
            "  }\n"
            "}\n"
            "\n"
            "// Option B: Remove from composable return — keep data() version\n"
            "// Only if the component intentionally manages its own 'query'"
        ),
    },
}

# Categories that share a recipe (all i18n variants point to this.$t)
_RECIPE_ALIASES: dict[str, str] = {
    "this.$tc": "this.$t",
    "this.$te": "this.$t",
    "this.$d": "this.$t",
    "this.$n": "this.$t",
    "this.$off": "this.$on",
    "this.$once": "this.$on",
    "this.$children": "this.$parent",
    "this.$listeners": "this.$attrs",
    "mixin-option:directives": "mixin-option:inject",
    "mixin-option:model": "mixin-option:props",
}


def build_recipes_section(
    entries_by_component: "list[tuple[Path, list[MixinEntry]]]",
) -> str:
    """Build a Migration Recipes reference section.

    Only includes recipes for categories that actually appear in the warnings.
    """
    # Collect unique warning categories across all entries
    seen_stems: set[str] = set()
    categories: set[str] = set()
    for _comp_path, entry_list in entries_by_component:
        for entry in entry_list:
            if entry.mixin_stem in seen_stems:
                continue
            seen_stems.add(entry.mixin_stem)
            for w in entry.warnings:
                if w.category not in _SKIPPED_CATEGORIES and w.category not in _AUTO_REWRITTEN_CATEGORIES:
                    categories.add(w.category)

    if not categories:
        return ""

    # Resolve to unique recipe keys (de-dup aliases)
    recipe_keys: list[str] = []
    seen_keys: set[str] = set()
    for cat in sorted(categories):
        key = _RECIPE_ALIASES.get(cat, cat)
        if key in _MIGRATION_RECIPES and key not in seen_keys:
            seen_keys.add(key)
            recipe_keys.append(key)

    if not recipe_keys:
        return ""

    lines: list[str] = []
    a = lines.append
    a("## Migration Patterns\n")

    for key in recipe_keys:
        recipe = _MIGRATION_RECIPES[key]
        anchor = key.replace("$", "").replace(".", "").replace(":", "-").replace("/", "-")
        a(f'<a id="recipe-{anchor}"></a>\n')
        a(f"### {recipe['title']}\n")
        if "why" in recipe:
            a(f"{recipe['why']}\n")
        a("**Before:**\n")
        a("```js")
        a(recipe["before"])
        a("```\n")
        a("**After:**\n")
        a("```js")
        a(recipe["after"])
        a("```\n")
        if "alt" in recipe:
            a(f"> **Alt:** {recipe['alt']}\n")
        a("---\n")

    return "\n".join(lines)


def _recipe_link(category: str) -> str:
    """Return a markdown anchor link to a recipe for the given category."""
    key = _RECIPE_ALIASES.get(category, category)
    if key not in _MIGRATION_RECIPES:
        return ""
    anchor = key.replace("$", "").replace(".", "").replace(":", "-").replace("/", "-")
    return f"[see how](#recipe-{anchor})"


def _rel_link(path: "Path | str", project_root: Path, label: str | None = None) -> str:
    """Return a markdown hyperlink with a relative path."""
    p = Path(path) if not isinstance(path, Path) else path
    try:
        rel = p.relative_to(project_root)
    except ValueError:
        rel = p
    display = label or rel.name
    return f"[`{display}`]({str(rel).replace(chr(92), '/')})"


def build_component_report(
    component_path: Path,
    mixin_entries: list[MixinEntry],
    project_root: Path,
) -> str:
    """Build a markdown migration report for a single component."""
    from datetime import datetime

    lines: list[str] = []
    w = lines.append

    ready_count = sum(
        1 for e in mixin_entries
        if not e.used_members or (e.classification and e.classification.is_ready)
    )
    blocked_count = len(mixin_entries) - ready_count

    w(f"# Migration Report: {_rel_link(component_path, project_root)}\n")
    parts = [f"{len(mixin_entries)} mixin{'s' if len(mixin_entries) != 1 else ''}"]
    parts.append(f"{ready_count} ready")
    parts.append(f"{blocked_count} blocked")
    w(f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` \u2014 {' \u00b7 '.join(parts)}\n")
    w("---\n")

    ready_entries = []
    blocked_entries = []

    for entry in mixin_entries:
        mixin_name = entry.mixin_stem
        w(f"## Mixin: {_rel_link(entry.mixin_path, project_root, mixin_name)}\n")

        # Members breakdown
        for section in ("data", "computed", "methods"):
            section_members = getattr(entry.members, section)
            if section_members:
                w(f"**{section}:** {', '.join(section_members)}\n")

        # Lifecycle hooks
        if entry.lifecycle_hooks:
            w(f"\n**Lifecycle hooks:** {', '.join(entry.lifecycle_hooks)}")
            w("> Must be manually migrated (e.g. `mounted` -> `onMounted`).\n")

        # Used members
        used = entry.used_members
        w(f"\n**Used by component:** {', '.join(used) if used else 'none detected'}\n")

        # Composable analysis
        comp = entry.composable
        cls = entry.classification

        if not entry.used_members:
            w("**Status: READY** -- no members used, mixin can be safely removed.\n")
            ready_entries.append(entry)
        elif not comp or not cls:
            w(f"**Composable:** {md_yellow('NOT FOUND')}\n")
            blocked_entries.append(entry)
        else:
            w(f"**Composable:** {_rel_link(comp.file_path, project_root)}")
            w(f"**Function:** `{comp.fn_name}`")
            w(f"**Import path:** `{comp.import_path}`")
            w(f"> {md_yellow('Verify the above path and function name are correct.')}\n")

            if cls.truly_missing:
                w(f"**MISSING from composable:** {', '.join(cls.truly_missing)}\n")
            if cls.overridden:
                w(f"**Overridden by component:** {', '.join(cls.overridden)}")
                w("> These mixin members are redefined in the component itself, "
                  "so the composable doesn't need to provide them.\n")

            if cls.truly_not_returned:
                w(f"**NOT in return statement:** {', '.join(cls.truly_not_returned)}")
                w("> These exist in the composable but are not returned, "
                  "so the component cannot access them.\n")
            if cls.overridden_not_returned:
                w(f"**Overridden (not returned):** {', '.join(cls.overridden_not_returned)}")
                w("> Not returned by composable, but the component defines them itself.\n")

            if cls.is_ready:
                status_note = ""
                override_count = len(cls.overridden) + len(cls.overridden_not_returned)
                if override_count:
                    status_note = f" ({override_count} member(s) overridden by component)"
                w(f"**Status: READY**{status_note} -- all needed members are present and returned.\n")
                ready_entries.append(entry)
            else:
                blocked_entries.append(entry)

        # Warnings for this mixin
        if entry.warnings:
            _SEV_ICON = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
            w(f"\n**Warnings ({len(entry.warnings)}):**\n")
            for warning in entry.warnings:
                icon = _SEV_ICON.get(warning.severity, "❓")
                w(f"- {icon} **{warning.category}** ({warning.severity}): {warning.message}")
                w(f"    → {warning.action_required}\n")

        w("---\n")

    # --- Actionable Summary ---
    w("\n## Action Items\n")

    if blocked_entries:
        for entry in blocked_entries:
            mixin_name = entry.mixin_stem
            comp = entry.composable
            cls = entry.classification

            if not comp:
                w(f"### {mixin_name}: Create composable")
                w(f"- {md_yellow('A composable needs to be created')} for `{mixin_name}`.")
                if entry.used_members:
                    w(f"- It must expose: {', '.join(entry.used_members)}\n")
            else:
                w(f"### {mixin_name}: Update `{comp.fn_name}`")
                if cls and cls.missing:
                    w(f"- Add to composable: {', '.join(cls.missing)}")
                if cls and cls.not_returned:
                    w(f"- Add to return statement: {', '.join(cls.not_returned)}")
                w(f"- File: {_rel_link(comp.file_path, project_root)}\n")

    if ready_entries:
        w("### Ready for injection")
        for entry in ready_entries:
            if not entry.used_members:
                w(f"- `{entry.mixin_stem}` -- no members used, will just remove mixin")
            else:
                comp = entry.composable
                w(f"- `{entry.mixin_stem}` -> `{comp.fn_name}` ({len(entry.used_members)} members)")
        w("")

    if not blocked_entries:
        w("All mixins are ready. Run the script again to inject.\n")
    elif ready_entries:
        w(f"{len(ready_entries)} of {len(mixin_entries)} mixin(s) are ready for partial injection.\n")
    else:
        w(f"{md_yellow('No mixins are ready for injection yet.')} Fix the issues above and re-run.\n")

    return "\n".join(lines)


def generate_status_report(project_root: Path, config) -> str:
    """Generate a detailed markdown status report of migration progress."""
    import os
    import re as _re
    from collections import Counter
    from datetime import datetime

    from ..core.component_analyzer import parse_imports, parse_mixins_array
    from ..core.composable_search import (
        collect_composable_stems,
        find_composable_dirs,
        mixin_has_composable,
    )
    from ..core.file_resolver import resolve_mixin_stem

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs, project_root=project_root)

    # Detect composables that need manual migration (reactive() or variable return)
    manual_stems: set[str] = set()
    for comp_dir in composable_dirs:
        for dirpath_c, _, filenames_c in os.walk(comp_dir):
            for fn_c in filenames_c:
                fp = Path(dirpath_c) / fn_c
                if fp.suffix not in (".js", ".ts") or not fp.stem.lower().startswith("use"):
                    continue
                try:
                    content = read_source(fp)
                except Exception:
                    continue
                if 'reactive(' in content or not _re.search(r'\breturn\s*\{', content):
                    manual_stems.add(fp.stem.lower())

    mixin_counter: Counter[str] = Counter()
    components_info: list[dict] = []

    for dirpath, _, filenames in os.walk(project_root):
        rel_dir = Path(dirpath).relative_to(project_root)
        if any(part in config.skip_dirs for part in rel_dir.parts):
            continue
        for fn in filenames:
            if not fn.endswith(".vue"):
                continue
            filepath = Path(dirpath) / fn
            try:
                source = read_source(filepath)
            except Exception:
                continue
            mixin_names = parse_mixins_array(source)
            if not mixin_names:
                continue
            imports = parse_imports(source)
            stems = []
            for name in mixin_names:
                imp = imports.get(name, "")
                stems.append(resolve_mixin_stem(imp) if imp else name)
                mixin_counter[stems[-1]] += 1
            covered = sum(
                1 for s in stems
                if mixin_has_composable(s, composable_stems)
                and not mixin_has_composable(s, manual_stems)
            )
            needs_manual = sum(
                1 for s in stems
                if mixin_has_composable(s, manual_stems)
            )
            try:
                rel = filepath.relative_to(project_root)
            except ValueError:
                rel = filepath
            components_info.append(
                {
                    "rel_path": rel,
                    "stems": stems,
                    "covered": covered,
                    "needs_manual": needs_manual,
                    "total": len(stems),
                    "all_covered": covered == len(stems) and needs_manual == 0,
                    "has_manual": needs_manual > 0,
                }
            )

    ready = sum(1 for c in components_info if c["all_covered"])
    needs_manual_count = sum(1 for c in components_info if c["has_manual"])
    blocked = len(components_info) - ready - needs_manual_count

    header_parts = [f"{len(components_info)} component{'s' if len(components_info) != 1 else ''}"]
    header_parts.append(f"{ready} ready")
    if needs_manual_count:
        header_parts.append(f"{needs_manual_count} manual")
    header_parts.append(f"{blocked} blocked")

    lines: list[str] = [
        "# Vue Migration Status Report",
        "",
        f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` \u2014 {' \u00b7 '.join(header_parts)}",
        "",
        "---",
        "",
        "> Run `vue3-migration auto` to generate a detailed diff report with warnings, per-component guide, and checklist.",
        "",
        "## Mixin Overview",
        "",
        "| Mixin | Used in | Composable |",
        "|-------|---------|------------|",
    ]

    for stem, count in mixin_counter.most_common():
        has_comp = mixin_has_composable(stem, composable_stems)
        is_manual = mixin_has_composable(stem, manual_stems)
        if is_manual:
            status = "found (needs manual migration)"
        elif has_comp:
            status = "found"
        else:
            status = "needs generation"
        lines.append(f"| {stem} | {count} | {status} |")

    lines += ["", "## Components", ""]

    # Ready first, then needs-manual, then blocked; alphabetical within each group
    components_info.sort(key=lambda c: (
        0 if c["all_covered"] else (1 if c["has_manual"] else 2),
        str(c["rel_path"]),
    ))

    for comp in components_info:
        if comp["all_covered"]:
            status_str = "**Ready** -- all composables found"
        elif comp["has_manual"]:
            status_str = "**Needs manual migration** -- composable uses reactive() or variable return"
        else:
            missing = comp["total"] - comp["covered"] - comp["needs_manual"]
            status_str = f"**Blocked** -- {missing} composable(s) missing or incomplete"

        lines.append(f"### [`{comp['rel_path']}`]({str(comp['rel_path']).replace(chr(92), '/')})")
        lines.append(f"- Mixins: {', '.join(f'`{s}`' for s in comp['stems'])}")
        lines.append(f"- Status: {status_str}")
        lines.append("")

    return "\n".join(lines)


def build_audit_report(
    mixin_path: Path,
    members: dict[str, list[str]],
    lifecycle_hooks: list[str],
    importing_files: list[Path],
    all_member_names: list[str],
    composable_path_arg: str | None,
    composable_identifiers: list[str],
    composable_exists: bool,
    project_root: Path,
    usage_map: dict[str, list[str]],
    warnings: list[MigrationWarning] | None = None,
) -> str:
    """Build a markdown audit report for a single mixin."""
    from datetime import datetime

    lines: list[str] = []
    w = lines.append

    total_members = len(all_member_names)
    header_parts = [f"{total_members} member{'s' if total_members != 1 else ''}"]
    header_parts.append(f"{len(lifecycle_hooks)} hook{'s' if len(lifecycle_hooks) != 1 else ''}")
    header_parts.append(f"{len(importing_files)} file{'s' if len(importing_files) != 1 else ''}")

    w(f"# Mixin Audit: {_rel_link(mixin_path, project_root, mixin_path.name)}\n")
    w(f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` \u2014 {' \u00b7 '.join(header_parts)}\n")
    w("---\n")

    w("## Mixin Members\n")
    for section in ("data", "computed", "methods"):
        if members[section]:
            w(f"**{section}:** {', '.join(members[section])}\n")

    w("\n## Lifecycle Hooks\n")
    if lifecycle_hooks:
        w(f"{', '.join(lifecycle_hooks)}\n")
        w("\n> These hooks contain logic that must be manually migrated "
          "to the composable (e.g. `mounted` -> `onMounted`).\n")
    else:
        w("*No lifecycle hooks found in this mixin.*\n")

    w(f"\n## Files Importing the Mixin ({len(importing_files)})\n")

    for file_path in sorted(importing_files):
        relative_path = file_path.relative_to(project_root)
        used = usage_map.get(str(relative_path), [])
        w(f"### {_rel_link(file_path, project_root, str(relative_path))}\n")
        if used:
            w(f"Uses: {', '.join(used)}\n")
        else:
            w("Uses: *(none detected -- mixin may be unused here)*\n")

    all_used_members = sorted(set(
        member for used_list in usage_map.values() for member in used_list
    ))

    w("\n## Composable Status\n")
    if not composable_path_arg:
        w("**No composable path provided.** A composable should be created.\n")
    elif not composable_exists:
        w(f"**Composable file not found at `{composable_path_arg}`.** It should be created.\n")
    else:
        missing = [m for m in all_used_members if m not in composable_identifiers]
        if missing:
            w(f"**Missing from composable:** {', '.join(missing)}\n")
        else:
            w("All used members are present in the composable.\n")

    w("\n## Summary\n")
    w(f"- Total mixin members: {len(all_member_names)}\n")
    w(f"- Lifecycle hooks: {len(lifecycle_hooks)}\n")
    w(f"- Members used across codebase: {len(all_used_members)}\n")

    unused_members = [m for m in all_member_names if m not in all_used_members]
    if unused_members:
        w(f"- Unused members (candidates for removal): {', '.join(unused_members)}\n")

    if warnings:
        _SEV_ICON = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        w(f"\n## Migration Warnings ({len(warnings)})\n")
        for warning in warnings:
            icon = _SEV_ICON.get(warning.severity, "❓")
            w(f"- {icon} **{warning.category}** ({warning.severity}): {warning.message}")
            w(f"    → {warning.action_required}\n")

    return "\n".join(lines)


def build_per_component_index(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
    confidence_map: dict[str, ConfidenceLevel],
    project_root: Path,
) -> str:
    """Build a per-component quick-reference index."""
    if not entries_by_component:
        return ""

    lines: list[str] = []
    a = lines.append
    a("## Per-Component Guide\n")

    for comp_path, entry_list in entries_by_component:
        a(f"### {_rel_link(comp_path, project_root)}\n")

        for entry in entry_list:
            entry_cats = {w.category for w in entry.warnings}
            is_skipped = entry_cats and entry_cats <= _SKIPPED_CATEGORIES

            if is_skipped:
                reason = entry.warnings[0].message if entry.warnings else "skipped"
                a(f"- \u2139\ufe0f **{entry.mixin_stem}** skipped \u2014 {reason}")
            elif entry.composable:
                conf = confidence_map.get(entry.mixin_stem, ConfidenceLevel.HIGH)
                dot = _CONF_DOT.get(conf, "\u2753")
                error_count = sum(1 for w in entry.warnings if w.severity == "error")
                warn_count = sum(1 for w in entry.warnings if w.severity == "warning")
                comp_link = _rel_link(entry.composable.file_path, project_root, entry.composable.fn_name)
                if error_count or warn_count:
                    parts = []
                    if error_count:
                        parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
                    if warn_count:
                        parts.append(f"{warn_count} warning{'s' if warn_count != 1 else ''}")
                    detail = ", ".join(parts)
                    a(f"- {dot} {comp_link} \u2014 {detail} \u2192 [See warnings](#{entry.mixin_stem})")
                else:
                    a(f"- {dot} {comp_link} \u2014 No issues")
            else:
                blocked_w = next(
                    (w for w in entry.warnings if w.category.startswith("blocked-")),
                    None,
                )
                reason = blocked_w.message if blocked_w else "composable not found"
                a(f"- \U0001f534 **{entry.mixin_stem}** \u2014 {reason}")

        a("")

    return "\n".join(lines)


def build_summary_section(
    entries_by_component: "list[tuple[Path, list[MixinEntry]]]",
) -> str:
    """Build an enhanced summary section for the top of the report."""
    # De-duplicate entries by mixin_stem
    seen_stems: set[str] = set()
    entries: list[MixinEntry] = []
    skipped_count = 0
    for _comp_path, entry_list in entries_by_component:
        for entry in entry_list:
            if entry.mixin_stem in seen_stems:
                continue
            seen_stems.add(entry.mixin_stem)
            entry_cats = {w.category for w in entry.warnings}
            if entry_cats and entry_cats <= _SKIPPED_CATEGORIES:
                skipped_count += 1
                continue
            entries.append(entry)

    if not entries:
        return ""

    # Separate unused mixins from active entries
    active_entries = [e for e in entries if not any(w.category == "unused-mixin" for w in e.warnings)]
    unused_count = len(entries) - len(active_entries)

    total_errors = sum(1 for e in active_entries for w in e.warnings
                       if w.severity == "error" and w.category not in _AUTO_REWRITTEN_CATEGORIES)
    total_warns = sum(1 for e in active_entries for w in e.warnings
                      if w.severity == "warning" and w.category not in _AUTO_REWRITTEN_CATEGORIES)
    quick = sum(1 for e in active_entries
                if not any(w.severity in ("error", "warning") and w.category not in _AUTO_REWRITTEN_CATEGORIES
                           for w in e.warnings))
    needs_work = len(active_entries) - quick

    lines: list[str] = []
    a = lines.append
    a("## Summary\n")

    # Overview sentence
    a(f"This report covers **{len(active_entries)}** composable{'s' if len(active_entries) != 1 else ''}.\n")

    if quick:
        a(f"- \U0001f7e2 **{quick}** can be applied as-is — no manual steps needed")
    if needs_work:
        a(f"- \U0001f7e1 **{needs_work}** need{'s' if needs_work == 1 else ''} manual attention before the migration is complete")
    if total_errors:
        a(f"- \u274c **{total_errors}** blocker{'s' if total_errors != 1 else ''} must be resolved — code won't run until fixed")
    if total_warns:
        a(f"- \u26a0\ufe0f **{total_warns}** warning{'s' if total_warns != 1 else ''} — known patterns with documented fixes")
    if unused_count:
        a(f"- \U0001f5d1\ufe0f **{unused_count}** mixin{'s' if unused_count != 1 else ''} not imported by any component — safe to delete")
    if skipped_count:
        a(f"- \u2139\ufe0f **{skipped_count}** mixin{'s' if skipped_count != 1 else ''} skipped (unused or fully overridden by component)")
    a("")
    a("> Start with the **Action Plan** below for step-by-step guidance on each composable.\n")

    return "\n".join(lines)


def build_action_plan(
    entries_by_component: "list[tuple[Path, list[MixinEntry]]]",
    composable_changes: "list[FileChange] | None" = None,
    project_root: "Path | None" = None,
) -> str:
    """Build an action plan grouped by difficulty tier with per-composable steps."""
    from collections import OrderedDict

    from ..core.warning_collector import compute_confidence

    # De-duplicate entries by mixin_stem
    seen_stems: set[str] = set()
    entries: list[MixinEntry] = []
    skipped_count = 0
    for _comp_path, entry_list in entries_by_component:
        for entry in entry_list:
            if entry.mixin_stem in seen_stems:
                continue
            seen_stems.add(entry.mixin_stem)
            entry_cats = {w.category for w in entry.warnings}
            if entry_cats and entry_cats <= _SKIPPED_CATEGORIES:
                skipped_count += 1
                continue
            entries.append(entry)

    if not entries:
        return ""

    # Build composable content map for confidence computation and line lookups
    # Keyed by file_path, with a secondary stem-based index for newly generated composables
    composable_content_map: dict[Path, str] = {}
    composable_path_by_stem: dict[str, Path] = {}
    if composable_changes:
        for change in composable_changes:
            if change.has_changes:
                composable_content_map[change.file_path] = change.new_content
                composable_path_by_stem[change.file_path.stem] = change.file_path

    # Classify each entry into tiers
    quick_wins: list[MixinEntry] = []    # HIGH confidence, no error/warning
    dropin_fixes: list[MixinEntry] = []  # MEDIUM confidence, only warnings
    design_decisions: list[MixinEntry] = []  # LOW confidence or errors
    unused_mixins: list[MixinEntry] = []  # Not imported by any component

    for entry in entries:
        # Standalone mixins not imported by any component get their own section
        if any(w.category == "unused-mixin" for w in entry.warnings):
            unused_mixins.append(entry)
            continue

        non_info = [w for w in entry.warnings
                    if w.severity in ("error", "warning") and w.category not in _AUTO_REWRITTEN_CATEGORIES]
        has_errors = any(w.severity == "error" and w.category not in _AUTO_REWRITTEN_CATEGORIES
                         for w in entry.warnings)

        if not non_info:
            quick_wins.append(entry)
        elif has_errors:
            design_decisions.append(entry)
        else:
            dropin_fixes.append(entry)

    lines: list[str] = []
    a = lines.append
    a("---\n")
    a("## Action Plan\n")

    a("### Recommended Order\n")
    idx = 0
    if quick_wins:
        idx += 1
        a(f"{idx}. \U0001f7e2 **Quick wins** ({len(quick_wins)} composable{'s' if len(quick_wins) != 1 else ''}) \u2014 apply changes as-is, no manual steps")
    if dropin_fixes:
        idx += 1
        a(f"{idx}. \U0001f7e1 **Drop-in fixes** ({len(dropin_fixes)} composable{'s' if len(dropin_fixes) != 1 else ''}) \u2014 mechanical replacements")
    if design_decisions:
        idx += 1
        a(f"{idx}. \U0001f534 **Design decisions** ({len(design_decisions)} composable{'s' if len(design_decisions) != 1 else ''}) \u2014 require architectural choices")
    if unused_mixins:
        idx += 1
        a(f"{idx}. \U0001f5d1\ufe0f **Unused mixins** ({len(unused_mixins)} file{'s' if len(unused_mixins) != 1 else ''}) \u2014 not imported by any component, safe to delete")
    a("")

    # Quick wins — just list names
    if quick_wins:
        a("---\n")
        a("### \U0001f7e2 Quick Wins \u2014 no manual steps needed\n")
        names = ", ".join(f"`{e.composable.fn_name}`" if e.composable else f"`{e.mixin_stem}`" for e in quick_wins)
        a(names)
        a("")
        a(f"These {len(quick_wins)} composable{'s are' if len(quick_wins) != 1 else ' is'} fully migrated. Apply the diff and test.\n")

    # Drop-in fixes — per-composable numbered steps
    if dropin_fixes:
        a("---\n")
        for entry in dropin_fixes:
            _append_composable_steps(a, entry, "\U0001f7e1", composable_content_map, composable_path_by_stem)

    # Design decisions — per-composable numbered steps
    if design_decisions:
        a("---\n")
        for entry in design_decisions:
            _append_composable_steps(a, entry, "\U0001f534", composable_content_map, composable_path_by_stem)

    # Unused mixins — not imported by any component
    if unused_mixins:
        a("---\n")
        a("### \U0001f5d1\ufe0f Unused Mixins \u2014 safe to delete\n")
        a("These mixin files are not imported by any component in the project.\n")
        for entry in unused_mixins:
            mixin_path = entry.mixin_path
            if mixin_path and project_root:
                try:
                    rel = mixin_path.relative_to(project_root)
                except ValueError:
                    rel = mixin_path
                a(f"- **`{entry.mixin_stem}`** \u2014 [`{rel}`]({rel})")
            else:
                a(f"- **`{entry.mixin_stem}`**")
            a(f"  - Delete this file, or keep it if used outside this project (shared library, dynamic import, etc.)")
        a("")

    return "\n".join(lines)


def _find_warning_lines(
    source: str, warning: MigrationWarning,
) -> list[int]:
    """Find 1-based line numbers in composable source matching a warning pattern.

    Uses a multi-strategy approach:
    1. Category-specific pattern search in composable source
    2. Fallback to line_hint text search
    3. Fallback to source_line from the warning model
    """
    import re
    lines = source.splitlines()
    result: list[int] = []

    # Build a search pattern based on the warning category
    pat = None
    if warning.category.startswith("this.$"):
        pat = warning.category
    elif warning.category == "external-dependency":
        m = re.match(r"'(\w+)'", warning.message)
        if m:
            pat = f"this.{m.group(1)}"
    elif warning.category == "this-alias":
        pat = "= this"
    elif warning.category == "remaining-this":
        pat = "this."
    elif warning.category.startswith("mixin-option:"):
        option = warning.category.split(":")[1]
        pat = f"{option}:"
    elif warning.category == "structural:factory-function":
        pat = "export default function"
    elif warning.category == "structural:nested-mixins":
        pat = "mixins:"
    elif warning.category == "structural:render-function":
        pat = "render("
    elif warning.category == "structural:serverPrefetch":
        pat = "serverPrefetch"
    elif warning.category == "structural:class-component":
        pat = "@Component"
    elif warning.category == "todo-marker":
        pat = "TODO"
    elif warning.category == "data-setup-collision":
        m = re.match(r"'(\w+)'", warning.message)
        if m:
            pat = m.group(1)

    # Search composable source for the pattern
    if pat:
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("//"):
                continue
            if pat in line:
                result.append(i)
        if result:
            return result

    # Fallback: search for line_hint text in composable source
    if warning.line_hint:
        hint = warning.line_hint.strip()
        if len(hint) > 5:  # skip very short hints that could match noise
            for i, line in enumerate(lines, 1):
                if hint in line:
                    result.append(i)
            if result:
                return result

    return result


def _vscode_link(file_path: Path, line: int, label: str) -> str:
    """Build a vscode:// URI link to a specific file and line."""
    abs_path = str(file_path.resolve()).replace("\\", "/")
    return f"[{label}](vscode://file/{abs_path}:{line}:1)"


def _step_label(warning: MigrationWarning) -> str:
    """Build a descriptive step label including specific member names."""
    import re
    if warning.category == "external-dependency":
        m = re.match(r"'(\w+)'", warning.message)
        member = f"`this.{m.group(1)}`" if m else "external dep"
        return f"Resolve {member} — composable param, function arg, or import"
    if warning.category == "this-alias":
        return "`this` alias won't work \u2014 replace with direct refs"
    if warning.category.startswith("mixin-option:"):
        option = warning.category.split(":")[1]
        return f"Mixin `{option}` option needs manual migration"
    # this.$ categories — already descriptive
    return f"Replace `{warning.category}`"


def _append_composable_steps(
    a: "callable",
    entry: MixinEntry,
    dot: str,
    composable_content_map: "dict[Path, str] | None" = None,
    composable_path_by_stem: "dict[str, Path] | None" = None,
) -> None:
    """Append numbered action steps for one composable to the output."""
    name = entry.composable.fn_name if entry.composable else entry.mixin_stem
    comp_source = ""
    comp_path = None
    if composable_content_map:
        if entry.composable:
            comp_path = entry.composable.file_path
            comp_source = composable_content_map.get(comp_path, "")
        # Fallback: match by stem name for newly generated composables
        if not comp_source and composable_path_by_stem:
            # Try common naming: mixin "dashboardMixin" → composable "useDashboard"
            import re
            stem = re.sub(r"[Mm]ixin$", "", entry.mixin_stem)
            use_name = f"use{stem[0].upper()}{stem[1:]}" if stem else ""
            if use_name in composable_path_by_stem:
                comp_path = composable_path_by_stem[use_name]
                comp_source = composable_content_map.get(comp_path, "")

    # Separate actionable warnings from info-only, excluding auto-rewritten categories
    actionable = [w for w in entry.warnings
                  if w.severity in ("error", "warning") and w.category not in _AUTO_REWRITTEN_CATEGORIES]
    info_warnings = [w for w in entry.warnings if w.severity == "info" and w.category not in _SKIPPED_CATEGORIES]

    # De-duplicate steps by recipe key (aliases like $t/$tc share one step)
    seen_keys: set[str] = set()
    steps: list[str] = []
    for w in actionable:
        recipe_key = _RECIPE_ALIASES.get(w.category, w.category)
        if recipe_key in seen_keys:
            continue
        seen_keys.add(recipe_key)

        label = _step_label(w)
        link = _recipe_link(w.category)

        # Find line numbers for VS Code links
        line_refs = ""
        if comp_source and comp_path:
            line_nums = _find_warning_lines(comp_source, w)
            if line_nums:
                vscode_links = [_vscode_link(comp_path, ln, f"L{ln}") for ln in line_nums[:5]]
                line_refs = f" ({', '.join(vscode_links)})"
        # Fallback: link to mixin source if we have source_line
        if not line_refs and w.source_line and hasattr(entry, 'mixin_path'):
            mixin_path = entry.mixin_path
            if mixin_path and mixin_path.exists():
                line_refs = f" ({_vscode_link(mixin_path, w.source_line, f'mixin L{w.source_line}')})"

        if link:
            steps.append(f"{label} \u2192 {link}{line_refs}")
        else:
            steps.append(f"{label} \u2192 {w.action_required}{line_refs}")

    step_count = len(steps)
    a(f"### {dot} `{name}` \u2014 {step_count} step{'s' if step_count != 1 else ''}\n")

    for i, step_text in enumerate(steps, 1):
        a(f"- **Step {i}:** {step_text}")

    # Info section — grouped by category for clarity
    if info_warnings:
        unused = [w for w in info_warnings if w.category == "unused-mixin-member"]
        overridden = [w for w in info_warnings if w.category == "overridden-member"]
        other_info = [w for w in info_warnings
                      if w.category not in ("unused-mixin-member", "overridden-member")]

        a("")

        if unused:
            names = ", ".join(
                f"`{w.message.split('`')[1]}`" if "`" in w.message
                else f"`{w.message.split(chr(39))[1]}`" if "'" in w.message
                else w.message
                for w in unused
            )
            a(f"> **Unused members:** {names} — consider removing from composable return")

        if overridden:
            names = ", ".join(
                f"`{m.strip()}`"
                for w in overridden
                for part in [w.message.split(":")[1] if ":" in w.message else w.message]
                for m in part.split(".")[0].split(",")
            )
            a(f"> **Overridden by component:** {names} — composable version won't be used")

        for w in other_info:
            a(f"> \u2139\ufe0f {w.message}")

    a("")


