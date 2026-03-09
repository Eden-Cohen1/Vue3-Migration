"""Collect migration warnings and compute confidence scores.

Warning collector is a separate module so Plans 2-4 can add detectors
here without touching the generator or patcher.
"""
import re

from ..models import ConfidenceLevel, MigrationWarning, MixinMembers


# Patterns: (regex, category, message, action_required, severity)
_THIS_DOLLAR_PATTERNS: list[tuple[str, str, str, str, str]] = [
    # --- error: will crash, requires architectural change ---
    (r"this\.\$emit\b", "this.$emit", "this.$emit is not available in composables",
     "Accept an emit function parameter or use defineEmits", "error"),
    (r"this\.\$refs\b", "this.$refs", "this.$refs is not available in composables",
     "Use template refs with ref() instead", "error"),
    (r"this\.\$on\b", "this.$on", "this.$on is removed in Vue 3",
     "Use an external event bus library or provide/inject", "error"),
    (r"this\.\$off\b", "this.$off", "this.$off is removed in Vue 3",
     "Use an external event bus library or provide/inject", "error"),
    (r"this\.\$once\b", "this.$once", "this.$once is removed in Vue 3",
     "Use an external event bus library or provide/inject", "error"),
    (r"this\.\$el\b", "this.$el", "this.$el has no composable equivalent",
     "Use a template ref on the root element instead", "error"),
    (r"this\.\$parent\b", "this.$parent", "this.$parent — avoid in composables",
     "Use provide/inject or props/emit instead", "error"),
    (r"this\.\$children\b", "this.$children", "this.$children is removed in Vue 3",
     "Use template refs or provide/inject", "error"),
    (r"this\.\$listeners\b", "this.$listeners", "$listeners is removed in Vue 3",
     "Listeners are merged into $attrs in Vue 3", "error"),
    # --- error: will crash at runtime, no 'this' in composables ---
    (r"this\.\$router\b", "this.$router", "this.$router is not available in composables",
     "Import and use useRouter() from vue-router", "error"),
    (r"this\.\$route\b", "this.$route", "this.$route is not available in composables",
     "Import and use useRoute() from vue-router", "error"),
    (r"this\.\$store\b", "this.$store", "this.$store is not available in composables",
     "Import and use the Pinia/Vuex store directly", "error"),
    # --- error: i18n — will crash at runtime, no 'this' in composables ---
    (r"this\.\$t\b", "this.$t", "this.$t (i18n) is not available in composables",
     "Import and use useI18n() from 'vue-i18n': const { t } = useI18n()", "error"),
    (r"this\.\$tc\b", "this.$tc", "this.$tc (i18n pluralization) is removed in vue-i18n v9",
     "Use t() with plural syntax instead: const { t } = useI18n()", "error"),
    (r"this\.\$te\b", "this.$te", "this.$te (i18n key existence) is not available in composables",
     "Use te() from useI18n(): const { te } = useI18n()", "error"),
    (r"this\.\$d\b", "this.$d", "this.$d (i18n date) is not available in composables",
     "Use d() from useI18n(): const { d } = useI18n()", "error"),
    (r"this\.\$n\b", "this.$n", "this.$n (i18n number) is not available in composables",
     "Use n() from useI18n(): const { n } = useI18n()", "error"),
    # --- warning: has known drop-in replacement ---
    (r"this\.\$attrs\b", "this.$attrs", "this.$attrs used — needs useAttrs()",
     "Add const attrs = useAttrs() and import from 'vue'", "warning"),
    (r"this\.\$slots\b", "this.$slots", "this.$slots used — needs useSlots()",
     "Add const slots = useSlots() and import from 'vue'", "warning"),
    (r"this\.\$watch\b", "this.$watch", "this.$watch — use watch() from vue instead",
     "Import watch from 'vue' and use watch() directly", "warning"),
    # $nextTick, $set, $delete are auto-migrated by rewrite_this_dollar_refs()
    # in this_rewriter.py — no warning needed.
    # --- info: probably removable, low urgency ---
    (r"this\.\$forceUpdate\b", "this.$forceUpdate", "$forceUpdate — rarely needed in Vue 3",
     "Reactive system usually handles it; review logic", "info"),
]


