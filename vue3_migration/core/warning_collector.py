"""Collect migration warnings and compute confidence scores.

Warning collector is a separate module so Plans 2-4 can add detectors
here without touching the generator or patcher.
"""
import re

from ..models import ConfidenceLevel, MigrationWarning, MixinMembers


# Patterns: (regex, category, message, action_required)
_THIS_DOLLAR_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        r"this\.\$router\b",
        "this.$router",
        "this.$router is not available in composables",
        "Import and use useRouter() from vue-router",
    ),
    (
        r"this\.\$route\b",
        "this.$route",
        "this.$route is not available in composables",
        "Import and use useRoute() from vue-router",
    ),
    (
        r"this\.\$store\b",
        "this.$store",
        "this.$store is not available in composables",
        "Import and use the Pinia/Vuex store directly",
    ),
    (
        r"this\.\$emit\b",
        "this.$emit",
        "this.$emit is not available in composables",
        "Accept an emit function parameter or use defineEmits",
    ),
    (
        r"this\.\$refs\b",
        "this.$refs",
        "this.$refs is not available in composables",
        "Use template refs with ref() instead",
    ),
    (
        r"this\.\$nextTick\b",
        "this.$nextTick",
        "this.$nextTick should use the imported nextTick",
        "Import nextTick from 'vue' and call it directly",
    ),
    (
        r"this\.\$set\b",
        "this.$set",
        "this.$set is removed in Vue 3",
        "Assign directly — Vue 3 reactivity tracks new properties",
    ),
    (
        r"this\.\$delete\b",
        "this.$delete",
        "this.$delete is removed in Vue 3",
        "Use delete operator directly — Vue 3 reactivity tracks deletions",
    ),
    (
        r"this\.\$on\b",
        "this.$on",
        "this.$on is removed in Vue 3",
        "Use an external event bus library or provide/inject",
    ),
    (
        r"this\.\$off\b",
        "this.$off",
        "this.$off is removed in Vue 3",
        "Use an external event bus library or provide/inject",
    ),
    (
        r"this\.\$once\b",
        "this.$once",
        "this.$once is removed in Vue 3",
        "Use an external event bus library or provide/inject",
    ),
    (
        r"this\.\$el\b",
        "this.$el",
        "this.$el has no composable equivalent",
        "Use a template ref on the root element instead",
    ),
    (
        r"this\.\$parent\b",
        "this.$parent",
        "this.$parent — avoid in composables",
        "Use provide/inject or props/emit instead",
    ),
    (
        r"this\.\$children\b",
        "this.$children",
        "this.$children is removed in Vue 3",
        "Use template refs or provide/inject",
    ),
    (
        r"this\.\$listeners\b",
        "this.$listeners",
        "$listeners is removed in Vue 3",
        "Listeners are merged into $attrs in Vue 3",
    ),
    (
        r"this\.\$attrs\b",
        "this.$attrs",
        "this.$attrs used — needs useAttrs()",
        "Add const attrs = useAttrs() and import from 'vue'",
    ),
    (
        r"this\.\$slots\b",
        "this.$slots",
        "this.$slots used — needs useSlots()",
        "Add const slots = useSlots() and import from 'vue'",
    ),
    (
        r"this\.\$forceUpdate\b",
        "this.$forceUpdate",
        "$forceUpdate — rarely needed in Vue 3",
        "Reactive system usually handles it; review logic",
    ),
    (
        r"this\.\$watch\b",
        "this.$watch",
        "this.$watch — use watch() from vue instead",
        "Import watch from 'vue' and use watch() directly",
    ),
]


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

    for pattern, category, message, action in _THIS_DOLLAR_PATTERNS:
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
                severity="warning",
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

    # Check for TODO or MIGRATION markers (MEDIUM)
    if re.search(r"//\s*TODO\b", composable_source):
        return ConfidenceLevel.MEDIUM

    if "⚠ MIGRATION" in composable_source:
        return ConfidenceLevel.MEDIUM

    # Check for warnings (MEDIUM)
    if warnings:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.HIGH


def inject_inline_warnings(
    source: str,
    warnings: list[MigrationWarning],
    confidence: ConfidenceLevel | None = None,
    warning_count: int = 0,
) -> str:
    """Inject inline warning comments into generated composable source.

    For each warning with a line_hint, inserts ``// ⚠ MIGRATION: {message}``
    above the first line that contains the hint text.

    Optionally prepends a confidence header comment at the top.
    """
    if confidence is not None:
        header = f"// Migration confidence: {confidence.value} ({warning_count} warnings — see migration report)\n"
        source = header + source

    for w in warnings:
        if not w.line_hint:
            continue
        # Find a line containing the hint text
        lines = source.splitlines(keepends=True)
        new_lines: list[str] = []
        injected = False
        for line in lines:
            if not injected and w.line_hint in line:
                indent = line[: len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}// ⚠ MIGRATION: {w.message}\n")
                injected = True
            new_lines.append(line)
        if injected:
            source = "".join(new_lines)

    return source


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
