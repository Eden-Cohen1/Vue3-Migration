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

    if "MIGRATION WARNINGS" in composable_source:
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
_SUFFIX_ICON_RE = re.compile(r"\s+//\s*[\u274c\u26a0\u2139]\ufe0f?\s*$")


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

_FUNC_RE = re.compile(
    r"^\s*(?:async\s+)?function\s+\w+|^\s*const\s+\w+\s*=\s*(?:async\s*)?\("
)


def _find_containing_function(lines: list[str], line_idx: int) -> int:
    """Scan backward from *line_idx* to find the nearest function declaration."""
    for i in range(line_idx, -1, -1):
        if _FUNC_RE.match(lines[i]):
            return i
    return line_idx


def _build_warning_box(
    warnings_with_lines: list[tuple[MigrationWarning, int]],
    indent: str,
) -> str:
    """Build a box-style warning block (open right — emoji widths render
    inconsistently across editors/terminals so right border is omitted)."""
    box = [f"{indent}// \u250c\u2500 MIGRATION WARNINGS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"]
    for w, _ in warnings_with_lines:
        icon = _INLINE_ICON.get(w.severity, "\u26a0\ufe0f")
        # Use only the first line of the message (guard against embedded newlines)
        msg = w.message.split("\n")[0]
        box.append(f"{indent}// \u2502 {icon} {msg}\n")
        if w.action_required:
            box.append(f"{indent}// \u2502    \u2192 {w.action_required}\n")
    box.append(f"{indent}// \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n")
    return "".join(box)


def inject_inline_warnings(
    source: str,
    warnings: list[MigrationWarning],
    confidence: ConfidenceLevel | None = None,
    warning_count: int = 0,
) -> str:
    """Inject inline warning comments into generated composable source.

    For each warning with a line_hint, finds the first matching line and:
    1. Groups all warnings by their containing function
    2. Inserts a box-style warning block above each function
    3. Adds a severity suffix icon on the matched line

    Warnings that cannot be placed inline (no line_hint or no matching line)
    are collected and inserted as a box block after the confidence header.

    Optionally prepends a confidence header comment at the top.
    """
    # Strip any existing inline warnings from previous runs
    source = _strip_old_inline_warnings(source)

    if confidence is not None:
        header = f"// Transformation confidence: {confidence.value} ({warning_count} warnings \u2014 see migration report)\n"
        source = header + source

    lines = source.splitlines(keepends=True)

    # Phase 1: Match warnings to source lines
    placed: list[tuple[MigrationWarning, int]] = []
    unplaced: list[MigrationWarning] = []

    for w in warnings:
        if not w.line_hint:
            unplaced.append(w)
            continue
        matched = None
        # Try exact line_hint match on code lines first
        for i, line in enumerate(lines):
            if w.line_hint in line and not line.lstrip().startswith("//"):
                matched = i
                break
        # Fallback: match using the category (e.g. "this.$emit") on code lines
        if matched is None and w.category.startswith("this.$"):
            for i, line in enumerate(lines):
                if w.category in line and not line.lstrip().startswith("//"):
                    matched = i
                    break
        if matched is None:
            unplaced.append(w)
        else:
            placed.append((w, matched))

    # Phase 2: Group placed warnings by containing function
    func_groups: dict[int, list[tuple[MigrationWarning, int]]] = {}
    for w, matched_idx in placed:
        func_idx = _find_containing_function(lines, matched_idx)
        func_groups.setdefault(func_idx, []).append((w, matched_idx))

    # Phase 3: Add suffix icons on matched lines (best severity per line)
    line_severity: dict[int, str] = {}
    for w, matched_idx in placed:
        current = line_severity.get(matched_idx)
        if current is None or _SEVERITY_ORDER.get(w.severity, 2) < _SEVERITY_ORDER.get(current, 2):
            line_severity[matched_idx] = w.severity

    for line_idx, severity in line_severity.items():
        icon = _INLINE_ICON.get(severity, "\u26a0\ufe0f")
        line = lines[line_idx]
        lines[line_idx] = line.rstrip("\n") + f"  // {icon}\n"

    # Phase 3b: Add suffix icons on ALL lines matching a warning category,
    # not just the first matched line.  This ensures every this.$emit, this.$router,
    # external deps (this.entityId), etc. gets a visible ❌ even if it didn't get
    # its own warning box.
    category_severity: dict[str, str] = {}
    # Pattern to match in source lines: for this.$ categories use the category
    # itself (e.g. "this.$emit"); for external-dependency use "this.<name>".
    category_patterns: dict[str, str] = {}
    for w in warnings:
        if w.category.startswith("this.$"):
            pat = w.category
        elif w.category == "external-dependency":
            # Extract the dep name from the message: "'entityId' — external dep..."
            m = re.match(r"'(\w+)'", w.message)
            pat = f"this.{m.group(1)}" if m else None
        else:
            pat = None
        if pat:
            cur = category_severity.get(pat)
            if cur is None or _SEVERITY_ORDER.get(w.severity, 2) < _SEVERITY_ORDER.get(cur, 2):
                category_severity[pat] = w.severity
    for i, line in enumerate(lines):
        if i in line_severity:
            continue  # already has a suffix from Phase 3
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        for pat, sev in category_severity.items():
            if pat in line:
                icon = _INLINE_ICON.get(sev, "\u26a0\ufe0f")
                lines[i] = line.rstrip("\n") + f"  // {icon}\n"
                break

    # Phase 4: Insert box blocks above functions (bottom to top to preserve indices)
    for func_idx in sorted(func_groups.keys(), reverse=True):
        group = func_groups[func_idx]
        indent = lines[func_idx][: len(lines[func_idx]) - len(lines[func_idx].lstrip())]
        box = _build_warning_box(group, indent)
        # Add blank line before box if previous line is not already blank
        if func_idx > 0 and lines[func_idx - 1].strip():
            box = "\n" + box
        lines.insert(func_idx, box)

    source = "".join(lines)

    # Phase 5: Place unplaced warnings as box block
    if unplaced:
        box = _build_warning_box([(w, -1) for w in unplaced], "")
        if confidence is not None:
            idx = source.index("\n") + 1
            source = source[:idx] + box + source[idx:]
        else:
            source = box + source

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