_RESOLVED_PATTERNS: dict[str, str] = {
    "this.$router": "useRouter",
    "this.$route": "useRoute",
    "this.$store": r"use\w+Store",
    "this.$attrs": "useAttrs",
    "this.$slots": "useSlots",
    "this.$t": "useI18n",
    "this.$tc": "useI18n",
    "this.$te": "useI18n",
    "this.$d": "useI18n",
    "this.$n": "useI18n",
}


def suppress_resolved_warnings(
    warnings: list[MigrationWarning],
    composable_declared: list[str],
    composable_source: str | None = None,
) -> list[MigrationWarning]:
    """Filter out warnings that are already resolved by the composable.

    Suppresses:
    1. External-dependency warnings where the dep name is in composable_declared.
    2. this.$X warnings where the composable source already contains the
       corresponding API call (e.g. useRouter for this.$router).

    Warnings that are NOT suppressed are returned unchanged.
    """
    declared_set = set(composable_declared)
    result: list[MigrationWarning] = []

    for w in warnings:
        # Check external-dependency suppression
        if w.category == "external-dependency":
            m = re.match(r"'(\w+)'", w.message)
            if m and m.group(1) in declared_set:
                continue  # suppressed

        # Check this.$X suppression
        if w.category in _RESOLVED_PATTERNS and composable_source:
            pattern = _RESOLVED_PATTERNS[w.category]
            if re.search(pattern, composable_source):
                continue  # suppressed

        result.append(w)

    return result


def collect_mixin_warnings(
    mixin_source: str,
    mixin_members: MixinMembers,
    lifecycle_hooks: list[str],
) -> list[MigrationWarning]:
    """Scan mixin source for known problematic patterns.

    Returns warning objects (does NOT modify source).
    The mixin_stem field is left empty — the caller sets it when
    attaching warnings to a MixinEntry.
    """
    warnings: list[MigrationWarning] = []
    seen_categories: set[str] = set()

    for pattern, category, message, action, severity in _THIS_DOLLAR_PATTERNS:
        if category in seen_categories:
            continue
        match = re.search(pattern, mixin_source)
        if match:
            seen_categories.add(category)
            # Extract the matching line as line_hint
            line_start = mixin_source.rfind("\n", 0, match.start()) + 1
            line_end = mixin_source.find("\n", match.end())
            if line_end == -1:
                line_end = len(mixin_source)
            line_hint = mixin_source[line_start:line_end].strip()

            warnings.append(MigrationWarning(
                mixin_stem="",
                category=category,
                message=message,
                action_required=action,
                line_hint=line_hint,
                severity=severity,
            ))

    # External dependencies (this.X where X is not in this mixin)
    warnings.extend(detect_external_dependencies(mixin_source, mixin_members))

    # this-aliasing (const self = this)
    warnings.extend(detect_this_aliasing(mixin_source, ""))

    # Mixin options that can't be auto-migrated (props, inject, filters, etc.)
    warnings.extend(detect_mixin_options(mixin_source, ""))

    # Structural patterns (factory functions, nested mixins, render, etc.)
    warnings.extend(detect_structural_patterns(mixin_source, ""))

    return warnings


def detect_external_dependencies(
    mixin_source: str,
    mixin_members: MixinMembers,
) -> list[MigrationWarning]:
    """Detect ``this.X`` references where X is not defined in the mixin.

    These are external dependencies — members that come from the component
    or a sibling mixin via shared ``this`` context. They break in composables
    because composables are isolated functions without ``this``.
    """
    from .mixin_analyzer import find_external_this_refs

    external = find_external_this_refs(mixin_source, mixin_members.all_names)
    warnings: list[MigrationWarning] = []

    for name in external:
        # Find the first line containing this.<name> for line_hint
        match = re.search(rf"\bthis\.{re.escape(name)}\b", mixin_source)
        line_hint = None
        if match:
            line_start = mixin_source.rfind("\n", 0, match.start()) + 1
            line_end = mixin_source.find("\n", match.end())
            if line_end == -1:
                line_end = len(mixin_source)
            line_hint = mixin_source[line_start:line_end].strip()

        warnings.append(MigrationWarning(
            mixin_stem="",
            category="external-dependency",
            message=f"'{name}' — external dep, not available in composable scope",
            action_required=f"Accept '{name}' as a composable parameter and rewrite this.{name}",
            line_hint=line_hint,
            severity="error",
        ))

    return warnings


def detect_this_aliasing(
    mixin_source: str, mixin_stem: str
) -> list[MigrationWarning]:
    """Detect `const self = this` and similar aliasing patterns.

    Auto-rewriting alias.x is too complex (requires scope tracking), so
    this is warn-only. Returns warnings for each alias found.
    """
    pattern = re.compile(
        r"\b(?:const|let|var)\s+(self|that|vm|_this|_self)\s*=\s*this\b"
    )
    warnings: list[MigrationWarning] = []
    for m in pattern.finditer(mixin_source):
        alias = m.group(1)
        line_start = mixin_source.rfind("\n", 0, m.start()) + 1
        line_end = mixin_source.find("\n", m.end())
        if line_end == -1:
            line_end = len(mixin_source)
        line_hint = mixin_source[line_start:line_end].strip()
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="this-alias",
            message=f"'this' is aliased as '{alias}' — references via {alias}.x won't be auto-rewritten",
            action_required=f"Manually replace {alias}.x with composable equivalents",
            line_hint=line_hint,
            severity="warning",
        ))
    return warnings


def compute_confidence(
    composable_source: str,
    warnings: list[MigrationWarning],
) -> ConfidenceLevel:
    """Compute confidence level for a generated/patched composable.

    Scans for:
    - Remaining this. references → LOW
    - Unbalanced brackets/braces → LOW
    - // TODO or // ⚠ MIGRATION markers → MEDIUM
    - Warnings list non-empty → MEDIUM
    - No issues → HIGH
    """
    # Check for remaining this. references (LOW) — skip comment lines
    for line in composable_source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        if re.search(r"\bthis\.", stripped):
            return ConfidenceLevel.LOW

    # Check for unbalanced braces (LOW)
    if _has_unbalanced_braces(composable_source):
        return ConfidenceLevel.LOW

    # Check for error-severity warnings (LOW)
    if any(w.severity == "error" for w in warnings):
        return ConfidenceLevel.LOW

    # Check for TODO or MIGRATION markers (MEDIUM)
    if re.search(r"//\s*TODO\b", composable_source):
        return ConfidenceLevel.MEDIUM

    if "MIGRATION WARNINGS" in composable_source or "manual step" in composable_source:
        return ConfidenceLevel.MEDIUM

    # Check for warnings (MEDIUM)
    if warnings:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.HIGH


# Matches old-format inline warnings: "// ⚠ MIGRATION: ..." or "// ❌ MIGRATION [error]: ..."
# Uses .*MIGRATION to handle encoding-corrupted icon characters (e.g. âš )
_OLD_INLINE_RE = re.compile(
    r"^\s*//.+\bMIGRATION\s*(?:\[(?:error|warning|info)\])?\s*:.*$"
)
_BOX_LINE_RE = re.compile(r"^\s*//\s*[\u250c\u2502\u2514]")
_CONFIDENCE_RE = re.compile(r"^//\s*Transformation confidence:")
_HEADER_RE = re.compile(r"^//\s*[\u26a0\u2705]\ufe0f?\s*(?:\d+\s+(?:manual step|issue|advisory note)|0 issues)")
_SUFFIX_ICON_RE = re.compile(r"\s+//\s*[\u274c\u26a0\u2139]\ufe0f?(?:\s+\S.*)?\s*$")


def _strip_old_inline_warnings(source: str) -> str:
    """Remove old-format inline warnings, box blocks, confidence headers, and suffix icons."""
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        stripped = line.rstrip("\n")
        if _OLD_INLINE_RE.match(stripped):
            continue
        if _BOX_LINE_RE.match(stripped):
            continue
        if _CONFIDENCE_RE.match(stripped):
            continue
        if _HEADER_RE.match(stripped):
            continue
        # Remove suffix icons from code lines
        cleaned = _SUFFIX_ICON_RE.sub("", stripped)
        if cleaned != stripped:
            result.append(cleaned + "\n")
        else:
            result.append(line)
    return "".join(result)


_INLINE_ICON = {
    "error": "\u274c",      # ❌
    "warning": "\u26a0\ufe0f",  # ⚠️
    "info": "\u2139\ufe0f",     # ℹ️
}

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

# Short hints for inline suffix comments (icon + hint on the code line itself)
_SHORT_HINT: dict[str, str] = {
    "this.$emit": "not available in composable — use defineEmits or emit param",
    "this.$refs": "not available in composable — use template refs",
    "this.$on": "removed in Vue 3 — use event bus or provide/inject",
    "this.$off": "removed in Vue 3 — use event bus or provide/inject",
    "this.$once": "removed in Vue 3 — use event bus or provide/inject",
    "this.$el": "not available in composable — use template ref on root",
    "this.$parent": "not available in composable — use provide/inject",
    "this.$children": "removed in Vue 3 — use template refs",
    "this.$listeners": "removed in Vue 3 — merged into $attrs",
    "this.$router": "not available in composable — use useRouter()",
    "this.$route": "not available in composable — use useRoute()",
    "this.$store": "not available in composable — use Pinia store",
    "this.$t": "not available in composable — use useI18n()",
    "this.$tc": "not available in composable — use useI18n()",
    "this.$te": "not available in composable — use useI18n()",
    "this.$d": "not available in composable — use useI18n()",
    "this.$n": "not available in composable — use useI18n()",
    "this.$attrs": "not available in composable — use useAttrs()",
    "this.$slots": "not available in composable — use useSlots()",
    "this.$watch": "not available in composable — use watch() from vue",
    "this.$forceUpdate": "rarely needed in Vue 3",
    "this-alias": "this alias won't work — replace with direct refs",
    "mixin-option:props": "mixin props — use defineProps() in component",
    "mixin-option:inject": "mixin inject — use inject() from vue",
    "mixin-option:provide": "mixin provide — use provide() from vue",
    "mixin-option:filters": "filters removed in Vue 3 — convert to functions",
    "mixin-option:directives": "mixin directives — register in component",
    "mixin-option:model": "mixin model — use modelValue + update:modelValue",
}


def _get_short_hint(warning: MigrationWarning) -> str:
    """Get a short hint for inline suffix from a warning."""
    # External-dependency: include the member name for specificity
    if warning.category == "external-dependency":
        m = re.match(r"'(\w+)'", warning.message)
        member = f"this.{m.group(1)}" if m else "external dep"
        return f"pass {member} as composable param"
    hint = _SHORT_HINT.get(warning.category)
    if hint:
        return hint
    # Fallback: truncate action_required to ~30 chars
    action = warning.action_required
    if len(action) > 35:
        return action[:32] + "..."
    return action


def inject_inline_warnings(
    source: str,
    warnings: list[MigrationWarning],
    confidence: ConfidenceLevel | None = None,
    warning_count: int = 0,
) -> str:
    """Inject inline warning comments into generated composable source.

    Adds a severity icon + short hint suffix on every line matching a warning
    pattern (e.g. ``this.$emit('done')  // ❌ use defineEmits or emit param``).

    Optionally prepends a header with action count at the top.
    """
    # Strip any existing inline warnings from previous runs
    source = _strip_old_inline_warnings(source)

    # Build header: count of error+warning severity (not info)
    if confidence is not None:
        actionable = sum(1 for w in warnings if w.severity in ("error", "warning"))
        if actionable:
            header = f"// \u26a0\ufe0f {actionable} manual step{'s' if actionable != 1 else ''} needed \u2014 see migration report for details\n"
        elif warning_count:
            header = f"// \u26a0\ufe0f {warning_count} advisory note{'s' if warning_count != 1 else ''} \u2014 see migration report for details\n"
        else:
            header = "// \u2705 0 issues \u2014 all mixin members have composable equivalents\n"
        source = header + source

    if not warnings:
        return source

    lines = source.splitlines(keepends=True)

    # Build pattern→(severity, hint) map for suffix annotation
    # For this.$ categories: use the category itself as the pattern
    # For external-dependency: use "this.<name>" as the pattern
    pattern_info: dict[str, tuple[str, str]] = {}  # pat -> (severity, hint)
    pattern_fallbacks: dict[str, str] = {}  # pat -> bare fallback name

    for w in warnings:
        if w.category.startswith("this.$"):
            pat = w.category
        elif w.category == "external-dependency":
            m = re.match(r"'(\w+)'", w.message)
            if m:
                dep_name = m.group(1)
                pat = f"this.{dep_name}"
                if dep_name.startswith("_"):
                    pattern_fallbacks[pat] = dep_name
            else:
                continue
        else:
            continue

        cur = pattern_info.get(pat)
        if cur is None or _SEVERITY_ORDER.get(w.severity, 2) < _SEVERITY_ORDER.get(cur[0], 2):
            pattern_info[pat] = (w.severity, _get_short_hint(w))

    # Annotate every code line that matches a warning pattern
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        if _SUFFIX_ICON_RE.search(line):
            continue
        for pat, (sev, hint) in pattern_info.items():
            matched = pat in line
            if not matched and pat in pattern_fallbacks:
                bare = pattern_fallbacks[pat]
                if re.search(rf'\b{re.escape(bare)}\b', line):
                    matched = True
            if matched:
                icon = _INLINE_ICON.get(sev, "\u26a0\ufe0f")
                lines[i] = line.rstrip("\n") + f"  // {icon} {hint}\n"
                break

    return "".join(lines)


def post_generation_check(composable_source: str) -> list[MigrationWarning]:
    """Scan a generated composable for residual issues.

    Checks:
    - Remaining ``this.`` references (should be zero after rewriting)
    - Unbalanced braces/brackets
    - ``// TODO`` marker count
    """
    warnings: list[MigrationWarning] = []

    # Remaining this. references (skip comment lines)
    for line in composable_source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        if re.search(r"\bthis\.", stripped):
            warnings.append(MigrationWarning(
                mixin_stem="",
                category="remaining-this",
                message=f"Remaining this. reference: {stripped.strip()}",
                action_required="Replace this.x with composable variable references",
                line_hint=stripped.strip(),
                severity="error",
            ))
            break  # one warning is enough

    # Unbalanced braces
    if _has_unbalanced_braces(composable_source):
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="unbalanced-braces",
            message="Unbalanced braces detected in generated composable",
            action_required="Review and fix brace/bracket structure manually",
            line_hint=None,
            severity="error",
        ))

    # Check for this. in function parameter positions (indicates rewriter bug)
    param_this_matches = re.findall(r'function\s+\w+\([^)]*this\.[^)]*\)', composable_source)
    for match in param_this_matches:
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="this-in-params",
            message=f"'this.' reference found in function parameter position — likely a rewriter bug: {match.strip()}",
            action_required="Remove this. from function parameters and use a local variable instead",
            line_hint=match.strip(),
            severity="error",
        ))

    # Check lifecycle hook bodies for references to undefined functions
    lifecycle_pattern = re.compile(
        r'on(?:Mounted|BeforeUnmount|Activated|Deactivated)\(\(\)\s*=>\s*\{([^}]+)\}',
        re.DOTALL,
    )
    _BUILTIN_NAMES = frozenset({
        'console', 'window', 'document', 'setTimeout', 'setInterval',
        'clearTimeout', 'clearInterval', 'addEventListener', 'removeEventListener',
        'nextTick', 'Math', 'Date', 'JSON', 'Object', 'Array', 'String',
        'Number', 'Boolean', 'Promise', 'Error', 'RegExp', 'parseInt', 'parseFloat',
        'undefined', 'null', 'true', 'false', 'if', 'else', 'return', 'new',
        'typeof', 'void', 'delete', 'throw', 'try', 'catch', 'finally',
        'for', 'while', 'do', 'switch', 'case', 'break', 'continue',
        'const', 'let', 'var', 'function', 'class', 'async', 'await',
        'this', 'super', 'import', 'export', 'from', 'of', 'in',
    })
    for m in lifecycle_pattern.finditer(composable_source):
        hook_body = m.group(1)
        # Find standalone function calls (not method calls like obj.method())
        called_funcs = re.findall(r'(?<!\.)(\b\w+)\s*\(', hook_body)
        for func in called_funcs:
            if func in _BUILTIN_NAMES:
                continue
            # Check if function is defined in the composable
            if (
                f'function {func}(' not in composable_source
                and re.search(rf'\bconst\s+{re.escape(func)}\b', composable_source) is None
                and re.search(rf'\blet\s+{re.escape(func)}\b', composable_source) is None
            ):
                warnings.append(MigrationWarning(
                    mixin_stem="",
                    category="undefined-in-lifecycle",
                    message=f"Lifecycle hook references '{func}' which is not defined in the composable",
                    action_required=f"Define '{func}' in the composable or import it",
                    line_hint=None,
                    severity="error",
                ))

    # Count TODO markers
    todo_count = len(re.findall(r"//\s*TODO\b", composable_source))
    if todo_count:
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="todo-marker",
            message=f"{todo_count} TODO marker(s) remain in generated composable",
            action_required="Implement the TODO items manually",
            line_hint=None,
            severity="info",
        ))

    return warnings


# Mixin option patterns: (option key, message, action_required, severity)
_MIXIN_OPTION_PATTERNS: list[tuple[str, str, str, str]] = [
    ("props", "Mixin defines props — not migrated to composable",
     "Use defineProps() in component or pass as composable params", "warning"),
    ("inject", "Mixin uses inject — not auto-migrated",
     "Use inject() from 'vue' in composable", "warning"),
    ("provide", "Mixin uses provide — not auto-migrated",
     "Use provide() from 'vue' in composable", "warning"),
    ("filters", "Mixin uses filters — REMOVED in Vue 3",
     "Convert to methods or standalone functions", "error"),
    ("directives", "Mixin registers local directives",
     "Register in component or globally instead", "warning"),
    ("components", "Mixin registers local components",
     "Move registration to component", "warning"),
    ("extends", "Mixin uses extends — complex inheritance",
     "Flatten into composable manually", "warning"),
    ("model", "Mixin uses custom v-model — API changed in Vue 3",
     "Use modelValue prop + update:modelValue emit", "warning"),
]


def _brace_depth_at(source: str, pos: int) -> int:
    """Count net brace depth from start of *source* to *pos*, skipping non-code."""
    from .js_parser import skip_non_code

    depth = 0
    i = 0
    while i < pos:
        new_i, skipped = skip_non_code(source, i)
        if skipped:
            i = new_i
            continue
        ch = source[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        i += 1
    return depth


def detect_mixin_options(
    mixin_source: str, mixin_stem: str
) -> list[MigrationWarning]:
    """Detect mixin option keys that can't be auto-migrated to composables."""
    from .js_parser import skip_non_code

    warnings: list[MigrationWarning] = []
    for option, message, action, severity in _MIXIN_OPTION_PATTERNS:
        # Scan for `option:` at top level, skipping strings/comments
        pattern = re.compile(rf'\b{option}\s*(?::\s*|\()')
        for m in pattern.finditer(mixin_source):
            # Check if this match is inside a string or comment
            # by walking from last known safe position
            pos = 0
            in_non_code = False
            check_pos = m.start()
            while pos < check_pos:
                new_pos, skipped = skip_non_code(mixin_source, pos)
                if skipped:
                    if new_pos > check_pos:
                        in_non_code = True
                        break
                    pos = new_pos
                else:
                    pos += 1
            if in_non_code:
                continue
            # Mixin options sit at brace depth 1 (inside `export default {}`).
            # Deeper matches (e.g. `filters` inside data()) are not options.
            if _brace_depth_at(mixin_source, m.start()) != 1:
                continue
            warnings.append(MigrationWarning(
                mixin_stem=mixin_stem,
                category=f"mixin-option:{option}",
                message=message,
                action_required=action,
                line_hint=None,
                severity=severity,
            ))
            break  # one warning per option is enough
    return warnings


def detect_structural_patterns(
    mixin_source: str, mixin_stem: str
) -> list[MigrationWarning]:
    """Detect structural patterns the tool can't auto-migrate."""
    warnings: list[MigrationWarning] = []

    # Mixin factory function: export default function
    factory_m = re.search(r'\bexport\s+default\s+function\s*\w*\s*\(([^)]*)\)', mixin_source)
    if factory_m:
        params = factory_m.group(1).strip()
        if params:
            message = f"Factory mixin with params ({params}) — cannot auto-convert"
            action = f"Create composable with matching parameters ({params})"
        else:
            message = "Factory mixin (no params) — convert to regular composable"
            action = "Manually convert factory function to composable"
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:factory-function",
            message=message,
            action_required=action,
            line_hint=None,
            severity="warning",
        ))
    elif re.search(r'\bexport\s+default\s+function\b', mixin_source):
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:factory-function",
            message="Mixin factory function — cannot auto-convert",
            action_required="Manually convert factory function to composable",
            line_hint=None,
            severity="warning",
        ))

    # Nested mixins: mixins: [...] inside the mixin source
    nested_mixins_m = re.search(r'\bmixins\s*:\s*\[([^\]]+)\]', mixin_source)
    if nested_mixins_m:
        mixin_names = nested_mixins_m.group(1).strip()
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:nested-mixins",
            message=f"Nested mixins [{mixin_names}] — transitive members may be missed",
            action_required="Ensure all transitive mixin members are accounted for",
            line_hint=None,
            severity="warning",
        ))
    elif re.search(r'\bmixins\s*:', mixin_source):
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:nested-mixins",
            message="Mixin uses nested mixins — transitive members may be missed",
            action_required="Ensure all transitive mixin members are accounted for",
            line_hint=None,
            severity="warning",
        ))

    # render() in mixin
    if re.search(r'\brender\s*\(', mixin_source):
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:render-function",
            message="Mixin defines render function — not supported in composable",
            action_required="Move render logic to component template or setup",
            line_hint=None,
            severity="warning",
        ))

    # serverPrefetch hook
    if re.search(r'\bserverPrefetch\b', mixin_source):
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:serverPrefetch",
            message="serverPrefetch not auto-converted",
            action_required="Manually add onServerPrefetch() in composable",
            line_hint=None,
            severity="warning",
        ))

    # Class-component decorators: @Component or @Prop
    if re.search(r'@(?:Component|Prop)\b', mixin_source):
        warnings.append(MigrationWarning(
            mixin_stem=mixin_stem,
            category="structural:class-component",
            message="Class-component syntax not supported",
            action_required="Convert from class-component to Options API first, then migrate",
            line_hint=None,
            severity="warning",
        ))

    return warnings


def detect_name_collisions(
    composable_members: dict[str, list[str]],
) -> list[MigrationWarning]:
    """Detect member name collisions across composables for the same component.

    Args:
        composable_members: mapping of composable fn name → list of member names
    """
    warnings: list[MigrationWarning] = []
    # Build reverse map: member_name → list of composable names
    member_to_composables: dict[str, list[str]] = {}
    for fn_name, members in composable_members.items():
        for member in members:
            member_to_composables.setdefault(member, []).append(fn_name)

    for member, sources in member_to_composables.items():
        if len(sources) > 1:
            warnings.append(MigrationWarning(
                mixin_stem="",
                category="name-collision",
                message=f"Member '{member}' provided by both {' and '.join(sources)} — name collision",
                action_required=f"Rename '{member}' in one of the composables to avoid conflict",
                line_hint=None,
                severity="warning",
            ))

    return warnings


def detect_missing_cleanup(composable_source: str) -> list[str]:
    """Detect addEventListener without matching removeEventListener cleanup.

    Also detects setInterval/setTimeout without corresponding clear calls.
    Returns a list of warning message strings.
    """
    warnings: list[str] = []

    # Check for addEventListener in onMounted without removeEventListener in onBeforeUnmount
    has_add_listener = bool(re.search(r'addEventListener\s*\(', composable_source))
    has_remove_listener = bool(re.search(r'removeEventListener\s*\(', composable_source))
    has_on_mounted = bool(re.search(r'onMounted\s*\(', composable_source))
    has_on_before_unmount = bool(re.search(r'onBeforeUnmount\s*\(', composable_source))

    if has_add_listener and has_on_mounted:
        if not has_remove_listener or not has_on_before_unmount:
            warnings.append(
                "MIGRATION: onMounted adds event listener but no corresponding "
                "onBeforeUnmount cleanup was generated."
            )

    # Check for setInterval/setTimeout without cleanup
    has_set_interval = bool(re.search(r'setInterval\s*\(', composable_source))
    has_clear_interval = bool(re.search(r'clearInterval\s*\(', composable_source))
    if has_set_interval and not has_clear_interval:
        warnings.append(
            "MIGRATION: setInterval used but no clearInterval cleanup detected."
        )

    has_set_timeout = bool(re.search(r'setTimeout\s*\(', composable_source))
    has_clear_timeout = bool(re.search(r'clearTimeout\s*\(', composable_source))
    if has_set_timeout and not has_clear_timeout:
        warnings.append(
            "MIGRATION: setTimeout used but no clearTimeout cleanup detected."
        )

    return warnings


def _has_unbalanced_braces(source: str) -> bool:
    """Check if braces {} are unbalanced in the source."""
    depth = 0
    in_string = None
    prev = ""
    for ch in source:
        if prev != "\\":
            if in_string is None:
                if ch in ('"', "'", "`"):
                    in_string = ch
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        return True
            elif ch == in_string:
                in_string = None
        prev = ch
    return depth != 0
